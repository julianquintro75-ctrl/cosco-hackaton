import { Component, computed, inject, input } from '@angular/core';
import { Desglose } from '../core/modelos';
import { I18n } from '../i18n/i18n.service';

const ORDEN = ['precio', 'retraso_esperado', 'incidente_esperado', 'incertidumbre', 'concentracion'] as const;
const COLOR: Record<string, string> = { precio: 'var(--seg-precio)', retraso_esperado: 'var(--seg-retraso)', incidente_esperado: 'var(--seg-incidente)', incertidumbre: 'var(--seg-incert)', concentracion: 'var(--seg-conc)' };

/** Barra apilada del costo esperado: es la pieza distintiva de la pantalla de recomendación. */
@Component({
  selector: 'app-desglose',
  template: `
    <div class="barra" role="img" [attr.aria-label]="resumen()" [style.width.%]="escala()">
      @for (s of segmentos(); track s.k) { <span [style.flex]="s.v" [style.background]="s.c"></span> }
    </div>
    @if (leyenda()) {
      <ul class="ley">
        @for (s of segmentos(); track s.k) {
          <li><i [style.background]="s.c"></i><span>{{ i18n.t('comp.' + s.k) }}</span><b class="num">{{ i18n.cop(s.v) }}</b></li>
        }
      </ul>
    }`,
  styles: `
    .barra { display: flex; height: 12px; border-radius: 6px; overflow: hidden; gap: 2px; min-width: 40px; }
    .barra span { min-width: 3px; }
    .ley { list-style: none; margin: .75rem 0 0; padding: 0; display: grid; gap: .35rem; font-size: .875rem; }
    .ley li { display: grid; grid-template-columns: 12px 1fr auto; gap: .6rem; align-items: center; }
    .ley i { width: 12px; height: 12px; border-radius: 3px; }`,
})
export class DesgloseBarra {
  i18n = inject(I18n);
  d = input.required<Desglose>();
  maximo = input<number>(0);
  leyenda = input(false);
  total = computed(() => ORDEN.reduce((a, k) => a + this.d()[k], 0));
  escala = computed(() => (this.maximo() > 0 ? Math.max(8, (this.total() / this.maximo()) * 100) : 100));
  segmentos = computed(() => ORDEN.filter(k => this.d()[k] > 0).map(k => ({ k, v: this.d()[k], c: COLOR[k] })));
  resumen = computed(() => this.segmentos().map(s => `${this.i18n.t('comp.' + s.k)}: ${this.i18n.cop(s.v)}`).join(', '));
}
