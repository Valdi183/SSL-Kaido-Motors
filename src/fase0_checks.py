"""
Fase 0: comprobaciones de integridad y primera exploración de los datos.

Ejecutar desde la raíz del repositorio:
    python src/fase0_checks.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import datos as d

pd.set_option('display.width', 160)
pd.set_option('display.max_columns', 30)

ven = d.ventas()
mer = d.mercado()
sto = d.stock()
mac = d.macro()
cal = d.calendario_A013()
seg = d.segmentos()
cod = d.codigos()

print('=== 1. Tamaños y rangos ===')
for nombre, df in [('ventas', ven), ('mercado', mer), ('stock', sto)]:
    print(f'{nombre:8s} {len(df):5d} filas  {df.periodo.min()} -> {df.periodo.max()}')
print(f'macro    {len(mac):5d} filas  {mac.periodo.min()} -> {mac.periodo.max()}')
print(f'calendario A013: {len(cal)} meses, {cal.dias_laborables.sum()} días laborables')
print(f'códigos: {len(cod)}, en tarifa A013: {cod.en_tarifa_A013.sum()}')

print('\n=== 2. Total de ventas de Kaido A003-A012 (esperado 125.030) ===')
tot_ven = ven.unidades.sum()
tot_mer = mer.loc[mer.anio >= 'A003', 'marca_propia'].sum()
tot_seg = seg.unidades_totales.sum()
tot_cod = cod.unidades.sum()
print(f'ventas_mensual: {tot_ven}  mercado.marca_propia: {tot_mer}  '
      f'segmentos: {tot_seg}  codigos: {tot_cod}')

print('\n=== 3. Coherencia ventas vs mercado.marca_propia (desde A003) ===')
k = ['periodo', 'segmento', 'canal']
cruce = ven[k + ['unidades']].merge(
    mer.loc[mer.anio >= 'A003', k + ['marca_propia']], on=k, how='outer')
print('celdas que no cuadran:', (cruce.unidades != cruce.marca_propia).sum())

print('\n=== 4. Ecuación de stock: S_t = S_{t-1} + wholesale - ventas ===')
v_seg = ven.groupby(['fecha', 'segmento']).unidades.sum().rename('ventas')
s = sto.set_index(['fecha', 'segmento'])[['stock_total', 'wholesale']].join(v_seg)
s['s_prev'] = s.groupby(level='segmento').stock_total.shift()
s['desvio'] = s.stock_total - (s.s_prev + s.wholesale - s.ventas)
print(s.groupby(level='segmento').desvio.describe()[['count', 'mean', 'min', 'max']].round(1))

print('\n=== 5. Ventas anuales de Kaido por segmento ===')
anual = ven.pivot_table(index='anio', columns='segmento', values='unidades',
                        aggfunc='sum')[d.SEGMENTOS]
anual['TOTAL'] = anual.sum(axis=1)
print(anual)

print('\n=== 6. Mercado anual por segmento (miles) ===')
m_anual = mer.pivot_table(index='anio', columns='segmento', values='unidades',
                          aggfunc='sum')[d.SEGMENTOS] / 1000
m_anual['TOTAL'] = m_anual.sum(axis=1)
print(m_anual.round(1))

print('\n=== 7. Automatriculaciones y canal por año (% de ventas Kaido) ===')
a = ven.groupby('anio')[['unidades', 'u_automatriculacion']].sum()
a['pct_auto'] = a.u_automatriculacion / a.unidades
canal = ven.pivot_table(index='anio', columns='canal', values='unidades', aggfunc='sum')
print(a.join(canal.div(canal.sum(axis=1), axis=0)).round(3))

print('\n=== 8. Stock fin de año y cobertura (meses de venta) por segmento ===')
v_mes = v_seg.unstack()
st = sto.pivot_table(index='fecha', columns='segmento', values='stock_total')
cob = st / v_mes.rolling(12).mean().reindex(st.index)
dic = st.index.month == 12
print('stock dic:\n', st[dic][d.SEGMENTOS])
print('cobertura dic:\n', cob[dic][d.SEGMENTOS].round(2))

print('\n=== 9. Envejecimiento: % del stock con más de 90 días ===')
sv = sto.groupby('fecha')[['stock_total', 's_91_180', 's_mas_180']].sum()
sv['pct_90'] = (sv.s_91_180 + sv.s_mas_180) / sv.stock_total
print(sv.loc[sv.index.month.isin([1, 10, 12]), ['stock_total', 'pct_90']].round(3))

print('\n=== 10. Meses con cobertura muy baja (< 0,5 meses): posible falta de coches ===')
baja = cob.stack().rename('cobertura').reset_index()
baja = baja[baja.cobertura < 0.5]
print(baja.groupby('segmento').size().rename('meses').to_string())

print('\n=== 11. Sucesos marcados en macro ===')
suc = ['incentivo_publico', 'adelanto_compras', 'caida_tras_adelanto', 'subida_iva']
for c in suc:
    meses = mac.index[mac[c] == 1]
    print(f'{c:22s} {len(meses):3d} meses  ',
          ', '.join(f'A{m.year - 2000:03d}-{m.month:02d}' for m in meses[:12]),
          '...' if len(meses) > 12 else '')

print('\n=== 12. Renovaciones de gama ===')
ren = ven[ven.renovacion_gama == 1].drop_duplicates(['periodo', 'segmento'])
print(ren.groupby('segmento').periodo.apply(lambda p: ', '.join(p.str[:7])).to_string())

print('\n=== 13. Ficha económica por segmento (€/coche) ===')
print(seg.loc[d.SEGMENTOS, ['unidades_ult_anio', 'beneficio_bruto_marca_eur', 'prima_co2_eur',
                           'vm_tarifa_eur', 'vm_real_eur', 'cvp_tarifa_eur', 'cvp_real_eur',
                           'vm_real_0_90_eur', 'vm_real_mas_180_eur']])

print('\n=== 14. Nulos por fichero ===')
for nombre, df in [('ventas', ven), ('mercado', mer), ('stock', sto), ('macro', mac)]:
    n = df.isna().sum()
    print(nombre, dict(n[n > 0]))
