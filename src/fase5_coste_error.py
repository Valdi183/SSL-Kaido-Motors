"""
Fase 5: cuánto cuesta equivocarse y qué recomendamos (pregunta 5 del caso).

  A. Coste unitario de pasarse (Co) y de quedarse corto (Cu) por segmento, y el nivel
     de servicio que justifican: ratio crítico Cu / (Cu + Co) -> z teórico.
  B. Stock de seguridad óptimo por segmento en la simulación: se prueba una rejilla
     de z y se elige el que da más resultado (CVP - coste del stock) esperado,
     ponderando los escenarios (pesimista 25 %, central 50 %, optimista 25 %).
  C. Coste de planificar con el escenario equivocado: matriz plan x realidad.
  D. Señales: cuánto se desvía la demanda frente al plan en los primeros meses de
     cada escenario y a partir de qué mes se distinguen.
  E. Tabla de recomendación por segmento.

Ejecutar desde la raíz del repositorio (necesita las salidas de las Fases 2 y 3):
    python src/fase5_coste_error.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import datos as d
import fase4_simulacion as f4
from fase3_escenarios import ESCENARIOS

pd.set_option('display.width', 220)
pd.set_option('display.max_columns', 30)

PESOS = {'pesimista': 0.25, 'central': 0.50, 'optimista': 0.25}
Z_REJILLA = [0.0, 0.5, 0.84, 1.28, 1.65, 2.05, 2.33]
MESES_REACCION = 3          # lo que tarda en corregirse un error (sección 7.2)


def costes_unitarios(eco):
    """Coste de un coche de más (Co) y de uno de menos (Cu), escenario central."""
    cvp = eco.bruto - eco.vm_0_90
    co = MESES_REACCION * f4.COSTE_STOCK_MES + (eco.vm_91_180 - eco.vm_0_90).clip(lower=0)
    coste_transfer = f4.PERDIDA_TRANSFER * eco.bruto
    hace_transfer = (cvp - coste_transfer) > 0
    cu = np.where(hace_transfer,
                  f4.CUOTA_TRANSFER * coste_transfer + (1 - f4.CUOTA_TRANSFER) * cvp,
                  cvp.clip(lower=0))
    t = pd.DataFrame({'CVP_coche': cvp, 'Co_pasarse': co, 'Cu_quedarse_corto': cu},
                     index=eco.index)
    t['ratio_critico'] = t.Cu_quedarse_corto / (t.Cu_quedarse_corto + t.Co_pasarse)
    t['z_teorico'] = norm.ppf(t.ratio_critico.clip(0.5, 0.995))
    return t


def esperado(r):
    return sum(PESOS[e] * r[e] for e in ESCENARIOS)


def main():
    dic, en_camino, res, plan, eco = f4.datos_partida()

    # ---------------------------------------------------------------- A
    cu = costes_unitarios(eco)
    print('=== A. Coste de equivocarse por coche (EUR, escenario central) ===')
    print('Co = 3 meses de stock (180 EUR) + VM extra si pasa de 90 días')
    print('Cu = 50 % transfer (20 % del beneficio bruto) + 50 % venta perdida (CVP); 0 si el CVP <= 0')
    print(cu.round(2).to_string())

    # ---------------------------------------------------------------- B
    filas = []
    for s in d.SEGMENTOS:
        for z in Z_REJILLA:
            r = {}
            for e in ESCENARIOS:
                rep = f4.resumen_replicas(f4.simular_segmento(
                    s, e, dic, en_camino, res, plan, eco, z=z, rng=np.random.default_rng(f4.SEMILLA)))
                r[e] = rep.mean()
            filas.append({'segmento': s, 'z': z,
                          'resultado_esperado': esperado({e: r[e].resultado for e in ESCENARIOS}),
                          'resultado_central': r['central'].resultado,
                          'resultado_pesimista': r['pesimista'].resultado,
                          'resultado_optimista': r['optimista'].resultado,
                          'stock_medio_central': r['central'].stock_medio,
                          'meses_stock_central': r['central'].meses_stock,
                          'perdidas_central': r['central'].perdidas,
                          'transfer_central': r['central'].transfer,
                          'coste_stock_central': r['central'].coste_stock})
    rej = pd.DataFrame(filas)
    rej.to_csv(d.RESULTADOS / 'fase5_rejilla_z.csv', index=False)
    mejor = rej.loc[rej.groupby('segmento').resultado_esperado.idxmax()].set_index('segmento')
    base = rej[rej.z == f4.Z].set_index('segmento')
    z_opt = mejor.z.reindex(d.SEGMENTOS)
    comp = pd.DataFrame({
        'z_teorico': cu.z_teorico, 'z_optimo_sim': z_opt,
        'resultado_z1.28_M': base.resultado_esperado / 1e6,
        'resultado_zopt_M': mejor.resultado_esperado / 1e6,
        'ganancia_EUR': mejor.resultado_esperado - base.resultado_esperado,
        'meses_stock_z1.28': base.meses_stock_central, 'meses_stock_zopt': mejor.meses_stock_central,
        'perdidas_z1.28': base.perdidas_central, 'perdidas_zopt': mejor.perdidas_central,
    }).reindex(d.SEGMENTOS)
    print('\n=== B. Stock de seguridad: z óptimo por segmento (resultado esperado ponderado) ===')
    print(comp.round(2).to_string())
    print(f'Ganancia total frente a z = {f4.Z} para todos: {comp.ganancia_EUR.sum():,.0f} EUR')
    print('\nResultado esperado (M EUR) según z:')
    print((rej.pivot(index='z', columns='segmento', values='resultado_esperado')[d.SEGMENTOS] / 1e6)
          .round(2).to_string())

    # ---------------------------------------------------------------- C
    z_dict = z_opt.to_dict()
    matriz, detalle = {}, {}
    for p in ESCENARIOS:
        out = f4.simular_todo(z=z_dict, plan_de=p)
        tot = {e: sum(out[(e, s)] for s in d.SEGMENTOS).mean() for e in ESCENARIOS}
        matriz[p] = {e: tot[e].resultado for e in ESCENARIOS}
        detalle[p] = tot
    m = pd.DataFrame(matriz).T          # filas: plan; columnas: realidad
    lamento = m - np.diag(m.values)[None, :]
    print('\n=== C. Resultado (CVP - coste del stock, M EUR): filas = plan con el que se fabrica, '
          'columnas = lo que de verdad pasa ===')
    print((m / 1e6).round(2).to_string())
    print('\nCoste de haberse equivocado de plan (M EUR, frente a acertar el escenario):')
    print((lamento / 1e6).round(2).to_string())
    print('\nDetalle por plan y realidad:')
    for p in ESCENARIOS:
        for e in ESCENARIOS:
            t = detalle[p][e]
            print(f'  plan {p:9s} | real {e:9s} | llegan {t.llegadas:7,.0f} | stock medio {t.stock_medio:6,.0f}'
                  f' | >90 días fin {t.mas_90_fin:5,.0f} | perdidas {t.perdidas:5,.0f} | transfer {t.transfer:5,.0f}'
                  f' | coste stock {t.coste_stock / 1e6:5.2f} M | CVP {t.cvp / 1e6:6.2f} M')
    pd.concat({'resultado': m, 'lamento': lamento}).to_csv(d.RESULTADOS / 'fase5_matriz_plan.csv')

    # ---------------------------------------------------------------- D
    print('\n=== D. Señal: demanda real acumulada / plan central (3 últimos meses), total Kaido ===')
    senal = {}
    for e in ESCENARIOS:
        rng = np.random.default_rng(f4.SEMILLA)
        D = np.zeros((f4.N_REPLICAS, 12))
        P = plan.loc['central'].sum(axis=1).to_numpy()
        for s in d.SEGMENTOS:
            D += f4.simular_segmento(s, e, dic, en_camino, res, plan, eco, z=z_dict[s], rng=rng)['demanda']
        ratios = {}
        for mes in range(1, 7):
            desde = max(0, mes - 3)
            ratios[mes] = D[:, desde:mes].sum(axis=1) / P[desde:mes].sum()
        senal[e] = ratios
    filas = []
    for mes in range(1, 7):
        fila = {'mes': mes}
        for e in ESCENARIOS:
            r = senal[e][mes]
            fila[e] = f'{np.median(r):.2f} ({np.quantile(r, .1):.2f}-{np.quantile(r, .9):.2f})'
        fila['P(<0,90 | pesimista)'] = (senal['pesimista'][mes] < 0.90).mean()
        fila['P(<0,90 | central)'] = (senal['central'][mes] < 0.90).mean()
        fila['P(>1,10 | optimista)'] = (senal['optimista'][mes] > 1.10).mean()
        fila['P(>1,10 | central)'] = (senal['central'][mes] > 1.10).mean()
        filas.append(fila)
    tab_senal = pd.DataFrame(filas).set_index('mes')
    print('Mediana (P10-P90) y probabilidad de que salte la alarma:')
    print(tab_senal.round(2).to_string())
    tab_senal.to_csv(d.RESULTADOS / 'fase5_senales.csv')

    # ---------------------------------------------------------------- E
    seg = d.segmentos().loc[d.SEGMENTOS]
    t5 = pd.read_csv(d.RESULTADOS / 'tabla5_segmentos.csv', index_col=0, header=[0, 1])
    pes = eco.bruto - eco.vm_0_90 - eco.prima_co2
    reco = pd.DataFrame({
        'CVP_real_A012': seg.cvp_real_eur,
        'CVP_coche_central': cu.CVP_coche,
        'CVP_coche_con_CO2': pes,
        'mercado_A013_%': pd.read_csv(d.RESULTADOS / 'prevision_resumen.csv', index_col=0)['var_mercado_%'],
        'stock_dic_A012_meses': dic.stock_total / (plan.loc['central'].mean()),
        'CVP_anual_central_M': [float(str(t5[(s, 'central')].loc['Margen de la marca CVP (EUR)'])
                                      .replace(',', '')) / 1e6 for s in d.SEGMENTOS],
        'z_optimo': z_opt,
    }).reindex(d.SEGMENTOS)
    print('\n=== E. Datos para la recomendación por segmento ===')
    print(reco.round(2).to_string())
    reco.to_csv(d.RESULTADOS / 'fase5_recomendacion.csv')
    print(f'\nGuardado en {d.RESULTADOS}')


if __name__ == '__main__':
    main()
