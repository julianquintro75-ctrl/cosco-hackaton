import { I18n } from '../i18n/i18n.service';
import { Tablas } from '../core/modelos';

/** Puntualidad mensual por proveedor a partir de los servicios entregados (meses con menos de 5 servicios quedan en blanco). */
export function mensual(servicios: Tablas['servicios'], i18n: I18n) {
  const por = new Map<string, Map<string, { ok: number; n: number }>>();
  const meses = new Set<string>();
  for (const s of servicios) {
    if (s.estado !== 'ENTREGADO' || !s.entrega_real || s.a_tiempo == null) continue;
    const m = s.entrega_real.slice(0, 7); meses.add(m);
    const pm = por.get(s.proveedor_id) ?? new Map(); por.set(s.proveedor_id, pm);
    const a = pm.get(m) ?? { ok: 0, n: 0 }; a.n++; a.ok += s.a_tiempo ? 1 : 0; pm.set(m, a);
  }
  const orden = [...meses].sort();
  const porProveedor: Record<string, (number | null)[]> = {};
  for (const [p, pm] of por) porProveedor[p] = orden.map(m => { const a = pm.get(m); return a && a.n >= 5 ? a.ok / a.n : null; });
  return { meses: orden, etiquetas: orden.map(m => i18n.mes(m + '-01')), porProveedor };
}
