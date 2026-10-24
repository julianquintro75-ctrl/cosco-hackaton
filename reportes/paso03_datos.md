# Paso 3 · Verificación de datos y limpieza

Datos **sintéticos** (semilla 7). Generado con `python seed/generate.py --sucio`.

## Historias (check_story.py)
```
== % de entregas a tiempo por proveedor y mes ==
mes                   2025-11  2025-12  2026-01  2026-02  2026-03  2026-04  2026-05  2026-06  2026-07  2026-08  2026-09  2026-10
nombre                                                                                                                          
Altiplano Trans          96.0     83.0     87.0     75.0     85.0     87.0     88.0     80.0     87.0     81.0     88.0     93.0
Andina Cargo             96.0     91.0     97.0     95.0     98.0     93.0     90.0     97.0     95.0     76.0     78.0     67.0
Caribe Express           76.0     85.0     85.0     82.0     82.0     81.0     68.0     90.0     78.0     83.0     87.0     89.0
Economica del Sur        74.0     77.0     72.0     79.0     69.0     76.0     68.0     73.0     80.0     68.0     69.0     80.0
FrioCol                  92.0     89.0     90.0     89.0     87.0     83.0     88.0     90.0     94.0     94.0     96.0     90.0
Mulas del Valle          84.0     91.0     85.0     85.0     88.0     87.0     84.0     86.0     84.0     85.0     85.0     82.0
Nuevo Rumbo                 .        .        .        .        .        .        .        .        .    100.0     92.0     89.0
Premium Logistics       100.0    100.0    100.0     89.0     90.0    100.0    100.0     90.0     92.0    100.0    100.0     86.0
Rapido SAS               83.0     86.0     90.0     88.0     86.0     75.0     80.0     80.0     73.0     79.0    100.0     60.0
Seguridad Total          81.0     90.0     98.0     92.0     92.0     87.0     92.0     94.0     91.0     93.0     93.0     90.0
TransPacifico            62.0     77.0     69.0     74.0     81.0     61.0     79.0     93.0     69.0     88.0    100.0     89.0
Veteranos del Camino    100.0     71.0     73.0     75.0    100.0    100.0     90.0     78.0     75.0     67.0     78.0     75.0

== Servicios por proveedor (cuota) ==
nombre
Mulas del Valle         1931
Economica del Sur       1099
Caribe Express           799
Andina Cargo             547
Altiplano Trans          366
Seguridad Total          334
TransPacifico            239
FrioCol                  239
Premium Logistics        154
Rapido SAS               150
Veteranos del Camino     121
Nuevo Rumbo               26

Cuota mensual de Mulas del Valle (%): [24, 29, 29, 31, 28, 33, 34, 33, 38, 34, 37, 37]

== Andina Cargo (P01): colapsa el 2026-08-01 (P(tarde) real 6% -> 35% en 20 dias). Primer dia con P(tarde)>15% ==
  sin decaimiento   : None  (+- dias)
  vida media 90 d   : None  (+- dias)
  vida media 45 d   : 2026-09-15  (+45 dias)
  vida media 30 d   : 2026-08-31  (+30 dias)

== Altiplano (P12): paro 10-24 mar. Pico de P(tarde) con cada configuracion, y cuando vuelve <20% ==
  vida media 90 d: pico 17% el 2026-03-25; vuelve <20% el 2026-03-26
  vida media 30 d: pico 19% el 2026-03-25; vuelve <20% el 2026-03-26

== TransPacifico (P02): mejora abr-jun. P(tarde) bayesiana (vida media 45 d) al 1 de cada mes ==
   {'2026-02-01': np.float64(0.237), '2026-04-01': np.float64(0.209), '2026-06-01': np.float64(0.229), '2026-08-01': np.float64(0.198), '2026-10-01': np.float64(0.121)}

== Caribe Express (P03) a tiempo por corredor (debil en Pacifico C1-C3) ==
corredor_id
C1    68.0
C2    69.0
C4    92.0
C5    89.0
C6    88.0
C7    93.0
C8    90.0
```

## Validador
```
35 reglas · 33 OK · 2 con problemas (0 criticas)
35 reglas · 23 OK · 12 con problemas (9 criticas)
35 reglas · 33 OK · 2 con problemas (0 criticas)
```

## Limpieza (limpiar.py)
```
   nombre P01: 'ANDINA CARGO S.A.S.' -> 'Andina Cargo'

== Correcciones ==
  servicios duplicados eliminados                                    41
  entregas anteriores al cargue corregidas (con GPS)                 41
  entregas anteriores al cargue corregidas (sin GPS, = planeada)      0
  a_tiempo vacio recalculado                                         41
  a_tiempo incoherente recalculado (tras corregir entregas)           0
  nombres de proveedor normalizados                                   1
  tarifas con factor 1000 corregidas                                  6

== Conteos: limpia vs referencia (cosco.db) ==
  capacidad_snapshot          1468    1468  OK
  certificacion                  5       5  OK
  cliente                       40      40  OK
  corredor                       8       8  OK
  decision                    6023    6023  OK
  estadistica_proveedor          0       0  OK
  evento_servicio            13050   13050  OK
  feedback                    1793    1793  OK
  flota                         31      31  OK
  modelo_version                 0       0  OK
  proveedor                     12      12  OK
  recomendacion                  0       0  OK
  servicio                    6196    6196  OK
  solicitud                   6169    6169  OK
  tarifa                       692     692  OK
  tipo_vehiculo                  5       5  OK

  a_tiempo distinto de la referencia: 0 · error max. en entrega_real: 2 min · tarifas distintas: 0 · nombres distintos: 0
  RESULTADO: conteos iguales a la referencia

Guardado: /home/claude/work/proyecto/data/cosco_limpio.db
```
