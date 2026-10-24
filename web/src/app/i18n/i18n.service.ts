import { Injectable, computed, signal } from '@angular/core';
import { Clave, es } from './es';
import { en } from './en';
import { zh } from './zh';

export type Idioma = 'es' | 'en' | 'zh';
export const IDIOMAS: { codigo: Idioma; nombre: string; locale: string; html: string }[] = [
  { codigo: 'es', nombre: 'Español', locale: 'es-CO', html: 'es' },
  { codigo: 'en', nombre: 'English', locale: 'en-US', html: 'en' },
  { codigo: 'zh', nombre: '简体中文', locale: 'zh-CN', html: 'zh-CN' },
];
const DICC = { es, en, zh } as const;
const LLAVE = 'cosco.idioma';

function inicial(): Idioma {
  try {
    const g = localStorage.getItem(LLAVE) as Idioma | null;
    if (g && g in DICC) return g;
  } catch { /* sin almacenamiento: se usa el idioma del navegador */ }
  const n = (navigator.language || 'es').toLowerCase();
  return n.startsWith('zh') ? 'zh' : n.startsWith('en') ? 'en' : 'es';
}

@Injectable({ providedIn: 'root' })
export class I18n {
  readonly idioma = signal<Idioma>(inicial());
  readonly locale = computed(() => IDIOMAS.find(i => i.codigo === this.idioma())!.locale);
  private readonly moneda = computed(() => new Intl.NumberFormat(this.locale(), { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }));
  private readonly moneda2 = computed(() => new Intl.NumberFormat(this.locale(), { style: 'currency', currency: 'COP', notation: 'compact', maximumFractionDigits: 1 }));

  constructor() { this.aplicar(this.idioma()); }

  poner(i: Idioma) {
    this.idioma.set(i);
    try { localStorage.setItem(LLAVE, i); } catch { /* ignorar */ }
    this.aplicar(i);
  }

  private aplicar(i: Idioma) {
    document.documentElement.lang = IDIOMAS.find(x => x.codigo === i)!.html;
    document.title = DICC[i]['app.nombre'];
  }

  /** Traduce una clave; {x} se reemplaza con los parámetros. Las claves dinámicas desconocidas devuelven el valor tal cual. */
  t(clave: Clave | (string & {}), params?: Record<string, string | number>): string {
    let s: string = (DICC[this.idioma()] as Record<string, string>)[clave] ?? (clave.includes('.') ? clave.split('.').pop()! : clave);
    if (params) for (const [k, v] of Object.entries(params)) s = s.replaceAll(`{${k}}`, String(v));
    return s;
  }

  cop(n: number | null | undefined, compacto = false): string {
    if (n == null || Number.isNaN(n)) return '—';
    return (compacto ? this.moneda2() : this.moneda()).format(n);
  }
  num(n: number | null | undefined, dec = 0): string {
    return n == null ? '—' : new Intl.NumberFormat(this.locale(), { maximumFractionDigits: dec, minimumFractionDigits: dec }).format(n);
  }
  pct(n: number | null | undefined, dec = 0): string {
    return n == null ? '—' : new Intl.NumberFormat(this.locale(), { style: 'percent', maximumFractionDigits: dec }).format(n);
  }
  fecha(iso: string | null | undefined, hora = false): string {
    if (!iso) return '—';
    const d = new Date(iso);
    return new Intl.DateTimeFormat(this.locale(), hora ? { dateStyle: 'medium', timeStyle: 'short' } : { dateStyle: 'medium' }).format(d);
  }
  mes(iso: string): string {
    return new Intl.DateTimeFormat(this.locale(), { month: 'short', year: '2-digit' }).format(new Date(iso));
  }
}
