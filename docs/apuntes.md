# Apuntes: respuestas a las 5 preguntas del caso Kaido

> Documento de trabajo, en sucio. Se actualiza cada vez que se responde una pregunta.
> Última actualización: 2026-10-14 (preguntas 1 y 2 respondidas).

**Cómo reproducir todo** (desde la raíz del repo, con el `.venv` activado):

```
python src/fase0_checks.py      # comprobaciones de datos
python src/fase1_demanda.py     # P1 -> resultados/demanda_real.csv
python src/fase2_prevision.py   # P2 -> resultados/prevision_*.csv (necesita la salida de fase 1)
```

Las salidas van a `resultados/`, que está en `.gitignore` porque se regenera con el código.

**Estado**

| # | Pregunta | Estado | Script |
|---|---|---|---|
| 1 | ¿Cuál es la demanda real? | ✅ Respondida | [fase1_demanda.py](../src/fase1_demanda.py) |
| 2 | ¿Cuánto vamos a vender en A013? | ✅ Respondida (escenario central) | [fase2_prevision.py](../src/fase2_prevision.py) |
| 3 | ¿Qué pasa si el año sale mejor o peor? | ⏳ Pendiente | — |
| 4 | ¿Cuántos coches fabricamos y cuánto stock? | ⏳ Pendiente | — |
| 5 | ¿Cuánto cuesta equivocarse y qué recomendamos? | ⏳ Pendiente | — |

---

## 0. Comprobaciones de los datos (antes de responder)

**Conclusión:** los datos son íntegros. No hay que arreglar nada técnico.

| Comprobación | Resultado | Dónde |
|---|---|---|
| Ventas Kaido A003–A012 = 125.030 (Anexo 5) | ✅ Igual en ventas, mercado, segmentos y códigos | [fase0_checks.py](../src/fase0_checks.py), sección 2 |
| `ventas_mensual` = `mercado.marca_propia` | ✅ 0 celdas distintas | sección 3 |
| Stock_t = Stock_{t−1} + wholesale − ventas | ✅ Desvíos de pocos coches (SSUV hasta ±50) | sección 4 |
| % del stock con más de 90 días | 20 % en enero de A012 → 35 % en diciembre (cuadra con el PDF) | sección 9 |

**Rarezas detectadas** (útiles después):
- **SSUV y S acaban A012 con stock 0 y 1.** Hubo rotura y en diciembre se vendió lo que había. El SSUV facturó solo 2 coches en diciembre, probablemente por un cambio de código: tiene uno nuevo en A013.
- **C acaba con 1.107 coches (3,2 meses de cobertura).** Es el segmento con más exceso.
- **CSUV tiene 1.011 coches para unas ~400 ventas al mes** (unos 2,5 meses).
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
1. **Automatriculaciones**: las matricula el concesionario o la marca a su nombre para cumplir objetivos. Cuentan como venta pero no hay cliente (Tabla 1 del PDF: *"Cuenta como venta, pero no es demanda"*). Se restan.
2. **Compras adelantadas**: clientes de A013 que compraron en noviembre y diciembre de A012 para evitar el cambio de normativa. Es demanda que pertenece a A013. Se quita el exceso.
3. **Falta de coches**: si no había stock, la venta fue menor que la demanda. Se rellena.

Por qué importa: si el modelo aprende de las ventas brutas, prevé demanda fantasma, se fabrica de más y se repite el problema de A012 (stock viejo y más VM).

### Cómo se calculó (método)
Todo está en [fase1_demanda.py](../src/fase1_demanda.py):
- **Retail** = `unidades − u_automatriculacion`, de `ventas_mensual.csv`.
- **Demanda "normal" esperada en un mes** = nivel desestacionalizado de los meses normales vecinos × factor estacional del mes.
  - Función `esperado()`, [línea 68](../src/fase1_demanda.py#L68).
  - Con meses posteriores disponibles se usan 3 antes y 3 después. Si no los hay (final de A012), los 6 anteriores.
  - **Factores estacionales**: se sacan del **mercado** de cada segmento A001–A012, que tiene más historia que Kaido. Función `factores_estacionales()`, [línea 57](../src/fase1_demanda.py#L57).
- **Reglas** ([línea 100](../src/fase1_demanda.py#L100)):
  - Meses de adelanto o subida del IVA → `min(vendido, esperado)`. Solo se recorta el exceso.
  - Meses de caída tras el adelanto → `max(vendido, esperado)`. Solo se rellena el hueco.
  - Rotura de stock → `max(vendido, esperado)`. Se considera rotura cuando el stock a fin de mes es menor que el 15 % de la venta media mensual ([línea 87](../src/fase1_demanda.py#L87)). Solo se detecta desde A009, que es cuando hay datos de stock.
  - Los meses con suceso salen de `macro_mensual.csv` (`adelanto_compras`, `caida_tras_adelanto`, `subida_iva`).
- **CSUV**: no se corrige ([línea 112](../src/fase1_demanda.py#L112)). Su mercado no muestra adelanto en noviembre y diciembre (×0,95 y ×0,87) y está en rampa de lanzamiento.
- **No se corrigen** los segmentos con menos de 3 meses de historia, porque aún no se vendían.

### Datos que la respaldan
- **Coches adelantados en noviembre y diciembre de A012:** MSUV 600, C 341, SSUV 86, B 70, S 11. **Total: 1.108.**
- **Demanda no servida por rotura en diciembre de A012:** SSUV 111.
- **Mercado en el adelanto de A011:**
  - agosto: +41 % sobre lo normal;
  - después, 4 meses de caída: −19 %, −11 %, −4 % y −9 % (unos 2.590 coches menos frente a ~21.600 adelantados).
  - → Útil para calibrar la duración de la caída en los escenarios de la P3.
- **Por segmento, demanda A012 frente a A011:**
  - MSUV −15 % (pierde cuota: del 6 % al 4 %);
  - MD −40 % (su mercado se hunde);
  - SSUV +17 %, S +11 %, C +8 %, B +7 %.

**Ficheros:**
- `resultados/demanda_real.csv`: demanda limpia por mes y segmento, con columnas `vendido`, `automat`, `retail`, `demanda` y `motivo`. Es la entrada de la P2.
- `resultados/fase1_demanda.png`: gráfico de vendido frente a demanda real.

### Limitaciones / dudas abiertas
- En MSUV y C las ventas ya suben en septiembre y octubre de A012. El adelanto pudo empezar antes, pero solo se corrigen los meses marcados (noviembre y diciembre): es la opción conservadora.
- Antes de A009 no hay datos de stock, así que no se pueden detectar roturas.
- El umbral de rotura (15 %) y la ventana de 6 meses son criterios propios.

---

## Pregunta 2: ¿Cuánto vamos a vender en A013?

### Respuesta corta (escenario central)
**Demanda de Kaido en A013: unos 18.600 coches (−5,6 % sobre la demanda real de A012).**
- El mercado de sus segmentos cae alrededor de un 20 %.
- El CSUV amortigua la caída porque pasa de 5 meses de ventas a un año completo.
- **Sin el CSUV, Kaido caería un ~18 %.**

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

El desglose mensual está en `resultados/prevision_A013_central.csv`.

### Cómo se calculó (método)
Todo está en [fase2_prevision.py](../src/fase2_prevision.py). Se sigue la sección 5.2 del PDF: **demanda Kaido = mercado del segmento × cuota de Kaido.**

**Modelo de mercado** (`ajustar_mercado()`, [línea 87](../src/fase2_prevision.py#L87)):
- Regresión sobre log(unidades) con errores SARIMA(0,0,0)(0,1,1)12. En la práctica: *"cada mes se parece al mismo mes del año anterior, suavizado"*.
- Variables:
  - **confianza del consumidor con 3 meses de retraso**, que ya se conoce cuando se decide la producción (PDF 5.1) ([línea 45–46](../src/fase2_prevision.py#L45));
  - calendario: `dias_laborables` y `semana_santa`;
  - sucesos: `adelanto_compras`, `caida_tras_adelanto`, `subida_iva` e `incentivo_publico`;
  - **tendencia de declive solo en C, B y MD** ([línea 47](../src/fase2_prevision.py#L47)), porque pierden mercado frente al SUV desde A001. Por ejemplo, el mercado MD pasó de 91.000 coches en A001 a 20.000 en A012.

**Cuota** (`cuota_reciente()`, [línea 98](../src/fase2_prevision.py#L98)):
- Media de los últimos 6 meses sin sucesos.
- CSUV: media de los 3 últimos meses. Está en rampa, y por analogía con el lanzamiento del SSUV en A008, que se estabilizó en ~3 meses, ya estaría cerca de su cuota estable.

**S (descapotable)** (`prever_nivel_estacional()`, [línea 109](../src/fase2_prevision.py#L109)):
- Se prevé directamente la demanda de Kaido. Su mercado es casi solo Kaido (60–100 % de cuota) y tiene meses con 1 coche, así que modelarlo no tiene sentido.

**Supuestos del escenario central para A013** (`exog_A013()`, [línea 70](../src/fase2_prevision.py#L70)):
- Confianza: enero–marzo usan los datos reales de octubre–diciembre de A012 (73,3 / 77,4 / 77,7). Desde abril se mantiene en **77,7**, "como al final de A012" (Tabla 4).
- Caída tras el adelanto: **3 meses** (enero–marzo), según la Tabla 4.
- Calendario: `calendario_A013.csv`.
- Sin planes de ayuda ni subidas del IVA.

### Por qué este modelo y no el del Anexo 4
Se probaron 9 variantes entrenando hasta A011 y previendo el mercado de A012: el SARIMA(1,0,0) del Anexo 4, el modelo airline y versiones con paro, confianza, hipotecas y actividad.

| Modelo | Error del mercado A012 (MSUV / SSUV / C / B / CSUV / MD) |
|---|---|
| Anexo 4 (AR(1) + paro + confianza) | +16 / +4 / +44 / +23 / +44 / +78 % |
| Elegido (sin AR + confianza, con tendencia en C/B/MD) | −3 / −11 / +12 / +7 / −4 / +16 % |
| Repetir A011 ("naive") | −7 / −10 / +17 / +13 / −5 / +40 % |

- El modelo del Anexo 4 arrastra la inercia de crecimiento de A010–A011 y sobreestima.
- La confianza es la variable que mejor explica el frenazo de A012.
- Los experimentos se hicieron en scripts temporales que no se guardaron en el repo. Si hace falta mostrarlos, se pueden rehacer en un notebook.

### Validación (entrenado hasta A011, previsión de la demanda limpia de A012)

| Segmento | Real A012 | Previsto | Error anual | Error mensual medio (MAPE) | MAPE de repetir A011 |
|---|---|---|---|---|---|
| MSUV | 6.881 | 7.479 | +9 % | 18 % | 20 % |
| SSUV | 5.660 | 3.534 | −38 % | 39 % | 20 % |
| C | 3.355 | 2.883 | −14 % | 48 % | 62 % |
| B | 1.553 | 1.042 | −33 % | 29 % | 19 % |
| MD | 591 | 741 | +25 % | 37 % | 76 % |
| S | 477 | 436 | −9 % | 23 % | 23 % |
| **Total (sin CSUV)** | **18.517** | **16.114** | **−13 %** | **17 %** | |

- El CSUV no se puede validar porque no tiene historia antes de A012-08.
- **Lectura:** el modelo de **mercado** funciona razonablemente. El error grande viene de la **cuota**, que cambió mucho de A011 a A012 en SSUV y B (cambios de modelo, roturas de stock).
- **Sesgo:** previó A012 un 13 % por debajo, así que puede ser algo pesimista también en A013.

### Error de previsión (entrada para las P3 y P4)
- **σ** = error típico mensual de la validación, en % del nivel, aplicado al nivel previsto de A013 ([línea 178–181](../src/fase2_prevision.py#L178)). Va del 15 al 33 % según el segmento.
- Al CSUV se le asigna el mayor error relativo de los SUV.
- **Autocorrelación del error: 0,2–0,7.** Los errores de meses seguidos se parecen, sobre todo en C (0,7). El PDF (7.3) avisa de que, en ese caso, la fórmula del stock de seguridad se queda corta y la simulación lo mide mejor.

**Ficheros:**
- `resultados/prevision_A013_central.csv`: mercado, cuota y demanda por mes y segmento.
- `resultados/prevision_resumen.csv`: resumen por segmento, con σ y la autocorrelación.
- `resultados/validacion_A012.csv`: lo previsto frente a lo real en A012.
- `resultados/fase2_prevision.png`: gráfico de la validación y de la previsión.

### Limitaciones / dudas abiertas
- **El supuesto que más pesa:** que la confianza se quede en 77, un nivel de crisis comparable a A004–A005. En A005 la confianza cayó unos 21 puntos y el mercado un 13 %. El modelo prevé ahora entre −17 % y −30 %, algo agresivo. → Los escenarios de la P3 lo acotan.
- **La cuota es una media reciente.** No modela los 7 códigos nuevos de A013 (en MSUV, SSUV, B y CSUV). Su efecto entra por los escenarios: retraso en el pesimista, éxito en el optimista.
- **La cuota del MSUV bajó del 6 % al 4 % en A012.** Se asume que sigue en el 4,1 %. Si los 2 códigos nuevos recuperan cuota, la previsión se queda corta.
- **El CSUV es la mayor incertidumbre:** solo 5 meses de historia.

---

## Pregunta 3: ¿Qué pasa si el año sale mejor o peor?
⏳ *Pendiente.* Plan: traducir la Tabla 4 a valores del modelo (confianza, duración de la caída, cuota de los códigos nuevos, prima de CO₂, suministro) y simular unas 1.000 réplicas con error σ autocorrelacionado.

## Pregunta 4: ¿Cuántos coches fabricamos y cuánto stock queremos?
⏳ *Pendiente.* Plan: el plan rodante de la sección 7, `L_{t+3} = max(0, D̂_{t+3} + SS − Ŝ_{t+2})` con `SS = z·σ·√3`. Partir del stock real de diciembre de A012 y estimar lo que ya viene en camino.

## Pregunta 5: ¿Cuánto cuesta equivocarse y qué recomendamos?
⏳ *Pendiente.* Pistas ya vistas en los datos:
- **B tiene CVP real negativo** (−69 €/coche) → candidato a frenar.
- **MD:** su mercado se hunde (−30 % previsto).
- **C tiene exceso de stock** (3,2 meses) y un CVP bajo (1.187 €).
- **MSUV, CSUV, S y MD dejan más margen por coche.**

---

## Registro de decisiones propias (para defenderlas)

| Decisión | Por qué | Dónde |
|---|---|---|
| Demanda = retail sin automatriculaciones | Tabla 1 del PDF: no es demanda | fase1, retail |
| Estacionalidad sacada del mercado, no de Kaido | Más historia y menos ruido | fase1, `factores_estacionales` |
| Adelanto → min; caída → max | No inventar demanda que los datos no muestran | fase1, línea 100 |
| No corregir el adelanto del CSUV | Su mercado no lo muestra; está en rampa | fase1, línea 112 |
| Solo la confianza como variable macro | La que mejor validó; con 12 años de datos, pocas variables (PDF 5.2) | fase2, línea 46 |
| 3 meses de retraso en la macro | Se conoce cuando se decide la producción (PDF 5.1) | fase2, línea 45 |
| Tendencia de declive solo en C, B y MD | Declive estructural desde A001; en los SUV la tendencia empeoraba la validación | fase2, línea 47 |
| Cuota = media de 6 meses normales | Sencillo y transparente; el efecto producto va a los escenarios | fase2, `cuota_reciente` |
| Caída tras el adelanto en el central = 3 meses | Tabla 4 del PDF | fase2, línea 51 |
