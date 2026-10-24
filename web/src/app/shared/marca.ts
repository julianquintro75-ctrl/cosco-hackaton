import { Component, input } from '@angular/core';

/** Marca de la aplicación: pila de contenedores. No reproduce el logotipo de COSCO; usa sus dos colores. */
@Component({
  selector: 'app-marca',
  template: `<svg [attr.width]="tam()" [attr.height]="tam()" viewBox="0 0 32 32" aria-hidden="true">
    <rect width="32" height="32" rx="8" fill="#00508f"/><rect x="6" y="8" width="9" height="7" rx="1.2" fill="#fff"/>
    <rect x="17" y="8" width="9" height="7" rx="1.2" fill="#fff" opacity=".6"/><rect x="6" y="17" width="9" height="7" rx="1.2" fill="#d6000e"/>
    <rect x="17" y="17" width="9" height="7" rx="1.2" fill="#fff"/></svg>`,
  styles: ':host { display: inline-flex; } svg { display: block; }',
})
export class Marca { tam = input(32); }
