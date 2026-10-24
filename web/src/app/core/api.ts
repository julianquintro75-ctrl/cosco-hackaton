import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { CONFIG } from './config';
import { Ficha, Nivel, Pendiente, Recomendacion, Sesion, Solicitud, Tablas } from './modelos';

@Injectable({ providedIn: 'root' })
export class Api {
  private http = inject(HttpClient);
  private u = (p: string) => CONFIG.apiUrl.replace(/\/$/, '') + p;
  private cache = new Map<string, Promise<unknown>>();

  /** Para datos de referencia que no cambian durante la sesión (se piden una sola vez). */
  private una<T>(clave: string, f: () => Promise<T>): Promise<T> {
    if (!this.cache.has(clave)) this.cache.set(clave, f().catch(e => { this.cache.delete(clave); throw e; }));
    return this.cache.get(clave) as Promise<T>;
  }

  login(usuario: string, clave: string) { return firstValueFrom(this.http.post<Sesion>(this.u('/auth/login'), { usuario, clave })); }
  config() { return this.una('config', () => firstValueFrom(this.http.get<Record<string, any>>(this.u('/config')))); }
  tablas() { return this.una('tablas', () => firstValueFrom(this.http.get<Tablas>(this.u('/datos/tablas')))); }
  solicitudesPrueba() { return this.una('prueba', () => firstValueFrom(this.http.get<Solicitud[]>(this.u('/solicitudes/prueba')))); }
  solicitud(id: string) { return firstValueFrom(this.http.get<Solicitud>(this.u(`/solicitudes/${encodeURIComponent(id)}`))); }
  decisionDe(id: string) { return firstValueFrom(this.http.get<{ usuario: string; proveedor_elegido: string } | null>(this.u(`/decisiones/${encodeURIComponent(id)}`))); }
  pendientes(filtro: 'revision' | 'gerencia') { return firstValueFrom(this.http.get<Pendiente[]>(this.u('/pendientes'), { params: { filtro } })); }
  ficha(pid: string) { return this.una('ficha' + pid, () => firstValueFrom(this.http.get<Ficha>(this.u(`/proveedores/${pid}/ficha`)))); }
  decisiones() { return firstValueFrom(this.http.get<{ acepto_recomendacion?: number }[]>(this.u('/tableros/decisiones'))); }

  recomendar(s: Solicitud, nivel: Nivel) {
    const body = { solicitud_id: s.solicitud_id, cliente_id: s.cliente_id, corredor_id: s.corredor_id, tipo_vehiculo_req: s.tipo_vehiculo_req,
      tipo_carga: s.tipo_carga, peso_ton: s.peso_ton, mercancia_peligrosa: !!s.mercancia_peligrosa, fecha_cargue: s.fecha_cargue,
      plazo_entrega: s.plazo_entrega, nivel_servicio: nivel, tarifa_cliente: s.tarifa_cliente };
    return firstValueFrom(this.http.post<Recomendacion>(this.u('/recomendar'), body));
  }
  decidir(rec: Recomendacion, proveedorId: string, motivo: string | null) {
    return firstValueFrom(this.http.post<Record<string, unknown>>(this.u('/decision'),
      { recomendacion_id: rec.recomendacion_id, solicitud_id: rec.solicitud_id, proveedor_elegido: proveedorId, usuario: 'sesion', motivo }));
  }
}
