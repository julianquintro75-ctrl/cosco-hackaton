import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { CanActivateFn } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { Api } from './api';
import { CONFIG } from './config';
import { Rol, Sesion } from './modelos';

const LLAVE = 'cosco.sesion';

@Injectable({ providedIn: 'root' })
export class Auth {
  private api = inject(Api);
  private router = inject(Router);
  private _s = signal<(Sesion & { vence: number }) | null>(this.leer());
  readonly usuario = computed(() => this._s()?.usuario ?? null);
  readonly rol = computed<Rol | null>(() => this._s()?.usuario.rol ?? null);
  readonly token = computed(() => this._s()?.access_token ?? null);
  readonly activa = computed(() => !!this._s() && this._s()!.vence > Date.now());
  private reloj?: ReturnType<typeof setTimeout>;

  constructor() { this.armarReloj(); }

  private leer() {
    try {
      const s = JSON.parse(sessionStorage.getItem(LLAVE) ?? 'null');
      return s && s.vence > Date.now() ? s : null;
    } catch { return null; }
  }

  async entrar(usuario: string, clave: string) {
    const s = await this.api.login(usuario, clave);
    const conVence = { ...s, vence: Date.now() + s.expira_en * 1000 };
    this._s.set(conVence);
    try { sessionStorage.setItem(LLAVE, JSON.stringify(conVence)); } catch { /* sesión solo en memoria */ }
    this.armarReloj();
  }

  salir(vencida = false) {
    this._s.set(null);
    try { sessionStorage.removeItem(LLAVE); } catch { /* ignorar */ }
    clearTimeout(this.reloj);
    this.router.navigate(['/login'], { queryParams: vencida ? { vencida: 1 } : {} });
  }

  private armarReloj() {
    clearTimeout(this.reloj);
    const s = this._s();
    if (s) this.reloj = setTimeout(() => this.salir(true), Math.max(0, Math.min(s.vence - Date.now(), 2 ** 31 - 1)));
  }
}

export const guardia: CanActivateFn = (_r, estado) => {
  const a = inject(Auth);
  return a.activa() ? true : inject(Router).createUrlTree(['/login'], { queryParams: { volver: estado.url } });
};

/** Deja entrar a una pantalla solo a ciertos roles; el resto vuelve al inicio (el servidor también lo hace cumplir). */
export const rolGuardia = (...roles: Rol[]): CanActivateFn => () => {
  const r = inject(Auth).rol();
  return r && roles.includes(r) ? true : inject(Router).createUrlTree(['/']);
};

export const interceptor: HttpInterceptorFn = (req, next) => {
  const a = inject(Auth);
  const propia = req.url.startsWith(CONFIG.apiUrl.replace(/\/$/, ''));
  const t = a.token();
  const r = propia && t ? req.clone({ setHeaders: { Authorization: `Bearer ${t}` } }) : req;
  return next(r).pipe(catchError((e: HttpErrorResponse) => {
    if (e.status === 401 && propia && !req.url.endsWith('/auth/login')) a.salir(true);
    return throwError(() => e);
  }));
};
