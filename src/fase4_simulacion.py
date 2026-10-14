"""
Fase 4: simulación de un año de la cadena de suministro (preguntas 4 y 5, secciones 7 y 9.3).

Por segmento, mes a mes, repetido N veces con una demanda real distinta cada vez:
  1. Llegan a la red los coches pedidos 3 meses antes (L_t).
  2. La demanda real D_t = demanda del escenario x error al azar (lognormal, AR(1):
     los errores de meses seguidos se parecen, con la autocorrelación medida en la Fase 2).
  3. Se vende V_t = min(D_t, stock + llegadas), primero los coches más viejos (FIFO).
     Lo que falta se cubre con transfer (si deja dinero y hay coches en otros países)
     o se pierde.
  4. Al cerrar el mes se revisa la previsión (D_hat = previsión central x lo que se
     desvió la demanda real en los 3 últimos meses) y se pide la llegada de t+3:
         S_hat(t+2) = S_t + L(t+1) + L(t+2) - D_hat(t+1) - D_hat(t+2)   (sin bajar de 0)
         L(t+3)     = max(0, D_hat(t+3) + SS - S_hat(t+2)),   SS = z * sigma * sqrt(3)
  El plan sale del escenario central; en los otros la demanda real es distinta y solo
  se puede corregir a 3 meses vista (sección 7.6).

Costes (secciones 2.3-2.5 y 7.5, datos de segmentos.csv):
  * Coste del stock: 2 EUR/día por coche (60 EUR/mes) mientras tiene menos de 180 días.
  * VM según la edad al venderse: vm_real_0_90 / 91_180 / mas_180.
  * CVP de cada coche vendido = beneficio bruto - VM (- prima de CO2 y arancel si el
    escenario los carga). El transfer deja el 80 % del beneficio bruto.
  * Venta perdida: el CVP que no se gana.

Supuestos propios:
  * Lo que ya viene en camino (llegadas de enero y febrero, decididas en A012) = la
    facturación media a la red de julio-diciembre de A012, sin meses anómalos
    (p. ej. diciembre en SSUV, cambio de código).
  * Edad del stock de diciembre: 0-90 días repartido en meses 0-2, 91-180 en 3-5,
    más de 180 en el mes 7.
  * La mitad de los faltantes se puede cubrir con transfer (el resto se pierde);
    en el optimista, todos ("la fábrica tiene coches de sobra"). Solo se hace transfer
    si deja dinero.

Ejecutar desde la raíz del repositorio (necesita las salidas de las Fases 2 y 3):
    python src/fase4_simulacion.py
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import datos as d
from fase3_escenarios import ESCENARIOS, PARAMETROS

pd.set_option('display.width', 220)
pd.set_option('display.max_columns', 30)

N_REPLICAS = 1000
Z = 1.28                    # cubre 9 de cada 10 meses (sección 7.3)
# Stock de seguridad recomendado por segmento (Fase 5): más colchón donde quedarse corto
# es caro (margen alto), poco en C y ninguno en B (cada coche apenas deja dinero).
Z_RECOMENDADO = {'MSUV': 2.05, 'SSUV': 2.05, 'CSUV': 2.05, 'MD': 2.05, 'S': 2.05,
                 'C': 0.84, 'B': 0.0}
COSTE_STOCK_MES = 60        # 2 EUR/día
MESES_COSTE_STOCK = 6       # hasta 180 días
EDAD_MAX = 24
CUOTA_TRANSFER = 0.5
PERDIDA_TRANSFER = 0.20     # el transfer cuesta el 20 % del beneficio bruto
SEMILLA = 2013


# --- Datos de partida ----------------------------------------------------------------
def datos_partida():
    seg = d.segmentos().loc[d.SEGMENTOS]
    sto = d.stock()
    dic = sto[sto.periodo == 'A0121201'].set_index('segmento').loc[d.SEGMENTOS]

    wh = sto.pivot_table(index='fecha', columns='segmento', values='wholesale').loc['2012-07':]
    en_camino = {}
    for s in d.SEGMENTOS:
        w = wh[s]
        en_camino[s] = w[w >= 0.2 * w.mean()].mean()

    res = pd.read_csv(d.RESULTADOS / 'prevision_resumen.csv', index_col=0).loc[d.SEGMENTOS]
    plan = pd.read_csv(d.RESULTADOS / 'escenarios_demanda.csv', index_col=[0, 1], parse_dates=[1])

    ingreso = seg.pff_medio * (1 - seg.margen_conc_base_pct - seg.margen_conc_var_pct)
    eco = pd.DataFrame({
        'bruto': seg.beneficio_bruto_marca_eur,
        'coste': ingreso - seg.beneficio_bruto_marca_eur,
        'prima_co2': seg.prima_co2_eur,
        'vm_0_90': seg.vm_real_0_90_eur,
        'vm_91_180': seg.vm_real_91_180_eur,
        'vm_mas_180': seg.vm_real_mas_180_eur.fillna(seg.vm_real_91_180_eur),
    })
    return dic, pd.Series(en_camino), res, plan, eco


def stock_inicial(fila):
    edades = np.zeros(EDAD_MAX + 1)
    edades[0:3] = fila.s_0_90 / 3
    edades[3:6] = fila.s_91_180 / 3
    edades[7] = fila.s_mas_180
    return edades


def errores_ar1(n, meses, sigma, rho, rng):
    """Error multiplicativo lognormal con autocorrelación rho y desviación sigma (media 1)."""
    e = np.zeros((n, meses))
    e[:, 0] = rng.normal(0, sigma, n)
    for t in range(1, meses):
        e[:, t] = rho * e[:, t - 1] + np.sqrt(1 - rho ** 2) * rng.normal(0, sigma, n)
    return np.exp(e - sigma ** 2 / 2)


# --- Simulación de un segmento ---------------------------------------------------------
def simular_segmento(s, escenario, dic, en_camino, res, plan, eco, z=Z, n=N_REPLICAS,
                     con_ruido=True, rng=None, plan_de='central'):
    p = PARAMETROS[escenario]
    rng = rng or np.random.default_rng(SEMILLA)
    d_plan = plan.loc[plan_de][s].to_numpy()            # lo que prevé la planificadora
    d_esc = plan.loc[escenario][s].to_numpy()           # lo que de verdad espera el escenario
    T = len(d_plan)
    sigma_rel = res.loc[s, 'error_rel_mes_%'] / 100
    rho = float(np.clip(res.loc[s, 'autocorr'], 0, 0.95))
    ss = z * res.loc[s, 'sigma_mes'] * np.sqrt(3)

    ruido = errores_ar1(n, T, sigma_rel, rho, rng) if con_ruido else np.ones((n, T))
    D = d_esc * ruido

    # economía por coche en este escenario
    e = eco.loc[s]
    bruto = e.bruto - p['coste_extra'] * e.coste - (e.prima_co2 if p['prima_co2'] else 0)
    vm_edad = np.where(np.arange(EDAD_MAX + 1) <= 2, e.vm_0_90,
                       np.where(np.arange(EDAD_MAX + 1) <= 5, e.vm_91_180, e.vm_mas_180))
    cvp_transfer = (1 - PERDIDA_TRANSFER) * e.bruto - p['coste_extra'] * e.coste \
        - (e.prima_co2 if p['prima_co2'] else 0) - e.vm_0_90
    cuota_transfer = (1.0 if p['transfer_total'] else CUOTA_TRANSFER) if cvp_transfer > 0 else 0.0

    # estado
    cohortes = np.tile(stock_inicial(dic.loc[s]), (n, 1))
    L = np.zeros((n, T + 3))
    L[:, 0] = L[:, 1] = en_camino[s]                     # enero y febrero: ya en camino
    sin_llegadas = [m - 1 for m in p['sin_llegadas'].get(s, [])]

    reg = {k: np.zeros((n, T)) for k in
           ['vendidos', 'faltan', 'transfer', 'perdidas', 'stock_fin', 'coste_stock', 'vm', 'cvp',
            'llegadas', 'desvio']}

    def pedir(t, stock_t, k):
        """Al cerrar el mes t (0 = diciembre de A012) se pide la llegada de t+3."""
        if t + 2 >= T:
            return
        dh = d_plan * k[:, None]
        s1 = np.maximum(0, stock_t + L[:, t] - dh[:, t]) if t < T else stock_t
        s2 = np.maximum(0, s1 + L[:, t + 1] - dh[:, t + 1])
        L[:, t + 2] = np.maximum(0, dh[:, t + 2] + ss - s2)

    # decisión de diciembre de A012: llegada de marzo
    pedir(0, cohortes.sum(axis=1), np.ones(n))

    for t in range(T):
        llegan = L[:, t] * (0 if t in sin_llegadas else 1)
        cohortes[:, 0] += llegan
        reg['llegadas'][:, t] = llegan

        # ventas FIFO: primero los más viejos
        pendiente = D[:, t].copy()
        vm_mes = np.zeros(n)
        coste_mes = np.zeros(n)
        for a in range(EDAD_MAX, -1, -1):
            v = np.minimum(cohortes[:, a], pendiente)
            cohortes[:, a] -= v
            pendiente -= v
            vm_mes += v * vm_edad[a]
            if a < MESES_COSTE_STOCK:
                coste_mes += v * COSTE_STOCK_MES / 2          # vendidos: medio mes en la red
        vendidos = D[:, t] - pendiente
        transfer = pendiente * cuota_transfer
        coste_mes += cohortes[:, :MESES_COSTE_STOCK].sum(axis=1) * COSTE_STOCK_MES

        reg['vendidos'][:, t] = vendidos + transfer
        reg['faltan'][:, t] = pendiente
        reg['transfer'][:, t] = transfer
        reg['perdidas'][:, t] = pendiente - transfer
        reg['coste_stock'][:, t] = coste_mes
        reg['vm'][:, t] = vm_mes + transfer * e.vm_0_90
        reg['cvp'][:, t] = vendidos * bruto - vm_mes + transfer * cvp_transfer

        # envejecer
        cohortes[:, -1] += cohortes[:, -2]
        cohortes[:, 1:-1] = cohortes[:, :-2].copy()
        cohortes[:, 0] = 0
        reg['stock_fin'][:, t] = cohortes.sum(axis=1)

        # revisión de la previsión con la demanda observada (últimos 3 meses)
        desde = max(0, t - 2)
        k = D[:, desde:t + 1].sum(axis=1) / d_plan[desde:t + 1].sum()
        reg['desvio'][:, t] = k
        pedir(t + 1, cohortes.sum(axis=1), k)

    reg['mas_90_fin'] = cohortes[:, 4:].sum(axis=1)       # >= 4 meses tras envejecer: > 90 días
    reg['valor_perdidas'] = reg['perdidas'].sum(axis=1) * max(0, bruto - e.vm_0_90)
    reg['demanda'] = D
    return reg


# --- Tabla 5 ---------------------------------------------------------------------------
def resumen_replicas(reg):
    """Indicadores anuales por réplica."""
    dem_media = reg['demanda'].mean(axis=1)
    return pd.DataFrame({
        'demanda': reg['demanda'].sum(axis=1),
        'vendidos': reg['vendidos'].sum(axis=1),
        'llegadas': reg['llegadas'].sum(axis=1),
        'stock_medio': reg['stock_fin'].mean(axis=1),
        'meses_stock': reg['stock_fin'].mean(axis=1) / dem_media,
        'stock_fin_anio': reg['stock_fin'][:, -1],
        'mas_90_fin': reg['mas_90_fin'],
        'coste_stock': reg['coste_stock'].sum(axis=1),
        'transfer': reg['transfer'].sum(axis=1),
        'perdidas': reg['perdidas'].sum(axis=1),
        'valor_perdidas': reg['valor_perdidas'],
        'vm': reg['vm'].sum(axis=1),
        'cvp': reg['cvp'].sum(axis=1),
    }).assign(resultado=lambda x: x.cvp - x.coste_stock)


def simular_todo(z=Z, n=N_REPLICAS, plan_de='central'):
    dic, en_camino, res, plan, eco = datos_partida()
    out = {}
    for e in ESCENARIOS:
        rng = np.random.default_rng(SEMILLA)       # misma suerte en todos los escenarios
        for s in d.SEGMENTOS:
            zs = z[s] if isinstance(z, dict) else z
            out[(e, s)] = resumen_replicas(simular_segmento(
                s, e, dic, en_camino, res, plan, eco, z=zs, n=n, rng=rng, plan_de=plan_de))
    return out


def tabla5(out, segmento=None):
    filas = {}
    for e in ESCENARIOS:
        if segmento:
            r = out[(e, segmento)]
        else:
            r = sum(out[(e, s)] for s in d.SEGMENTOS)
            r['meses_stock'] = r.stock_medio / (r.demanda / 12)
        filas[e] = r
    indicadores = [
        ('Demanda (coches)', 'demanda', 0), ('Coches vendidos', 'vendidos', 0),
        ('Coches que llegan a la red (fabricados)', 'llegadas', 0),
        ('Stock medio en la red (coches)', 'stock_medio', 0),
        ('Stock medio (meses de venta)', 'meses_stock', 2),
        ('Stock a fin de año (coches)', 'stock_fin_anio', 0),
        ('Coches con más de 90 días a fin de año', 'mas_90_fin', 0),
        ('Coste del stock para la marca (EUR)', 'coste_stock', 0),
        ('Transfers (coches)', 'transfer', 0), ('Ventas perdidas (coches)', 'perdidas', 0),
        ('Ventas perdidas (EUR de CVP)', 'valor_perdidas', 0),
        ('Gasto comercial VM (EUR)', 'vm', 0), ('Margen de la marca CVP (EUR)', 'cvp', 0),
        ('CVP - coste del stock (EUR)', 'resultado', 0),
    ]
    t = pd.DataFrame({e: {nombre: filas[e][col].mean() for nombre, col, _ in indicadores}
                      for e in ESCENARIOS})
    banda = pd.DataFrame({e: {nombre: f'{filas[e][col].quantile(.1):,.0f} – {filas[e][col].quantile(.9):,.0f}'
                              if dec == 0 else f'{filas[e][col].quantile(.1):.2f} – {filas[e][col].quantile(.9):.2f}'
                              for nombre, col, dec in indicadores} for e in ESCENARIOS})
    return t, banda


def plan_central():
    """Plan de llegadas mensual del escenario central sin ruido: lo que se propone pedir."""
    dic, en_camino, res, plan, eco = datos_partida()
    filas = {}
    for s in d.SEGMENTOS:
        reg = simular_segmento(s, 'central', dic, en_camino, res, plan, eco, n=1, con_ruido=False,
                               z=Z_RECOMENDADO[s])
        filas[s] = pd.Series(reg['llegadas'][0], index=plan.loc['central'].index)
    p = pd.DataFrame(filas)
    p['TOTAL'] = p.sum(axis=1)
    return p, en_camino


def main():
    plan, en_camino = plan_central()
    print('=== Plan de llegadas a la red, escenario central (coches) ===')
    print('Enero y febrero ya están en camino (supuesto: facturación media jul-dic A012).')
    print('De marzo en adelante: lo que se pide a la fábrica 3 meses antes.')
    tabla = plan.round().astype(int)
    tabla.index = [f'A013-{m:02d}' for m in tabla.index.month]
    tabla.loc['TOTAL'] = tabla.sum()
    print(tabla.to_string())

    out = simular_todo(z=Z_RECOMENDADO)
    t, banda = tabla5(out)
    print(f'\n=== Tabla 5, TOTAL (media de {N_REPLICAS} réplicas; plan central, z recomendado por segmento) ===')
    print(t.map(lambda x: f'{x:,.0f}' if abs(x) >= 100 else f'{x:,.2f}').to_string())
    print('\nBanda P10 – P90:')
    print(banda.to_string())

    filas = []
    for s in d.SEGMENTOS:
        ts, _ = tabla5(out, s)
        ts.columns = pd.MultiIndex.from_product([[s], ts.columns])
        filas.append(ts)
    por_seg = pd.concat(filas, axis=1)
    print('\n=== Tabla 5 por segmento (medias) ===')
    for s in d.SEGMENTOS:
        print(f'\n--- {s} ---')
        print(por_seg[s].map(lambda x: f'{x:,.0f}' if abs(x) >= 100 else f'{x:,.2f}').to_string())

    plan.to_csv(d.RESULTADOS / 'plan_llegadas_central.csv')
    t.to_csv(d.RESULTADOS / 'tabla5_total.csv')
    banda.to_csv(d.RESULTADOS / 'tabla5_total_bandas.csv')
    por_seg.to_csv(d.RESULTADOS / 'tabla5_segmentos.csv')

    # gráfico: stock medio mensual y demanda por escenario (total)
    dic, en_camino_, res, plan_d, eco = datos_partida()
    fig, ejes = plt.subplots(1, 2, figsize=(14, 4.5))
    colores = {'pesimista': 'tab:red', 'central': 'tab:blue', 'optimista': 'tab:green'}
    meses = np.arange(1, 13)
    for e in ESCENARIOS:
        stock = np.zeros((N_REPLICAS, 12))
        vend = np.zeros((N_REPLICAS, 12))
        rng = np.random.default_rng(SEMILLA)
        for s in d.SEGMENTOS:
            reg = simular_segmento(s, e, dic, en_camino_, res, plan_d, eco, rng=rng, z=Z_RECOMENDADO[s])
            stock += reg['stock_fin']
            vend += reg['vendidos']
        for ax, m, nombre in [(ejes[0], stock, 'Stock en la red a fin de mes'),
                              (ejes[1], vend, 'Coches vendidos al mes')]:
            ax.plot(meses, m.mean(axis=0), color=colores[e], label=e)
            ax.fill_between(meses, np.percentile(m, 10, axis=0), np.percentile(m, 90, axis=0),
                            color=colores[e], alpha=0.15)
            ax.set_title(nombre)
            ax.set_xticks(meses)
    ejes[0].legend()
    fig.suptitle('Simulación de A013 con el plan central (media y banda P10–P90)')
    fig.tight_layout()
    fig.savefig(d.RESULTADOS / 'fase4_simulacion.png', dpi=120)
    print(f'\nGuardado en {d.RESULTADOS}')


if __name__ == '__main__':
    main()
