# Kaido Motors España: plan de ventas y producción de A013

Resolución del caso **Kaido Motors España: demanda, stock y beneficio**, de la asignatura **Simulación de Sistemas Logísticos** (Universidad Alfonso X el Sabio). Autores del caso: Jacinto Velasco y Javier Goikoetxea.

Kaido Motors España importa coches de una marca que fabrica fuera de Europa y los reparte entre 64 concesionarios. Lo que se decide producir hoy llega a la red tres meses después. El proyecto responde a las cinco preguntas del caso: cuál es la demanda real, cuánto se venderá en A013, qué pasa en un escenario pesimista o en uno optimista, cuántos coches hay que fabricar y cuánto cuesta equivocarse.

## Resultados principales

- **Demanda real.** Las ventas de A012 crecieron un 8,5 %, pero con la misma gama la demanda real **cayó un 2 %**. La diferencia se explica por las automatriculaciones, unos 1.100 coches de compras adelantadas a A013 y el lanzamiento del CSUV.
- **Previsión de A013.** En el escenario central se esperan **~18.200 coches**, un 8 % menos que la demanda real de A012. En el pesimista serían ~15.700 y en el optimista ~23.300.
- **Plan de producción.** Deben llegar a la red **~16.300 coches** con el plan central, menos de lo que se vende, para vaciar el exceso de stock. El stock medio queda en 1,4 meses de venta y los coches con más de 90 días desaparecen a fin de año.
- **Margen (CVP).** **+61 M€** en el central, **+88 M€** en el optimista y **−3 M€** en el pesimista. Lo que lleva el pesimista a pérdidas es sobre todo la posible prima de CO₂, no la producción.
- **Recomendación.** Empujar MSUV y CSUV; mantener SSUV, MD y S; frenar C y B. El stock de seguridad también va por segmento: alto donde quedarse corto cuesta 7–10 veces más que pasarse, y nulo en B.

El plan y sus resultados para el comité están en [entrega/](entrega/): el resumen ejecutivo y la presentación, en PDF.

## Estructura

```
SSL-Kaido-Motors/
├── src/
│   ├── datos.py                 # Carga común de los CSV y rutas del proyecto
│   ├── fase0_checks.py          # Comprobaciones de integridad de los datos
│   ├── fase1_demanda.py         # P1: demanda real (sin automatriculaciones, adelantos ni roturas)
│   ├── fase2_prevision.py       # P2: modelo mercado × cuota, validación con A012 y previsión de A013
│   ├── fase3_escenarios.py      # P3: escenarios pesimista, central y optimista (Tabla 4)
│   ├── fase4_simulacion.py      # P3–P4: simulación Monte Carlo del año, plan de llegadas y Tabla 5
│   └── fase5_coste_error.py     # P5: coste de equivocarse, stock de seguridad y señales
├── docs/
│   └── kaido-motors-case-study.pdf   # Enunciado (no está en el repositorio)
├── entrega/
│   ├── resumen_ejecutivo.pdf    # Resumen ejecutivo para el comité (Tabla 5)
│   └── Plan de ventas y producción A013.pdf   # Presentación para el comité
├── examples/
│   ├── annex4_demand_baseline.ipynb  # Ejemplo del Anexo 4 del enunciado
│   └── annex4_demand_baseline.py
├── data/                        # Datos del caso (no están en el repositorio)
├── resultados/                  # Salidas generadas por los scripts (no están en el repositorio)
└── requirements.txt
```

## Puesta en marcha

### 1. Datos y enunciado

> **En la entrega en ZIP, `data/`, el enunciado y `resultados/` ya están incluidos**: este paso solo hace falta al clonar el repositorio desde GitHub.

El repositorio **no incluye los datos ni el enunciado**: son material del curso y su uso es exclusivamente docente. Después de clonar, copia los ficheros del curso en estas rutas:

```
data/
├── ventas_mensual.csv
├── stock_mensual.csv
├── mercado_mensual.csv
├── segmentos.csv
├── codigos.csv
├── macro_mensual.csv
└── calendario_A013.csv
docs/kaido-motors-case-study.pdf
```

**No abras ni guardes los CSV con Excel.** Puede cambiar el separador y los decimales, y además convierte el código de modelo `NA` en una celda vacía.

### 2. Librerías

Necesitas Python 3.10 o superior.

```bash
pip install -r requirements.txt
```

Si prefieres aislar las librerías, crea antes un entorno virtual con `python -m venv .venv` y actívalo. En Windows se activa con `.venv\Scripts\activate`.

## Cómo ejecutarlo

Ejecuta los scripts desde la raíz del repositorio y en este orden, porque cada fase usa la salida de la anterior:

| Orden | Script | Pregunta | Salidas principales en `resultados/` |
|---|---|---|---|
| 0 | `python src/fase0_checks.py` | — | Comprobaciones por pantalla |
| 1 | `python src/fase1_demanda.py` | P1 | `demanda_real.csv`, `fase1_demanda.png` |
| 2 | `python src/fase2_prevision.py` | P2 | `prevision_A013_central.csv`, `validacion_A012.csv`, `fase2_prevision.png` |
| 3 | `python src/fase3_escenarios.py` | P3 | `escenarios_demanda.csv`, `fase3_escenarios.png` |
| 4 | `python src/fase4_simulacion.py` | P3–P4 | `plan_llegadas_central.csv`, `tabla5_total.csv`, `tabla5_segmentos.csv`, `fase4_simulacion.png` |
| 5 | `python src/fase5_coste_error.py` | P5 | `fase5_rejilla_z.csv`, `fase5_matriz_plan.csv`, `fase5_senales.csv`, `fase5_recomendacion.csv` |

La carpeta `resultados/` se crea sola al ejecutar los scripts. En el ZIP ya viene generada; volver a ejecutarlos da exactamente los mismos ficheros, porque la simulación usa una semilla fija.

## Notas sobre los datos

- **Años.** Los años reales del caso se han sustituido por códigos: A001 es el primero y A012 el último cerrado. A013 es el año que se planifica. Para las series temporales, A001 se trata como el año ficticio 2001, A002 como 2002, y así sucesivamente (Anexo 4). Los días laborables y la Semana Santa se toman de los datos, no de esas fechas ficticias.
- **Lectura de los CSV.** [src/datos.py](src/datos.py) los lee con `keep_default_na=False` para que el código de modelo `NA` no se interprete como un dato que falta.

## Uso

El caso está basado en uno real, con datos y nombres modificados. El enunciado y los datos son material docente de la asignatura y no se redistribuyen en este repositorio.
