import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Api } from '../core/api';
import { Ficha, Tablas } from '../core/modelos';
import { I18n } from '../i18n/i18n.service';
import { Lineas, Serie } from '../shared/lineas';
import { mensual } from '../shared/series';
import { Icono } from '../shared/icono';

@Component({
  selector: 'app-panel',
  imports: [FormsModule, Lineas, Icono],
  template: `
  <div class="pagina">
    <header class="cabecera-pagina"><h1>{{ i18n.t('pan.titulo') }}</h1><p>{{ i18n.t('pan.ayuda') }}</p></header>
    @if (error()) {
      <div class="error-caja" role="alert"><strong>{{ i18n.t('c.error') }}</strong><span>{{ i18n.t('c.errorDetalle') }}</span><button class="btn" type="button" (click)="cargar()">{{ i18n.t('c.reintentar') }}</button></div>
    } @else if (!t()) {
      <p class="tenue" role="status"><span class="giro"></span> {{ i18n.t('c.cargando') }}</p>
    } @else {
      <section class="kpis">
        <div class="tarjeta pad kpi"><span class="tenue peq">{{ i18n.t('pan.kpi.servicios') }}</span><strong class="num">{{ i18n.num(kpi().total) }}</strong></div>
        <div class="tarjeta pad kpi"><span class="tenue peq">{{ i18n.t('pan.kpi.puntualidad') }}</span><strong class="num">{{ i18n.pct(kpi().p30, 1) }}</strong>
          <span class="peq num" [class.baja]="kpi().delta < 0" [class.sube]="kpi().delta >= 0">{{ i18n.t('pan.kpi.contraAnterior', { n: (kpi().delta >= 0 ? '+' : '') + i18n.num(kpi().delta * 100, 1) }) }}</span></div>
        <div class="tarjeta pad kpi"><span class="tenue peq">{{ i18n.t('pan.kpi.pendientes') }}</span><strong class="num">{{ pend().revision ?? '—' }}</strong></div>
        <div class="tarjeta pad kpi"><span class="tenue peq">{{ i18n.t('pan.kpi.gerencia') }}</span><strong class="num" [class.rojo]="(pend().gerencia ?? 0) > 0">{{ pend().gerencia ?? '—' }}</strong></div>
      </section>

      <section class="tarjeta pad">
        <div class="enc"><div><h2>{{ i18n.t('pan.tendencia') }}</h2><p class="peq tenue">{{ i18n.t('pan.tendenciaAyuda') }}</p></div>
          <select class="ctl corto" [ngModel]="resalta()" (ngModelChange)="resalta.set($event)" [attr.aria-label]="i18n.t('pan.tendencia')">
            <option value="">{{ i18n.t('pan.todos') }}</option>
            @for (p of t()!.proveedor; track p.proveedor_id) { <option [value]="p.proveedor_id">{{ p.nombre }}</option> }
          </select></div>
        <app-lineas [titulo]="i18n.t('pan.tendencia')" [etiquetas]="serie().etiquetas" [series]="serie().series" [min]="0.4" />
        @if (deterioro().length) {
          <p class="aviso rojo peq"><app-icono nombre="aviso" [tam]="18" /><span>{{ i18n.t('pan.deterioro') }}: {{ deterioro().join(', ') }}</span></p>
        }
      </section>

      <div class="dos">
        <section class="tarjeta pad">
          <h2>{{ i18n.t('pan.precios') }}</h2><p class="peq tenue">{{ i18n.t('pan.preciosAyuda') }}</p>
          <div class="filtros">
            <label class="campo"><span class="peq">{{ i18n.t('pan.corredor') }}</span>
              <select class="ctl" [ngModel]="corr()" (ngModelChange)="corr.set($event)">@for (c of t()!.corredor; track c.corredor_id) { <option [value]="c.corredor_id">{{ c.corredor_id }} · {{ c.origen }} → {{ c.destino }}</option> }</select></label>
            <label class="campo"><span class="peq">{{ i18n.t('pan.vehiculo') }}</span>
              <select class="ctl" [ngModel]="veh()" (ngModelChange)="veh.set($event)">@for (v of t()!.tipo_vehiculo; track v.tipo_vehiculo_id) { <option [value]="v.tipo_vehiculo_id">{{ v.tipo_vehiculo_id }} · {{ v.nombre }}</option> }</select></label>
          </div>
          @if (precios().length) {
            <ul class="barras">@for (p of precios(); track p.nombre) { <li><span>{{ p.nombre }}</span><div class="pista"><i [style.width.%]="p.pct"></i></div><b class="num">{{ i18n.cop(p.v) }}</b></li> }</ul>
          } @else { <p class="tenue vacio">{{ i18n.t('pan.sinTarifa') }}</p> }
        </section>

        <section class="tarjeta pad">
          <h2>{{ i18n.t('pan.capacidad') }}</h2><p class="peq tenue">{{ i18n.t('pan.capacidadAyuda') }}</p>
          <div class="filtros"><label class="campo"><span class="peq">{{ i18n.t('pan.vehiculo') }}</span>
            <select class="ctl" [ngModel]="veh()" (ngModelChange)="veh.set($event)">@for (v of t()!.tipo_vehiculo; track v.tipo_vehiculo_id) { <option [value]="v.tipo_vehiculo_id">{{ v.tipo_vehiculo_id }} · {{ v.nombre }}</option> }</select></label></div>
          @if (capacidad().length) {
            <ul class="barras">@for (p of capacidad(); track p.nombre) { <li><span>{{ p.nombre }}</span><div class="pista"><i [style.width.%]="p.pct" [class.alto]="p.pct < 15"></i></div><b class="num">{{ p.libres }} {{ i18n.t('c.de') }} {{ p.flota }}</b></li> }</ul>
          } @else { <p class="tenue vacio">{{ i18n.t('pan.sinTarifa') }}</p> }
        </section>
      </div>

      <section class="tarjeta pad">
        <div class="enc"><div><h2>{{ i18n.t('pan.transito') }}</h2><p class="peq tenue">{{ i18n.t('pan.transitoAyuda') }}</p></div>
          <select class="ctl corto" [ngModel]="provT()" (ngModelChange)="elegirT($event)" [attr.aria-label]="i18n.t('pan.transito')">
            @for (p of t()!.proveedor; track p.proveedor_id) { <option [value]="p.proveedor_id">{{ p.nombre }}</option> }
          </select></div>
        <ul class="barras doble">@for (r of transito(); track r.c) {
          <li><span>{{ r.c }}</span><div class="pista"><i class="p90" [style.width.%]="r.p90pct"></i><i class="p50" [style.width.%]="r.p50pct"></i></div>
            <b class="num">{{ i18n.num(r.p50) }} / {{ i18n.num(r.p90) }} {{ i18n.t('c.horas') }}</b></li> }</ul>
      </section>
    }
  </div>`,
  styles: `
    .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 1rem; }
    .kpi { display: grid; gap: .15rem; } .kpi strong { font-size: 2rem; letter-spacing: -.02em; line-height: 1.2; } .kpi .rojo { color: var(--rojo-texto); }
    .baja { color: var(--rojo-texto); } .sube { color: var(--ok); }
    .enc { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; flex-wrap: wrap; margin-bottom: .5rem; } .corto { width: auto; min-width: 200px; }
    .dos { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
    .filtros { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: .75rem; margin: .9rem 0; }
    .barras { list-style: none; margin: .5rem 0 0; padding: 0; display: grid; gap: .6rem; }
    .barras li { display: grid; grid-template-columns: minmax(7rem, 11rem) 1fr minmax(6.5rem, auto); gap: .75rem; align-items: center; font-size: .9375rem; } .barras li b { text-align: right; }
    .pista { position: relative; height: 10px; border-radius: 5px; background: var(--linea-suave); overflow: hidden; } .pista i { display: block; height: 100%; background: var(--seg-precio); border-radius: 5px; } .pista i.alto { background: var(--seg-retraso); }
    .doble .pista { height: 14px; } .doble .pista i { position: absolute; left: 0; top: 0; } .doble i.p90 { background: var(--seg-conc); } .doble i.p50 { background: var(--seg-precio); }
    .aviso { margin-top: .75rem; }
    @media (max-width: 900px) { .dos { grid-template-columns: 1fr; } .barras li { grid-template-columns: 1fr auto; } .barras li .pista { grid-column: 1 / -1; order: 3; } }`,
})
export class Panel {
  i18n = inject(I18n);
  private api = inject(Api);
  t = signal<Tablas | null>(null); error = signal(false);
  pend = signal<{ revision?: number; gerencia?: number }>({});
  resalta = signal(''); corr = signal(''); veh = signal(''); provT = signal(''); ficha = signal<Ficha | null>(null);

  constructor() { this.cargar(); }

  async cargar() {
    this.error.set(false);
    try {
      const t = await this.api.tablas(); this.t.set(t);
      this.corr.set(t.corredor[0]?.corredor_id ?? ''); this.veh.set(t.tipo_vehiculo[0]?.tipo_vehiculo_id ?? '');
      await this.elegirT(t.proveedor[0]?.proveedor_id ?? '');
      Promise.all([this.api.pendientes('revision'), this.api.pendientes('gerencia')]).then(([r, g]) => this.pend.set({ revision: r.length, gerencia: g.length })).catch(() => {});
    } catch { this.error.set(true); }
  }
  async elegirT(id: string) { this.provT.set(id); if (id) this.ficha.set(await this.api.ficha(id).catch(() => null)); }

  private m = computed(() => (this.t() ? mensual(this.t()!.servicios, this.i18n) : null));
  kpi = computed(() => {
    const s = (this.t()?.servicios ?? []).filter(x => x.estado === 'ENTREGADO' && x.entrega_real && x.a_tiempo != null);
    const fin = s.reduce((m, x) => (x.entrega_real! > m ? x.entrega_real! : m), '');
    const d = (n: number) => new Date(new Date(fin).getTime() - n * 864e5).toISOString().slice(0, 16);
    const tasa = (a: string, b: string) => { const r = s.filter(x => x.entrega_real! > a && x.entrega_real! <= b); return r.length ? r.filter(x => x.a_tiempo).length / r.length : 0; };
    const p30 = fin ? tasa(d(30), fin) : 0;
    return { total: s.length, p30, delta: fin ? p30 - tasa(d(60), d(30)) : 0 };
  });
  deterioro = computed(() => this.degradados().map(d => d.nombre));
  private degradados = computed(() => {
    const m = this.m(), t = this.t(); if (!m || !t) return [];
    return t.proveedor.filter(p => {
      const v = (m.porProveedor[p.proveedor_id] ?? []).filter((x): x is number => x != null);
      if (v.length < 5) return false;
      const ult = v.slice(-2).reduce((a, b) => a + b, 0) / 2, ant = v.slice(-6, -2).reduce((a, b) => a + b, 0) / Math.max(1, v.slice(-6, -2).length);
      return ant - ult >= 0.1;
    });
  });
  serie = computed(() => {
    const m = this.m(), t = this.t();
    if (!m || !t) return { etiquetas: [] as string[], series: [] as Serie[] };
    const malos = new Set(this.degradados().map(d => d.proveedor_id));
    const series: Serie[] = t.proveedor.map(p => ({
      id: p.proveedor_id, nombre: p.nombre, puntos: m.porProveedor[p.proveedor_id] ?? [],
      color: p.proveedor_id === this.resalta() ? 'var(--azul)' : malos.has(p.proveedor_id) ? 'var(--rojo)' : 'var(--seg-incert)',
      resaltada: p.proveedor_id === this.resalta() || (!this.resalta() && malos.has(p.proveedor_id)),
    }));
    return { etiquetas: m.etiquetas, series };
  });
  precios = computed(() => {
    const t = this.t(); if (!t) return [];
    const filas = t.proveedor.map(p => {
      const ts = t.tarifa.filter(x => x.proveedor_id === p.proveedor_id && x.corredor_id === this.corr() && x.tipo_vehiculo_id === this.veh()).sort((a, b) => a.vigente_desde.localeCompare(b.vigente_desde));
      return { nombre: p.nombre, v: ts.at(-1)?.precio_cop ?? 0 };
    }).filter(f => f.v > 0).sort((a, b) => a.v - b.v);
    const max = Math.max(1, ...filas.map(f => f.v));
    return filas.map(f => ({ ...f, pct: (f.v / max) * 100 }));
  });
  capacidad = computed(() => {
    const t = this.t(); if (!t) return [];
    return t.proveedor.map(p => {
      const flota = t.flota.find(f => f.proveedor_id === p.proveedor_id && f.tipo_vehiculo_id === this.veh())?.cantidad ?? 0;
      const ult = t.capacidad_snapshot.filter(c => c.proveedor_id === p.proveedor_id && c.tipo_vehiculo_id === this.veh()).sort((a, b) => a.fecha_hora.localeCompare(b.fecha_hora)).at(-1);
      return { nombre: p.nombre, flota, libres: ult?.unidades_disponibles ?? 0, pct: flota ? ((ult?.unidades_disponibles ?? 0) / flota) * 100 : 0 };
    }).filter(f => f.flota > 0).sort((a, b) => b.libres - a.libres);
  });
  transito = computed(() => {
    const f = this.ficha(); if (!f) return [];
    const m = new Map<string, { p50: number; p90: number; n: number }>();
    for (const e of f.estadisticas.filter(x => x.tipo_carga === 'general')) { const a = m.get(e.corredor_id); if (!a || e.n_servicios > a.n) m.set(e.corredor_id, { p50: e.transito_p50_h, p90: e.transito_p90_h, n: e.n_servicios }); }
    const filas = [...m].map(([c, v]) => ({ c, p50: v.p50, p90: v.p90 })).sort((a, b) => a.c.localeCompare(b.c));
    const max = Math.max(1, ...filas.map(r => r.p90));
    return filas.map(r => ({ ...r, p50pct: (r.p50 / max) * 100, p90pct: (r.p90 / max) * 100 }));
  });
}
