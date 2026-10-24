import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { Auth } from '../core/auth';
import { I18n } from '../i18n/i18n.service';
import { Icono } from '../shared/icono';
import { Marca } from '../shared/marca';
import { SelectorPreferencias } from '../shared/preferencias';

@Component({
  selector: 'app-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Icono, Marca, SelectorPreferencias],
  template: `
    <a class="saltar" href="#contenido">{{ i18n.t('nav.saltar') }}</a>
    <div class="marco">
      <aside class="lateral">
        <div class="logo"><app-marca [tam]="34" /><div><strong>{{ i18n.t('app.nombre') }}</strong><small>COSCO SHIPPING</small></div></div>
        <nav [attr.aria-label]="i18n.t('nav.principal')">
          @for (n of items; track n.ruta) {
            <a [routerLink]="n.ruta" routerLinkActive="activo" #rla="routerLinkActive" [attr.aria-current]="rla.isActive ? 'page' : null">
              <app-icono [nombre]="n.icono" /><span>{{ i18n.t(n.clave) }}</span>
            </a>
          }
        </nav>
        <div class="pie">
          <app-preferencias [claro]="true" />
          <div class="yo">
            <span class="avatar" aria-hidden="true">{{ inicial() }}</span>
            <div class="quien"><strong>{{ auth.usuario()?.nombre }}</strong><small>{{ rolTexto() }} · {{ auth.usuario()?.usuario }}</small></div>
            <button type="button" class="salir" (click)="auth.salir()" [attr.aria-label]="i18n.t('nav.salir')" [title]="i18n.t('nav.salir')"><app-icono nombre="salir" /></button>
          </div>
          <small class="sint">{{ i18n.t('app.sintetico') }}</small>
        </div>
      </aside>
      <div class="cuerpo">
        <header class="superior">
          <app-marca [tam]="28" /><strong>{{ i18n.t('app.nombre') }}</strong>
          <span class="espacio"></span>
          <app-preferencias />
          <button type="button" class="salir oscuro" (click)="auth.salir()" [attr.aria-label]="i18n.t('nav.salir')"><app-icono nombre="salir" /></button>
        </header>
        <main id="contenido" tabindex="-1"><router-outlet /></main>
      </div>
      <nav class="pestanas" [attr.aria-label]="i18n.t('nav.principal')">
        @for (n of items; track n.ruta) {
          <a [routerLink]="n.ruta" routerLinkActive="activo"><app-icono [nombre]="n.icono" [tam]="24" /><span>{{ i18n.t(n.clave) }}</span></a>
        }
      </nav>
    </div>`,
  styles: `
    .saltar { position: absolute; left: -999px; top: .5rem; z-index: 50; background: var(--tarjeta); padding: .6rem 1rem; border-radius: 8px; }
    .saltar:focus { left: .5rem; }
    .marco { display: grid; grid-template-columns: 252px 1fr; min-height: 100dvh; }
    .lateral { position: sticky; top: 0; height: 100dvh; background: var(--lateral); color: var(--lateral-texto); display: flex; flex-direction: column; padding: 1.25rem .85rem; gap: 1.5rem; }
    .logo { display: flex; gap: .7rem; align-items: center; padding: 0 .5rem; color: #fff; }
    .logo strong { display: block; line-height: 1.2; font-size: .9375rem; } .logo small { color: var(--lateral-texto); letter-spacing: .02em; }
    nav { display: grid; gap: 2px; }
    .lateral nav a { display: flex; align-items: center; gap: .75rem; min-height: 44px; padding: 0 .75rem; border-radius: 10px; color: var(--lateral-texto); text-decoration: none; font-weight: 550; }
    .lateral nav a:hover { background: var(--lateral-activo); color: #fff; }
    .lateral nav a.activo { background: var(--lateral-activo); color: #fff; box-shadow: inset 3px 0 0 #fff; }
    .pie { margin-top: auto; display: grid; gap: .6rem; }
    .yo { display: flex; align-items: center; gap: .65rem; padding: .5rem; border-radius: 10px; background: rgba(255,255,255,.06); }
    .avatar { width: 34px; height: 34px; border-radius: 50%; background: #fff; color: #00508f; display: grid; place-items: center; font-weight: 700; flex: none; }
    .quien { min-width: 0; flex: 1; display: grid; line-height: 1.25; } .quien strong { color: #fff; font-size: .875rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; } .quien small { color: var(--lateral-texto); }
    .salir { width: 40px; height: 40px; border: 0; border-radius: 9px; background: transparent; color: var(--lateral-texto); cursor: pointer; display: grid; place-items: center; }
    .salir:hover { background: var(--lateral-activo); color: #fff; } .salir.oscuro { color: var(--tenue); } .salir.oscuro:hover { background: var(--linea-suave); color: var(--texto); }
    .sint { padding: 0 .5rem; color: var(--lateral-texto); opacity: .8; }
    .cuerpo { min-width: 0; } .superior, .pestanas { display: none; }
    main:focus { outline: none; }
    @media (max-width: 960px) {
      .marco { grid-template-columns: 1fr; } .lateral { display: none; }
      .superior { display: flex; align-items: center; gap: .6rem; padding: .5rem .75rem; background: var(--tarjeta); border-bottom: 1px solid var(--linea); position: sticky; top: 0; z-index: 10; }
      .espacio { flex: 1; }
      .pestanas { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(76px, 1fr); overflow-x: auto; position: fixed; inset: auto 0 0 0; z-index: 20; background: var(--tarjeta); border-top: 1px solid var(--linea); padding-bottom: env(safe-area-inset-bottom); }
      .pestanas a { display: grid; justify-items: center; gap: 2px; padding: .55rem .25rem; min-height: 56px; color: var(--tenue); text-decoration: none; font-size: .75rem; font-weight: 600; }
      .pestanas a.activo { color: var(--azul); }
    }`,
})
export class Shell {
  i18n = inject(I18n);
  auth = inject(Auth);
  private todos = [
    { ruta: '/nueva', icono: 'mas', clave: 'nav.nueva' as const, roles: ['solicitante', 'operador', 'gerencia'] },
    { ruta: '/recomendar', icono: 'recomendar', clave: 'nav.recomendar' as const, roles: ['solicitante', 'operador', 'gerencia'] },
    { ruta: '/solicitudes', icono: 'lista', clave: 'nav.solicitudes' as const, roles: ['solicitante', 'operador', 'gerencia'] },
    { ruta: '/pendientes', icono: 'pendientes', clave: 'nav.pendientes' as const, roles: ['operador', 'gerencia'] },
    { ruta: '/proveedores', icono: 'proveedores', clave: 'nav.proveedores' as const, roles: ['operador', 'gerencia'] },
    { ruta: '/panel', icono: 'panel', clave: 'nav.panel' as const, roles: ['operador', 'gerencia'] },
    { ruta: '/avisos', icono: 'campana', clave: 'nav.avisos' as const, roles: ['operador', 'gerencia'] },
    { ruta: '/acerca', icono: 'libro', clave: 'nav.acerca' as const, roles: ['solicitante', 'operador', 'gerencia'] },
  ];
  /** Menú según el rol de la sesión. */
  get items() { const r = this.auth.rol(); return this.todos.filter(n => r && n.roles.includes(r)); }
  rolTexto = () => { const r = this.auth.rol(); return r ? this.i18n.t(('rol.' + r) as 'rol.operador') : ''; };
  inicial = () => (this.auth.usuario()?.nombre ?? '?').trim().charAt(0).toUpperCase();
}
