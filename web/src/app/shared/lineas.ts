import { Component, ElementRef, computed, inject, input, signal } from '@angular/core';
import { I18n } from '../i18n/i18n.service';

export interface Serie { id: string; nombre: string; color: string; puntos: (number | null)[]; resaltada?: boolean }

/** Líneas en SVG puro: sin librería, tema claro/oscuro por variables y tabla accesible equivalente. */
@Component({
  selector: 'app-lineas',
  template: `
    <figure>
      <svg [attr.viewBox]="'0 0 ' + W + ' ' + H" role="img" [attr.aria-label]="titulo()" preserveAspectRatio="xMidYMid meet">
        @for (g of rejilla(); track g.v) {
          <line [attr.x1]="M.l" [attr.x2]="W - M.r" [attr.y1]="g.y" [attr.y2]="g.y" class="rej" />
          <text [attr.x]="M.l - 8" [attr.y]="g.y + 4" class="eje" text-anchor="end">{{ g.t }}</text>
        }
        @for (e of etiquetasX(); track e.x) { <text [attr.x]="e.x" [attr.y]="H - 8" class="eje" text-anchor="middle">{{ e.t }}</text> }
        @for (s of orden(); track s.id) {
          <path [attr.d]="s.d" fill="none" [attr.stroke]="s.color" [attr.stroke-width]="s.resaltada ? 3.2 : 1.6" stroke-linejoin="round" stroke-linecap="round"
            [attr.opacity]="alguna() && !s.resaltada ? .28 : 1" />
          @if (s.resaltada && s.fin) { <text [attr.x]="s.fin.x" [attr.y]="s.fin.y - 9" class="rot" [attr.fill]="s.color" text-anchor="end">{{ s.nombre }}</text> }
        }
      </svg>
      <figcaption class="solo-lector">{{ titulo() }}</figcaption>
    </figure>`,
  styles: `
    figure { margin: 0; } svg { width: 100%; height: auto; display: block; }
    .rej { stroke: var(--linea-suave); stroke-width: 1; } .rot { font-size: 14.5px; font-weight: 650; paint-order: stroke; stroke: var(--tarjeta); stroke-width: 4px; }
    .eje { fill: var(--tenue); font-size: 13.5px; font-variant-numeric: tabular-nums; }`,
})
export class Lineas {
  i18n = inject(I18n);
  titulo = input('');
  etiquetas = input.required<string[]>();
  series = input.required<Serie[]>();
  min = input(0.4);
  readonly W = 760; readonly H = 300; readonly M = { l: 50, r: 12, t: 12, b: 28 };
  alguna = computed(() => this.series().some(s => s.resaltada));
  orden = computed(() => {
    const n = this.etiquetas().length, { l, r, t, b } = this.M, min = this.min();
    const x = (i: number) => l + (n <= 1 ? 0 : (i / (n - 1)) * (this.W - l - r));
    const y = (v: number) => t + (1 - (Math.min(1, Math.max(min, v)) - min) / (1 - min)) * (this.H - t - b);
    const trazo = (p: (number | null)[]) => p.map((v, i) => (v == null ? '' : `${p.slice(0, i).every(q => q == null) || p[i - 1] == null ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`)).join('');
    return [...this.series()].sort((a, b) => Number(!!a.resaltada) - Number(!!b.resaltada)).map(s => {
      const i = s.puntos.map(v => v != null).lastIndexOf(true);
      return { ...s, d: trazo(s.puntos), fin: i >= 0 ? { x: x(i), y: y(s.puntos[i]!) } : null };
    });
  });
  rejilla = computed(() => {
    const min = this.min(), { t, b } = this.M;
    return Array.from({ length: 5 }, (_, i) => min + ((1 - min) * i) / 4).map(v => ({ v, y: t + (1 - (v - min) / (1 - min)) * (this.H - t - b), t: this.i18n.pct(v) }));
  });
  etiquetasX = computed(() => {
    const e = this.etiquetas(), n = e.length, paso = Math.max(1, Math.ceil(n / 7)), { l, r } = this.M;
    return e.map((t, i) => ({ t, x: l + (n <= 1 ? 0 : (i / (n - 1)) * (this.W - l - r)), i })).filter(o => o.i % paso === 0);
  });
}
