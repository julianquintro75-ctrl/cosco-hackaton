import { Component, computed, inject, signal } from '@angular/core';
import { Api } from '../core/api';
import { Auth } from '../core/auth';
import { AjustesAvisos, Aviso, EstadoAvisos } from '../core/modelos';
import { I18n } from '../i18n/i18n.service';
import { Icono } from '../shared/icono';

type Llave = keyof AjustesAvisos;

@Component({
  selector: 'app-avisos',
  imports: [Icono],
  template: `
  <div class="pagina">
    <header class="cabecera-pagina"><h1>{{ i18n.t('av.titulo') }}</h1><p>{{ i18n.t('av.ayuda') }}</p></header>
    @if (error()) {
      <div class="error-caja" role="alert"><strong>{{ i18n.t('c.error') }}</strong><button class="btn" type="button" (click)="cargar()">{{ i18n.t('c.reintentar') }}</button></div>
    } @else if (estado(); as e) {
      @if (!puedeEditar()) { <div class="aviso info" role="status"><app-icono nombre="info" />{{ i18n.t('av.soloLectura') }}</div> }
      @if (mensaje(); as m) { <div class="aviso" [class.ok]="m.ok" [class.rojo]="!m.ok" role="status"><app-icono [nombre]="m.ok ? 'ok' : 'aviso'" />{{ m.texto }}</div> }

      <section class="tarjeta pad ajustes" [attr.aria-label]="i18n.t('av.ajustes')">
        @for (a of filas; track a.llave) {
          <div class="ajuste" [class.sub]="a.sub">
            <div><strong id="t-{{ a.llave }}">{{ i18n.t(a.titulo) }}</strong><p class="tenue peq">{{ i18n.t(a.detalle) }}</p></div>
            <button type="button" role="switch" class="interruptor" [attr.aria-checked]="e.ajustes[a.llave]" [attr.aria-labelledby]="'t-' + a.llave"
                    [disabled]="!puedeEditar() || guardando() || (a.sub && !e.ajustes.slack_activo)" (click)="alternar(a.llave)"><span></span></button>
          </div>
        }
      </section>

      <section class="tarjeta pad">
        <h2>{{ i18n.t('av.canales') }}</h2>
        <ul class="canales">
          <li><span>{{ i18n.t('av.operaciones') }}</span><span class="chip" [class.ok]="e.webhooks.operaciones" [class.ambar]="!e.webhooks.operaciones">{{ i18n.t(e.webhooks.operaciones ? 'av.configurado' : 'av.sinConfigurar') }}</span></li>
          <li><span>{{ i18n.t('av.gerencia') }}</span><span class="chip" [class.ok]="e.webhooks.gerencia" [class.ambar]="!e.webhooks.gerencia">{{ i18n.t(e.webhooks.gerencia ? 'av.configurado' : 'av.sinConfigurar') }}</span></li>
        </ul>
        @if (!e.webhooks.operaciones && !e.webhooks.gerencia) { <p class="tenue peq">{{ i18n.t('av.comoConfigurar') }}</p> }
        @if (puedeEditar()) {
          <button type="button" class="btn" (click)="probar()" [disabled]="probando() || !e.ajustes.slack_activo">
            @if (probando()) { <span class="giro"></span> } {{ i18n.t('av.probar') }}
          </button>
        }
      </section>

      <section class="tarjeta pad">
        <h2>{{ i18n.t('av.historial') }}</h2>
        @if (!historial().length) { <p class="tenue">{{ i18n.t('av.historialVacio') }}</p> }
        @else {
          <div class="tabla-caja"><table>
            <thead><tr><th>{{ i18n.t('av.fecha') }}</th><th>{{ i18n.t('av.evento') }}</th><th>{{ i18n.t('av.solicitud') }}</th><th>{{ i18n.t('av.destino') }}</th><th>{{ i18n.t('av.resultado') }}</th></tr></thead>
            <tbody>
              @for (h of historial(); track h.id) {
                <tr>
                  <td class="num">{{ i18n.fecha(h.fecha) }}</td><td>{{ i18n.t('av.ev.' + h.evento) }}</td><td class="num">{{ h.solicitud_id ?? '—' }}</td>
                  <td>{{ i18n.t('av.' + h.destino) }}</td>
                  <td><span class="chip" [class.ok]="h.estado === 'enviada'" [class.rojo]="h.estado === 'fallo'" [class.ambar]="h.estado === 'sin_webhook'" [title]="h.detalle">{{ i18n.t('av.est.' + h.estado) }}</span></td>
                </tr>
              }
            </tbody>
          </table></div>
        }
      </section>
    } @else {
      <p class="tenue" role="status"><span class="giro"></span> {{ i18n.t('c.cargando') }}</p>
    }
  </div>`,
  styles: `
    :host { display: block; } section { margin-top: 1rem; } h2 { font-size: 1.0625rem; margin: 0 0 .75rem; }
    .ajustes { display: grid; gap: 0; padding-block: .25rem; }
    .ajuste { display: flex; justify-content: space-between; align-items: center; gap: 1rem; padding: .9rem 0; border-top: 1px solid var(--linea-suave); }
    .ajuste:first-child { border-top: 0; } .ajuste.sub { padding-left: 1.25rem; } .ajuste p { margin: .15rem 0 0; }
    .interruptor { flex: none; width: 52px; height: 32px; border-radius: 999px; border: 0; background: var(--linea); position: relative; cursor: pointer; transition: background .15s; }
    .interruptor span { position: absolute; top: 3px; left: 3px; width: 26px; height: 26px; border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.3); transition: transform .15s; }
    .interruptor[aria-checked='true'] { background: var(--azul); } .interruptor[aria-checked='true'] span { transform: translateX(20px); }
    .interruptor:disabled { opacity: .5; cursor: not-allowed; }
    .canales { list-style: none; margin: 0 0 1rem; padding: 0; display: grid; gap: .5rem; } .canales li { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
    .tabla-caja { overflow-x: auto; } table { width: 100%; border-collapse: collapse; font-size: .9rem; }
    th, td { text-align: left; padding: .55rem .6rem; border-bottom: 1px solid var(--linea-suave); white-space: nowrap; } th { color: var(--tenue); font-weight: 600; }
    @media (prefers-reduced-motion: reduce) { .interruptor, .interruptor span { transition: none; } }`,
})
export class Avisos {
  i18n = inject(I18n);
  private api = inject(Api);
  private auth = inject(Auth);
  estado = signal<EstadoAvisos | null>(null);
  historial = signal<Aviso[]>([]);
  error = signal(false); guardando = signal(false); probando = signal(false);
  mensaje = signal<{ ok: boolean; texto: string } | null>(null);
  puedeEditar = computed(() => this.auth.rol() === 'gerencia');
  filas = [
    { llave: 'slack_activo' as Llave, titulo: 'av.slack' as const, detalle: 'av.slackDetalle' as const, sub: false },
    { llave: 'avisar_revision' as Llave, titulo: 'av.revision' as const, detalle: 'av.revisionDetalle' as const, sub: true },
    { llave: 'avisar_escalamiento' as Llave, titulo: 'av.escalamiento' as const, detalle: 'av.escalamientoDetalle' as const, sub: true },
  ];
  constructor() { this.cargar(); }

  async cargar() {
    this.error.set(false);
    try { const [e, h] = await Promise.all([this.api.estadoAvisos(), this.api.historialAvisos()]); this.estado.set(e); this.historial.set(h); }
    catch { this.error.set(true); }
  }

  async alternar(l: Llave) {
    const e = this.estado(); if (!e || this.guardando() || !this.puedeEditar()) return;
    this.guardando.set(true); this.mensaje.set(null);
    try { this.estado.set(await this.api.cambiarAvisos({ [l]: !e.ajustes[l] })); }
    catch { this.mensaje.set({ ok: false, texto: this.i18n.t('c.errorDetalle') }); }
    finally { this.guardando.set(false); }
  }

  async probar() {
    this.probando.set(true); this.mensaje.set(null);
    try {
      const r = await this.api.probarAvisos();
      const bien = r.filter(x => x.estado === 'enviada').length;
      this.mensaje.set({ ok: bien > 0 && r.every(x => x.estado !== 'fallo'), texto: this.i18n.t('av.pruebaResultado', { ok: String(bien), total: String(r.length) }) });
      this.historial.set(await this.api.historialAvisos());
    } catch { this.mensaje.set({ ok: false, texto: this.i18n.t('c.errorDetalle') }); }
    finally { this.probando.set(false); }
  }
}
