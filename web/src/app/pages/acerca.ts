import { Component, inject, signal } from '@angular/core';
import { Api } from '../core/api';
import { I18n } from '../i18n/i18n.service';
import { Icono } from '../shared/icono';

@Component({
  selector: 'app-acerca',
  imports: [Icono],
  template: `
  <div class="pagina">
    <header class="cabecera-pagina"><h1>{{ i18n.t('acerca.titulo') }}</h1><p>{{ i18n.t('acerca.intro') }}</p></header>

    <section aria-labelledby="h-pasos">
      <h2 id="h-pasos">{{ i18n.t('acerca.pasos') }}</h2>
      <ol class="pasos">
        @for (n of [1, 2, 3, 4]; track n) {
          <li class="tarjeta pad"><span class="n num" aria-hidden="true">{{ n }}</span>
            <div><h3>{{ i18n.t('acerca.p' + n + '.t') }}</h3><p class="tenue">{{ i18n.t('acerca.p' + n + '.d') }}</p></div></li>
        }
      </ol>
    </section>

    <div class="dos">
      <section class="tarjeta pad" aria-labelledby="h-niv">
        <h2 id="h-niv">{{ i18n.t('acerca.niveles') }}</h2><p class="peq tenue">{{ i18n.t('acerca.nivelesAyuda') }}</p>
        <table class="tabla"><tbody>
          @for (n of niveles; track n) { <tr><td>{{ i18n.t('rec.nivel.' + n) }}</td><td class="der num"><b>{{ i18n.cop(costos()[n]) }}</b></td></tr> }
        </tbody></table>
      </section>
      <section class="tarjeta pad" aria-labelledby="h-col">
        <h2 id="h-col">{{ i18n.t('acerca.colores') }}</h2>
        <ul class="colores">
          <li><i style="background: var(--azul)"></i>{{ i18n.t('acerca.azul') }}</li>
          <li><i style="background: var(--ambar)"></i>{{ i18n.t('acerca.ambar') }}</li>
          <li><i style="background: var(--rojo)"></i>{{ i18n.t('acerca.rojo') }}</li>
        </ul>
      </section>
    </div>

    <section class="aviso ambar limites" aria-labelledby="h-lim">
      <app-icono nombre="info" />
      <div><span id="h-lim">{{ i18n.t('acerca.limites') }}</span>
        <ul>@for (n of [1, 2, 3, 4]; track n) { <li>{{ i18n.t('acerca.l' + n) }}</li> }</ul></div>
    </section>
  </div>`,
  styles: `
    .pasos { list-style: none; margin: .75rem 0 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; }
    .pasos li { display: grid; gap: .75rem; align-content: start; }
    .pasos h3 { margin-bottom: .4rem; } .n { width: 34px; height: 34px; border-radius: 10px; background: var(--azul); color: var(--sobre-azul); display: grid; place-items: center; font-weight: 700; }
    .dos { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; } .dos .tabla { margin-top: .5rem; }
    .colores { list-style: none; margin: .75rem 0 0; padding: 0; display: grid; gap: .7rem; } .colores li { display: flex; gap: .75rem; align-items: center; } .colores i { width: 14px; height: 14px; border-radius: 4px; flex: none; }
    .limites ul { font-weight: 450; } @media (max-width: 800px) { .dos { grid-template-columns: 1fr; } }`,
})
export class Acerca {
  i18n = inject(I18n);
  private api = inject(Api);
  niveles = ['Flexible', 'Estandar', 'Urgente'] as const;
  costos = signal<Record<string, number>>({});
  constructor() { this.api.config().then(c => this.costos.set(c['costo_retraso'] ?? {})).catch(() => {}); }
}
