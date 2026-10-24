import { Component, computed, effect, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { Api } from '../core/api';
import { Auth } from '../core/auth';
import { Nivel, Recomendacion, Solicitud, Tablas } from '../core/modelos';
import { I18n } from '../i18n/i18n.service';
import { cargaTexto, traducir } from '../i18n/motor';
import { Icono } from '../shared/icono';
import { DesgloseBarra } from '../shared/desglose';

const NIVELES: Nivel[] = ['Flexible', 'Estandar', 'Urgente'];
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
  niveles = NIVELES; motivos = MOTIVOS;

  filtradas = computed(() => {
    const q = this.buscar().trim().toLowerCase();
    const l = this.solicitudes();
    const f = q ? l.filter(s => this.etiqueta(s).toLowerCase().includes(q) || this.nombreCliente(s.cliente_id).toLowerCase().includes(q)) : l;
    return f.slice(0, 80);
  });
  actual = computed(() => this.solicitudes().find(s => s.solicitud_id === this.elegida()) ?? null);
  maxCosto = computed(() => Math.max(0, ...(this.rec()?.ranking.map(r => r.costo_esperado) ?? [0])));
  estado = computed<'ok' | 'ambar' | 'rojo'>(() => { const r = this.rec(); return !r || !r.ranking.length || r.escalar_gerencia ? 'rojo' : r.requiere_revision ? 'ambar' : 'ok'; });
  /** Solo operador y gerencia deciden; lo escalado a gerencia lo decide únicamente gerencia. */
  puedeDecidir = computed(() => { const r = this.auth.rol(); return r === 'gerencia' || (r === 'operador' && !this.rec()?.escalar_gerencia); });
  esSolicitante = computed(() => this.auth.rol() === 'solicitante');
  costoRetraso = signal<Record<string, number>>({});

  constructor() {
    this.cargar();
    effect(() => { const s = this.sid(); if (s && this.solicitudes().length) { this.elegir(s); this.recomendar(); } });
  }

  async cargar() {
    this.cargaError.set(false);
    try {
      const [t, s, c] = await Promise.all([this.api.tablas(), this.api.solicitudesPrueba(), this.api.config()]);
      this.tablas.set(t); this.costoRetraso.set(c['costo_retraso'] ?? {});
      this.solicitudes.set(s);
      if (!this.elegida() && !this.sid() && s.length) this.elegir(s[0].solicitud_id);
    } catch { this.cargaError.set(true); }
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
    this.rec.set(null); this.error.set(''); this.registrada.set(null); this.previa.set(null); this.eligiendo.set(null); this.abiertos.set(new Set());
  }

  async recomendar() {
    const s = this.actual(); if (!s || this.calculando()) return;
    this.calculando.set(true); this.error.set(''); this.registrada.set(null); this.eligiendo.set(null);
    try {
      const [r, d] = await Promise.all([this.api.recomendar(s, this.nivel()), this.api.decisionDe(s.solicitud_id).catch(() => null)]);
      this.rec.set(r); this.previa.set(d ? { usuario: d.usuario } : null);
    } catch (e) { this.error.set(this.mensaje(e)); } finally { this.calculando.set(false); }
  }

  alternar(id: string) { const n = new Set(this.abiertos()); n.has(id) ? n.delete(id) : n.add(id); this.abiertos.set(n); }

  pedirMotivo(pid: string) { this.eligiendo.set(pid); this.motivo.set(''); }

  async aprobar() { const r = this.rec(); if (r?.ranking.length) await this.decidir(r.ranking[0].proveedor_id, null); }
  async confirmar() { const p = this.eligiendo(); if (p && this.motivo()) await this.decidir(p, this.motivo()); }

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
