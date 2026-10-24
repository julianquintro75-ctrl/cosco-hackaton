import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../core/api';
import { Pendiente } from '../core/modelos';
import { I18n } from '../i18n/i18n.service';
import { Icono } from '../shared/icono';

@Component({
  selector: 'app-pendientes',
  imports: [RouterLink, Icono],
  template: `
  <div class="pagina">
    <header class="cabecera-pagina"><h1>{{ i18n.t('pen.titulo') }}</h1><p>{{ i18n.t('pen.ayuda') }}</p></header>
    <div class="segmentos" role="radiogroup" [attr.aria-label]="i18n.t('pen.titulo')">
      <button type="button" role="radio" [attr.aria-checked]="filtro() === 'revision'" (click)="poner('revision')">{{ i18n.t('pen.revision') }}</button>
      <button type="button" role="radio" [attr.aria-checked]="filtro() === 'gerencia'" (click)="poner('gerencia')">{{ i18n.t('pen.gerencia') }}</button>
    </div>
    @if (error()) {
      <div class="error-caja" role="alert"><strong>{{ i18n.t('c.error') }}</strong><button class="btn" type="button" (click)="poner(filtro())">{{ i18n.t('c.reintentar') }}</button></div>
    } @else if (cargando()) {
      <p class="tenue" role="status"><span class="giro"></span> {{ i18n.t('c.cargando') }}</p>
    } @else if (!lista().length) {
      <div class="tarjeta vacio"><strong>{{ i18n.t('pen.vacio') }}</strong><span>{{ i18n.t('pen.vacioDetalle') }}</span></div>
    } @else {
      <ul class="lista">
        @for (p of lista(); track p.solicitud.solicitud_id) {
          <li class="tarjeta fila">
            <div class="que">
              <strong class="num">{{ p.solicitud.solicitud_id }}</strong>
              <span class="tenue peq">{{ p.solicitud.corredor_id }} · {{ p.solicitud.tipo_vehiculo_req }} · {{ i18n.t('rec.nivel.' + p.solicitud.nivel_servicio) }} · {{ i18n.fecha(p.solicitud.fecha_cargue) }}</span>
            </div>
            <ul class="motivos" [attr.aria-label]="i18n.t('pen.motivos')">
              @for (m of p.recomendacion.motivos_revision; track m) { <li class="chip" [class.rojo]="m === 'margen_negativo' || m === 'sin_candidato_en_plazo'" [class.ambar]="m === 'urgente' || m === 'confianza_baja'">{{ i18n.t('rev.' + m) }}</li> }
            </ul>
            <a class="btn primario peq" [routerLink]="['/recomendar', p.solicitud.solicitud_id]">{{ i18n.t('pen.abrir') }} <app-icono nombre="flecha" [tam]="16" /></a>
          </li>
        }
      </ul>
    }
  </div>`,
  styles: `
    .lista { list-style: none; margin: 0; padding: 0; display: grid; gap: .6rem; }
    .fila { display: grid; grid-template-columns: minmax(180px, 1fr) 2fr auto; gap: 1rem; align-items: center; padding: .9rem 1.1rem; }
    .que { display: grid; } .motivos { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: .4rem; }
    @media (max-width: 760px) { .fila { grid-template-columns: 1fr; } .fila .btn { justify-self: start; } }`,
})
export class Pendientes {
  i18n = inject(I18n);
  private api = inject(Api);
  filtro = signal<'revision' | 'gerencia'>('revision');
  lista = signal<Pendiente[]>([]);
  cargando = signal(true); error = signal(false);
  constructor() { this.poner('revision'); }
  async poner(f: 'revision' | 'gerencia') {
    this.filtro.set(f); this.cargando.set(true); this.error.set(false);
    try { this.lista.set(await this.api.pendientes(f)); } catch { this.error.set(true); } finally { this.cargando.set(false); }
  }
}
