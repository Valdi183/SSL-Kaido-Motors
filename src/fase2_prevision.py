"""
Fase 2: previsión de la demanda de Kaido (pregunta 2 del caso).

demanda Kaido = mercado del segmento x cuota de Kaido   (sección 5.2 del caso)

  * Mercado: regresión con errores SARIMA(0,0,0)(0,1,1)12 sobre log(unidades)
    ("mismo mes del año anterior, suavizado") con:
      - economía: confianza del consumidor con 3 meses de retraso
        (se conoce cuando se decide la producción, sección 5.1)
      - calendario: días laborables y Semana Santa
      - sucesos: adelanto de compras, caída posterior, subida del IVA, plan de ayuda
      - tendencia (drift) solo en C, B y MD: segmentos en declive estructural
        desde A001 porque el cliente se pasa al SUV.
    Se eligió frente al SARIMA(1,0,0) del Anexo 4 y otras variables macro (paro,
    hipotecas, actividad) porque es el que mejor previó A012: el Anexo 4 arrastra
    la inercia de crecimiento de A010-A011 y sobreestima.
  * Cuota: media de los últimos 6 meses normales (demanda limpia / mercado).
    El efecto de los lanzamientos entra por los escenarios (Fase 4).
  * S (descapotable): su mercado es casi solo Kaido y tiene meses con 1 coche,
    así que se prevé directamente la demanda de Kaido: nivel x estacionalidad.

Validación: entrenar hasta A011, prever A012 y comparar con la demanda real.
Después se reentrena hasta A012 y se prevé A013 (escenario central).

Ejecutar desde la raíz del repositorio (necesita resultados/demanda_real.csv de la Fase 1):
    python src/fase2_prevision.py
"""
import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import datos as d

warnings.filterwarnings('ignore')
pd.set_option('display.width', 200)
pd.set_option('display.max_columns', 30)

RETRASO = 3
MACRO = ['confianza_consumidor']
CON_TENDENCIA = ['C', 'B', 'MD']
CALENDARIO = ['dias_laborables', 'semana_santa']
SUCESOS = ['adelanto_compras', 'caida_tras_adelanto', 'subida_iva', 'incentivo_publico']
MESES_CUOTA = 6
CAIDA_A013 = 3          # escenario central: la caída tras el adelanto dura tres meses
CON_MERCADO = [s for s in d.SEGMENTOS if s != 'S']

mer = d.mercado()
mercado = mer.groupby(['fecha', 'segmento']).unidades.sum().unstack()[d.SEGMENTOS]
dem = pd.read_csv(d.RESULTADOS / 'demanda_real.csv', parse_dates=['fecha'])
demanda = dem.pivot(index='fecha', columns='segmento', values='demanda')[d.SEGMENTOS]
mac = d.macro()
cal = d.calendario_A013()


# --- Variables explicativas -------------------------------------------------------
def exog_historico():
    X = mac[CALENDARIO + SUCESOS].copy()
    for v in MACRO:
        X[v] = mac[v].shift(RETRASO)
    return X.dropna()


def exog_A013(caida_meses=CAIDA_A013, macro_futuro=None):
    """Escenario central: la economía se queda como al final de A012.

    Con 3 meses de retraso, enero-marzo de A013 usan octubre-diciembre de A012 (conocidos);
    de abril en adelante se repite el último dato (o el que se pase en macro_futuro).
    """
    X = cal[CALENDARIO].copy()
    for s in SUCESOS:
        X[s] = 0
    X.iloc[:caida_meses, X.columns.get_loc('caida_tras_adelanto')] = 1
    for v in MACRO:
        conocidos = mac[v].iloc[-RETRASO:].to_numpy()
        futuro = macro_futuro[v] if macro_futuro and v in macro_futuro else conocidos[-1]
        X[v] = np.r_[conocidos, np.repeat(futuro, len(X) - RETRASO)]
    return X


def ajustar_mercado(y, X, tendencia=False):
    return sm.tsa.SARIMAX(np.log(y), exog=X, order=(0, 0, 0), seasonal_order=(0, 1, 1, 12),
                          trend='c' if tendencia else 'n').fit(disp=False, maxiter=1000)


def prever_mercado(y, X, X_fut, tendencia=False):
    res = ajustar_mercado(y, X, tendencia)
    return np.exp(res.forecast(len(X_fut), exog=X_fut)).set_axis(X_fut.index), res


# --- Cuota --------------------------------------------------------------------------
def cuota_reciente(seg, hasta):
    """Media de la cuota en los últimos meses normales (sin sucesos)."""
    c = (demanda[seg] / mercado[seg]).loc[:hasta]
    if seg == 'CSUV':       # en rampa de lanzamiento: los 3 últimos meses (sin adelanto en su mercado)
        return c.iloc[-3:].mean()
    normal = (mac[SUCESOS].sum(axis=1) == 0).reindex(c.index, fill_value=True)
    c = c[normal & (demanda[seg].loc[:hasta] > 0)]
    return c.iloc[-MESES_CUOTA:].mean()


# --- S: nivel x estacionalidad sobre la demanda de Kaido ----------------------------
def prever_nivel_estacional(y, meses_fut):
    y = y[y.index.year >= y.index.year.max() - 3]        # últimos 4 años
    f = (y / y.rolling(12, center=True).mean()).groupby(y.index.month).mean()
    f = f / f.mean()
    nivel = (y.iloc[-12:] / f.reindex(y.index[-12:].month).to_numpy()).mean()
    return pd.Series(nivel * f.reindex(meses_fut.month).to_numpy(), index=meses_fut)


# --- Modelo completo para un corte ---------------------------------------------------
def prevision(hasta, X_fut):
    """Previsión de mercado, cuota y demanda de Kaido para los meses de X_fut."""
    X = exog_historico()
    filas = {}
    for s in CON_MERCADO:
        y = mercado[s].loc[:hasta]
        y = y[y.index >= X.index[0]]
        merc, _ = prever_mercado(y, X.loc[y.index], X_fut, s in CON_TENDENCIA)
        cuota = cuota_reciente(s, hasta)
        filas[s] = pd.DataFrame({'mercado': merc, 'cuota': cuota, 'demanda': merc * cuota})
    y_s = demanda['S'].loc[:hasta]
    dem_s = prever_nivel_estacional(y_s, X_fut.index)
    filas['S'] = pd.DataFrame({'mercado': np.nan, 'cuota': np.nan, 'demanda': dem_s})
    return pd.concat(filas, names=['segmento', 'fecha'])


# ==================================================================================
# 1. Validación: entrenar hasta A011, prever A012
# ==================================================================================
X_hist = exog_historico()
X_2012 = X_hist.loc['2012'].copy()
X_2012['adelanto_compras'] = 0     # se compara con la demanda limpia, que ya no tiene el adelanto
val = prevision('2011-12', X_2012)
val['real'] = [demanda.loc[f, s] for s, f in val.index]
val['merc_real'] = [mercado.loc[f, s] for s, f in val.index]
val['naive'] = [demanda.loc[f - pd.DateOffset(years=1), s] for s, f in val.index]

print('=== Validación A012 (entrenado hasta A011) ===')
filas = []
for s in d.SEGMENTOS:
    if s == 'CSUV':
        continue                # sin historia antes de A012-08: no se puede validar
    v = val.loc[s]
    err = v.demanda - v.real
    filas.append({
        'segmento': s,
        'real_A012': v.real.sum(), 'prev_A012': v.demanda.sum(),
        'error_anual_%': (v.demanda.sum() / v.real.sum() - 1) * 100,
        'MAPE_mes_%': (err.abs() / v.real).mean() * 100,
        'MAPE_naive_%': ((v.naive - v.real).abs() / v.real).mean() * 100,
        'error_mercado_%': (v.mercado.sum() / v.merc_real.sum() - 1) * 100 if s != 'S' else np.nan,
        'sigma_coches': err.std(),
        'autocorr_err': err.autocorr(),
    })
tabla_val = pd.DataFrame(filas).set_index('segmento')
print(tabla_val.round(1).to_string())
tot = val.drop('CSUV').groupby(level='fecha')[['demanda', 'real']].sum()
print(f"TOTAL (sin CSUV): real {tot.real.sum():.0f}  previsto {tot.demanda.sum():.0f}  "
      f"error {(tot.demanda.sum() / tot.real.sum() - 1) * 100:+.1f} %  "
      f"MAPE mensual {((tot.demanda - tot.real).abs() / tot.real).mean() * 100:.1f} %")

# ==================================================================================
# 2. Previsión de A013 (escenario central), reentrenando hasta A012
# ==================================================================================
X_2013 = exog_A013()
prev = prevision('2012-12', X_2013)

# Error típico mensual (sigma) para el stock de seguridad y la simulación:
# error relativo de la validación aplicado al nivel previsto de A013.
# CSUV no se pudo validar: se le asigna el mayor error relativo de los SUV.
err_rel = (tabla_val.sigma_coches / (tabla_val.real_A012 / 12))
err_rel['CSUV'] = err_rel[['MSUV', 'SSUV']].max()
media_mes = prev.groupby(level='segmento').demanda.mean()
sigma = (err_rel * media_mes).rename('sigma_coches')
autocorr = tabla_val.autocorr_err.reindex(d.SEGMENTOS).fillna(tabla_val.autocorr_err.mean())

print('\n=== Previsión A013, escenario central (coches) ===')
tabla = prev.demanda.unstack('segmento')[d.SEGMENTOS].round()
tabla['TOTAL'] = tabla.sum(axis=1)
tabla.index = [f'A013-{m:02d}' for m in tabla.index.month]
print(tabla.astype(int).to_string())

resumen = pd.DataFrame({
    'demanda_A012': demanda.loc['2012'].sum(),
    'prev_A013': prev.groupby(level='segmento').demanda.sum(),
    'cuota_A013_%': prev.groupby(level='segmento').cuota.mean() * 100,
    'mercado_A012': mercado.loc['2012'].sum(),
    'mercado_A013': prev.groupby(level='segmento').mercado.sum(min_count=1),
    'sigma_mes': sigma, 'error_rel_mes_%': err_rel * 100, 'autocorr': autocorr,
}).reindex(d.SEGMENTOS)
resumen['var_demanda_%'] = (resumen.prev_A013 / resumen.demanda_A012 - 1) * 100
resumen['var_mercado_%'] = (resumen.mercado_A013 / resumen.mercado_A012 - 1) * 100
print('\n=== Resumen por segmento ===')
print(resumen.round(1).to_string())
print(f"\nTOTAL: demanda A012 {resumen.demanda_A012.sum():.0f} -> A013 {resumen.prev_A013.sum():.0f} "
      f"({(resumen.prev_A013.sum() / resumen.demanda_A012.sum() - 1) * 100:+.1f} %)")

# --- Guardar -----------------------------------------------------------------------
prev.reset_index().to_csv(d.RESULTADOS / 'prevision_A013_central.csv', index=False)
resumen.to_csv(d.RESULTADOS / 'prevision_resumen.csv')
val.reset_index().to_csv(d.RESULTADOS / 'validacion_A012.csv', index=False)

fig, ejes = plt.subplots(4, 2, figsize=(14, 12), sharex=True)
for ax, s in zip(ejes.flat, d.SEGMENTOS + ['TOTAL']):
    cols = d.SEGMENTOS if s == 'TOTAL' else [s]
    ax.plot(demanda.loc['2010':, cols].sum(axis=1), color='0.3', label='demanda real')
    v = val.loc[cols].groupby(level='fecha').demanda.sum() if s != 'TOTAL' else \
        val.drop('CSUV').groupby(level='fecha').demanda.sum()
    if s != 'CSUV':
        ax.plot(v, color='tab:orange', ls='--', label='validación A012')
    ax.plot(prev.loc[cols].groupby(level='fecha').demanda.sum(), color='tab:red',
            label='previsión A013')
    ax.axvline(pd.Timestamp('2013-01-01'), color='0.6', lw=0.8)
    ax.set_title(s)
ejes[0, 0].legend(fontsize=8)
fig.suptitle('Demanda de Kaido: validación con A012 y previsión central de A013')
fig.tight_layout()
fig.savefig(d.RESULTADOS / 'fase2_prevision.png', dpi=120)
print(f'\nGuardado en {d.RESULTADOS}')
