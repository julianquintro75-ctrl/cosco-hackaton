import { Component, DestroyRef, ElementRef, afterNextRender, computed, inject, input, signal, viewChild } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../core/api';
import { Auth } from '../core/auth';
import { MOTOR_MAPA, MotorMapa, PuntoGeo } from '../core/mapa/motor-mapa';
import { ServicioSeguimiento } from '../core/modelos';
import { I18n } from '../i18n/i18n.service';
import { Icono } from '../shared/icono';

const COLORES = ['#00508f', '#d6000e', '#0f8a63', '#8a5200', '#6a3fb5', '#00838f', '#b8336a', '#4d6a88'];
const CICLO_S = 24;          // segundos reales que dura un recorrido completo en la animación (a velocidad 1×)
const PAUSA_FINAL_S = 2.5;   // al llegar se queda quieto un momento antes de repetir

/** 'YYYY-MM-DDTHH:mm' en hora local (las horas del servidor no traen zona: son hora de Colombia). */
const horaLocal = (ms: number) => { const d = new Date(ms), z = (n: number) => String(n).padStart(2, '0'); return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}`; };

interface Estado { f: number; t: string; pos: PuntoGeo; fase: 'por_salir' | 'en_ruta' | 'detenido' | 'entregado'; ciudad: string }

/** Seguimiento en ruta. Habla con el mapa solo a través de MotorMapa (hoy Leaflet; mañana Google Maps u otro). */
@Component({
  selector: 'app-seguimiento',
  imports: [RouterLink, Icono],
  template: `
  <div class="pagina">
    <header class="cabecera-pagina"><h1>{{ i18n.t('seg.titulo') }}</h1><p>{{ i18n.t('seg.ayuda') }}</p></header>
    <div class="aviso info" role="note"><app-icono nombre="info" /><div>{{ i18n.t('seg.simulado') }}</div></div>

    @if (error()) {
      <div class="error-caja" role="alert"><strong>{{ i18n.t('c.error') }}</strong><button class="btn" type="button" (click)="cargar()">{{ i18n.t('c.reintentar') }}</button></div>
    }
    <div class="rejilla">
      <section class="tarjeta mapa-caja">
        <div class="controles">
          <button type="button" class="btn peq" (click)="alternar()" [attr.aria-pressed]="!corriendo()">
            <app-icono [nombre]="corriendo() ? 'pausa' : 'play'" [tam]="16" />{{ i18n.t(corriendo() ? 'seg.pausa' : 'seg.reproducir') }}</button>
          <button type="button" class="btn peq fantasma" (click)="reiniciar()"><app-icono nombre="reiniciar" [tam]="16" />{{ i18n.t('seg.reiniciar') }}</button>
          <div class="segmentos vel" role="radiogroup" [attr.aria-label]="i18n.t('seg.velocidad')">
            @for (v of velocidades; track v) { <button type="button" role="radio" [attr.aria-checked]="velocidad() === v" (click)="velocidad.set(v)">{{ v }}×</button> }
          </div>
          <span class="espacio"></span>
          @if (sel(); as s) { <span class="peq tenue reloj">{{ i18n.t('seg.reloj') }} <b class="num">{{ i18n.fecha(estado()[s.servicio_id]?.t, true) }}</b></span> }
        </div>
        <div #mapa class="mapa" role="application" [attr.aria-label]="i18n.t('seg.mapa')"></div>
        <p class="peq tenue pie">{{ i18n.t('seg.leyenda') }}</p>
      </section>

      <section class="lista" aria-live="off">
        @if (cargando()) { <p class="tenue" role="status"><span class="giro"></span> {{ i18n.t('c.cargando') }}</p> }
        @for (g of grupos(); track g.clave) {
          <h2>{{ i18n.t(g.clave) }} <span class="chip num">{{ g.items.length }}</span></h2>
          @if (!g.items.length) { <p class="peq tenue vacio">{{ i18n.t(esSolicitante() ? 'seg.vacioSolicitante' : 'seg.vacioEnCurso') }}</p> }
          <ul>
            @for (s of g.items; track s.servicio_id) {
              @let e = estado()[s.servicio_id];
              <li>
                <button type="button" class="item tarjeta" [class.activo]="sel()?.servicio_id === s.servicio_id" (click)="elegir(s)" [attr.aria-pressed]="sel()?.servicio_id === s.servicio_id">
                  <span class="color" [style.background]="color(s)" aria-hidden="true"></span>
                  <span class="cuerpo">
                    <span class="linea1"><strong>{{ s.proveedor }}</strong>
                      <span class="chip" [class.ok]="s.a_tiempo" [class.rojo]="!s.a_tiempo">{{ i18n.t(s.tipo === 'en_curso' ? (s.a_tiempo ? 'seg.aTiempo' : 'seg.tarde') : (s.a_tiempo ? 'seg.llegoATiempo' : 'seg.llegoTarde')) }}</span></span>
                    <span class="peq tenue">{{ s.origen }} → {{ s.destino }} · <span class="num">{{ s.solicitud_id }}</span></span>
                    <span class="barra" role="progressbar" [attr.aria-valuenow]="pct(e?.f)" aria-valuemin="0" aria-valuemax="100"><i [style.width.%]="pct(e?.f)" [style.background]="color(s)"></i></span>
                    <span class="peq">{{ fase(e) }}</span>
                    <span class="peq tenue num">{{ i18n.t('seg.llega') }} {{ i18n.fecha(s.llegada, true) }} · {{ i18n.t('seg.plazo') }} {{ i18n.fecha(s.entrega_planeada, true) }}</span>
                  </span>
                </button>
                @if (sel()?.servicio_id === s.servicio_id && !esSolicitante()) {
                  <a class="btn fantasma peq ver" [routerLink]="['/recomendar', s.solicitud_id]">{{ i18n.t('seg.verSolicitud') }}</a>
                }
              </li>
            }
          </ul>
        }
      </section>
    </div>
  </div>`,
  styles: `
    .rejilla { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 1.25rem; align-items: start; margin-top: 1rem; }
    .mapa-caja { padding: .75rem; display: grid; gap: .6rem; position: sticky; top: 1rem; }
    .mapa { height: min(68vh, 620px); border-radius: 10px; overflow: hidden; z-index: 0; }
    .controles { display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }
    .controles .btn { display: inline-flex; gap: .35rem; align-items: center; }
    .vel button { min-width: 44px; }
    .espacio { flex: 1; } .pie { margin: 0; }
    .lista { display: grid; gap: .6rem; } .lista h2 { font-size: 1rem; display: flex; gap: .5rem; align-items: center; margin: .25rem 0 0; }
    .lista ul { list-style: none; margin: 0; padding: 0; display: grid; gap: .6rem; }
    .vacio { margin: 0; }
    .item { width: 100%; text-align: left; display: grid; grid-template-columns: 6px 1fr; gap: .75rem; padding: .8rem .9rem; cursor: pointer; font: inherit; color: inherit; }
    .item.activo { border-color: var(--azul); box-shadow: 0 0 0 2px color-mix(in srgb, var(--azul) 30%, transparent); }
    .color { border-radius: 3px; }
    .cuerpo { display: grid; gap: .3rem; min-width: 0; }
    .linea1 { display: flex; justify-content: space-between; gap: .5rem; align-items: center; }
    .barra { display: block; height: 6px; border-radius: 3px; background: var(--linea-suave); overflow: hidden; }
    .barra i { display: block; height: 100%; }
    .ver { margin-top: .35rem; }
    @media (max-width: 1080px) { .rejilla { grid-template-columns: minmax(0, 1fr); } .mapa-caja { position: static; } .mapa { height: 52vh; } }`,
})
export class Seguimiento {
  i18n = inject(I18n);
  private api = inject(Api);
  private fabrica = inject(MOTOR_MAPA);
  private auth = inject(Auth);
  /** ?s=<solicitud_id> para abrir con un servicio elegido. */
  s = input<string>();

  private host = viewChild.required<ElementRef<HTMLElement>>('mapa');
  private motor?: MotorMapa;
  servicios = signal<ServicioSeguimiento[]>([]);
  cargando = signal(true);
  error = signal(false);
  sel = signal<ServicioSeguimiento | null>(null);
  corriendo = signal(!matchMedia('(prefers-reduced-motion: reduce)').matches);
  velocidad = signal(1);
  velocidades = [1, 2, 4];
  estado = signal<Record<string, Estado>>({});
  esSolicitante = computed(() => this.auth.rol() === 'solicitante');
  grupos = computed(() => {
    const l = this.servicios();
    const g = [{ clave: 'seg.enCurso', items: l.filter(s => s.tipo === 'en_curso') }];
    if (!this.esSolicitante()) g.push({ clave: 'seg.repeticiones', items: l.filter(s => s.tipo === 'repeticion') });
    return g;
  });

  private g = 0;                 // avance global de la animación (0..1)
  private espera = 0;            // segundos de pausa al final del ciclo
  private ultimo = 0;
  private ultimoPintado = 0;
  private raf = 0;
  private tiempos = new Map<string, number[]>();

  constructor() {
    afterNextRender(async () => {
      this.motor = this.fabrica();
      await this.motor.montar(this.host().nativeElement);
      await this.cargar();
      this.raf = requestAnimationFrame(t => this.cuadro(t));
    });
    inject(DestroyRef).onDestroy(() => { cancelAnimationFrame(this.raf); this.motor?.destruir(); });
  }

  async cargar() {
    this.cargando.set(true); this.error.set(false);
    try {
      const l = await this.api.seguimiento();
      this.servicios.set(l);
      this.tiempos = new Map(l.map(s => [s.servicio_id, s.puntos.map(p => Date.parse(p.t))]));
      this.dibujar();
      const pedido = this.s();
      const pedida = l.find(x => x.solicitud_id === pedido);
      this.elegir(pedida ?? l.find(x => x.tipo === 'en_curso') ?? l[0] ?? null, !!pedida);
      if (!pedida) this.motor?.enfocar(l.length ? l.flatMap(x => x.paradas) : [{ lat: 1.5, lon: -78 }, { lat: 11.5, lon: -71 }]);
      this.pintar(true);
    } catch { this.error.set(true); } finally { this.cargando.set(false); }
  }

  color(s: ServicioSeguimiento) { return COLORES[this.servicios().indexOf(s) % COLORES.length]; }
  pct(f?: number) { return Math.round((f ?? 0) * 100); }

  fase(e?: Estado) {
    if (!e) return '';
    return this.i18n.t('seg.fase.' + e.fase, { ciudad: e.ciudad });
  }

  elegir(s: ServicioSeguimiento | null, enfocar = true) {
    this.sel.set(s);
    if (!s || !this.motor) return;
    this.dibujar();
    if (enfocar) this.motor.enfocar(s.paradas);
  }

  alternar() { this.corriendo.update(v => !v); }
  reiniciar() { this.g = 0; this.espera = 0; this.pintar(true); }

  /** Rutas y ciudades (se repinta al cambiar el elegido para resaltar su ruta). */
  private dibujar() {
    const m = this.motor; if (!m) return;
    const elegido = this.sel()?.servicio_id;
    const ciudades = new Map<string, { lat: number; lon: number; extremo: boolean }>();
    for (const s of this.servicios()) {
      const activo = s.servicio_id === elegido;
      m.ruta('r-' + s.servicio_id, s.paradas, { color: this.color(s), ancho: activo ? 6 : 3, opacidad: activo ? 0.95 : 0.45, discontinua: s.tipo === 'repeticion' && !activo });
      s.paradas.forEach((p, i) => {
        const extremo = i === 0 || i === s.paradas.length - 1;
        const prev = ciudades.get(p.nombre);
        ciudades.set(p.nombre, { lat: p.lat, lon: p.lon, extremo: extremo || !!prev?.extremo });
      });
    }
    for (const [nombre, c] of ciudades) {
      m.marcador('c-' + nombre, c, { tipo: 'ciudad', color: '#4d6a88', etiqueta: nombre, permanente: c.extremo });
    }
  }

  private cuadro(t: number) {
    const dt = this.ultimo ? Math.min(0.1, (t - this.ultimo) / 1000) : 0;
    this.ultimo = t;
    if (this.corriendo() && this.servicios().length) {
      if (this.g >= 1) {
        this.espera += dt;
        if (this.espera > PAUSA_FINAL_S) { this.g = 0; this.espera = 0; }
      } else {
        this.g = Math.min(1, this.g + (dt * this.velocidad()) / CICLO_S);
      }
      this.pintar(t - this.ultimoPintado > 200);
      if (t - this.ultimoPintado > 200) this.ultimoPintado = t;
    }
    this.raf = requestAnimationFrame(x => this.cuadro(x));
  }

  /** Mueve los camiones (cada cuadro) y, cada 200 ms, actualiza el texto y las barras de la lista. */
  private pintar(conTexto: boolean) {
    const m = this.motor; if (!m) return;
    const elegido = this.sel()?.servicio_id;
    const nuevo: Record<string, Estado> = {};
    for (const s of this.servicios()) {
      const ts = this.tiempos.get(s.servicio_id)!;
      const t = ts[0] + this.g * (ts[ts.length - 1] - ts[0]);
      let i = 0;
      while (i < ts.length - 2 && ts[i + 1] <= t) i++;
      const a = s.puntos[i], b = s.puntos[i + 1] ?? a;
      const u = ts[i + 1] > ts[i] ? Math.min(1, (t - ts[i]) / (ts[i + 1] - ts[i])) : 1;
      const pos = { lat: a.lat + (b.lat - a.lat) * u, lon: a.lon + (b.lon - a.lon) * u };
      const quieto = a.evento === 'parada' && b.lat === a.lat && b.lon === a.lon;
      const fase: Estado['fase'] = this.g >= 1 ? 'entregado' : this.g === 0 ? 'por_salir' : quieto ? 'detenido' : 'en_ruta';
      const activo = s.servicio_id === elegido;
      m.marcador('k-' + s.servicio_id, pos, { tipo: 'camion', color: this.color(s), activo, etiqueta: `${s.proveedor} · ${s.origen} → ${s.destino}`, alPulsar: () => this.elegir(s) });
      if (conTexto) nuevo[s.servicio_id] = { f: this.g, t: horaLocal(t), pos, fase, ciudad: this.cercana(s, pos) };
    }
    if (conTexto) this.estado.set(nuevo);
  }

  private cercana(s: ServicioSeguimiento, p: PuntoGeo) {
    let mejor = s.paradas[0], d = Infinity;
    for (const c of s.paradas) { const x = (c.lat - p.lat) ** 2 + (c.lon - p.lon) ** 2; if (x < d) { d = x; mejor = c; } }
    return mejor.nombre;
  }
}
