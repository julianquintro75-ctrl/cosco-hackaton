import { Injectable, effect, signal } from '@angular/core';

export type Tema = 'sistema' | 'claro' | 'oscuro';
const LLAVE = 'cosco.preferencias';
interface Datos { tema: Tema; escala: number; contraste: boolean; sinMovimiento: boolean }
const BASE: Datos = { tema: 'sistema', escala: 1, contraste: false, sinMovimiento: false };

function leer(): Datos {
  try { return { ...BASE, ...JSON.parse(localStorage.getItem(LLAVE) ?? '{}') }; } catch { return { ...BASE }; }
}

/** Preferencias de apariencia y accesibilidad de la persona (se guardan en su navegador). */
@Injectable({ providedIn: 'root' })
export class Preferencias {
  private ini = leer();
  readonly tema = signal<Tema>(this.ini.tema);
  readonly escala = signal<number>(this.ini.escala);
  readonly contraste = signal<boolean>(this.ini.contraste);
  readonly sinMovimiento = signal<boolean>(this.ini.sinMovimiento);

  constructor() {
    effect(() => {
      const r = document.documentElement;
      this.tema() === 'sistema' ? r.removeAttribute('data-tema') : r.setAttribute('data-tema', this.tema());
      r.style.setProperty('--escala', String(this.escala()));
      this.contraste() ? r.setAttribute('data-contraste', '') : r.removeAttribute('data-contraste');
      this.sinMovimiento() ? r.setAttribute('data-movimiento', 'reducido') : r.removeAttribute('data-movimiento');
      try { localStorage.setItem(LLAVE, JSON.stringify({ tema: this.tema(), escala: this.escala(), contraste: this.contraste(), sinMovimiento: this.sinMovimiento() })); } catch { /* ignorar */ }
    });
  }

  ciclarTema() { this.tema.set(this.tema() === 'sistema' ? 'claro' : this.tema() === 'claro' ? 'oscuro' : 'sistema'); }
  restablecer() { this.tema.set('sistema'); this.escala.set(1); this.contraste.set(false); this.sinMovimiento.set(false); }
}
