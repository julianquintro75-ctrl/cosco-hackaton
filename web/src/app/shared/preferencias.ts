import { Component, ElementRef, HostListener, inject, input, signal } from '@angular/core';
import { I18n, IDIOMAS, Idioma } from '../i18n/i18n.service';
import { Preferencias } from '../core/preferencias';
import { Icono } from './icono';

/** Idioma, tema y accesibilidad en un solo grupo de controles (idea tomada de EciWise). */
@Component({
  selector: 'app-preferencias',
  imports: [Icono],
  template: `
    <div class="grupo" [class.claro]="claro()">
      <div class="pop">
        <button type="button" class="b" (click)="abrir('idioma')" [attr.aria-expanded]="menu() === 'idioma'" aria-haspopup="menu">
          <app-icono nombre="idioma" [tam]="18" /><b>{{ cod() }}</b><app-icono nombre="abajo" [tam]="14" />
          <span class="solo-lector">{{ i18n.t('nav.idioma') }}</span>
        </button>
        @if (menu() === 'idioma') {
          <ul class="menu" role="menu" [attr.aria-label]="i18n.t('nav.idioma')">
            @for (i of idiomas; track i.codigo) {
              <li role="none"><button type="button" role="menuitemradio" [attr.aria-checked]="i.codigo === i18n.idioma()" [attr.lang]="i.html" (click)="elegir(i.codigo)">
                <span>{{ i.nombre }}</span><kbd>{{ i.codigo.toUpperCase() }}</kbd></button></li>
            }
          </ul>
        }
      </div>

      <button type="button" class="b" (click)="p.ciclarTema()" [attr.aria-label]="i18n.t('pref.tema') + ': ' + i18n.t('pref.tema.' + p.tema())" [title]="i18n.t('pref.tema') + ': ' + i18n.t('pref.tema.' + p.tema())">
        <app-icono [nombre]="p.tema() === 'oscuro' ? 'luna' : p.tema() === 'claro' ? 'sol' : 'auto'" [tam]="18" />
      </button>

      <div class="pop">
        <button type="button" class="b" (click)="abrir('acc')" [attr.aria-expanded]="menu() === 'acc'" aria-haspopup="dialog" [attr.aria-label]="i18n.t('pref.accesibilidad')" [title]="i18n.t('pref.accesibilidad')">
          <app-icono nombre="acceso" [tam]="18" />
        </button>
        @if (menu() === 'acc') {
          <div class="menu panel" role="dialog" [attr.aria-label]="i18n.t('pref.accesibilidad')">
            <h2>{{ i18n.t('pref.accesibilidad') }}</h2>
            <div class="fila"><span id="lbl-txt">{{ i18n.t('pref.texto') }}</span>
              <div class="paso" role="group" aria-labelledby="lbl-txt">
                <button type="button" (click)="tam(-1)" [disabled]="p.escala() <= 1" [attr.aria-label]="i18n.t('pref.texto.menos')">A−</button>
                <output class="num">{{ (p.escala() * 100).toFixed(0) }}%</output>
                <button type="button" (click)="tam(1)" [disabled]="p.escala() >= 1.3" [attr.aria-label]="i18n.t('pref.texto.mas')">A+</button>
              </div></div>
            <label class="fila"><span>{{ i18n.t('pref.contraste') }}</span><input type="checkbox" role="switch" [checked]="p.contraste()" (change)="p.contraste.set(!p.contraste())" /></label>
            <label class="fila"><span>{{ i18n.t('pref.movimiento') }}</span><input type="checkbox" role="switch" [checked]="p.sinMovimiento()" (change)="p.sinMovimiento.set(!p.sinMovimiento())" /></label>
            <button type="button" class="reset" (click)="p.restablecer()">{{ i18n.t('pref.restablecer') }}</button>
          </div>
        }
      </div>
    </div>`,
  styles: `
    .grupo { display: inline-flex; align-items: center; gap: 2px; color: var(--tenue); } .grupo.claro { color: var(--lateral-texto); }
    .pop { position: relative; }
    .b { display: inline-flex; align-items: center; gap: .3rem; min-height: 44px; min-width: 44px; padding: 0 .6rem; justify-content: center; border: 0; border-radius: 9px; background: transparent; color: inherit; cursor: pointer; font-weight: 600; }
    .b:hover { background: var(--linea-suave); } .claro .b:hover { background: var(--lateral-activo); color: #fff; }
    .menu { position: absolute; z-index: 40; top: calc(100% + 6px); right: 0; min-width: 190px; margin: 0; padding: .35rem; list-style: none; background: var(--tarjeta); color: var(--texto); border: 1px solid var(--linea); border-radius: 12px; box-shadow: var(--sombra); }
    :host-context(.lateral) .menu { top: auto; bottom: calc(100% + 6px); left: 0; right: auto; }
    .menu li button { width: 100%; display: flex; justify-content: space-between; align-items: center; gap: 1rem; min-height: 40px; padding: 0 .7rem; border: 0; border-radius: 8px; background: transparent; cursor: pointer; text-align: left; }
    .menu li button:hover { background: var(--linea-suave); } .menu li button[aria-checked='true'] { background: var(--azul-suave); color: var(--azul); font-weight: 650; }
    kbd { font: 600 .75rem var(--fuente); color: var(--tenue); }
    .panel { min-width: 270px; padding: 1rem; display: grid; gap: .5rem; } .panel h2 { font-size: .9375rem; margin-bottom: .25rem; }
    .fila { display: flex; justify-content: space-between; align-items: center; gap: 1rem; min-height: 40px; cursor: pointer; }
    .paso { display: inline-flex; align-items: center; gap: .25rem; } .paso button { min-width: 40px; min-height: 36px; border: 1px solid var(--linea); border-radius: 8px; background: var(--tarjeta); font-weight: 700; cursor: pointer; }
    .paso button:disabled { opacity: .4; cursor: not-allowed; } .paso output { min-width: 3.2rem; text-align: center; }
    input[role='switch'] { appearance: none; width: 42px; height: 26px; border-radius: 13px; background: var(--linea); position: relative; cursor: pointer; transition: background-color .15s; flex: none; }
    input[role='switch']::after { content: ''; position: absolute; top: 3px; left: 3px; width: 20px; height: 20px; border-radius: 50%; background: #fff; transition: transform .15s; box-shadow: 0 1px 2px rgba(0,0,0,.3); }
    input[role='switch']:checked { background: var(--azul); } input[role='switch']:checked::after { transform: translateX(16px); }
    .reset { margin-top: .25rem; min-height: 38px; border: 1px solid var(--linea); border-radius: 8px; background: transparent; cursor: pointer; font-weight: 600; }
    .reset:hover { border-color: var(--azul); }`,
})
export class SelectorPreferencias {
  i18n = inject(I18n);
  p = inject(Preferencias);
  private el = inject(ElementRef);
  claro = input(false);
  idiomas = IDIOMAS;
  menu = signal<'' | 'idioma' | 'acc'>('');
  cod = () => this.i18n.idioma().toUpperCase();
  abrir(m: 'idioma' | 'acc') { this.menu.set(this.menu() === m ? '' : m); }
  elegir(i: Idioma) { this.i18n.poner(i); this.menu.set(''); }
  tam(d: number) { this.p.escala.set(Math.min(1.3, Math.max(1, +(this.p.escala() + d * 0.15).toFixed(2)))); }
  @HostListener('document:click', ['$event']) fuera(e: Event) { if (!this.el.nativeElement.contains(e.target)) this.menu.set(''); }
  @HostListener('document:keydown.escape') esc() { this.menu.set(''); }
}
