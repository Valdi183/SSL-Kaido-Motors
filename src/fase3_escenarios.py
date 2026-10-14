"""
Fase 3: los tres escenarios de A013 (pregunta 3 del caso, Tabla 4).

Cada suceso de la Tabla 4 entra por un sitio distinto (sección 9.2):
  * economía, turismo, plan de ayuda -> variables del modelo de mercado de la Fase 2
  * caída tras el adelanto           -> multiplicador calibrado con A011 (Fase 1)
  * producto (códigos nuevos)        -> cuota de Kaido
  * arancel, euro, prima de CO2      -> beneficio por coche (lo usa la simulación)
  * suministro                       -> coches que llegan (lo usa la simulación)

Traducción a números (cada valor se justifica con un episodio de los datos):
  - Confianza: con 3 meses de retraso, enero-marzo ya se conocen (73,3 / 77,4 / 77,7).
    De abril en adelante: central 77,7 ("como al final de A012").
    Pesimista -12 puntos (65,7): el paro sube 2 puntos; en A004->A005 el paro subió
    3,4 puntos y la confianza cayó 21 (~6 puntos de confianza por punto de paro).
    Optimista +10 puntos (87,7, la media de A012): el paro baja 1 punto (+6) y el
    crédito se abarata (+4).
  - Caída tras el adelanto: el mercado cayó de media un 11 % en los 4 meses que
    siguieron al adelanto de A011 (Fase 1). Central 3 meses, pesimista 6, optimista 1.
  - Plan de ayuda (optimista): incentivo_publico = 1 de abril a diciembre.
  - Producto: pesimista, los 2 códigos nuevos del MSUV se retrasan 3 meses -> cuota
    del MSUV x0,85 de abril a junio. Optimista, los códigos nuevos venden mejor ->
    cuota x1,10 desde abril en MSUV, SSUV, B y CSUV (los segmentos con códigos nuevos).
  - Turismo: las compras de los alquiladores de marzo a junio -30 % / +30 %
    (pesan poco en Kaido: 0-5 % de sus ventas según segmento).
  - Beneficio por coche: pesimista, la matriz carga la prima de CO2 y el arancel
    sube 5 puntos sobre el coste; optimista, el euro fuerte y el combustible barato
    abaratan el coste un 3 %.
  - Suministro: pesimista, la fábrica pierde un mes de producción del MSUV (llegadas
    de junio = 0); optimista, la fábrica tiene coches de sobra (todo faltante se cubre
    con transfer).

Ejecutar desde la raíz del repositorio (necesita las salidas de las Fases 1 y 2):
    python src/fase3_escenarios.py
Genera resultados/escenarios_demanda.csv y resultados/fase3_escenarios.png
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
import fase2_prevision as f2

ESCENARIOS = ['pesimista', 'central', 'optimista']
CAIDA_TRAS_ADELANTO = 0.11      # caída media del mercado tras el adelanto de A011 (Fase 1)

PARAMETROS = {
    'central': dict(
        confianza=77.7, meses_caida=3, plan_ayuda=False,
        cuota={}, turismo=0.0,
        prima_co2=False, coste_extra=0.0,
        sin_llegadas={}, transfer_total=False),
    'pesimista': dict(
        confianza=77.7 - 12, meses_caida=6, plan_ayuda=False,
        cuota={'MSUV': ([4, 5, 6], 0.85)}, turismo=-0.30,
        prima_co2=True, coste_extra=0.05,
        sin_llegadas={'MSUV': [6]}, transfer_total=False),
    'optimista': dict(
        confianza=77.7 + 10, meses_caida=1, plan_ayuda=True,
        cuota={s: (list(range(4, 13)), 1.10) for s in ['MSUV', 'SSUV', 'B', 'CSUV']},
        turismo=+0.30,
        prima_co2=False, coste_extra=-0.03,
        sin_llegadas={}, transfer_total=True),
}


def peso_alquiladores():
    """Peso de los alquiladores en las ventas de Kaido de marzo a junio de A012, por segmento."""
    v = d.ventas()
    v = v[(v.anio == 'A012') & v.mes.between(3, 6)]
    tot = v.groupby('segmento').unidades.sum()
    alq = v[v.canal == 'ALQUILADORES'].groupby('segmento').unidades.sum()
    return (alq / tot).reindex(d.SEGMENTOS).fillna(0)


def demanda_escenario(nombre):
    """Demanda esperada de Kaido en A013 (coches por mes y segmento) para un escenario."""
    p = PARAMETROS[nombre]
    X = f2.exog_A013(caida_meses=0, macro_futuro={'confianza_consumidor': p['confianza']})
    if p['plan_ayuda']:
        X.iloc[3:, X.columns.get_loc('incentivo_publico')] = 1
    prev = f2.prevision('2012-12', X).demanda.unstack('segmento')[d.SEGMENTOS]
    meses = prev.index.month

    prev.loc[meses <= p['meses_caida']] *= 1 - CAIDA_TRAS_ADELANTO
    for s, (m, factor) in p['cuota'].items():
        prev.loc[meses.isin(m), s] *= factor
    alq = peso_alquiladores()
    prev.loc[meses.isin([3, 4, 5, 6])] *= (1 + p['turismo'] * alq)
    return prev


def main():
    filas = {e: demanda_escenario(e) for e in ESCENARIOS}
    dem = pd.concat(filas, names=['escenario', 'fecha'])
    dem.to_csv(d.RESULTADOS / 'escenarios_demanda.csv')

    anual = dem.groupby(level='escenario').sum().loc[ESCENARIOS].T
    anual.loc['TOTAL'] = anual.sum()
    real_A012 = pd.read_csv(d.RESULTADOS / 'prevision_resumen.csv', index_col=0).demanda_A012
    anual['demanda_A012'] = real_A012.reindex(anual.index)
    anual.loc['TOTAL', 'demanda_A012'] = real_A012.sum()
    for e in ESCENARIOS:
        anual[f'{e}_vs_A012_%'] = (anual[e] / anual.demanda_A012 - 1) * 100
    print('=== Demanda esperada de Kaido en A013 por escenario (coches) ===')
    print(anual.round(0).to_string())
    print('\nPeso de los alquiladores (mar-jun A012):', peso_alquiladores().round(3).to_dict())

    fig, ejes = plt.subplots(4, 2, figsize=(14, 12), sharex=True)
    colores = {'pesimista': 'tab:red', 'central': 'tab:blue', 'optimista': 'tab:green'}
    for ax, s in zip(ejes.flat, d.SEGMENTOS + ['TOTAL']):
        for e in ESCENARIOS:
            serie = dem.loc[e].sum(axis=1) if s == 'TOTAL' else dem.loc[e][s]
            ax.plot(serie, color=colores[e], label=e)
        ax.set_title(s)
    ejes[0, 0].legend(fontsize=8)
    fig.suptitle('Demanda esperada de Kaido en A013 por escenario')
    fig.tight_layout()
    fig.savefig(d.RESULTADOS / 'fase3_escenarios.png', dpi=120)
    print(f'\nGuardado en {d.RESULTADOS}')


if __name__ == '__main__':
    main()
