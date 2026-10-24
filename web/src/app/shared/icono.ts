import { Component, input } from '@angular/core';

const RUTAS: Record<string, string> = {
  recomendar: 'M4 17V7m0 0 3-3m-3 3L1 4M9 6h11M9 12h11M9 18h11',
  pendientes: 'M4 13h4l2 3h4l2-3h4M4 13V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v7M4 13v5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5',
  proveedores: 'M3 7h11v9H3zM14 10h4l3 3v3h-7M7 19a1.7 1.7 0 1 0 0-.01M17 19a1.7 1.7 0 1 0 0-.01',
  panel: 'M4 20V10m6 10V4m6 16v-7m4 7H2',
  idioma: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3 12h18M12 3c2.5 2.6 3.7 5.6 3.7 9s-1.2 6.4-3.7 9c-2.5-2.6-3.7-5.6-3.7-9S9.5 5.6 12 3z',
  salir: 'M9 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h3m6-4 4-4-4-4m4 4H9',
  ok: 'M5 12.5l4.2 4.2L19 7',
  aviso: 'M12 8v5m0 3.5v.01M10.3 3.9 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z',
  info: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 11v5m0-8.5v.01',
  alto: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM8 8l8 8M16 8l-8 8',
  flecha: 'M9 5l7 7-7 7',
  abajo: 'M5 9l7 7 7-7',
  ojo: 'M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
  ojoNo: 'M3 3l18 18M10.6 5.1A9.7 9.7 0 0 1 12 5c6.4 0 10 7 10 7a17 17 0 0 1-3.2 4M6.5 6.5C3.8 8.4 2 12 2 12s3.6 7 10 7c1.5 0 2.9-.4 4.1-1M9.9 9.9a3 3 0 0 0 4.2 4.2',
  prueba: 'M9 3h6M10 3v6L4.5 19a1.5 1.5 0 0 0 1.3 2.2h12.4A1.5 1.5 0 0 0 19.5 19L14 9V3',
  cerrar: 'M6 6l12 12M18 6 6 18',
  usuario: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0',
  sol: 'M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
  luna: 'M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z',
  auto: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 3v18M12 3a9 9 0 0 1 0 18',
  acceso: 'M12 5.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM5 8.5l7 1.5 7-1.5M12 10v4m0 0-3 6m3-6 3 6',
  libro: 'M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zM4 19a2 2 0 0 1 2-2h13',
  campana: 'M6 9a6 6 0 1 1 12 0c0 5 2 6.5 2 6.5H4S6 14 6 9zM10 19a2 2 0 0 0 4 0',
  lista: 'M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01',
  mas: 'M12 5v14M5 12h14',
  llave: 'M14 10a4 4 0 1 0-3.9 4H12l1.5 1.5L15 14l1.5 1.5L18 14l-1.3-1.3A4 4 0 0 0 14 10z',
};

@Component({
  selector: 'app-icono',
  template: `<svg [attr.width]="tam()" [attr.height]="tam()" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path [attr.d]="ruta()" /></svg>`,
  styles: ':host { display: inline-flex; flex: none; } svg { display: block; }',
})
export class Icono {
  nombre = input.required<string>();
  tam = input(20);
  ruta = () => RUTAS[this.nombre()] ?? '';
}
