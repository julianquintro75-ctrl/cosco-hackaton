import { Component, inject, input } from '@angular/core';
import { I18n, IDIOMAS, Idioma } from '../i18n/i18n.service';
import { Icono } from './icono';

@Component({
  selector: 'app-idioma',
  imports: [Icono],
  template: `
    <label class="sel" [class.claro]="claro()">
      <app-icono nombre="idioma" [tam]="18" />
      <span class="solo-lector">{{ i18n.t('nav.idioma') }}</span>
      <select (change)="cambiar($event)" [attr.aria-label]="i18n.t('nav.idioma')">
        @for (i of idiomas; track i.codigo) { <option [value]="i.codigo" [attr.lang]="i.html" [selected]="i.codigo === i18n.idioma()">{{ i.nombre }}</option> }
      </select>
    </label>`,
  styles: `
    .sel { display: inline-flex; align-items: center; gap: .5rem; min-height: 44px; padding: 0 .6rem; border-radius: 9px; color: var(--tenue); position: relative; }
    .sel:hover { background: var(--linea-suave); }
    .sel.claro { color: var(--lateral-texto); } .sel.claro:hover { background: var(--lateral-activo); }
    select { appearance: none; background: transparent; border: 0; color: inherit; font-weight: 600; padding: .5rem .25rem; cursor: pointer; }
    select option { color: #121e2b; background: #fff; }`,
})
export class SelectorIdioma {
  i18n = inject(I18n);
  idiomas = IDIOMAS;
  claro = input(false);
  cambiar(e: Event) { this.i18n.poner((e.target as HTMLSelectElement).value as Idioma); }
}
