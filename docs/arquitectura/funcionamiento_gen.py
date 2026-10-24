import html
W,H=1500,900
o=[]
def esc(s): return html.escape(s)
def text(x,y,s,size=16,weight=400,fill='#0a2640',anchor='middle',style=''):
    o.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" {style}>{esc(s)}</text>')
def box(x,y,w,h,title,lines=(),kind='auto',tag=None):
    st={'auto':('#e4edf6','#00508f',2,''),'humano':('#ffffff','#d6000e',2.5,''),'sol':('#ffffff','#00508f',2,''),
        'alerta':('#fdf0d9','#8a5200',2,''),'sim':('#f0eefc','#6a3fb5',2,'stroke-dasharray="7 5"'),'dato':('#ffffff','#00508f',2,'')}[kind]
    o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{st[0]}" stroke="{st[1]}" stroke-width="{st[2]}" {st[3]}/>')
    n=1+len(lines); y0=y+h/2-(n-1)*11+5
    if tag: y0+=8
    text(x+w/2,y0,title,17,700)
    for i,l in enumerate(lines): text(x+w/2,y0+24+i*21,l,14,400,'#33495f')
    if tag:
        tw=len(tag)*8+22
        o.append(f'<rect x="{x+w/2-tw/2}" y="{y-13}" width="{tw}" height="26" rx="13" fill="{st[1]}"/>')
        text(x+w/2,y+5,tag,13,700,'#ffffff')
def arrow(d,color='#4d6a88',dash=False,w=2.5,marker='a'):
    o.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{w}" {"stroke-dasharray=\"7 6\"" if dash else ""} marker-end="url(#{marker})"/>')
def label(x,y,s,bg='#ffffff',fill='#33495f',size=13,w=None):
    w=w or len(s)*6.6+14
    o.append(f'<rect x="{x-w/2}" y="{y-14}" width="{w}" height="22" rx="6" fill="{bg}" opacity=".96"/>'); text(x,y+2,s,size,600,fill)
def band(x,y,w,h,title):
    o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="20" fill="#f5f8fb" stroke="#c5d2df" stroke-width="1.5"/>'); text(x+22,y+28,title,15,700,'#4d6a88','start',' letter-spacing=".04em"')

o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Inter, \'Segoe UI\', Helvetica, Arial, sans-serif">')
o.append('<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0 10 5 0 10z" fill="#4d6a88"/></marker>'
         '<marker id="r" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0 10 5 0 10z" fill="#d6000e"/></marker>'
         '<marker id="g" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0 10 5 0 10z" fill="#0f6e4f"/></marker></defs>')
o.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
text(40,42,'Cómo funciona: de la solicitud a la decisión y de vuelta a los datos',26,800,'#0a2640','start')

# banda 1
band(20,95,1460,200,'1 · SOLICITUD Y MOTOR DE RECOMENDACIÓN (automático, determinista, ≈15 ms)')
Y1,H1=145,120
box(40,Y1,230,H1,'Crea la solicitud',['cliente · corredor · vehículo','peso · plazo'],'sol','SOLICITANTE')
box(330,Y1,230,H1,'Filtros duros',['certificación · vehículo','tarifa · capacidad','(cada descartado, con motivo)'],'auto')
box(620,Y1,230,H1,'Estadística bayesiana',['P(a tiempo) · tránsito · incidentes','por proveedor × corredor × carga','los datos recientes pesan más'],'auto')
box(910,Y1,230,H1,'Costo total esperado',['precio + retraso + incidentes','+ incertidumbre + concentración','todo en pesos'],'auto')
box(1200,Y1,250,H1,'Top-3 explicado',['por qué #1 sobre #2','alertas · confianza · margen'],'auto')
for a,b in [(270,330),(560,620),(850,910),(1140,1200)]: arrow(f'M{a} {Y1+H1/2} L{b-2} {Y1+H1/2}')
label(300,Y1+H1/2-18,'POST /solicitudes',w=122)

# banda 2
band(20,325,1460,230,'2 · PERSONAS')
Y2,H2=385,120
# diamante
cx,cy=1325,445
o.append(f'<path d="M{cx} {cy-62} L{cx+105} {cy} L{cx} {cy+62} L{cx-105} {cy} Z" fill="#fdf0d9" stroke="#8a5200" stroke-width="2"/>')
text(cx,cy-4,'¿Pide revisión',16,700); text(cx,cy+16,'o escalamiento?',16,700)
arrow(f'M1325 {Y1+H1+2} L1325 {cy-64}')
box(910,Y2,230,H2,'Aviso a Slack',['operaciones o gerencia','una sola vez por solicitud'],'alerta')
box(570,Y2-10,290,H2+20,'Una persona decide',['Operador: aprueba el #1 o elige otro','Gerencia: decide lo escalado','una sola decisión por solicitud'],'humano')
box(270,Y2,230,H2,'Devolver al solicitante',['motivo + nota','queda registrado'],'humano')
arrow(f'M{cx-106} {cy} L1142 {cy}'); label(1170,cy-16,'sí',w=34)
arrow(f'M910 {cy} L862 {cy}')
# no: un clic
arrow(f'M{cx} {cy+64} L{cx} 532 L810 532 L810 {Y2+H2+12}'); label(1060,545,'no: aprobación en un clic',w=176)
arrow(f'M570 {cy} L502 {cy}',dash=True,color='#d6000e',marker='r'); label(536,cy-14,'o',w=24)
# devolver -> solicitante
arrow(f'M270 {cy} L205 {cy} L205 {Y1+H1+2}',dash=True,color='#d6000e',marker='r'); label(205,Y2-24,'corrige y reenvía',w=112)

# banda 3
band(20,585,1460,225,'3 · DESPUÉS DE DECIDIR')
Y3,H3=650,120
box(560,Y3,300,H3,'Servicio EN CURSO',['capacidad del proveedor comprometida','(la siguiente solicitud ya no la ve)'],'dato')
box(910,Y3,230,H3,'Seguimiento en ruta',['mapa con animación','SIMULADO hoy'],'sim')
box(1200,Y3,250,H3,'Cierre del servicio',['resultado real: a tiempo,','incidente, costo final'],'dato')
arrow(f'M690 {Y2+H2+12} L690 {Y3-2}')
arrow(f'M860 {Y3+H3/2} L908 {Y3+H3/2}'); arrow(f'M1140 {Y3+H3/2} L1198 {Y3+H3/2}')
label(1025,Y3+H3+18,'GPS real o Google Maps entran aquí',bg='#f0eefc',fill='#4a2c8a',w=240)
# realimentación
arrow(f'M1450 {Y3+H3/2} L1472 {Y3+H3/2} L1472 76 L735 76 L735 {Y1-2}',color='#0f6e4f',w=3.5,marker='g')
label(1100,76,'cada cierre actualiza la estadística al instante: el sistema aprende de lo que pasó',bg='#e6f4ee',fill='#0f6e4f',w=520)

# leyenda
ly=842
items=[('#e4edf6','#00508f','',  'Automático'),('#fff','#d6000e','','Decide una persona'),('#fdf0d9','#8a5200','','Aviso'),('#f0eefc','#6a3fb5','stroke-dasharray="5 4"','Simulado')]
x=40
for f,s,d,t in items:
    o.append(f'<rect x="{x}" y="{ly}" width="26" height="18" rx="5" fill="{f}" stroke="{s}" stroke-width="2" {d}/>'); text(x+36,ly+14,t,14,600,'#33495f','start'); x+=len(t)*8+80
text(1460,ly+14,'Si dos personas actúan a la vez: gana una, la otra recibe aviso claro (docs/CASOS_BORDE.md)',14,600,'#33495f','end')
o.append('</svg>')
open('../img/funcionamiento.svg','w',encoding='utf8').write('\n'.join(o))

# PNG opcional (necesita playwright): python funcionamiento_gen.py
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={'width': W, 'height': H}, device_scale_factor=2)
        import pathlib; pg.goto(pathlib.Path('../img/funcionamiento.svg').resolve().as_uri()); pg.screenshot(path='../img/funcionamiento.png'); b.close()
except Exception as e:  # sin playwright solo se actualiza el SVG
    print('PNG no regenerado:', e)
