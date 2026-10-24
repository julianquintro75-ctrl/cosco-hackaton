/* Prueba de punta a punta del flujo por roles (navegador real). Requiere la pila arriba (docker compose up) y Playwright:
     npm i -D playwright && npx playwright install chromium
     WEB=http://localhost:4200 PASS='Cosco-2026!' node web/e2e/flujo_roles.cjs
   Usa solicitudes de la fase de prueba de la semilla 7: R005907 (escalada), R005910 (revisión por «urgente»). */
const { chromium } = require('playwright');
const WEB = process.env.WEB || 'http://localhost:4200', PASS = process.env.PASS || 'Cosco-2026!';
let posts = 0;
const login = async (p, u) => { await p.goto(WEB + '/login'); await p.fill('#usuario', u); await p.fill('#clave', PASS); await p.click('button[type=submit]'); await p.waitForURL('**/recomendar'); };
const txt = async p => (await p.innerText('main')).replace(/\n+/g,' | ');
const ok = (c, m) => console.log((c ? 'OK   ' : 'FALLA') + ' ' + m);
(async () => {
  const b = await chromium.launch();
  const mk = async () => { const c = await b.newContext({ viewport: {width:1280,height:1000}, locale:'es-CO' }); const p = await c.newPage();
    p.on('pageerror', e => console.log('PAGEERROR', e.message.slice(0,200)));
    p.on('response', r => { if (r.url().includes(':8000') && r.request().method()==='POST' && r.url().endsWith('/recomendar')) posts++; });
    return p; };
  // comercial pide una escalada y una de revisión
  let p = await mk(); await login(p, 'comercial');
  for (const sid of ['R005907', 'R005910']) {
    posts = 0; await p.goto(WEB + '/recomendar/' + sid); await p.waitForSelector('text=Top-3', { timeout: 15000 }).catch(()=>{});
    await p.waitForTimeout(2500);
    const t = await txt(p); ok(/Aprobar/.test(t) === false, `comercial ${sid}: sin botones de decisión`); ok(posts === 1, `comercial ${sid}: 1 sola llamada a /recomendar (hubo ${posts})`);
    await p.screenshot({ path: `/tmp/f_com_${sid}.png`, fullPage: false });
  }
  await p.goto(WEB + '/solicitudes'); await p.waitForTimeout(1500); const ts = await txt(p); ok(/R005907/.test(ts) && /R005910/.test(ts), 'comercial ve sus 2 solicitudes: ' + ts.slice(0,160));
  // operador
  p = await mk(); await login(p, 'operador');
  await p.goto(WEB + '/pendientes'); await p.waitForTimeout(2000); let tp = await txt(p); ok(!/Cargando/.test(tp), 'operador: pendientes cargan'); console.log('   ', tp.slice(0,260));
  await p.screenshot({ path: '/tmp/f_op_pend.png' });
  const abrir = p.locator('a:has-text("Abrir caso")').first();
  if (await abrir.count()) { posts = 0; await abrir.click(); await p.waitForTimeout(5000); const tc = await txt(p); ok(posts === 1, `operador abrir caso: 1 llamada a /recomendar (hubo ${posts})`); ok(!/Cargando/.test(tc), 'operador: el caso abre'); await p.screenshot({ path: '/tmp/f_op_caso.png' }); console.log('   ', tc.slice(0,200)); }
  ok(/R005910/.test(tp), 'operador ve R005910 en "Para revisar"');
  await p.goto(WEB + '/recomendar/R005910'); await p.waitForTimeout(3500);
  await p.locator('button:has-text("Aprobar")').first().click(); await p.waitForTimeout(1500); ok(/registrad/i.test(await txt(p)), 'operador aprueba un caso de revisión');
  await p.goto(WEB + '/recomendar/R005907'); await p.waitForTimeout(3500); const te = await txt(p); ok(/solo gerencia|only management|只有管理层/i.test(te) && !/Aprobar/.test(te), 'operador en escalado: aviso y sin botones');
  // gerencia decide el escalado
  p = await mk(); await login(p, 'jurado');
  await p.goto(WEB + '/pendientes'); await p.waitForTimeout(1500);
  await p.click('button[role=radio]:has-text("Escalados")'); await p.waitForTimeout(1500); const tg = await txt(p); ok(/R005907/.test(tg), 'gerencia ve R005907 en escalados');
  await p.goto(WEB + '/recomendar/R005907'); await p.waitForTimeout(3500);
  await p.locator('button:has-text("Aprobar")').first().click(); await p.waitForTimeout(1500); const td = await txt(p); ok(/registrad/i.test(td), 'gerencia aprueba y queda registrado'); await p.screenshot({ path: '/tmp/f_ger_dec.png' });
  await p.goto(WEB + '/solicitudes'); await p.waitForTimeout(1500); ok(/Decidida/.test(await txt(p)), 'solicitudes muestra "Decidida"');
  await p.goto(WEB + '/avisos'); await p.waitForTimeout(1500); console.log('   avisos:', (await txt(p)).slice(0,120));
  await b.close();
})();
