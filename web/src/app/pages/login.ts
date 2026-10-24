import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { Auth } from '../core/auth';
import { CONFIG } from '../core/config';
import { I18n } from '../i18n/i18n.service';
import { Icono } from '../shared/icono';
import { Marca } from '../shared/marca';
import { SelectorIdioma } from '../shared/idioma';

@Component({
  selector: 'app-login',
  imports: [FormsModule, Icono, Marca, SelectorIdioma],
  template: `
    <main class="login">
      <section class="patio" aria-hidden="true">
        <svg viewBox="0 0 480 640" preserveAspectRatio="xMidYMid slice">
          @for (c of contenedores; track $index) { <rect [attr.x]="c.x" [attr.y]="c.y" width="52" height="20" rx="2" [attr.fill]="c.f" [attr.opacity]="c.o" /> }
        </svg>
        <div class="patio-texto">
          <app-marca [tam]="40" />
          <p class="lema">{{ i18n.t('login.lema') }}</p>
          <p class="pie">{{ i18n.t('login.pie') }}</p>
        </div>
      </section>

      <section class="formulario">
        <div class="barra-idioma"><app-idioma /></div>
        <form (ngSubmit)="entrar()" class="caja" autocomplete="on">
          <header>
            <h1>{{ i18n.t('login.titulo') }}</h1>
            <p class="tenue">{{ i18n.t('login.subtitulo') }}</p>
          </header>

          @if (vencida) { <div class="aviso ambar" role="status"><app-icono nombre="info" />{{ i18n.t('login.sesionVencida') }}</div> }
          @if (error()) { <div class="aviso rojo" role="alert"><app-icono nombre="aviso" />{{ error() }}</div> }

          <div class="campo">
            <label for="usuario">{{ i18n.t('login.usuario') }}</label>
            <input id="usuario" name="usuario" class="ctl" [(ngModel)]="usuario" autocomplete="username" autocapitalize="none" spellcheck="false" required />
          </div>
          <div class="campo">
            <label for="clave">{{ i18n.t('login.clave') }}</label>
            <div class="con-boton">
              <input id="clave" name="clave" class="ctl" [type]="ver() ? 'text' : 'password'" [(ngModel)]="clave" autocomplete="current-password" required />
              <button type="button" class="ojo" (click)="ver.set(!ver())" [attr.aria-label]="ver() ? i18n.t('login.ocultar') : i18n.t('login.mostrar')" [attr.aria-pressed]="ver()">
                <app-icono [nombre]="ver() ? 'ojoNo' : 'ojo'" />
              </button>
            </div>
          </div>
          <button class="btn primario" type="submit" [disabled]="enviando() || !usuario || !clave">
            @if (enviando()) { <span class="giro"></span> {{ i18n.t('login.entrando') }} } @else { {{ i18n.t('login.entrar') }} }
          </button>

          @if (demo) {
            <aside class="demo">
              <div><strong>{{ i18n.t('login.demoTitulo') }}</strong><p class="tenue peq">{{ i18n.t('login.demoTexto') }}</p></div>
              <dl class="peq">
                <div><dt>{{ i18n.t('login.usuario') }}</dt><dd class="num">{{ demo.usuario }}</dd></div>
                <div><dt>{{ i18n.t('login.clave') }}</dt><dd class="num">{{ demo.clave }}</dd></div>
              </dl>
              <button type="button" class="btn peq" (click)="usarDemo()">{{ i18n.t('login.demoUsar') }}</button>
            </aside>
          }
        </form>
        <p class="sint peq tenue">{{ i18n.t('app.sintetico') }}</p>
      </section>
    </main>`,
  styles: `
    .login { min-height: 100dvh; display: grid; grid-template-columns: minmax(340px, 5fr) 6fr; }
    .patio { position: relative; background: #00508f; color: #fff; overflow: hidden; display: grid; align-items: end; }
    .patio svg { position: absolute; inset: 0; width: 100%; height: 100%; }
    .patio-texto { position: relative; padding: 3rem; display: grid; gap: 1.25rem; background: linear-gradient(to top, #00508f 70%, rgba(0,80,143,0)); padding-top: 11rem; }
    .lema { font-size: 1.75rem; line-height: 1.25; font-weight: 700; letter-spacing: -.01em; max-width: 18ch; }
    :lang(zh-CN) .lema { max-width: 14em; letter-spacing: 0; }
    .pie { color: rgba(255,255,255,.82); max-width: 36ch; }
    .formulario { display: grid; grid-template-rows: auto 1fr auto; padding: 1rem 2rem 1.5rem; }
    .barra-idioma { display: flex; justify-content: flex-end; }
    .caja { align-self: center; justify-self: center; width: min(420px, 100%); display: grid; gap: 1.1rem; }
    header { display: grid; gap: .35rem; margin-bottom: .5rem; }
    .con-boton { position: relative; } .con-boton .ctl { padding-right: 3rem; }
    .ojo { position: absolute; right: 2px; top: 2px; width: 40px; height: 40px; border: 0; background: transparent; color: var(--tenue); border-radius: 8px; cursor: pointer; display: grid; place-items: center; }
    .ojo:hover { background: var(--linea-suave); }
    .demo { margin-top: .5rem; padding: 1rem 1.1rem; border-radius: 12px; background: var(--azul-suave); display: grid; gap: .75rem; }
    .demo dl { margin: 0; display: grid; grid-template-columns: auto 1fr; gap: .15rem 1rem; } .demo dl div { display: contents; }
    .demo dt { color: var(--tenue); } .demo dd { margin: 0; font-weight: 600; user-select: all; }
    .demo .btn { justify-self: start; }
    .sint { text-align: center; }
    @media (max-width: 860px) {
      .login { grid-template-columns: 1fr; grid-template-rows: auto 1fr; }
      .patio { min-height: 150px; } .patio-texto { padding: 1.25rem; padding-top: 3rem; gap: .6rem; } .lema { font-size: 1.15rem; } .pie { display: none; }
      .formulario { padding: 1rem 1.25rem 1.5rem; }
    }`,
})
export class Login {
  i18n = inject(I18n);
  private auth = inject(Auth);
  private router = inject(Router);
  private ruta = inject(ActivatedRoute);
  usuario = ''; clave = '';
  ver = signal(false); enviando = signal(false); error = signal('');
  demo = CONFIG.demo;
  vencida = !!this.ruta.snapshot.queryParamMap.get('vencida');
  contenedores = patio();

  usarDemo() { if (this.demo) { this.usuario = this.demo.usuario; this.clave = this.demo.clave; } }

  async entrar() {
    if (this.enviando()) return;
    this.enviando.set(true); this.error.set('');
    try {
      await this.auth.entrar(this.usuario.trim(), this.clave);
      const destino = this.ruta.snapshot.queryParamMap.get('volver');
      await this.router.navigateByUrl(destino && destino.startsWith('/') && !destino.startsWith('//') ? destino : '/recomendar');
    } catch (e) {
      const st = (e as HttpErrorResponse).status;
      this.error.set(this.i18n.t(st === 401 ? 'login.errorCredenciales' : st === 429 ? 'login.errorBloqueo' : 'login.errorRed'));
      this.clave = '';
    } finally { this.enviando.set(false); }
  }
}

/** Vista cenital de un patio de contenedores: filas con colores de la marca. Determinista (sin azar) para que no cambie entre cargas. */
function patio() {
  const colores = ['#ffffff', '#ffffff', '#7fb2de', '#4d8fc7', '#003d6f', '#003d6f', '#d6000e', '#9cc4e6'];
  const out: { x: number; y: number; f: string; o: number }[] = [];
  for (let fila = 0; fila < 22; fila++)
    for (let col = 0; col < 8; col++) {
      const h = (fila * 7 + col * 13 + fila * col * 3) % 17;
      if (h === 0 || h === 9) continue;
      out.push({ x: col * 60 - 6 + (fila % 2) * 14, y: fila * 30 - 4, f: colores[(fila * 5 + col * 3 + h) % colores.length], o: fila < 8 ? 0.95 : 0.55 });
    }
  return out;
}
