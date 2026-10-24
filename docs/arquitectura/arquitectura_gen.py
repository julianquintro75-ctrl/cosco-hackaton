"""Genera docs/img/arquitectura.svg y .png. Editar el texto y volver a correr desde esta carpeta: python arquitectura_gen.py"""
import html
W, H = 1500, 930
o = []
def esc(s): return html.escape(s)
def text(x, y, s, size=16, weight=400, fill='#0a2640', anchor='middle', style=''):
    o.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" {style}>{esc(s)}</text>')
KINDS = {'now': ('#ffffff', '#00508f', 2, ''), 'data': ('#e4edf6', '#00508f', 2, ''), 'humano': ('#ffffff', '#d6000e', 2.5, ''),
         'warn': ('#fdf0d9', '#8a5200', 2, ''), 'fut': ('#f7f8fa', '#8a94a3', 2, 'stroke-dasharray="7 5"'), 'sim': ('#f0eefc', '#6a3fb5', 2, 'stroke-dasharray="7 5"')}
def box(x, y, w, h, title, lines=(), kind='now'):
    f, s, sw, d = KINDS[kind]
    o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{f}" stroke="{s}" stroke-width="{sw}" {d}/>')
    col = '#6b7280' if kind == 'fut' else '#0a2640'
    n = 1 + len(lines); y0 = y + h / 2 - (n - 1) * 11 + 5
    text(x + w / 2, y0, title, 16, 700, col)
    for i, l in enumerate(lines): text(x + w / 2, y0 + 22 + i * 19, l, 13, 400, '#33495f')
def band(y, h, title):
    o.append(f'<rect x="20" y="{y}" width="{W-40}" height="{h}" rx="16" fill="#f5f8fb" stroke="#c5d2df" stroke-width="1.5"/>')
    text(40, y + 24, title, 13, 700, '#4d6a88', 'start', 'letter-spacing=".06em"')
def arrow(x1, y1, x2, y2, dash=False, color='#4d6a88'):
    o.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2.4" {"stroke-dasharray=\"7 6\"" if dash else ""} marker-end="url(#a)"/>')

o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Inter, \'Segoe UI\', Helvetica, Arial, sans-serif">')
o.append('<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0 10 5 0 10z" fill="#4d6a88"/></marker></defs>')
o.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
text(40, 40, 'Arquitectura: capas, interfaces intercambiables y puntos de extensión', 26, 800, '#0a2640', 'start')
text(40, 64, 'Línea continua = existe hoy · línea punteada = punto de extensión (aún no construido). Una capa solo conoce a la de abajo.', 14, 400, '#55606e', 'start')

# 1 clientes
band(84, 130, '1 · CLIENTES')
box(40, 112, 330, 90, 'Web Angular · 3 roles', ['solicitante · operador · gerencia', 'recomendar · pendientes · panel · seguimiento'])
box(390, 112, 330, 90, 'Scripts y demostración', ['scripts/demo_api.py · replay.py', 'demo_concurrencia.py'])
box(740, 112, 330, 90, 'Integraciones', ['ERP / TMS / WhatsApp', 'consumen la misma API'], 'fut')
box(1090, 112, 370, 90, 'Mapa del seguimiento', ['interfaz MotorMapa: Leaflet + OpenStreetMap hoy', 'Google Maps mañana'], 'sim')
# 2 api
band(232, 100, '2 · API')
box(40, 260, 1420, 60, 'FastAPI · app/api.py · JWT por rol', ['≈ 22 endpoints: /solicitudes · /recomendar · /decision · devolver · /pendientes · /seguimiento · /notificaciones · /proveedores/{id}/ficha · /tableros/*'])
# 3 decision
band(350, 168, '3 · DECISIÓN')
box(40, 378, 330, 126, 'Motor A · propio', ['reglas duras → bayes Beta(17, 3)', '→ costo total esperado → explicación', 'determinista · 9,3 ms (p50)'])
box(390, 378, 330, 126, 'Motor B · Jev', ['adaptador de caja negra', 'MEDIDO: $159.419 de arrepentimiento', '50,7 % óptimo · 310 ms (p50)'], 'warn')
box(740, 378, 330, 126, 'Motor C · LLM', ['explica y critica; no ordena', 'NO MEDIDO (sin clave de API)'], 'warn')
box(1090, 378, 370, 126, 'Otro servicio backend', ['p. ej. pronóstico de demanda,', 'optimizador de rutas', '(microservicio nuevo)'], 'fut')
# 4 nucleo
band(536, 112, '4 · NÚCLEO')
box(40, 564, 270, 70, 'engine/estadisticas.py', ['bayes + decaimiento (vida media 30 d)'])
box(330, 564, 270, 70, 'engine/fichas.py · modelos.py', ['Índice de Dureza · ML (candidato)'])
box(620, 564, 270, 70, 'engine/config_motor.json', ['costos de retraso · λ · umbrales'])
box(910, 564, 270, 70, 'engine/ubicacion.py', ['FuenteUbicacion: simulador hoy'], 'sim')
box(1200, 564, 260, 70, 'contratos/ (pydantic)', ['SolicitudIn · Recomendacion'])
# 5 datos
band(666, 198, '5 · DATOS Y SERVICIOS')
box(40, 694, 330, 70, 'engine/repositorio.py', ['puerto Repositorio'])
box(390, 694, 330, 70, 'RepositorioSQLite', ['repo_sqlite.py · data/cosco.db · 17 tablas'], 'data')
box(740, 694, 330, 70, 'Nuevo Repositorio', ['PostgreSQL: registrar_backend()'], 'fut')
box(1090, 694, 370, 70, 'data/verdad_oculta.csv', ['solo evaluación · nunca entra al motor'], 'warn')
box(40, 784, 330, 64, 'Slack', ['avisos por webhook (solo en .env)'])
box(390, 784, 330, 64, 'Reentrenador nocturno', ['publica un candidato si mejora; la persona aprueba'])
box(740, 784, 720, 64, 'Despliegue · docker-compose.yml', ['init-datos → api (:8000) + web (:4200, nginx, sin acceso a la base) · reentrenador (perfil ml)'])
# flechas
arrow(205, 202, 205, 260); arrow(555, 202, 555, 260); arrow(905, 202, 905, 260, True); arrow(1275, 202, 1275, 260, True)
arrow(205, 320, 205, 378); arrow(555, 320, 555, 378); arrow(905, 320, 905, 378, True); arrow(1275, 320, 1275, 378, True)
arrow(290, 504, 290, 564)
arrow(290, 634, 290, 694); arrow(370, 729, 390, 729); arrow(720, 729, 740, 729, True)
text(40, 905, 'Los motores implementan el puerto MotorDecision; solo repo_sqlite.py ejecuta SQL; la web habla únicamente con la API.', 14, 600, '#33495f', 'start')
o.append('</svg>')
open('../img/arquitectura.svg', 'w', encoding='utf8').write('\n'.join(o))
try:
    from playwright.sync_api import sync_playwright
    import pathlib
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={'width': W, 'height': H}, device_scale_factor=2)
        pg.goto(pathlib.Path('../img/arquitectura.svg').resolve().as_uri()); pg.screenshot(path='../img/arquitectura.png'); b.close()
except Exception as e:
    print('PNG no regenerado:', e)
