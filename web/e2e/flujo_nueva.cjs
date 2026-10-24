/* Prueba de punta a punta: solicitud nueva, devolución al solicitante, repetir un envío y decisión final.
     WEB=http://localhost:4200 PASS='Cosco-2026!' node web/e2e/flujo_nueva.cjs      (pila arriba y base sin decisiones previas) */
const { chromium } = require('playwright');
const WEB = process.env.WEB || 'http://localhost:4200', PASS = process.env.PASS || 'Cosco-2026!', SHOTS = process.env.SHOTS || '/tmp';
let fallos = 0;
const ok = (c, m) => { if (!c) fallos++; console.log((c ? 'OK   ' : 'FALLA') + ' ' + m); };
const login = async (p, u) => { await p.goto(WEB + '/login'); await p.fill('#usuario', u); await p.fill('#clave', PASS); await p.click('button[type=submit]'); await p.waitForURL('**/recomendar'); };
const txt = async p => (await p.innerText('main')).replace(/\n+/g, ' | ');
(async () => {
  const b = await chromium.launch();
  const mk = async () => { const c = await b.newContext({ viewport: { width: 1280, height: 1000 }, locale: 'es-CO' }); const p = await c.newPage();
    p.on('pageerror', e => console.log('PAGEERROR', e.message.slice(0, 200))); p.post = []; p.on('response', r => { if (r.request().method() === 'POST' && r.url().includes(':8000')) p.post.push(r.url().split(':8000')[1] + ' ' + r.status()); }); return p; };

  // 1) comercial crea una solicitud urgente desde el formulario
  let c = await mk(); await login(c, 'comercial'); await c.goto(WEB + '/nueva'); await c.waitForSelector('text=Llenar con un ejemplo');
  ok(await c.locator('button[type=submit]').isDisabled(), 'formulario vacío: no se puede enviar');
  await c.click('text=Llenar con un ejemplo'); await c.fill('#n-peso', '99'); await c.waitForTimeout(300);
  ok(/Supera la capacidad/.test(await txt(c)) && await c.locator('button[type=submit]').isDisabled(), 'peso excesivo: error y envío bloqueado');
  await c.fill('#n-peso', '22'); await c.click('button[role=radio]:has-text("Urgente")');
  c.post.length = 0; await c.click('button[type=submit]'); await c.waitForURL('**/recomendar/W*', { timeout: 20000 }); await c.waitForTimeout(3500);
  const sid1 = c.url().split('/').pop(); ok(/^W\d{8}-/.test(sid1), 'nueva solicitud creada: ' + sid1);
  ok(c.post.filter(x => x.startsWith('/solicitudes')).length === 1, 'un solo POST /solicitudes');
  const t1 = await txt(c); ok(/Top|Aprobar|proveedor/i.test(t1) && !/Aprobar/.test(t1), 'comercial ve la recomendación sin botones de decisión');
  await c.screenshot({ path: SHOTS + '/n_com_recomendacion.png' });

  // 2) doble clic: una sola solicitud
  await c.goto(WEB + '/nueva'); await c.click('text=Llenar con un ejemplo'); await c.fill('#n-peso', '18'); await c.waitForSelector('button[type=submit]:not([disabled])'); c.post.length = 0;
  await c.dblclick('button[type=submit]'); await c.waitForURL('**/recomendar/W*', { timeout: 20000 }); await c.waitForTimeout(2500);
  const sid2 = c.url().split('/').pop();
  await c.goto(WEB + '/solicitudes'); await c.waitForTimeout(1500);
  const filas = await c.locator('li.fila').count(); ok(filas === 2, `doble clic: sigue habiendo 2 solicitudes (hay ${filas})`);

  // 3) operador la devuelve
  let o = await mk(); await login(o, 'operador'); await o.goto(WEB + '/pendientes'); await o.waitForTimeout(2500);
  ok(new RegExp(sid1).test(await txt(o)), 'operador ve la solicitud urgente en Pendientes');
  await o.goto(WEB + '/recomendar/' + sid1); await o.waitForTimeout(3500);
  await o.click('button:has-text("Devolver al solicitante")'); await o.selectOption('#motdev', 'datos_incompletos');
  await o.fill('#notadev', 'Falta confirmar la bodega de entrega'); await o.screenshot({ path: SHOTS + '/n_op_devolver.png' });
  await o.click('button:has-text("Devolver solicitud")'); await o.waitForTimeout(1500);
  ok(/devuelta al solicitante por operador/.test(await txt(o)) && !/Aprobar/.test(await txt(o)), 'operador devuelve: aviso y sin botones de decisión');
  await o.goto(WEB + '/pendientes'); await o.waitForTimeout(2000); ok(!new RegExp(sid1).test(await txt(o)), 'la devuelta sale de Pendientes');

  // 4) comercial ve el motivo y crea una nueva con los mismos datos
  await c.goto(WEB + '/solicitudes'); await c.waitForTimeout(1500); const ts = await txt(c);
  ok(/Devuelta/.test(ts) && /Datos incompletos/.test(ts) && /bodega de entrega/.test(ts), 'comercial ve «Devuelta», el motivo y la nota');
  await c.screenshot({ path: SHOTS + '/n_com_devuelta.png' });
  await c.click('a:has-text("Crear una nueva con estos datos")'); await c.waitForURL('**/nueva?desde=*'); await c.waitForTimeout(1500);
  ok(await c.inputValue('#n-peso') === '22', 'el formulario viene prellenado con los datos de la devuelta');
  await c.click('button[role=radio]:has-text("Estándar")'); await c.click('button[type=submit]'); await c.waitForURL('**/recomendar/W*', { timeout: 20000 }); await c.waitForTimeout(3000);
  const sid3 = c.url().split('/').pop(); ok(sid3 !== sid1, 'nueva solicitud corregida: ' + sid3);

  // 5) operador la aprueba; el comercial la ve decidida
  await o.goto(WEB + '/recomendar/' + sid3); await o.waitForTimeout(3500);
  await o.locator('button:has-text("Aprobar")').first().click(); await o.waitForTimeout(1500); ok(/registrad/i.test(await txt(o)), 'operador aprueba la corregida');
  await c.goto(WEB + '/solicitudes'); await c.waitForTimeout(1500); ok(/Decidida/.test(await txt(c)), 'comercial ve «Decidida»');
  await c.screenshot({ path: SHOTS + '/n_com_final.png' });
  await b.close(); console.log(fallos ? `\n${fallos} FALLA(S)` : '\nTodo OK'); process.exit(fallos ? 1 : 0);
})();
