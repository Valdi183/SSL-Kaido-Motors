# Apuntes: respuestas a las 5 preguntas del caso Kaido

> Documento de trabajo, en sucio. Se actualiza cada vez que se responde una pregunta.
> Última actualización: 2026-10-14 (las 5 preguntas respondidas).

**Cómo reproducir todo** (desde la raíz del repo, con el `.venv` activado y en este orden, porque cada fase usa la salida de la anterior):

```
python src/fase0_checks.py       # comprobaciones de datos
python src/fase1_demanda.py      # P1 -> resultados/demanda_real.csv
python src/fase2_prevision.py    # P2 -> resultados/prevision_*.csv
python src/fase3_escenarios.py   # P3 -> resultados/escenarios_demanda.csv
python src/fase4_simulacion.py   # P4 -> resultados/plan_llegadas_central.csv, tabla5_*.csv
python src/fase5_coste_error.py  # P5 -> resultados/fase5_*.csv
```

Las salidas van a `resultados/`, que está en `.gitignore` porque se regenera con el código.

**Estado**

| # | Pregunta | Estado | Script |
|---|---|---|---|
| 1 | ¿Cuál es la demanda real? | ✅ Respondida | [fase1_demanda.py](../src/fase1_demanda.py) |
| 2 | ¿Cuánto vamos a vender en A013? | ✅ Respondida (escenario central) | [fase2_prevision.py](../src/fase2_prevision.py) |
| 3 | ¿Qué pasa si el año sale mejor o peor? | ✅ Respondida | [fase3_escenarios.py](../src/fase3_escenarios.py) + [fase4_simulacion.py](../src/fase4_simulacion.py) |
| 4 | ¿Cuántos coches fabricamos y cuánto stock? | ✅ Respondida | [fase4_simulacion.py](../src/fase4_simulacion.py) |
| 5 | ¿Cuánto cuesta equivocarse y qué recomendamos? | ✅ Respondida | [fase5_coste_error.py](../src/fase5_coste_error.py) |

---

## 0. Comprobaciones de los datos (antes de responder)

**Conclusión:** los datos son íntegros. No hay que arreglar nada técnico.

| Comprobación | Resultado | Dónde |
|---|---|---|
| Ventas Kaido A003–A012 = 125.030 (Anexo 5) | ✅ Igual en ventas, mercado, segmentos y códigos | [fase0_checks.py](../src/fase0_checks.py), sección 2 |
| `ventas_mensual` = `mercado.marca_propia` | ✅ 0 celdas distintas | sección 3 |
| Stock_t = Stock_{t−1} + wholesale − ventas | ✅ Desvíos de pocos coches (SSUV hasta ±50) | sección 4 |
| % del stock con más de 90 días | 20 % en enero de A012 → 35 % en diciembre (cuadra con el PDF) | sección 9 |

**Rarezas detectadas:**
- **SSUV y S acaban A012 con stock 0 y 1.** Hubo rotura y en diciembre se vendió lo que había. El SSUV facturó solo 2 coches en diciembre, probablemente por un cambio de código.
- **C acaba con 1.107 coches (3,2 meses de cobertura).** Es el segmento con más exceso.
- **CSUV tiene 1.011 coches para unas ~400 ventas al mes.**
- Carga de datos común: [datos.py](../src/datos.py). Lee con `keep_default_na=False` para que el código de modelo `NA` no se convierta en nulo.

---

## Pregunta 1: ¿Cuál es la demanda real de Kaido?

### Respuesta corta
**Con la misma gama, la demanda de Kaido cayó un 2 % en A012.** El +8,5 % que se reportó se explica así:
- **unos 800 coches de automatriculaciones**;
- **unos 1.100 coches de compras adelantadas** de A013 a noviembre y diciembre;
- **el lanzamiento del CSUV**, que es el único crecimiento real.

| | A011 | A012 | Crecimiento |
|---|---|---|---|
| Coches vendidos (lo reportado) | 21.362 | 23.175 | **+8,5 %** |
| Sin automatriculaciones (retail) | 19.543 | 20.706 | +6,0 % |
| **Demanda real** | 18.904 | 19.709 | **+4,3 %** |
| **Demanda real sin CSUV** (misma gama) | 18.904 | 18.517 | **−2,0 %** |
| Mercado de los 7 segmentos | 934.224 | 902.437 | −3,4 % |

### Qué es la "demanda real"
Lo que los clientes quisieron comprar en ese periodo. Es distinto de lo vendido por tres motivos:
1. **Automatriculaciones**: las matricula el concesionario o la marca a su nombre para cumplir objetivos. Cuentan como venta pero no hay cliente (Tabla 1 del PDF). Se restan.
2. **Compras adelantadas**: clientes de A013 que compraron en noviembre y diciembre de A012. Se quita el exceso.
3. **Falta de coches**: si no había stock, la venta fue menor que la demanda. Se rellena.

Por qué importa: si el modelo aprende de las ventas brutas, prevé demanda fantasma, se fabrica de más y se repite el problema de A012.

### Cómo se calculó (método)
Todo está en [fase1_demanda.py](../src/fase1_demanda.py):
- **Retail** = `unidades − u_automatriculacion`.
- **Demanda "normal" esperada** = nivel desestacionalizado de los meses normales vecinos × factor estacional.
  - Función `esperado()`, [línea 71](../src/fase1_demanda.py#L71): 3 meses antes y 3 después si los hay; si no, los 6 anteriores.
  - Factores estacionales del **mercado** del segmento: `factores_estacionales()`, [línea 60](../src/fase1_demanda.py#L60).
- **Reglas** ([línea 103](../src/fase1_demanda.py#L103)):
  - Adelanto o subida del IVA → `min(vendido, esperado)`.
  - Caída tras el adelanto → `max(vendido, esperado)`.
  - Rotura de stock → `max(vendido, esperado)`. Se considera rotura cuando el stock a fin de mes es menor que el 15 % de la venta media mensual ([línea 90](../src/fase1_demanda.py#L90)). Solo se detecta desde A009.
- **CSUV**: no se corrige ([línea 115](../src/fase1_demanda.py#L115)). Su mercado no muestra adelanto (×0,95 y ×0,87) y está en rampa.

### Datos que la respaldan
- **Coches adelantados en noviembre y diciembre de A012:** MSUV 600, C 341, SSUV 86, B 70, S 11. **Total: 1.108.**
- **Demanda no servida por rotura en diciembre de A012:** SSUV 111.
- **Mercado en el adelanto de A011:**
  - agosto: +41 % sobre lo normal;
  - después, 4 meses de caída: −19 %, −11 %, −4 % y −9 %, **una media de −11 %**. Se usa en la P3.
- **Por segmento, demanda A012 frente a A011:** MSUV −15 %, MD −40 %, SSUV +17 %, S +11 %, C +8 %, B +7 %.

**Ficheros:** `resultados/demanda_real.csv` (entrada de la P2) y `resultados/fase1_demanda.png`.

### Limitaciones
- En MSUV y C las ventas ya suben en septiembre y octubre. El adelanto pudo empezar antes, pero solo se corrige lo marcado (conservador).
- Antes de A009 no se pueden detectar roturas.
- El umbral de rotura (15 %) y la ventana de 6 meses son criterios propios.

---

## Pregunta 2: ¿Cuánto vamos a vender en A013?

### Respuesta corta (escenario central)
**Demanda de Kaido en A013: unos 18.600 coches (−5,6 % sobre la demanda real de A012).**
- El mercado de sus segmentos cae alrededor de un 20 %.
- El CSUV amortigua la caída porque pasa de 5 meses de ventas a un año completo.
- **Sin el CSUV, Kaido caería un ~18 %.**

(En la P3 el central queda en ~18.200 porque la caída tras el adelanto se calibra de otra forma; ver la P3.)

| Segmento | Demanda A012 | Previsión A013 | Variación | Mercado A013 | Cuota usada | σ mensual (coches) |
|---|---|---|---|---|---|---|
| MSUV | 6.881 | 5.050 | −27 % | −23 % | 4,1 % | 103 |
| SSUV | 5.660 | 4.400 | −22 % | −23 % | 3,8 % | 54 |
| C | 3.355 | 3.192 | −5 % | −21 % | 2,4 % | 87 |
| B | 1.553 | 1.583 | +2 % | −17 % | 0,8 % | 43 |
| CSUV | 1.192 (5 meses) | 3.526 | — | −18 % | 2,5 % | 72 |
| MD | 591 | 364 | −38 % | −30 % | 2,5 % | 8 |
| S | 477 | 486 | +2 % | — | — | 12 |
| **Total** | **19.709** | **18.601** | **−5,6 %** | | | |

### Cómo se calculó (método)
Todo está en [fase2_prevision.py](../src/fase2_prevision.py). **Demanda Kaido = mercado del segmento × cuota de Kaido** (PDF 5.2).

**Modelo de mercado** (`ajustar_mercado()`, [línea 88](../src/fase2_prevision.py#L88)):
- Regresión sobre log(unidades) con errores SARIMA(0,0,0)(0,1,1)12: *"cada mes se parece al mismo mes del año anterior, suavizado"*.
- Variables:
  - **confianza del consumidor con 3 meses de retraso** ([líneas 46–47](../src/fase2_prevision.py#L46));
  - calendario: días laborables y Semana Santa;
  - sucesos: adelanto, caída, IVA y plan de ayuda;
  - **tendencia de declive solo en C, B y MD** ([línea 48](../src/fase2_prevision.py#L48)).

**Cuota** (`cuota_reciente()`, [línea 99](../src/fase2_prevision.py#L99)):
- Media de los últimos 6 meses sin sucesos.
- CSUV: media de los 3 últimos meses (en rampa; por analogía con el SSUV en A008, que se estabilizó en ~3 meses).

**S:** se prevé la demanda de Kaido directamente (`prever_nivel_estacional()`, [línea 110](../src/fase2_prevision.py#L110)).

**Supuestos del escenario central** (`exog_A013()`, [línea 71](../src/fase2_prevision.py#L71)):
- Confianza en **77,7** desde abril (enero–marzo ya se conocen).
- Caída tras el adelanto: 3 meses.
- Sin planes de ayuda ni subidas del IVA.

### Por qué este modelo y no el del Anexo 4
Se probaron 9 variantes entrenando hasta A011 y previendo el mercado de A012:

| Modelo | Error del mercado A012 (MSUV / SSUV / C / B / CSUV / MD) |
|---|---|
| Anexo 4 (AR(1) + paro + confianza) | +16 / +4 / +44 / +23 / +44 / +78 % |
| Elegido (sin AR + confianza, tendencia en C/B/MD) | −3 / −11 / +12 / +7 / −4 / +16 % |
| Repetir A011 ("naive") | −7 / −10 / +17 / +13 / −5 / +40 % |

Los experimentos se hicieron en scripts temporales que no están en el repo. Se pueden rehacer en un notebook si hace falta.

### Validación (entrenado hasta A011, previsión de la demanda limpia de A012)

| Segmento | Real A012 | Previsto | Error anual | MAPE mensual | MAPE de repetir A011 |
|---|---|---|---|---|---|
| MSUV | 6.881 | 7.479 | +9 % | 18 % | 20 % |
| SSUV | 5.660 | 3.534 | −38 % | 39 % | 20 % |
| C | 3.355 | 2.883 | −14 % | 48 % | 62 % |
| B | 1.553 | 1.042 | −33 % | 29 % | 19 % |
| MD | 591 | 741 | +25 % | 37 % | 76 % |
| S | 477 | 436 | −9 % | 23 % | 23 % |
| **Total (sin CSUV)** | **18.517** | **16.114** | **−13 %** | **17 %** | |

- El modelo de **mercado** funciona razonablemente; el error grande viene de la **cuota**.
- Previó A012 un 13 % por debajo, así que puede ser algo pesimista.

### Error de previsión (entrada para las P3 y P4)
- **σ** = error típico mensual de la validación, en % del nivel previsto de A013 ([líneas 180–183](../src/fase2_prevision.py#L180)). Va del 15 al 33 %.
- **Autocorrelación del error: 0,2–0,7.** Se usa en la simulación.

**Ficheros:** `resultados/prevision_A013_central.csv`, `prevision_resumen.csv`, `validacion_A012.csv` y `fase2_prevision.png`.

### Limitaciones
- **El supuesto que más pesa:** que la confianza se quede en 77, un nivel de crisis. → La P3 lo acota.
- La cuota no modela los 7 códigos nuevos; su efecto entra por los escenarios.
- La cuota del MSUV bajó del 6 % al 4 % en A012 y se asume que sigue en el 4,1 %.
- El CSUV solo tiene 5 meses de historia.

---

## Pregunta 3: ¿Qué pasa si el año sale mejor o peor?

### Respuesta corta
**Demanda de Kaido en A013:**
- **Pesimista: ~15.700 coches** (−20 % sobre A012);
- **Central: ~18.200** (−8 %);
- **Optimista: ~23.300** (+18 %).

Con el error de previsión, el rango P10–P90 es **14.800–16.800**, **17.100–19.400** y **21.900–24.900** respectivamente.

**Lo que más cambia es el margen, no las ventas:**
- **Pesimista:** el CVP del año se hunde a **−3,0 M€**. La prima de CO₂ y el arancel se comen el beneficio de todos los segmentos menos MSUV, CSUV y MD.
- **Central:** **+61,3 M€**.
- **Optimista:** **+88,4 M€**.

| Demanda A013 (coches) | Pesimista | Central | Optimista | Demanda A012 |
|---|---|---|---|---|
| MSUV | 4.233 | 5.066 | 6.825 | 6.881 |
| SSUV | 3.558 | 4.218 | 5.554 | 5.660 |
| C | 2.817 | 3.162 | 3.824 | 3.355 |
| B | 1.321 | 1.512 | 2.117 | 1.553 |
| CSUV | 2.990 | 3.389 | 4.117 | 1.192 |
| MD | 334 | 381 | 406 | 591 |
| S | 455 | 470 | 483 | 477 |
| **Total** | **15.708** | **18.198** | **23.325** | **19.709** |

### Cómo se tradujo la Tabla 4 a números
Todo en [fase3_escenarios.py](../src/fase3_escenarios.py), diccionario `PARAMETROS` ([línea 53](../src/fase3_escenarios.py#L53)). Cada valor se justifica con un episodio de los datos, como pide el PDF (9.2):

| Suceso (Tabla 4) | Pesimista | Central | Optimista | Justificación | Entra por |
|---|---|---|---|---|---|
| Economía | Confianza 65,7 (−12) desde abril | 77,7 | 87,7 (+10) | Paro +2 puntos ≈ −12 de confianza: en A004→A005 el paro subió 3,4 puntos y la confianza cayó 21 (~6 por punto). Optimista: paro −1 (+6) y crédito más barato (+4) = media de A012 | Modelo de mercado (P2) |
| Caída tras el adelanto | 6 meses | 3 meses | 1 mes | El mercado cayó un **11 %** de media tras el adelanto de A011 (P1) → multiplicador ×0,89 ([línea 51](../src/fase3_escenarios.py#L51)) | Demanda |
| Plan de ayuda | — | — | De abril a diciembre | El modelo estima +3 % a +22 % según el segmento | Modelo de mercado |
| Producto | Los códigos nuevos del MSUV se retrasan 3 meses → cuota ×0,85 de abril a junio | A tiempo | Los códigos nuevos venden más → cuota ×1,10 desde abril (MSUV, SSUV, B, CSUV) | Supuesto propio (no hay historia de los códigos nuevos) | Cuota |
| Turismo | Alquiladores −30 % (marzo–junio) | Igual que A012 | +30 % | Pesan poco en Kaido: B 13 %, S y SSUV 4 %, MSUV 1,5 %, resto ~0 | Demanda |
| Geopolítica | Arancel +5 % sobre el coste del coche | — | Euro fuerte y combustible barato: coste −3 % | Supuesto propio | Beneficio por coche |
| Normativa CO₂ | La matriz carga la prima (1.900–4.500 €/coche) | No | No | `segmentos.csv`, columna `prima_co2_eur` | Beneficio por coche |
| Suministro | Se pierde un mes de producción del MSUV (llegadas de junio = 0) | Sin problemas | Coches de sobra: todo faltante se cubre con transfer | Supuesto propio | Llegadas |

**Por qué la caída se calibra y no se usa el modelo:** el efecto de `caida_tras_adelanto` del modelo se estima con un solo episodio (A011) y sale con el signo cambiado en SSUV, B y CSUV. El −11 % medido en el mercado es más fiable. Por eso el central de la P3 (18.198) es algo menor que el de la P2 (18.601).

### Datos que la respaldan
- Demanda por escenario y mes: `resultados/escenarios_demanda.csv`. Gráfico: `resultados/fase3_escenarios.png`.
- Ventas, stock, costes y margen con su banda P10–P90: `resultados/tabla5_total.csv`, `tabla5_total_bandas.csv` y `tabla5_segmentos.csv` (salen de la P4).

### Limitaciones
- **El pesimista es un escenario de estrés:** acumula todos los sucesos a la vez (economía, CO₂, arancel, retraso y suministro).
- El tamaño del retraso de producto (×0,85) y del éxito de los códigos nuevos (×1,10) es un supuesto, sin datos que lo respalden.
- El combustible no está en el modelo; se ha metido dentro de la confianza y del coste.

---

## Pregunta 4: ¿Cuántos coches fabricamos y cuánto stock queremos?

### Respuesta corta
**Que lleguen a la red unos 16.300 coches en A013 con el plan central, frente a una demanda de ~18.200.** Se fabrica menos de lo que se vende para vaciar el exceso actual. Hay que empezar casi sin pedir nada:
- **en marzo solo ~400 coches;**
- **C no pide nada hasta julio y CSUV hasta junio**, porque tienen mucho stock y lo que ya viene en camino.

**El stock medio queda en 1,4 meses de venta (~2.100 coches)** y **cierra el año en unos 1.140 coches**, frente a los 2.877 de A012. A fin de año casi no quedan coches con más de 90 días: unos 7, frente a ~1.000 (35 %) en diciembre de A012.

**El stock de seguridad no es igual en todos los segmentos** (detalle en la P5):
- **z = 2,05** en MSUV, SSUV, CSUV, MD y S (cubre ~98 de cada 100 meses);
- **z = 0,84** en C;
- **z = 0** en B.

**Plan de llegadas a la red, escenario central** (`resultados/plan_llegadas_central.csv`). Enero y febrero ya vienen en camino; desde marzo es lo que se pide a la fábrica 3 meses antes:

| Mes | MSUV | SSUV | C | B | CSUV | MD | S | Total |
|---|---|---|---|---|---|---|---|---|
| Ene (en camino) | 576 | 467 | 454 | 124 | 489 | 50 | 34 | 2.195 |
| Feb (en camino) | 576 | 467 | 454 | 124 | 489 | 50 | 34 | 2.195 |
| Mar | 0 | 286 | 0 | 34 | 0 | 0 | 81 | 401 |
| Abr | 258 | 459 | 0 | 159 | 0 | 0 | 37 | 914 |
| May | 488 | 368 | 0 | 145 | 0 | 0 | 39 | 1.039 |
| Jun | 557 | 575 | 0 | 185 | 203 | 4 | 48 | 1.572 |
| Jul | 494 | 415 | 168 | 147 | 315 | 38 | 51 | 1.628 |
| Ago | 318 | 248 | 190 | 95 | 223 | 22 | 37 | 1.132 |
| Sep | 369 | 285 | 209 | 89 | 223 | 28 | 32 | 1.235 |
| Oct | 454 | 289 | 214 | 98 | 250 | 30 | 42 | 1.376 |
| Nov | 364 | 249 | 222 | 99 | 217 | 30 | 31 | 1.211 |
| Dic | 443 | 304 | 269 | 116 | 225 | 33 | 26 | 1.417 |
| **Total** | **4.897** | **4.412** | **2.180** | **1.415** | **2.634** | **285** | **492** | **16.315** |

### Tabla 5 (total; media de 1.000 réplicas; plan central con z por segmento)

| | Pesimista | Central | Optimista |
|---|---|---|---|
| Demanda (coches) | 15.752 | 18.250 | 23.391 |
| Coches vendidos (incluye transfers) | 15.212 | 17.826 | 23.391 |
| Coches que llegan a la red | 13.455 | 15.912 | 19.947 |
| Stock medio en la red | 2.198 coches (1,7 meses) | 2.088 (1,4 meses) | 1.835 (1,0 meses) |
| Stock a fin de año | 1.120 | 1.139 | 1.226 |
| Coches con más de 90 días a fin de año | 13 | 7 | 5 |
| Coste del stock para la marca | 1,98 M€ | 2,00 M€ | 1,95 M€ |
| Transfers | 0 | 176 | 1.793 |
| Ventas perdidas | 539 coches (0,2 M€) | 423 (0,7 M€) | 0 |
| Gasto comercial (VM) | 33,3 M€ | 38,6 M€ | 49,6 M€ |
| **Margen de la marca (CVP)** | **−3,0 M€** | **61,3 M€** | **88,4 M€** |
| CVP − coste del stock | −5,0 M€ | 59,3 M€ | 86,5 M€ |

- Las bandas P10–P90 están en `resultados/tabla5_total_bandas.csv`.
- Las ventas perdidas del central son, en su mayoría, de B (~250 coches). Se pierden a propósito, porque B no deja dinero (z = 0).
- **Comprobación:** el CVP central sale a ~3.440 €/coche, en línea con los ~3.450 € reales de A011–A012 (PDF sección 1). El VM, a ~2.160 €/coche, frente a los 2.081 € de media histórica (Anexo 3).

**Tabla 5 por segmento, escenario central** (`resultados/tabla5_segmentos.csv`):

| | MSUV | SSUV | C | B | CSUV | MD | S |
|---|---|---|---|---|---|---|---|
| Vendidos | 5.024 | 4.183 | 3.137 | 1.270 | 3.379 | 377 | 456 |
| Llegan a la red | 4.825 | 4.352 | 2.145 | 1.208 | 2.620 | 280 | 484 |
| Stock medio (meses) | 1,2 | 0,6 | 2,5 | 0,4 | 2,1 | 2,3 | 1,0 |
| CVP (M€) | 29,4 | 11,9 | 3,4 | 0,2 | 12,6 | 1,4 | 2,2 |
| CVP pesimista (M€) | 3,7 | −2,0 | −4,5 | −3,4 | 2,9 | 0,3 | −0,1 |

### Cómo se calculó (método)
Todo en [fase4_simulacion.py](../src/fase4_simulacion.py), función `simular_segmento()` ([línea 113](../src/fase4_simulacion.py#L113)). Sigue las secciones 7 y 9.3 del PDF, mes a mes y segmento a segmento:
1. **Llegan** los coches pedidos 3 meses antes.
2. **Demanda real** = demanda del escenario × error al azar. El error es lognormal con autocorrelación AR(1) (σ y ρ de la P2) ([línea 103](../src/fase4_simulacion.py#L103)).
3. **Se vende** `V = min(D, stock + llegadas)`, primero los más viejos (FIFO, [línea 163](../src/fase4_simulacion.py#L163)). Lo que falta va a transfer o se pierde.
4. **Al cerrar el mes**, la planificadora revisa su previsión: previsión central × lo que se desvió la demanda en los 3 últimos meses. Después pide la llegada de t+3 con la fórmula del PDF ([línea 146](../src/fase4_simulacion.py#L146)):
   - `Ŝ(t+2) = S_t + L(t+1) + L(t+2) − D̂(t+1) − D̂(t+2)` (sin bajar de 0);
   - `L(t+3) = max(0, D̂(t+3) + SS − Ŝ(t+2))`, con `SS = z·σ·√3` y z por segmento ([línea 58](../src/fase4_simulacion.py#L58)).
5. Se repite **1.000 veces por escenario**. El plan sale siempre del central; en el pesimista y el optimista la demanda real es otra y solo se corrige a 3 meses vista (PDF 7.6).

**Costes** (PDF 2.3–2.5 y 7.5; datos de `segmentos.csv`):
- **Stock:** 60 €/mes por coche con menos de 180 días. Los coches vendidos pagan medio mes.
- **VM según la edad al venderse:** `vm_real_0_90`, `91_180` y `mas_180` (el CSUV no tiene dato de más de 180 días; se usa el de 91–180).
- **CVP por coche** = beneficio bruto − VM (− prima de CO₂ y arancel si el escenario los carga).
- **Transfer:** deja el 80 % del beneficio bruto. **Solo se hace si deja dinero** ([línea 134](../src/fase4_simulacion.py#L134)).
- **Venta perdida:** el CVP que no se gana.

### Supuestos propios (importantes para defender)
| Supuesto | Valor | Dónde |
|---|---|---|
| **Lo que ya viene en camino** (enero y febrero) | Facturación media a la red de julio–diciembre de A012, sin meses anómalos (diciembre en SSUV) → **2.195 coches/mes** | [línea 78](../src/fase4_simulacion.py#L78) |
| Edad del stock de diciembre | 0–90 días → meses 0–2; 91–180 → 3–5; más de 180 → mes 7 | `stock_inicial()`, [línea 95](../src/fase4_simulacion.py#L95) |
| Faltantes cubiertos con transfer | 50 % (100 % en el optimista) | [línea 63](../src/fase4_simulacion.py#L63) |
| Stock de seguridad | z por segmento (P5) | [línea 58](../src/fase4_simulacion.py#L58) |
| La planificadora ve la demanda real | Incluye los pedidos que no se pudieron servir | `simular_segmento` |

### Lecturas para el comité
- **Lo que viene en camino pesa muchísimo.** En enero y febrero llegan ~4.400 coches para una demanda de ~2.400 (con la caída del adelanto). **El stock sube a ~4.700 coches en febrero** (gráfico `resultados/fase4_simulacion.png`). Es la lección del PDF (7.4): el ajuste lo sufre el primer mes que todavía se puede tocar.
- **C y CSUV son los segmentos con exceso:** no hay que pedir nada hasta el verano. C tiene el stock medio más alto (2,5 meses).
- **SSUV va justo:** arranca A013 sin stock y con 0,6 meses de cobertura media, aun con z = 2,05.
- **El plan central aguanta bien en el pesimista en cuanto a stock** (1,7 meses y 13 coches viejos). El problema del pesimista es el margen (CO₂), no el stock.
- **En el optimista faltan unos 1.800 coches**, que se cubren con transfer.

### Limitaciones
- **El supuesto de lo que viene en camino es el más sensible**: si fuera menor, el exceso de los primeros meses también.
- La revisión de la previsión es sencilla (un factor de los últimos 3 meses).
- No se modelan las automatriculaciones como palanca para vaciar stock.
- No se cuenta el coste para el concesionario (intereses), solo el de la marca.
- El stock que queda a fin de año no se penaliza en el resultado: el modelo no ve lo que costará venderlo en A014.

---

## Pregunta 5: ¿Cuánto cuesta equivocarse y qué recomendamos?

### Respuesta corta
1. **Quedarse corto cuesta entre 5 y 10 veces más que pasarse** en los segmentos de margen alto. Un coche de más en MSUV cuesta ~375 € (3 meses de stock más el VM extra por envejecer); uno de menos, ~3.700 € (mitad transfer, mitad venta perdida). → **Más colchón de stock en MSUV, SSUV, CSUV, MD y S; poco en C; ninguno en B.**
2. **Equivocarse de escenario al planificar cuesta poco: como mucho 1,5 M€, frente a un margen de ~60 M€.** La revisión mensual corrige el plan en 3 meses. Lo que de verdad mueve el resultado es el escenario en sí, sobre todo la prima de CO₂: de +59 M€ en el central a −5 M€ en el pesimista.
3. **Recomendación por segmento:**
   - **empujar MSUV y CSUV**;
   - **mantener SSUV, MD y S**;
   - **frenar C y B**.
4. **Señal para cambiar la producción:** si la demanda de 3 meses queda **por debajo del 90 % del plan**, se pasa al plan pesimista; si queda **por encima del 110 %**, al optimista. Se distingue con fiabilidad **a partir de abril o mayo**. Antes, vigilar la **confianza del consumidor**, que se adelanta 3 meses, y la **decisión de la matriz sobre el CO₂**.

### A. Coste de un coche de más y de uno de menos
Código: `costes_unitarios()` en [fase5_coste_error.py](../src/fase5_coste_error.py#L37).
- **Co (pasarse)** = 3 meses de stock (180 €), lo que se tarda en corregir, más el VM extra si pasa de 90 días.
- **Cu (quedarse corto)** = 50 % transfer (20 % del beneficio bruto) + 50 % venta perdida (CVP). Vale 0 si el coche no deja dinero.
- **Ratio crítico** = Cu / (Cu + Co): el % de meses que conviene cubrir. De él sale el **z teórico**.

| Segmento | CVP/coche | Co (pasarse) | Cu (corto) | Cu/Co | Ratio crítico | z teórico | z en la simulación |
|---|---|---|---|---|---|---|---|
| MSUV | 5.887 € | 375 € | 3.722 € | ×9,9 | 0,91 | 1,33 | 2,05 |
| SSUV | 2.857 € | 228 € | 1.912 € | ×8,4 | 0,89 | 1,25 | 2,05 |
| C | 1.367 € | 447 € | 1.051 € | ×2,4 | 0,70 | 0,53 | 0,84 |
| B | 125 € | 208 € | 125 € | ×0,6 | 0,38 | 0 | 0 |
| CSUV | 3.804 € | 280 € | 2.519 € | ×9,0 | 0,90 | 1,28 | 2,05 |
| MD | 4.044 € | 364 € | 2.778 € | ×7,6 | 0,88 | 1,20 | 2,05 |
| S | 4.954 € | 436 € | 3.161 € | ×7,3 | 0,88 | 1,17 | 2,05 |

**Ojo:** el CVP por coche de esta tabla usa el VM de un coche de menos de 90 días (el caso ideal), por eso es algo mayor que el CVP real de A012.

### B. Stock de seguridad óptimo por segmento (simulación)
- Se probó z ∈ {0; 0,5; 0,84; 1,28; 1,65; 2,05; 2,33} en cada segmento.
- Se eligió el que da más resultado esperado (CVP − coste del stock), ponderando pesimista 25 %, central 50 % y optimista 25 % ([línea 32](../src/fase5_coste_error.py#L32)).
- Datos: `resultados/fase5_rejilla_z.csv`.
- **Resultado:**
  - la simulación pide **más colchón que la teoría** en los segmentos de margen alto (2,05 frente a ~1,25), porque los errores de meses seguidos se parecen (autocorrelación). Es lo que avisa el PDF en 7.3;
  - **la curva es muy plana:** pasar de z = 1,28 a la z óptima gana solo **~0,5 M€** en total (+1 %);
  - **B gana dejando de cubrir** (+0,12 M€): pierde ~250 ventas, pero cada una casi no deja dinero.
- Se eligió **2,05 y no 2,33** (el máximo de la rejilla) porque de 2,05 a 2,33 se gana menos de 0,1 M€ y aumenta el stock a fin de año, que el modelo no penaliza.

| Segmento | z recomendado | Resultado esperado con z = 1,28 | Con z recomendado | Ventas perdidas central (antes → después) |
|---|---|---|---|---|
| MSUV | 2,05 | 25,51 M€ | 25,75 M€ | 106 → ~54 |
| SSUV | 2,05 | 9,52 | 9,57 | 60 → ~28 |
| C | 0,84 | 1,58 | 1,59 | 45 → ~60 |
| B | 0 | −0,78 | −0,65 | 84 → ~250 |
| CSUV | 2,05 | 10,84 | 10,89 | 43 → ~17 |
| MD | 2,05 | 1,18 | 1,19 | 6 → ~3 |
| S | 2,05 | 1,68 | 1,69 | 20 → ~14 |

### C. Coste de planificar con el escenario equivocado
Matriz plan × realidad: se fabrica con un plan y pasa otro escenario. Resultado = CVP − coste del stock, en M€ (`resultados/fase5_matriz_plan.csv`).

| Plan \ Realidad | Pesimista | Central | Optimista |
|---|---|---|---|
| Plan pesimista | **−4,7** | 58,5 | 85,5 |
| Plan central | −5,0 | **59,3** | 86,6 |
| Plan optimista | −5,6 | 59,3 | **87,1** |

**Coste de haberse equivocado** (frente a acertar el escenario):

| Plan \ Realidad | Pesimista | Central | Optimista |
|---|---|---|---|
| Plan pesimista (quedarse corto) | 0 | −0,85 | **−1,53** |
| Plan central | −0,27 | 0 | −0,46 |
| Plan optimista (pasarse) | −0,82 | −0,04 | 0 |

**Lectura:**
- **El plan central es el más robusto:** como mucho se pierden 0,46 M€.
- **Quedarse corto es más caro que pasarse:** planificar pesimista y que salga bien cuesta hasta 1,5 M€; planificar optimista y que salga mal, 0,8 M€.
- **El coste de equivocarse es pequeño** (< 3 % del margen) porque la revisión mensual corrige a 3 meses. Sin revisar el plan sería mucho mayor (no se ha simulado; posible pregunta).
- **Lo que de verdad cuesta es el escenario:** el mismo plan pasa de +59 a −5 M€ si la matriz carga la prima de CO₂ y la economía empeora. Eso no lo arregla la producción. Hace falta precio, mezcla de segmentos y gasto comercial.

### D. Señales que vigilar y cuándo cambiar la producción
Ratio = demanda real de los 3 últimos meses / plan central, total Kaido (`resultados/fase5_senales.csv`):

| Mes | Pesimista: mediana (P10–P90) | Central | Optimista | % de veces que salta la alarma "< 0,90" si es pesimista / si es central | % de veces que salta "> 1,10" si es optimista / si es central |
|---|---|---|---|---|---|
| Ene | 0,99 (0,87–1,15) | 0,99 | 0,99 | 18 % / 18 % | 18 % / 18 % |
| Feb | 0,99 | 0,99 | 1,06 | 13 % / 13 % | 36 % / 14 % |
| Mar | 0,99 | 1,00 | 1,09 | 11 % / 11 % | 45 % / 12 % |
| **Abr** | **0,90** | 1,00 | **1,20** | **51 %** / 10 % | **87 %** / 14 % |
| **May** | **0,82** | 1,00 | **1,27** | **86 %** / 10 % | **97 %** / 13 % |
| Jun | 0,74 | 1,00 | 1,35 | 99 % / 9 % | 100 % / 12 % |

**Lectura:**
- **De enero a marzo no se distinguen los escenarios por las ventas**, porque la demanda de esos meses ya está "decidida": la confianza con retraso es conocida y la caída tras el adelanto afecta a los tres.
- **A partir de abril o mayo la señal es clara**, con un ~10 % de falsas alarmas.
- **Regla propuesta:** si la demanda de 3 meses queda < 90 % del plan durante 2 meses seguidos, se pasa al plan pesimista; si queda > 110 %, al optimista.

**Señales adelantadas** (antes de que se vea en las ventas):
- **Confianza del consumidor:** se adelanta ~3 meses al mercado (es la variable del modelo).
- **Decisión de la matriz sobre la prima de CO₂:** es el suceso que más mueve el margen.
- **Fechas de lanzamiento de los 7 códigos nuevos**, sobre todo los 2 del MSUV.
- **Stock y antigüedad por segmento:** cobertura de más de 2 meses o más del 20 % del stock con más de 90 días → frenar pedidos y no esperar a dar descuentos.
- **Cobertura del SSUV:** es el que va más justo (0,6 meses).

### E. Recomendación por segmento
Datos: `resultados/fase5_recomendacion.csv`.

| Segmento | CVP/coche central | CVP/coche con CO₂ | Mercado A013 | Stock dic A012 (meses) | CVP anual central | Recomendación |
|---|---|---|---|---|---|---|
| **MSUV** | 5.887 € | 1.684 € | −23 % | 1,3 | 29,4 M€ | **Empujar.** La mitad del margen de Kaido; aguanta la prima de CO₂. Colchón alto (z = 2,05). Vigilar el lanzamiento de los 2 códigos nuevos |
| **CSUV** | 3.804 € | 1.892 € | −18 % | 3,6 | 12,6 M€ | **Empujar las ventas, no la producción.** Buen margen y aguanta el CO₂, pero hay mucho stock: no pedir hasta junio |
| **SSUV** | 2.857 € | 27 € | −23 % | 0,0 | 11,9 M€ | **Mantener.** Rentable, pero con la prima de CO₂ queda a cero. Va justo de stock |
| **MD** | 4.044 € | 1.962 € | −30 % | 3,9 | 1,4 M€ | **Mantener poco volumen.** Cada coche deja dinero, pero el mercado se hunde; no sobredimensionar |
| **S** | 4.954 € | 461 € | — | 0,0 | 2,2 M€ | **Mantener.** Nicho estable y rentable, muy expuesto al CO₂ (prima de 4.493 €) |
| **C** | 1.367 € | −585 € | −21 % | 4,2 | 3,4 M€ | **Frenar.** Poco margen, mucho stock y pierde dinero con CO₂. Menos colchón (z = 0,84) y menos gasto comercial |
| **B** | 125 € | −2.430 € | −17 % | 0,8 | 0,2 M€ | **Frenar al mínimo.** No deja dinero ni en el central (CVP real A012 −69 €). Sin colchón (z = 0), sin transfers ni campañas |

**Respuesta a las posiciones del comité (PDF sección 8):**
- **Ventas** quiere stock abundante: justificado solo en MSUV, CSUV, SSUV, MD y S, donde quedarse corto cuesta ~8–10 veces más que pasarse. En B y C, no.
- **Finanzas** quiere menos stock y no empujar segmentos que no dejan dinero: tiene razón con B y C. El stock medio baja de ~2.900 a ~2.100 coches y los coches de más de 90 días desaparecen.
- **Los concesionarios** se quejan de coches que no han pedido y del pago a los 180 días: con el plan apenas quedan coches de más de 90 días a fin de año, frente a ~1.000 en A012.
- **La matriz** no quiere cambios en lo que está en producción: el plan no toca enero y febrero, y los cambios entran a 3 meses vista, como establece el proceso. El mensaje para la matriz: **la prima de CO₂ convierte el año en pérdidas**, y eso pesa más que cualquier ajuste de producción.

### Limitaciones
- Los pesos de los escenarios (25 / 50 / 25 %) son un supuesto.
- La regla del 90 % / 110 % está calibrada con nuestros propios escenarios.
- No se ha simulado qué pasaría sin revisión mensual (plan fijo), que daría la referencia de cuánto vale revisar.
- El z alto de la simulación se debe en parte a que el stock a fin de año no se penaliza.

---

## Registro de decisiones propias (para defenderlas)

| Decisión | Por qué | Dónde |
|---|---|---|
| Demanda = retail sin automatriculaciones | Tabla 1 del PDF: no es demanda | fase1 |
| Estacionalidad sacada del mercado, no de Kaido | Más historia y menos ruido | fase1, `factores_estacionales` |
| Adelanto → min; caída → max | No inventar demanda que los datos no muestran | fase1, línea 103 |
| No corregir el adelanto del CSUV | Su mercado no lo muestra; está en rampa | fase1, línea 115 |
| Solo la confianza como variable macro | La que mejor validó; pocas variables (PDF 5.2) | fase2, línea 47 |
| 3 meses de retraso en la macro | Se conoce cuando se decide la producción (PDF 5.1) | fase2, línea 46 |
| Tendencia de declive solo en C, B y MD | Declive estructural desde A001 | fase2, línea 48 |
| Cuota = media de 6 meses normales | Sencillo; el efecto producto va a los escenarios | fase2, `cuota_reciente` |
| Caída tras el adelanto = −11 % calibrado con A011 | El coeficiente del modelo sale con el signo cambiado en 3 segmentos | fase3, línea 51 |
| Paro +2 puntos ≈ confianza −12 | Relación observada en A004→A005 | fase3, `PARAMETROS` |
| Lo que viene en camino = facturación media de julio–diciembre de A012 | El PDF pide estimarlo; es lo que se estaba facturando | fase4, línea 78 |
| Transfer solo si deja dinero; 50 % de los faltantes | Con la prima de CO₂ o en B el transfer pierde dinero | fase4, línea 134 |
| Error de demanda AR(1) | El PDF (7.3) avisa de que los errores seguidos se parecen | fase4, `errores_ar1` |
| z por segmento (2,05 / 0,84 / 0) | Óptimo de la simulación ponderando escenarios; 2,05 y no 2,33 porque la ganancia extra es < 0,1 M€ | fase4, línea 58; fase5 |
| Pesos de escenarios 25 / 50 / 25 % | Supuesto: el central es el más probable | fase5, línea 32 |
| Alarma: demanda 3 meses < 90 % o > 110 % del plan | Separa escenarios desde abril con ~10 % de falsas alarmas | fase5, sección D |
