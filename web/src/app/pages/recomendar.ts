import { Component, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { Api } from '../core/api';
import { Auth } from '../core/auth';
import { Devolucion, Evaluado, MotivoDevolucion, Nivel, Recomendacion, Solicitud, Tablas } from '../core/modelos';
import { I18n } from '../i18n/i18n.service';
import { cargaTexto, traducir } from '../i18n/motor';
import { Icono } from '../shared/icono';
import { DesgloseBarra } from '../shared/desglose';

const NIVELES: Nivel[] = ['Flexible', 'Estandar', 'Urgente'];
const MOTIVOS_DEV: MotivoDevolucion[] = ['datos_incompletos', 'sin_viabilidad_comercial', 'cliente_cancelo', 'precio_fuera_de_rango', 'otro'];
const MOTIVOS = ['precio', 'relacion', 'capacidad', 'experiencia_previa', 'cliente_pidio', 'otro'] as const;

@Component({
  selector: 'app-recomendar',
  imports: [FormsModule, RouterLink, Icono, DesgloseBarra],
  templateUrl: './recomendar.html',
  styleUrl: './recomendar.css',
})
export class Recomendar {
  i18n = inject(I18n);
  private api = inject(Api);
  private auth = inject(Auth);
  sid = input<string>();

  tablas = signal<Tablas | null>(null);
  solicitudes = signal<Solicitud[]>([]);
  cargaError = signal(false);
  buscar = signal('');
  elegida = signal<string>('');
  nivel = signal<Nivel>('Estandar');
  rec = signal<Recomendacion | null>(null);
  calculando = signal(false);
  error = signal('');
  abiertos = signal<Set<string>>(new Set());
  eligiendo = signal<string | null>(null);
  motivo = signal<string>('');
  enviando = signal(false);
  registrada = signal<{ acepto: boolean } | null>(null);
  previa = signal<{ usuario: string } | null>(null);
  niveles = NIVELES; motivos = MOTIVOS; motivosDev = MOTIVOS_DEV;
  devuelta = signal<Devolucion | null>(null);
  devolviendo = signal(false);
  motivoDev = signal<MotivoDevolucion | ''>('');
  notaDev = signal('');

  filtradas = computed(() => {
    const q = this.buscar().trim().toLowerCase();
    const l = this.solicitudes();
    const f = q ? l.filter(s => this.etiqueta(s).toLowerCase().includes(q) || this.nombreCliente(s.cliente_id).toLowerCase().includes(q)) : l;
    return f.slice(0, 80);
  });
  actual = computed(() => this.solicitudes().find(s => s.solicitud_id === this.elegida()) ?? null);
  maxCosto = computed(() => Math.max(0, ...(this.rec()?.ranking.map(r => r.costo_esperado) ?? [0])));
  /** Tabla comparativa: una fila por criterio, una columna por proveedor; marca el mejor valor de cada fila. */
  filas = computed(() => {
    const r = this.rec()?.ranking ?? [];
    if (!r.length) return [];
    const i = this.i18n;
    type F = { k: string; sub?: boolean; celdas: { t: string; s?: string; mejor: boolean; neg?: boolean }[] };
    const mk = (k: string, v: (p: Evaluado) => number | null, fmt: (p: Evaluado) => string, menor: boolean, sub?: (p: Evaluado) => string | undefined, esSub = false): F | null => {
      const vals = r.map(v);
      if (vals.every(x => x == null)) return null;
      const num = vals.filter((x): x is number => x != null);
      const mejor = menor ? Math.min(...num) : Math.max(...num);
      const hayDif = new Set(num).size > 1;
      return { k, sub: esSub, celdas: r.map((p, j) => ({ t: vals[j] == null ? '—' : fmt(p), s: sub?.(p), mejor: hayDif && vals[j] === mejor, neg: k === 'cmp.margen' && (vals[j] ?? 0) < 0 })) };
    };
    const base = r[0].costo_esperado;
    const dif = (p: Evaluado) => (p.posicion === 1 ? undefined : '+' + i.cop(p.costo_esperado - base) + ' ' + i.t('cmp.vsPrimero'));
    const comp = (k: keyof Evaluado['desglose']) => mk('comp.' + k, p => p.desglose[k], p => i.cop(p.desglose[k]), true, undefined, true);
    return [
      mk('rec.costoEsperado', p => p.costo_esperado, p => i.cop(p.costo_esperado), true, dif),
      comp('precio'), comp('retraso_esperado'), comp('incidente_esperado'), comp('incertidumbre'), comp('concentracion'),
      mk('rec.aTiempo', p => p.p_a_tiempo, p => this.pDec(p.p_a_tiempo), false, p => `${i.t('rec.ic90')} ${this.pDec(p.ic90_p_a_tiempo[0])}–${this.pDec(p.ic90_p_a_tiempo[1])}`),
      mk('rec.transito', p => p.transito_p50_h, p => `${i.num(p.transito_p50_h, 0)} ${i.t('c.horas')}`, true, p => i.t('cmp.pesimista', { p90: i.num(p.transito_p90_h, 0) })),
      mk('rec.margen', p => p.margen_esperado, p => i.cop(p.margen_esperado), false),
      mk('rec.capacidad', p => p.capacidad_unidades, p => String(p.capacidad_unidades), false),
      mk('cmp.servicios', p => p.n_servicios_corredor, p => String(p.n_servicios_corredor), false),
      mk('rec.dureza', p => p.indice_dureza, p => (p.banda_dureza ? i.t('banda.' + p.banda_dureza) + ' ' : '') + i.num(p.indice_dureza ?? 0, 1), false),
    ].filter((f): f is F => f != null);
  });
  /** Una frase que dice por qué el #1 quedó sobre el #2, en pesos y por componente. */
  porQue = computed(() => {
    const r = this.rec()?.ranking ?? [];
    if (r.length < 2) return '';
    const [a, b] = r, i = this.i18n;
    const d = (k: keyof Evaluado['desglose']) => a.desglose[k] - b.desglose[k];
    const parte = (n: number, c: string) => (Math.round(n) === 0 ? '' : i.t(n > 0 ? 'cmp.mas' : 'cmp.menos', { v: i.cop(Math.abs(n)), c }));
    const partes = [parte(d('precio'), i.t('comp.precio').toLowerCase()), parte(d('retraso_esperado'), i.t('comp.retraso_esperado').toLowerCase()),
      parte(d('incidente_esperado') + d('incertidumbre') + d('concentracion'), i.t('cmp.resto'))].filter(Boolean);
    return i.t('cmp.porQue', { a: a.nombre, b: b.nombre, x: i.cop(b.costo_esperado - a.costo_esperado), d: partes.join('; ') });
  });
  estado = computed<'ok' | 'ambar' | 'rojo'>(() => { const r = this.rec(); return !r || !r.ranking.length || r.escalar_gerencia ? 'rojo' : r.requiere_revision ? 'ambar' : 'ok'; });
  /** Solo operador y gerencia deciden; lo escalado a gerencia lo decide únicamente gerencia. */
  puedeDecidir = computed(() => { const r = this.auth.rol(); return r === 'gerencia' || (r === 'operador' && !this.rec()?.escalar_gerencia); });
  esSolicitante = computed(() => this.auth.rol() === 'solicitante');
  costoRetraso = signal<Record<string, number>>({});

  constructor() {
    this.cargar();
    // Solo reacciona a cambios de la ruta o a que lleguen las solicitudes. El resto va «untracked»: si no, elegir() y recomendar()
    // leen y escriben señales dentro del efecto y lo vuelven a disparar sin fin (pedía /recomendar en bucle).
    effect(() => { const s = this.sid(); const hay = this.solicitudes().length > 0; if (s && hay) untracked(async () => { await this.asegurar(s); this.elegir(s); this.recomendar(); }); });
  }

  async cargar() {
    this.cargaError.set(false);
    try {
      const [t, s, c] = await Promise.all([this.api.tablasLigeras(), this.api.solicitudesPrueba(), this.api.config()]);
      this.tablas.set(t); this.costoRetraso.set(c['costo_retraso'] ?? {});
      this.solicitudes.set(s);
      if (!this.elegida() && !this.sid() && s.length) this.elegir(s[0].solicitud_id);
    } catch { this.cargaError.set(true); }
  }

  /** Las solicitudes nuevas no están en la lista de prueba: se piden por su identificador y se suman a la lista. */
  private async asegurar(id: string) {
    if (this.solicitudes().some(x => x.solicitud_id === id)) return;
    try { const s = await this.api.solicitud(id); this.solicitudes.update(l => [s, ...l]); } catch { /* si no existe, el selector queda como estaba */ }
  }

  etiqueta(s: Solicitud) { return `${s.solicitud_id} · ${s.corredor_id} · ${s.tipo_vehiculo_req} · ${this.i18n.t('rec.nivel.' + s.nivel_servicio)}`; }
  nombreCliente(id: string) { return this.tablas()?.cliente.find(c => c.cliente_id === id)?.nombre ?? id; }
  corredor(id: string) { const c = this.tablas()?.corredor.find(x => x.corredor_id === id); return c ? `${id} · ${c.origen} → ${c.destino}` : id; }
  vehiculo(id: string) { return this.tablas()?.tipo_vehiculo.find(v => v.tipo_vehiculo_id === id)?.nombre ?? id; }
  nombreProv(id: string) { return this.tablas()?.proveedor.find(p => p.proveedor_id === id)?.nombre ?? id; }

  elegir(id: string) {
    this.elegida.set(id);
    const s = this.solicitudes().find(x => x.solicitud_id === id);
    if (s) this.nivel.set(s.nivel_servicio);
    this.rec.set(null); this.error.set(''); this.registrada.set(null); this.previa.set(null); this.devuelta.set(null); this.devolviendo.set(false); this.eligiendo.set(null); this.abiertos.set(new Set());
  }

  async recomendar() {
    const s = this.actual(); if (!s || this.calculando()) return;
    this.calculando.set(true); this.error.set(''); this.registrada.set(null); this.eligiendo.set(null);
    try {
      const dev = await this.api.devolucionDe(s.solicitud_id).catch(() => null);
      if (dev) { this.devuelta.set(dev); this.previa.set(null); return; }       // devuelta al solicitante: no se recalcula
      const [r, d] = await Promise.all([this.api.recomendar(s, this.nivel()), this.api.decisionDe(s.solicitud_id).catch(() => null)]);
      this.rec.set(r); this.previa.set(d ? { usuario: d.usuario } : null);
    } catch (e) { this.error.set(this.mensaje(e)); } finally { this.calculando.set(false); }
  }

  alternar(id: string) { const n = new Set(this.abiertos()); n.has(id) ? n.delete(id) : n.add(id); this.abiertos.set(n); }

  pedirMotivo(pid: string) { this.eligiendo.set(pid); this.motivo.set(''); }

  async aprobar() { const r = this.rec(); if (r?.ranking.length) await this.decidir(r.ranking[0].proveedor_id, null); }
  async confirmar() { const p = this.eligiendo(); if (p && this.motivo()) await this.decidir(p, this.motivo()); }

  async confirmarDevolucion() {
    const r = this.rec(), m = this.motivoDev(); if (!r || !m || this.enviando()) return;
    if (m === 'otro' && !this.notaDev().trim()) return;
    this.enviando.set(true); this.error.set('');
    try {
      await this.api.devolver(r.solicitud_id, m, this.notaDev().trim() || null);
      this.devuelta.set({ solicitud_id: r.solicitud_id, usuario: this.auth.usuario()?.usuario ?? '', motivo: m, nota: this.notaDev().trim() || null, fecha: '' });
      this.devolviendo.set(false);
    } catch (e) { this.error.set(this.mensaje(e)); } finally { this.enviando.set(false); }
  }

  private async decidir(pid: string, motivo: string | null) {
    const r = this.rec(); if (!r || this.enviando()) return;
    this.enviando.set(true); this.error.set('');
    try {
      await this.api.decidir(r, pid, motivo);
      this.registrada.set({ acepto: motivo === null }); this.eligiendo.set(null);
    } catch (e) { this.error.set(this.mensaje(e)); } finally { this.enviando.set(false); }
  }

  private mensaje(e: unknown) {
    const h = e as HttpErrorResponse;
    const d = h?.error?.detail ?? h?.error?.error;
    return typeof d === 'string' ? d : this.i18n.t('c.errorDetalle');
  }
  tr = (s: string | null | undefined) => traducir(s, this.i18n);
  carga = (s: string) => cargaTexto(s, this.i18n);
  pDec = (p: number) => this.i18n.pct(p, 0);
}
