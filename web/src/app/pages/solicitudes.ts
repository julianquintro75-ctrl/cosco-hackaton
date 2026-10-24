import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../core/api';
import { Auth } from '../core/auth';
import { MiSolicitud } from '../core/modelos';
import { I18n } from '../i18n/i18n.service';
import { Icono } from '../shared/icono';

@Component({
  selector: 'app-solicitudes',
  imports: [RouterLink, Icono],
  template: `
  <div class="pagina">
    <header class="cabecera-pagina">
      <h1>{{ i18n.t(propias() ? 'sol.tituloMias' : 'sol.titulo') }}</h1>
      <p>{{ i18n.t(propias() ? 'sol.ayudaMias' : 'sol.ayuda') }}</p>
    </header>
    @if (error()) {
      <div class="error-caja" role="alert"><strong>{{ i18n.t('c.error') }}</strong><button class="btn" type="button" (click)="cargar()">{{ i18n.t('c.reintentar') }}</button></div>
    } @else if (cargando()) {
      <p class="tenue" role="status"><span class="giro"></span> {{ i18n.t('c.cargando') }}</p>
    } @else if (!lista().length) {
      <div class="tarjeta vacio"><strong>{{ i18n.t('sol.vacio') }}</strong><span>{{ i18n.t('sol.vacioDetalle') }}</span>
        <a class="btn primario peq" routerLink="/recomendar">{{ i18n.t('sol.nueva') }} <app-icono nombre="flecha" [tam]="16" /></a></div>
    } @else {
      <ul class="lista">
        @for (s of lista(); track s.solicitud_id) {
          <li class="tarjeta fila">
            <div class="que">
              <strong class="num">{{ s.solicitud_id }}</strong>
              <span class="tenue peq">{{ i18n.fecha(s.fecha) }} @if (!propias()) { · {{ s.solicitante }} }</span>
            </div>
            <div class="estado">
              <span class="chip" [class.ok]="s.estado === 'decidida'" [class.rojo]="s.estado === 'escalada'" [class.ambar]="s.estado === 'en_revision'" [class.azul]="s.estado === 'lista'">{{ i18n.t('sol.estado.' + s.estado) }}</span>
              <span class="tenue peq">
                @if (s.proveedor_elegido) { {{ i18n.t('sol.elegido', { proveedor: s.proveedor_elegido, usuario: s.decidida_por ?? '' }) }} }
                @else if (s.proveedor_sugerido) { {{ i18n.t('sol.sugerido', { proveedor: s.proveedor_sugerido }) }} }
              </span>
            </div>
            <a class="btn peq" [routerLink]="['/recomendar', s.solicitud_id]">{{ i18n.t('sol.abrir') }} <app-icono nombre="flecha" [tam]="16" /></a>
          </li>
        }
      </ul>
    }
  </div>`,
  styles: `
    .lista { list-style: none; margin: 0; padding: 0; display: grid; gap: .6rem; }
    .fila { display: grid; grid-template-columns: minmax(160px, 1fr) 2fr auto; gap: 1rem; align-items: center; padding: .9rem 1.1rem; }
    .vacio .btn { text-decoration: none; }
    .que, .estado { display: grid; gap: .25rem; justify-items: start; }
    @media (max-width: 760px) { .fila { grid-template-columns: 1fr; } .fila .btn { justify-self: start; } }`,
})
export class Solicitudes {
  i18n = inject(I18n);
  private api = inject(Api);
  private auth = inject(Auth);
  lista = signal<MiSolicitud[]>([]);
  cargando = signal(true); error = signal(false);
  propias = computed(() => this.auth.rol() === 'solicitante');
  constructor() { this.cargar(); }
  async cargar() {
    this.cargando.set(true); this.error.set(false);
    try { this.lista.set(await this.api.misSolicitudes()); } catch { this.error.set(true); } finally { this.cargando.set(false); }
  }
}
