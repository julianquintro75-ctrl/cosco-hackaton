import { Component, computed, effect, inject, input, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Api } from '../core/api';
import { Ficha, Tablas } from '../core/modelos';
import { I18n } from '../i18n/i18n.service';
import { traducir } from '../i18n/motor';
import { Icono } from '../shared/icono';
import { Lineas } from '../shared/lineas';
import { mensual } from '../shared/series';

@Component({
  selector: 'app-proveedores',
  imports: [Icono, Lineas],
  template: `
  <div class="pagina">
    <header class="cabecera-pagina"><h1>{{ i18n.t('prov.titulo') }}</h1><p>{{ i18n.t('prov.ayuda') }}</p></header>
    @if (error()) {
      <div class="error-caja" role="alert"><strong>{{ i18n.t('c.error') }}</strong><span>{{ i18n.t('c.errorDetalle') }}</span><button class="btn" type="button" (click)="cargar()">{{ i18n.t('c.reintentar') }}</button></div>
    } @else if (!fichas().length) {
      <p class="tenue" role="status"><span class="giro"></span> {{ i18n.t('c.cargando') }}</p>
    } @else {
    <div class="rejilla">
      <section class="tarjeta desliza">
        <table class="tabla">
          <thead><tr><th>{{ i18n.t('prov.nombre') }}</th><th class="der">{{ i18n.t('prov.dureza') }}</th><th class="der">{{ i18n.t('prov.puntualidad') }}</th><th class="der">{{ i18n.t('prov.entregados') }}</th><th class="der">{{ i18n.t('prov.cuota') }}</th></tr></thead>
          <tbody>
            @for (f of fichas(); track f.proveedor_id) {
              <tr class="clic" [class.sel]="sel()?.proveedor_id === f.proveedor_id" tabindex="0" (click)="abrir(f.proveedor_id)" (keydown.enter)="abrir(f.proveedor_id)" [attr.aria-selected]="sel()?.proveedor_id === f.proveedor_id">
                <td><b>{{ f.nombre }}</b><br><span class="tenue peq">{{ f.ciudad_base }}</span></td>
                <td class="der num">{{ i18n.num(f.dureza_media, 1) }}</td>
                <td class="der num">{{ i18n.pct(f.puntualidad_general, 0) }}</td>
                <td class="der num">{{ i18n.num(f.servicios_entregados) }}</td>
                <td class="der num">{{ i18n.pct(f.cuota_30d, 0) }}</td>
              </tr>
            }
          </tbody>
        </table>
      </section>

      <section class="ficha" aria-live="polite">
        @if (sel(); as f) {
          <div class="tarjeta pad"><div class="enc"><h2>{{ f.nombre }}</h2>
            <button type="button" class="btn fantasma peq solo-chico" (click)="cerrar()"><app-icono nombre="cerrar" [tam]="16" /> {{ i18n.t('prov.cerrar') }}</button></div>
            <p class="tenue peq">{{ f.ciudad_base }} · {{ i18n.fecha(f.fecha_alta) }}</p>
            <p class="chips"><span class="chip azul">{{ i18n.t('prov.certs') }}:</span>
              @for (c of f.certificaciones; track c) { <span class="chip">{{ c }}</span> } @empty { <span class="tenue peq">{{ i18n.t('prov.sinCerts') }}</span> }</p>
          </div>

          <div class="tarjeta pad"><h3>{{ i18n.t('prov.tendencia') }}</h3>
            <app-lineas [titulo]="i18n.t('prov.tendencia') + ': ' + f.nombre" [etiquetas]="tendencia().etiquetas" [series]="tendencia().series" [min]="0.4" /></div>

          <div class="hallazgos">
            @for (b of bloques(f); track b.titulo) {
              <div class="tarjeta pad"><h3 [class]="b.cls">{{ i18n.t(b.titulo) }}</h3>
                <ul>@for (x of b.items; track x) { <li>{{ tr(x) }}</li> } @empty { <li class="tenue">{{ i18n.t('prov.ninguna') }}</li> }</ul></div>
            }
          </div>

          <div class="tarjeta"><div class="pad-t"><h3>{{ i18n.t('prov.capacidad') }}</h3></div>
            <div class="desliza"><table class="tabla"><thead><tr><th>{{ i18n.t('rec.vehiculo') }}</th><th class="der">{{ i18n.t('prov.flota') }}</th><th class="der">{{ i18n.t('prov.disponibles') }}</th><th class="der">{{ i18n.t('prov.reporte') }}</th></tr></thead>
              <tbody>@for (c of f.capacidad; track c.vehiculo) { <tr><td>{{ c.vehiculo }}</td><td class="der num">{{ c.flota }}</td><td class="der num">{{ c.disponibles }}</td><td class="der num">{{ i18n.fecha(c.reporte) }}</td></tr> }</tbody></table></div></div>

          <div class="tarjeta"><div class="pad-t"><h3>{{ i18n.t('prov.corredores') }}</h3></div>
            <ul class="barras">@for (e of corredores(f); track e.c) { <li><span>{{ e.c }}</span><div class="pista"><i [style.width.%]="e.p * 100" [class.alto]="e.p > .25"></i></div><b class="num">{{ i18n.pct(e.p, 0) }}</b></li> }</ul></div>
        } @else { <div class="tarjeta vacio"><span>{{ i18n.t('prov.seleccionar') }}</span></div> }
      </section>
    </div>
    }
  </div>`,
  styles: `
    .rejilla { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); gap: 1.5rem; align-items: start; }
    .ficha { display: grid; gap: 1rem; min-width: 0; } .enc { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
    .chips { margin: .6rem 0 0; display: flex; gap: .4rem; flex-wrap: wrap; align-items: center; }
    .hallazgos { display: grid; gap: 1rem; } .hallazgos ul { margin: .5rem 0 0; padding-left: 1.1rem; display: grid; gap: .4rem; font-size: .9375rem; }
    h3.ok { color: var(--ok); } h3.rojo { color: var(--rojo-texto); } h3.ambar { color: var(--ambar); }
    .pad-t { padding: 1.1rem 1.25rem .4rem; } .desliza { overflow-x: auto; }
    .barras { list-style: none; margin: 0; padding: .25rem 1.25rem 1.1rem; display: grid; gap: .55rem; }
    .barras li { display: grid; grid-template-columns: 2.5rem 1fr 3rem; gap: .75rem; align-items: center; font-size: .9375rem; }
    .pista { height: 10px; border-radius: 5px; background: var(--linea-suave); overflow: hidden; } .pista i { display: block; height: 100%; background: var(--seg-precio); border-radius: 5px; } .pista i.alto { background: var(--seg-retraso); }
    tr.clic:focus-visible { outline-offset: -2px; }
    .solo-chico { display: none; }
    @media (max-width: 1080px) { .rejilla { grid-template-columns: 1fr; } .solo-chico { display: inline-flex; } }`,
})
export class Proveedores {
  i18n = inject(I18n);
  private api = inject(Api);
  private router = inject(Router);
  id = input<string>();
  fichas = signal<Ficha[]>([]); error = signal(false);
  tablas = signal<Tablas | null>(null);
  sel = computed(() => this.fichas().find(f => f.proveedor_id === this.id()) ?? null);
  tendencia = computed(() => {
    const t = this.tablas(), f = this.sel();
    if (!t || !f) return { etiquetas: [] as string[], series: [] };
    const m = mensual(t.servicios, this.i18n);
    return { etiquetas: m.etiquetas, series: [{ id: f.proveedor_id, nombre: f.nombre, color: 'var(--azul)', resaltada: true, puntos: m.porProveedor[f.proveedor_id] ?? [] }] };
  });

  constructor() {
    this.cargar();
    effect(() => { if (!this.id() && this.fichas().length && window.matchMedia('(min-width: 1081px)').matches) this.abrir(this.fichas()[0].proveedor_id); });
  }

  async cargar() {
    this.error.set(false);
    try {
      const t = await this.api.tablas(); this.tablas.set(t);
      const f = await Promise.all(t.proveedor.filter(p => p.activo).map(p => this.api.ficha(p.proveedor_id)));
      this.fichas.set(f.sort((a, b) => (b.dureza_media ?? 0) - (a.dureza_media ?? 0)));
    } catch { this.error.set(true); }
  }
  tr = (s: string) => traducir(s, this.i18n);
  abrir(id: string) { this.router.navigate(['/proveedores', id], { replaceUrl: !this.id() }); }
  cerrar() { this.router.navigate(['/proveedores']); }
  bloques(f: Ficha) {
    return [{ titulo: 'prov.fortalezas' as const, cls: 'ok', items: f.fortalezas }, { titulo: 'prov.debilidades' as const, cls: 'ambar', items: f.debilidades }, { titulo: 'prov.riesgos' as const, cls: 'rojo', items: f.riesgos }];
  }
  corredores(f: Ficha) {
    const m = new Map<string, { s: number; n: number }>();
    for (const e of f.estadisticas) { const a = m.get(e.corredor_id) ?? { s: 0, n: 0 }; a.s += e.p_tarde * e.n_servicios; a.n += e.n_servicios; m.set(e.corredor_id, a); }
    return [...m].map(([c, a]) => ({ c, p: a.n ? a.s / a.n : 0 })).sort((x, y) => x.c.localeCompare(y.c));
  }
}
