import { Component, computed, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { Api } from '../core/api';
import { Nivel, NuevaSolicitud, Tablas } from '../core/modelos';
import { I18n } from '../i18n/i18n.service';
import { Icono } from '../shared/icono';

const CARGAS = ['general', 'refrigerada', 'peligrosa', 'sobredimensionada'] as const;
const NIVELES: Nivel[] = ['Flexible', 'Estandar', 'Urgente'];
const local = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);   // valor de <input type="datetime-local">
const hash = (s: string) => { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0; return h.toString(36); };

@Component({
  selector: 'app-nueva',
  imports: [FormsModule, Icono],
  template: `
  <div class="pagina">
    <header class="cabecera-pagina"><h1>{{ i18n.t('nueva.titulo') }}</h1><p>{{ i18n.t('nueva.ayuda') }}</p></header>
    @if (cargaError()) {
      <div class="error-caja" role="alert"><strong>{{ i18n.t('c.error') }}</strong><button class="btn" type="button" (click)="cargar()">{{ i18n.t('c.reintentar') }}</button></div>
    } @else if (!tablas()) {
      <p class="tenue" role="status"><span class="giro"></span> {{ i18n.t('c.cargando') }}</p>
    } @else {
      <form class="tarjeta pad formulario" (ngSubmit)="enviar()" novalidate>
        @if (error()) { <div class="aviso rojo ancho" role="alert"><app-icono nombre="aviso" /><span>{{ error() }}</span></div> }

        <div class="campo">
          <label for="n-cliente">{{ i18n.t('nueva.cliente') }}</label>
          <select id="n-cliente" name="cliente" class="ctl" [ngModel]="cliente()" (ngModelChange)="cliente.set($event)" required>
            <option value="" disabled>—</option>
            @for (c of tablas()!.cliente; track c.cliente_id) { <option [value]="c.cliente_id">{{ c.nombre }} · {{ c.segmento }}</option> }
          </select>
        </div>
        <div class="campo">
          <label for="n-corredor">{{ i18n.t('nueva.corredor') }}</label>
          <select id="n-corredor" name="corredor" class="ctl" [ngModel]="corredor()" (ngModelChange)="corredor.set($event)" required>
            <option value="" disabled>—</option>
            @for (c of tablas()!.corredor; track c.corredor_id) { <option [value]="c.corredor_id">{{ c.corredor_id }} · {{ c.origen }} → {{ c.destino }} ({{ c.distancia_km }} km)</option> }
          </select>
        </div>
        <div class="campo">
          <label for="n-veh">{{ i18n.t('nueva.vehiculo') }}</label>
          <select id="n-veh" name="vehiculo" class="ctl" [ngModel]="vehiculo()" (ngModelChange)="vehiculo.set($event)" required>
            <option value="" disabled>—</option>
            @for (v of tablas()!.tipo_vehiculo; track v.tipo_vehiculo_id) { <option [value]="v.tipo_vehiculo_id">{{ v.nombre }} · {{ v.capacidad_ton }} t</option> }
          </select>
        </div>
        <div class="campo">
          <label for="n-carga">{{ i18n.t('nueva.carga') }}</label>
          <select id="n-carga" name="carga" class="ctl" [ngModel]="carga()" (ngModelChange)="carga.set($event)">
            @for (c of cargas; track c) { <option [value]="c">{{ i18n.t('nueva.carga.' + c) }}</option> }
          </select>
        </div>
        <div class="campo">
          <label for="n-peso">{{ i18n.t('nueva.peso') }}</label>
          <input id="n-peso" name="peso" class="ctl" type="number" min="0.1" step="0.1" inputmode="decimal" [ngModel]="peso()" (ngModelChange)="peso.set($event)" required
                 [attr.aria-invalid]="errPeso() ? 'true' : null" aria-describedby="n-peso-ayuda" />
          <small id="n-peso-ayuda" [class.err]="errPeso()" class="tenue">{{ errPeso() ? i18n.t('nueva.errorPeso', { max: capacidad() }) : (capacidad() ? i18n.t('nueva.pesoAyuda', { max: capacidad() }) : '') }}</small>
        </div>
        <div class="campo">
          <span class="etiqueta" id="n-lbl-nivel">{{ i18n.t('rec.nivel') }}</span>
          <div class="segmentos" role="radiogroup" aria-labelledby="n-lbl-nivel">
            @for (n of niveles; track n) { <button type="button" role="radio" [attr.aria-checked]="nivel() === n" (click)="nivel.set(n)">{{ i18n.t('rec.nivel.' + n) }}</button> }
          </div>
        </div>
        <div class="campo">
          <label for="n-cargue">{{ i18n.t('nueva.cargue') }}</label>
          <input id="n-cargue" name="cargue" class="ctl" type="datetime-local" [ngModel]="cargue()" (ngModelChange)="cargue.set($event)" required />
        </div>
        <div class="campo">
          <label for="n-plazo">{{ i18n.t('nueva.plazo') }}</label>
          <input id="n-plazo" name="plazo" class="ctl" type="datetime-local" [ngModel]="plazo()" (ngModelChange)="plazo.set($event)" required
                 [attr.aria-invalid]="errPlazo() ? 'true' : null" aria-describedby="n-plazo-ayuda" />
          <small id="n-plazo-ayuda" class="err">{{ errPlazo() ? i18n.t('nueva.errorPlazo') : '' }}</small>
        </div>
        <div class="campo ancho">
          <label for="n-tarifa">{{ i18n.t('nueva.tarifa') }}</label>
          <input id="n-tarifa" name="tarifa" class="ctl" type="number" min="1" step="1000" inputmode="numeric" [ngModel]="tarifa()" (ngModelChange)="tarifa.set($event)" required aria-describedby="n-tarifa-ayuda" />
          <small id="n-tarifa-ayuda" class="tenue">{{ tarifa() ? i18n.cop(+tarifa()!) + ' · ' : '' }}{{ i18n.t('nueva.tarifaAyuda') }}</small>
        </div>

        <div class="acciones ancho">
          <button type="submit" class="btn primario" [disabled]="enviando() || !completo()">
            @if (enviando()) { <span class="giro"></span> {{ i18n.t('nueva.enviando') }} } @else { {{ i18n.t('nueva.enviar') }} }
          </button>
          <button type="button" class="btn fantasma" (click)="ejemplo()">{{ i18n.t('nueva.ejemplo') }}</button>
        </div>
      </form>
    }
  </div>`,
  styles: `
    .formulario { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem 1.25rem; max-width: 820px; }
    .ancho { grid-column: 1 / -1; } .acciones { display: flex; gap: .6rem; flex-wrap: wrap; align-items: center; }
    .campo { display: grid; gap: .35rem; align-content: start; } .campo > label, .etiqueta { font-size: .875rem; font-weight: 600; }
    .err { color: var(--rojo-texto); font-weight: 600; } small { min-height: 1.1em; }
    @media (max-width: 760px) { .formulario { grid-template-columns: 1fr; } }`,
})
export class Nueva {
  i18n = inject(I18n);
  private api = inject(Api);
  private router = inject(Router);
  desde = input<string>();      // ?desde=ID: copia los datos de una solicitud anterior (p. ej. una devuelta)

  tablas = signal<Tablas | null>(null);
  cargaError = signal(false);
  cliente = signal(''); corredor = signal(''); vehiculo = signal('');
  carga = signal<(typeof CARGAS)[number]>('general');
  peso = signal<number | null>(null);
  nivel = signal<Nivel>('Estandar');
  cargue = signal(''); plazo = signal('');
  tarifa = signal<number | null>(null);
  enviando = signal(false); error = signal('');
  cargas = CARGAS; niveles = NIVELES;
  private pagina = Math.random().toString(36).slice(2, 8);

  capacidad = computed(() => this.tablas()?.tipo_vehiculo.find(v => v.tipo_vehiculo_id === this.vehiculo())?.capacidad_ton ?? 0);
  errPeso = computed(() => { const p = this.peso(), c = this.capacidad(); return p != null && c > 0 && p > c; });
  errPlazo = computed(() => !!this.cargue() && !!this.plazo() && this.plazo() <= this.cargue());
  completo = computed(() => !!(this.cliente() && this.corredor() && this.vehiculo() && this.peso() && this.peso()! > 0 && this.cargue() && this.plazo() && this.tarifa() && this.tarifa()! > 0)
    && !this.errPeso() && !this.errPlazo());

  constructor() { this.fechas(); this.cargar(); }

  private fechas() {
    const c = new Date(); c.setDate(c.getDate() + 5); c.setHours(8, 0, 0, 0);
    const p = new Date(c); p.setDate(p.getDate() + 3);
    this.cargue.set(local(c)); this.plazo.set(local(p));
  }

  async cargar() {
    this.cargaError.set(false);
    try {
      this.tablas.set(await this.api.tablasLigeras());
      const d = this.desde();
      if (d) {
        const s = await this.api.solicitud(d).catch(() => null);
        if (s) {
          this.cliente.set(s.cliente_id); this.corredor.set(s.corredor_id); this.vehiculo.set(s.tipo_vehiculo_req);
          this.carga.set(s.tipo_carga as (typeof CARGAS)[number]); this.peso.set(s.peso_ton); this.nivel.set(s.nivel_servicio); this.tarifa.set(s.tarifa_cliente);
        }
      }
    } catch { this.cargaError.set(true); }
  }

  /** Un caso de uso completo para mostrar el flujo sin escribir todo. */
  ejemplo() {
    const t = this.tablas(); if (!t) return;
    this.cliente.set(t.cliente[0]?.cliente_id ?? ''); this.corredor.set(t.corredor.find(c => c.corredor_id === 'C1')?.corredor_id ?? t.corredor[0].corredor_id);
    this.vehiculo.set(t.tipo_vehiculo.find(v => v.tipo_vehiculo_id === 'V40')?.tipo_vehiculo_id ?? t.tipo_vehiculo[0].tipo_vehiculo_id);
    this.carga.set('general'); this.peso.set(22); this.nivel.set('Estandar'); this.tarifa.set(5_500_000); this.fechas();
  }

  private cuerpo(): NuevaSolicitud {
    const base = { cliente_id: this.cliente(), corredor_id: this.corredor(), tipo_vehiculo_req: this.vehiculo(), tipo_carga: this.carga(), peso_ton: Number(this.peso()),
      fecha_cargue: this.cargue(), plazo_entrega: this.plazo(), nivel_servicio: this.nivel(), tarifa_cliente: Number(this.tarifa()) };
    // misma pantalla + mismos datos = misma clave: un doble clic o un reintento no crea otra solicitud
    return { ...base, clave_envio: this.pagina + hash(JSON.stringify(base)) };
  }

  async enviar() {
    if (!this.completo() || this.enviando()) return;
    this.enviando.set(true); this.error.set('');
    try {
      const r = await this.api.nuevaSolicitud(this.cuerpo());
      await this.router.navigate(['/recomendar', r.solicitud_id]);
    } catch (e) { this.error.set(this.mensaje(e)); } finally { this.enviando.set(false); }
  }

  private mensaje(e: unknown) {
    const h = e as HttpErrorResponse; const d = h?.error?.detail ?? h?.error?.error;
    if (typeof d === 'string') return d;
    if (Array.isArray(d)) return d.map((x: { msg?: string }) => x.msg).filter(Boolean).join(' · ') || this.i18n.t('c.errorDetalle');
    return h?.status === 0 ? this.i18n.t('login.errorRed') : this.i18n.t('c.errorDetalle');
  }
}
