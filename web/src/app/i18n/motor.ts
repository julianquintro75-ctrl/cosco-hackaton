import type { I18n } from './i18n.service';

/**
 * El motor redacta sus explicaciones en español con plantillas fijas. Aquí se reconocen esas plantillas y se
 * vuelven a escribir en el idioma de la persona, con cifras y dinero formateados según su idioma.
 * Lo que no coincide con ninguna plantilla se muestra tal cual (no se inventa una traducción).
 */
type L = 'en' | 'zh';
type Regla = [RegExp, (m: RegExpMatchArray, a: Ayuda) => Record<L, string>];
interface Ayuda { $: (s: string) => string; comp: (s: string) => string; carga: (s: string) => string; n: (s: string) => string }

const CARGA: Record<string, Record<L, string>> = {
  general: { en: 'general', zh: '普通货物' }, refrigerada: { en: 'refrigerated', zh: '冷藏货物' },
  peligrosa: { en: 'hazardous', zh: '危险品' }, sobredimensionada: { en: 'oversized', zh: '超限货物' },
};
const COMP: Record<string, string> = {
  'Precio': 'precio', 'precio': 'precio', 'Retraso esperado': 'retraso_esperado', 'retraso esperado': 'retraso_esperado',
  'Incidente esperado': 'incidente_esperado', 'incidente esperado': 'incidente_esperado', 'Incertidumbre (poca evidencia)': 'incertidumbre',
  'incertidumbre (poca evidencia)': 'incertidumbre', 'Concentración': 'concentracion', 'concentración': 'concentracion',
};
const NIVEL: Record<string, string> = { Flexible: 'Flexible', Estandar: 'Estándar', Urgente: 'Urgente' };

const REGLAS: Regla[] = [
  // ---- alertas por proveedor
  [/^Sin historial en este corredor y carga: estimación con respaldo «(.+)»$/, m => ({ en: `No history on this corridor and cargo type: estimate uses fallback “${m[1]}”`, zh: `该线路和货物类型无历史记录：估算采用“${m[1]}”作为后备` })],
  [/^Poco historial: (\d+) servicios en el corredor$/, (m, a) => ({ en: `Little history: ${a.n(m[1])} services on this corridor`, zh: `历史较少：该线路仅 ${a.n(m[1])} 次服务` })],
  [/^Tendencia a empeorar: retrasos de los últimos (\d+) días \+(\d+) pts frente a su año anterior$/, (m, a) => ({ en: `Getting worse: delays in the last ${m[1]} days up ${a.n(m[2])} pts vs. its previous year`, zh: `呈恶化趋势：近 ${m[1]} 天延误率较上一年上升 ${a.n(m[2])} 个百分点` })],
  [/^Plazo en riesgo: P90 del tránsito (\d+) h > plazo (\d+) h$/, (m, a) => ({ en: `Deadline at risk: P90 transit ${a.n(m[1])} h > deadline ${a.n(m[2])} h`, zh: `期限有风险：P90 运输时间 ${a.n(m[1])} 小时 > 期限 ${a.n(m[2])} 小时` })],
  [/^Concentración: (\d+) % del volumen de (\d+) días$/, (m, a) => ({ en: `Concentration: ${a.n(m[1])} % of the volume of the last ${m[2]} days`, zh: `集中度：近 ${m[2]} 天业务量的 ${a.n(m[1])}%` })],
  [/^Capacidad no confirmada: sin reporte del proveedor$/, () => ({ en: 'Capacity unconfirmed: the provider has not reported', zh: '运力未确认：供应商未上报' })],
  [/^Capacidad no confirmada: último reporte hace (\d+) días$/, (m, a) => ({ en: `Capacity unconfirmed: last report ${a.n(m[1])} days ago`, zh: `运力未确认：上次上报在 ${a.n(m[1])} 天前` })],
  [/^Capacidad justa: 1 unidad disponible$/, () => ({ en: 'Tight capacity: 1 unit available', zh: '运力紧张：仅 1 辆可用' })],
  // ---- factores clave
  [/^Único proveedor factible$/, () => ({ en: 'Only feasible provider', zh: '唯一可行的供应商' })],
  [/^Costo esperado (\$[\d.]+) (menor|mayor) que #(\d) \((.+)\)$/, (m, a) => ({ en: `Expected cost ${a.$(m[1])} ${m[2] === 'menor' ? 'lower' : 'higher'} than #${m[3]} (${m[4]})`, zh: `预期成本比第 ${m[3]} 名（${m[4]}）${m[2] === 'menor' ? '低' : '高'} ${a.$(m[1])}` })],
  [/^(Precio|Retraso esperado|Incidente esperado|Incertidumbre \(poca evidencia\)|Concentración): (\$[\d.]+) (menos|más) que #(\d) \((.+)\)$/, (m, a) => ({ en: `${a.comp(m[1])}: ${a.$(m[2])} ${m[3] === 'menos' ? 'less' : 'more'} than #${m[4]} (${m[5]})`, zh: `${a.comp(m[1])}：比第 ${m[4]} 名（${m[5]}）${m[3] === 'menos' ? '少' : '多'} ${a.$(m[2])}` })],
  // ---- descartados
  [/^activo desde (.+)$/, m => ({ en: `active since ${m[1]}`, zh: `自 ${m[1]} 起启用` })],
  [/^no cubre el corredor (\w+)$/, m => ({ en: `does not cover corridor ${m[1]}`, zh: `不覆盖线路 ${m[1]}` })],
  [/^no tiene (\w+) en su flota$/, m => ({ en: `has no ${m[1]} in its fleet`, zh: `车队中没有 ${m[1]}` })],
  [/^sin tarifa vigente para (\w+) en (\w+)$/, m => ({ en: `no current rate for ${m[1]} on ${m[2]}`, zh: `${m[2]} 线路无 ${m[1]} 的现行运价` })],
  [/^le falta (.+)$/, m => ({ en: `missing ${m[1]}`, zh: `缺少 ${m[1]}` })],
  [/^0 unidades (\w+) en el reporte del (.+)$/, m => ({ en: `0 ${m[1]} units in the ${m[2]} report`, zh: `${m[2]} 的上报中 ${m[1]} 可用数为 0` })],
  // ---- explicación (por oraciones)
  [/^Se recomienda (.+) con costo esperado (\$[\d.]+) y P\(a tiempo\) (\d+)% \((\d+) servicios en el corredor\)\.$/, (m, a) => ({
    en: `${m[1]} is recommended, with an expected cost of ${a.$(m[2])} and ${a.n(m[3])}% on-time probability (${a.n(m[4])} services on this corridor).`,
    zh: `推荐 ${m[1]}：预期成本 ${a.$(m[2])}，准时概率 ${a.n(m[3])}%（该线路 ${a.n(m[4])} 次服务）。` })],
  [/^Supera a (.+) por (\$[\d.]+), sobre todo por (.+) \((\$[\d.]+)\)\.$/, (m, a) => ({
    en: `It beats ${m[1]} by ${a.$(m[2])}, mainly on ${a.comp(m[3]).toLowerCase()} (${a.$(m[4])}).`,
    zh: `比 ${m[1]} 低 ${a.$(m[2])}，主要来自${a.comp(m[3])}（${a.$(m[4])}）。` })],
  [/^El más barato \((.+), (\$[\d.]+)\) sale más caro en costo esperado por su riesgo de retraso o incertidumbre\.$/, (m, a) => ({
    en: `The cheapest (${m[1]}, ${a.$(m[2])}) costs more in expected terms because of its delay risk or uncertainty.`,
    zh: `价格最低的 ${m[1]}（${a.$(m[2])}）因延误风险或不确定性，预期成本反而更高。` })],
  [/^Nivel (\w+): un retraso cuesta (\$[\d.]+)\.$/, (m, a) => ({ en: `${NIVEL[m[1]] === 'Estándar' ? 'Standard' : m[1] === 'Urgente' ? 'Urgent' : 'Flexible'} level: a delay costs ${a.$(m[2])}.`, zh: `${m[1] === 'Flexible' ? '灵活' : m[1] === 'Urgente' ? '加急' : '标准'}等级：延误成本 ${a.$(m[2])}。` })],
  [/^Ningún proveedor puede atender la solicitud: (\d+) descartados por reglas duras\.$/, (m, a) => ({ en: `No provider can serve this request: ${a.n(m[1])} discarded by hard rules.`, zh: `没有供应商能承接该请求：${a.n(m[1])} 家因硬性规则被排除。` })],
  [/^Se requiere gestión de la excepción \(vehículo alterno, dividir la carga o mover la fecha\)\.$/, () => ({ en: 'This exception needs handling (alternative vehicle, splitting the load or moving the date).', zh: '需要人工处理该例外（更换车型、拆分货物或调整日期）。' })],
  // ---- sugerencia de prueba
  [/^(.+) tiene solo (\d+) servicios en este corredor; asignarle este servicio Flexible de bajo riesgo cuesta (\$[\d.]+) más en costo esperado y ayudaría a evaluarlo\. Decide la persona\.$/, (m, a) => ({
    en: `${m[1]} has only ${a.n(m[2])} services on this corridor. Giving it this low-risk Flexible service costs ${a.$(m[3])} more in expected cost and would help evaluate it. You decide.`,
    zh: `${m[1]} 在该线路仅有 ${a.n(m[2])} 次服务。把这单低风险的灵活服务交给它，预期成本多 ${a.$(m[3])}，有助于评估其表现。由您决定。` })],
  // ---- fichas: fortalezas, debilidades, riesgos
  [/^(\w+) · (\w+): puntualidad (\d+)%, (-?\d+) pts sobre su promedio y (-?\d+) pts sobre el mercado \((\d+) servicios\)$/, (m, a) => ({
    en: `${m[1]} · ${a.carga(m[2])}: ${m[3]}% on time, ${m[4]} pts above its average and ${m[5]} pts above the market (${a.n(m[6])} services)`,
    zh: `${m[1]} · ${a.carga(m[2])}：准时率 ${m[3]}%，比自身平均高 ${m[4]} 个百分点，比市场高 ${m[5]} 个百分点（${a.n(m[6])} 次服务）` })],
  [/^(\w+) · (\w+): puntualidad (\d+)% \((\d+) servicios\)$/, (m, a) => ({ en: `${m[1]} · ${a.carga(m[2])}: ${m[3]}% on time (${a.n(m[4])} services)`, zh: `${m[1]} · ${a.carga(m[2])}：准时率 ${m[3]}%（${a.n(m[4])} 次服务）` })],
  [/^(\w+) · (\w+): puntualidad (\d+)%, (-?\d+) pts bajo su promedio(?: y (-?\d+) pts bajo el mercado)? \((\d+) servicios\)$/, (m, a) => ({
    en: `${m[1]} · ${a.carga(m[2])}: ${m[3]}% on time, ${m[4]} pts below its average${m[5] ? ` and ${m[5]} pts below the market` : ''} (${a.n(m[6])} services)`,
    zh: `${m[1]} · ${a.carga(m[2])}：准时率 ${m[3]}%，比自身平均低 ${m[4]} 个百分点${m[5] ? `，比市场低 ${m[5]} 个百分点` : ''}（${a.n(m[6])} 次服务）` })],
  [/^Puntualidad en caída: retrasos de los últimos (\d+) días (-?\d+) pts por encima de su año anterior \(significativo\)$/, (m, a) => ({
    en: `On-time rate falling: delays in the last ${m[1]} days are ${m[2]} pts above its previous year (significant)`, zh: `准时率下降：近 ${m[1]} 天延误率比上一年高 ${m[2]} 个百分点（显著）` })],
  [/^Temporada de lluvias en el Pacífico: puntualidad (\d+) pts menor \((\d+) servicios en lluvia\)$/, (m, a) => ({
    en: `Pacific rainy season: on-time rate ${m[1]} pts lower (${a.n(m[2])} services in the rain)`, zh: `太平洋雨季：准时率低 ${m[1]} 个百分点（雨季 ${a.n(m[2])} 次服务）` })],
  [/^Concentración: (\d+)% del volumen de los últimos (\d+) días$/, m => ({ en: `Concentration: ${m[1]}% of the volume in the last ${m[2]} days`, zh: `集中度：近 ${m[2]} 天业务量的 ${m[1]}%` })],
  [/^Rechazos recientes: (\d+)% de las órdenes de 30 días$/, m => ({ en: `Recent rejections: ${m[1]}% of the last 30 days of orders`, zh: `近期拒单：近 30 天订单的 ${m[1]}%` })],
  [/^Incidentes recientes: (\d+) en los últimos 30 días$/, m => ({ en: `Recent incidents: ${m[1]} in the last 30 days`, zh: `近期事故：近 30 天 ${m[1]} 起` })],
  [/^Capacidad casi agotada en (\w+): (\d+) de (\d+) unidades$/, m => ({ en: `Capacity almost exhausted on ${m[1]}: ${m[2]} of ${m[3]} units`, zh: `${m[1]} 运力几乎耗尽：${m[3]} 辆中仅 ${m[2]} 辆可用` })],
];

export function traducir(texto: string | null | undefined, i18n: I18n): string {
  if (!texto) return '';
  const id = i18n.idioma();
  if (id === 'es') return texto;
  const L = id as L;
  const a: Ayuda = {
    $: s => i18n.cop(Number(s.replace(/[^\d]/g, ''))),
    comp: s => i18n.t('comp.' + (COMP[s] ?? COMP[s.charAt(0).toUpperCase() + s.slice(1)] ?? 'precio')),
    carga: s => CARGA[s]?.[L] ?? s,
    n: s => i18n.num(Number(s)),
  };
  const oraciones = texto.split(/(?<=\.)\s+(?=[A-ZÁÉÍÓÚ])/);
  return oraciones.map(o => {
    for (const [re, f] of REGLAS) { const m = o.match(re); if (m) return f(m, a)[L]; }
    return o;
  }).join(L === 'zh' ? '' : ' ');
}

export function cargaTexto(tipo: string, i18n: I18n): string {
  const id = i18n.idioma();
  return id === 'es' ? tipo : (CARGA[tipo]?.[id as L] ?? tipo);
}
