# Frontend Angular · Recomendador de proveedores COSCO

Interfaz web (Angular 21, componentes independientes y señales, sin librerías de gráficas) que habla **solo** con la API por HTTP.

| Pantalla | Qué hace |
|---|---|
| Iniciar sesión | Acceso con usuario y contraseña (JWT). Cuadro opcional de acceso de demostración |
| Recomendar | Elige una solicitud, cambia el nivel de servicio, ve el Top-3 con el costo desglosado, los descartados y decide (aprobar o elegir otro con motivo) |
| Pendientes | Casos para revisar y escalados a gerencia |
| Proveedores | Ranking por Índice de Dureza y ficha con fortalezas, debilidades, riesgos, capacidad y tendencia |
| Panel | Puntualidad por mes, precios, capacidad disponible y tránsito por corredor |
| Cómo funciona | El camino de una solicitud en cuatro pasos, costo de un retraso por nivel, significado de los colores y límites conocidos |

## Idiomas

Español, English y 简体中文. Se elige en la interfaz (se recuerda en el navegador; la primera vez sigue el idioma del navegador).
Los textos están en `src/app/i18n/{es,en,zh}.ts`; una prueba exige que los tres tengan las mismas claves.
Las explicaciones que redacta el motor en español se traducen con plantillas (`src/app/i18n/motor.ts`); si aparece una frase que
ninguna plantilla conoce, se muestra tal cual en español. **Para añadir otro idioma:** copia `en.ts`, tradúcelo y súmalo a `IDIOMAS` en `i18n.service.ts`.

## Preferencias de la persona

Un grupo de controles (idioma, tema, accesibilidad) disponible en el login y en la barra lateral: tema automático/claro/oscuro, tamaño de texto
(100–130 %), contraste alto y reducción de movimiento. Todo se recuerda en el navegador. La idea del grupo se tomó de la plataforma EciWise.

## Diseño

Colores de la marca COSCO SHIPPING: azul `#00508F` y rojo `#D6000E`. El azul es marca y acción; el **rojo se reserva a señales de riesgo**
(retraso, escalamiento, errores); el ámbar significa «revisar». Sigue el modo claro/oscuro del sistema. Tipografía del sistema (con
fuentes CJK de respaldo) y números tabulares. La pieza distintiva es la barra apilada del costo esperado. No usa el logotipo de COSCO.

## Seguridad

- Contraseñas con PBKDF2-HMAC-SHA256 (600 000 iteraciones) y sal propia; JWT firmado (HS256) con vida de 60 min; 5 intentos fallidos → bloqueo de 15 min.
- Token en `sessionStorage` (se borra al cerrar la pestaña) y cierre de sesión automático al vencer. Rutas protegidas por guardia y por la API.
- El autor de cada decisión sale de la sesión, no del cuerpo de la petición.
- Cabeceras de seguridad y CSP estricta en nginx. **El usuario semilla es solo de demostración**: en un despliegue real defina
  `COSCO_SEED_USER`/`COSCO_SEED_PASSWORD`, `COSCO_JWT_SECRET` (≥ 32 caracteres) y deje vacíos `COSCO_DEMO_USER`/`COSCO_DEMO_PASSWORD`.

## Desarrollo

```bash
npm install --legacy-peer-deps
npm start            # http://localhost:4200  (API en http://localhost:8000, ver public/config.json)
npm test             # pruebas (vitest)
npm run build
```
Requiere Node ≥ 22.12. Con Docker: `docker compose up --build` desde la raíz y abrir http://localhost:4200.
