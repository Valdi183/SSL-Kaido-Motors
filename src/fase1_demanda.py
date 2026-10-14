"""
Fase 1: demanda real de Kaido (pregunta 1 del caso).

Pasos, por segmento y mes:
  1. Retail = matriculaciones - automatriculaciones.
  2. Meses de compras adelantadas (adelanto_compras) y de caída posterior
     (caida_tras_adelanto): se sustituyen por la demanda "normal" esperada,
     nivel desestacionalizado de los 6 meses normales previos x factor estacional.
     El factor estacional sale del mercado del segmento (A001-A012), que tiene
     más historia y menos ruido que las ventas de Kaido.
  3. Meses con rotura de stock (desde A009, único periodo con stock): el stock
     a fin de mes es casi cero, así que se vendió lo que había y la demanda fue
     al menos eso. Se toma el máximo entre lo vendido y lo esperado.
  4. CSUV (lanzado en A012-08, sin nivel previo): se le aplica el mismo exceso
     relativo que tuvo su mercado en los meses de adelanto.

Ejecutar desde la raíz del repositorio:
    python src/fase1_demanda.py
Genera resultados/demanda_real.csv y resultados/fase1_demanda.png
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

pd.set_option('display.width', 200)
pd.set_option('display.max_columns', 30)

MESES_NIVEL = 6         # meses normales previos para fijar el nivel
UMBRAL_ROTURA = 0.15    # stock fin de mes < 15 % de la venta media mensual -> rotura

ven = d.ventas()
mer = d.mercado()
sto = d.stock()
mac = d.macro()

ven['retail'] = ven.unidades - ven.u_automatriculacion
tabla = lambda df, col: df.groupby(['fecha', 'segmento'])[col].sum().unstack()[d.SEGMENTOS]
vendido = tabla(ven, 'unidades').loc['2003':]
retail = tabla(ven, 'retail').loc['2003':]
automat = tabla(ven, 'u_automatriculacion').loc['2003':]
mercado = tabla(mer, 'unidades')
stock = sto.pivot_table(index='fecha', columns='segmento', values='stock_total')[d.SEGMENTOS]

adelanto = mac.adelanto_compras == 1
caida = mac.caida_tras_adelanto == 1
evento = adelanto | caida | (mac.subida_iva == 1)


# --- Factores estacionales del mercado de cada segmento (multiplicativos, media 1) ---
def factores_estacionales(y):
    ratio = y / y.rolling(12, center=True).mean()
    ratio = ratio[~evento.reindex(ratio.index, fill_value=False)]
    f = ratio.groupby(ratio.index.month).median()
    return f / f.mean()


estac = pd.DataFrame({s: factores_estacionales(mercado[s]) for s in d.SEGMENTOS})
f_mes = lambda idx, s: estac[s].reindex(idx.month).to_numpy()


def esperado(serie, s, mes, excluir):
    """Demanda normal esperada en `mes`: nivel desestacionalizado de los meses normales vecinos.

    Si hay meses normales después (sucesos pasados), se usan 3 antes y 3 después,
    para recoger la tendencia. Si no (final de A012), los 6 previos.
    """
    normal = serie[~excluir.reindex(serie.index, fill_value=False) & (serie > 0)]
    previos = normal.loc[:mes - pd.DateOffset(months=1)]
    despues = normal.loc[mes + pd.DateOffset(months=1):].iloc[:3]
    if len(previos) < 3:    # segmento sin historia suficiente (aún no se vendía)
        return np.nan
    vecinos = (pd.concat([previos.iloc[-3:], despues]) if len(despues) == 3
               else previos.iloc[-MESES_NIVEL:])
    nivel = (vecinos / f_mes(vecinos.index, s)).mean()
    return nivel * estac.loc[mes.month, s]


# --- Meses con rotura de stock ---
media_12 = vendido.rolling(12, min_periods=3).mean().reindex(stock.index)
rotura = (stock < UMBRAL_ROTURA * media_12) & (media_12 > 0)

# --- Limpieza ---
demanda = retail.astype(float).copy()
marca = pd.DataFrame('', index=demanda.index, columns=d.SEGMENTOS)
excluir = evento.copy()
for s in d.SEGMENTOS:
    excl_s = excluir | rotura[s].reindex(excluir.index, fill_value=False)
    for mes in demanda.index[evento.reindex(demanda.index, fill_value=False)]:
        e = esperado(retail[s], s, mes, excl_s)
        if np.isnan(e):
            continue
        # adelanto/IVA: solo se quita el exceso; caída: solo se rellena el hueco
        nuevo = max(retail.loc[mes, s], e) if caida[mes] else min(retail.loc[mes, s], e)
        if nuevo != retail.loc[mes, s]:
            demanda.loc[mes, s] = nuevo
            marca.loc[mes, s] = 'adelanto' if adelanto[mes] else ('caida' if caida[mes] else 'iva')
    for mes in rotura.index[rotura[s]]:
        e = esperado(retail[s], s, mes, excl_s)
        if not np.isnan(e) and e > retail.loc[mes, s]:
            demanda.loc[mes, s] = max(e, demanda.loc[mes, s])
            marca.loc[mes, s] += '+rotura' if marca.loc[mes, s] else 'rotura'

# CSUV: sin nivel previo -> exceso relativo de su mercado en los meses de adelanto.
# Si su mercado no muestra exceso (ratio <= 1) se deja lo vendido: está en rampa de lanzamiento.
for mes in mac.index[adelanto & (mac.index.year == 2012)]:
    e_merc = esperado(mercado['CSUV'], 'CSUV', mes, excluir)
    exceso = max(1.0, mercado.loc[mes, 'CSUV'] / e_merc)
    demanda.loc[mes, 'CSUV'] = retail.loc[mes, 'CSUV'] / exceso
    marca.loc[mes, 'CSUV'] = f'adelanto(merc x{mercado.loc[mes, "CSUV"] / e_merc:.2f})'

demanda = demanda.round()

# --- Resultados ---
print('=== Factores estacionales del mercado (1 = mes medio) ===')
print(estac.round(2).T.to_string())

print('\n=== Meses corregidos ===')
corr = marca.stack()
corr = corr[corr != ''].rename('motivo').to_frame()
corr['retail'] = [retail.loc[i] for i in corr.index]
corr['demanda'] = [demanda.loc[i] for i in corr.index]
corr['diferencia'] = corr.demanda - corr.retail
corr.index = [f'A{f.year - 2000:03d}-{f.month:02d} {s}' for f, s in corr.index]
print(corr.to_string())

print('\n=== Kaido A012: coches adelantados (nov+dic) y demanda no servida por rotura ===')
dif = (retail - demanda).loc['2012-11':'2012-12']
print('  adelantados:', dif.clip(lower=0).sum().round().astype(int).to_dict(),
      ' total', int(dif.clip(lower=0).sum().sum()))
print('  no servidos:', (-dif).clip(lower=0).sum().round().astype(int).to_dict(),
      ' total', int((-dif).clip(lower=0).sum().sum()))

print('\n=== Mercado (7 segmentos): vendido frente a esperado en los sucesos ===')
merc_tot = mercado.sum(axis=1)
estac['TOTAL'] = factores_estacionales(merc_tot)
filas = []
for mes in mac.index[(adelanto | caida) & (mac.index.year >= 2011)]:
    e = esperado(merc_tot, 'TOTAL', mes, evento)
    filas.append((f'A{mes.year - 2000:03d}-{mes.month:02d}',
                  'adelanto' if adelanto[mes] else 'caida', merc_tot[mes], round(e),
                  f'{merc_tot[mes] / e - 1:+.0%}'))
print(pd.DataFrame(filas, columns=['mes', 'suceso', 'vendido', 'esperado', 'desvio'])
      .to_string(index=False))

anual = pd.DataFrame({
    'vendido': vendido.groupby(vendido.index.year).sum().sum(axis=1),
    'automat': automat.groupby(automat.index.year).sum().sum(axis=1),
    'retail': retail.groupby(retail.index.year).sum().sum(axis=1),
    'demanda_real': demanda.groupby(demanda.index.year).sum().sum(axis=1),
})
sin_csuv = demanda.drop(columns='CSUV')
anual['demanda_sin_CSUV'] = sin_csuv.groupby(sin_csuv.index.year).sum().sum(axis=1)
anual['mercado'] = mercado.loc['2003':].groupby(mercado.loc['2003':].index.year).sum().sum(axis=1)
anual.index = [f'A{a - 2000:03d}' for a in anual.index]
print('\n=== Totales anuales ===')
print(anual.astype(int).to_string())
print('\n=== Crecimiento anual (%) ===')
print((anual.pct_change() * 100).round(1).loc['A009':].to_string())

seg_anual = demanda.groupby(demanda.index.year).sum().loc[[2011, 2012]]
seg_vend = vendido.groupby(vendido.index.year).sum().loc[[2011, 2012]]
print('\n=== A012 vs A011 por segmento ===')
cmp = pd.DataFrame({
    'vendido_A011': seg_vend.loc[2011], 'vendido_A012': seg_vend.loc[2012],
    'crec_vendido_%': (seg_vend.loc[2012] / seg_vend.loc[2011] - 1) * 100,
    'demanda_A011': seg_anual.loc[2011], 'demanda_A012': seg_anual.loc[2012],
    'crec_demanda_%': (seg_anual.loc[2012] / seg_anual.loc[2011] - 1) * 100,
})
print(cmp.round(1).to_string())

# --- Guardar ---
d.RESULTADOS.mkdir(exist_ok=True)
salida = (pd.concat({'vendido': vendido, 'automat': automat, 'retail': retail,
                     'demanda': demanda, 'motivo': marca}, axis=1)
          .stack(level=1, future_stack=True).reset_index()
          .rename(columns={'level_1': 'segmento'}))
salida.to_csv(d.RESULTADOS / 'demanda_real.csv', index=False)

fig, ejes = plt.subplots(4, 2, figsize=(14, 12), sharex=True)
for ax, s in zip(ejes.flat, d.SEGMENTOS + ['TOTAL']):
    cols = d.SEGMENTOS if s == 'TOTAL' else [s]
    per = slice('2009', '2012')
    ax.plot(vendido.loc[per, cols].sum(axis=1), color='0.7', label='vendido')
    ax.plot(retail.loc[per, cols].sum(axis=1), color='tab:blue', lw=1, label='retail (sin automat.)')
    ax.plot(demanda.loc[per, cols].sum(axis=1), color='tab:red', lw=1.5, label='demanda real')
    ax.set_title(s)
ejes[0, 0].legend(fontsize=8)
fig.suptitle('Kaido: ventas frente a demanda real (A009-A012)')
fig.tight_layout()
fig.savefig(d.RESULTADOS / 'fase1_demanda.png', dpi=120)
print(f'\nGuardado en {d.RESULTADOS}')
