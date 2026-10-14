"""
Carga de los datos del caso Kaido Motors.

Ejecutar siempre desde la raíz del repositorio o importar este módulo:
las rutas se resuelven respecto a la raíz, no al directorio actual.
"""
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / 'data'
RESULTADOS = RAIZ / 'resultados'

SEGMENTOS = ['MSUV', 'SSUV', 'C', 'B', 'CSUV', 'MD', 'S']
CANALES = ['PARTICULARES', 'EMPRESAS_RENTING', 'ALQUILADORES']


def leer(fichero):
    """Lee un CSV del caso. Solo las celdas vacías son nulos (el código de modelo 'NA' no)."""
    return pd.read_csv(DATOS / fichero, keep_default_na=False, na_values=[''])


def fecha(df):
    """A001 -> año ficticio 2001, A002 -> 2002, ... (Anexo 4)."""
    anio = 2000 + df['anio'].str[1:].astype(int)
    return pd.to_datetime(dict(year=anio, month=df['mes'], day=1))


def _con_fecha(df):
    df['fecha'] = fecha(df)
    return df


def ventas():
    return _con_fecha(leer('ventas_mensual.csv'))


def mercado():
    return _con_fecha(leer('mercado_mensual.csv'))


def stock():
    return _con_fecha(leer('stock_mensual.csv'))


def macro():
    return _con_fecha(leer('macro_mensual.csv')).set_index('fecha').asfreq('MS')


def calendario_A013():
    return _con_fecha(leer('calendario_A013.csv')).set_index('fecha').asfreq('MS')


def segmentos():
    return leer('segmentos.csv').set_index('segmento')


def codigos():
    return leer('codigos.csv')


def serie(df, segmento, col='unidades', canal=None):
    """Serie mensual (freq MS) de un segmento, sumando canales salvo que se indique uno."""
    d = df[df['segmento'] == segmento]
    if canal is not None:
        d = d[d['canal'] == canal]
    return d.groupby('fecha')[col].sum().asfreq('MS')
