# Seguimiento en ruta (simulado) y cómo conectar GPS o Google Maps

Pantalla **Seguimiento** (web, los tres roles): mapa con el camión de cada servicio moviéndose por su corredor, reproducir/pausa, velocidad 1×/2×/4× y estado «llegaría a tiempo / tarde». **Es una simulación**: no hay GPS conectado, y la pantalla lo dice.

## Quién ve qué
| Rol | Ve |
|---|---|
| Solicitante | solo los servicios de **sus** solicitudes, una vez que tienen proveedor asignado |
| Operador / gerencia | todos los servicios en curso y 6 repeticiones de la fase de prueba (una por corredor, con las horas reales de cargue y entrega) |

Un servicio aparece en «En curso» apenas se aprueba la solicitud (se crea el servicio EN_CURSO).

## De dónde salen las posiciones
`engine/ubicacion.py`: `SimuladorUbicacion` genera el recorrido de forma determinista (mismo servicio, mismo recorrido) sobre una ruta aproximada por ciudades intermedias.
- En curso: dura el tránsito típico (p50) del proveedor en ese corredor; con la probabilidad de retraso del proveedor hay una parada larga que lo acerca o pasa el pesimista (p90).
- Repetición: respeta la hora real de cargue y de entrega, y si llegó tarde, hay una parada.

## Cambiar la fuente de ubicación (GPS real, telemetría del proveedor, sticker)
Backend: implementar `FuenteUbicacion.traza(servicio) -> Traza` (misma forma: lista de puntos `t, lat, lon, evento`) y registrarlo en `crear_fuente()`; se elige con `COSCO_UBICACION`. La tabla `evento_servicio` ya admite eventos de tipo `GPS`. La API (`GET /seguimiento`) y el frontend no cambian.

## Cambiar el mapa (Google Maps u otro)
Frontend: la pantalla solo usa la interfaz `MotorMapa` (`web/src/app/core/mapa/motor-mapa.ts`): `montar`, `ruta`, `marcador`, `quitar`, `enfocar`, `destruir`. Hoy la implementa `MapaLeaflet` (Leaflet + OpenStreetMap: gratis, sin clave). Para Google Maps: escribir `MapaGoogle implements MotorMapa` y cambiar la fábrica `MOTOR_MAPA` en `app.config.ts`. Ojo con:
- la clave de Google va restringida por dominio y **nunca** en el repositorio;
- ajustar la política CSP de `web/nginx.conf` (`script-src`, `img-src`, `connect-src`);
- sus términos limitan guardar datos de Google en tu propia base.

## Límites
- Rutas aproximadas por ciudades; no son la vía exacta (un servicio de rutas las reemplazaría).
- Las teselas del mapa base vienen de OpenStreetMap: sin internet se ve el contorno de Colombia y las rutas, sin calles.
- Pruebas: `tests/test_seguimiento.py` (13).
