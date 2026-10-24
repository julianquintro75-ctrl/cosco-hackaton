import { InjectionToken } from '@angular/core';
import { MapaLeaflet } from './mapa-leaflet';

/** Coordenada geográfica (grados decimales). */
export interface PuntoGeo { lat: number; lon: number }

export interface EstiloRuta { color: string; ancho?: number; opacidad?: number; discontinua?: boolean }
export interface EstiloMarcador {
  tipo: 'camion' | 'ciudad' | 'parada';
  color: string;
  etiqueta?: string;       // texto accesible / tooltip
  permanente?: boolean;    // muestra la etiqueta siempre (ciudades de origen y destino)
  activo?: boolean;        // resaltado (el servicio elegido)
  alPulsar?: () => void;
}

/**
 * Puerto del mapa. La pantalla de seguimiento solo habla con esta interfaz, nunca con Leaflet directamente.
 * Para usar Google Maps (u otro proveedor) se escribe otra clase que implemente estos métodos y se cambia
 * el proveedor de MOTOR_MAPA en app.config.ts. Ver docs/SEGUIMIENTO.md.
 */
export interface MotorMapa {
  /** Crea el mapa dentro del elemento (carga la librería bajo demanda). */
  montar(el: HTMLElement): Promise<void>;
  ruta(id: string, puntos: PuntoGeo[], estilo: EstiloRuta): void;
  /** Crea el marcador o, si ya existe, lo mueve y actualiza su estilo. Se llama en cada cuadro de la animación. */
  marcador(id: string, p: PuntoGeo, estilo: EstiloMarcador): void;
  quitar(id: string): void;
  enfocar(puntos: PuntoGeo[]): void;
  destruir(): void;
}

/** Fábrica inyectable: cada pantalla crea su propio mapa. Cambiar aquí (o en app.config.ts) para otro proveedor. */
export const MOTOR_MAPA = new InjectionToken<() => MotorMapa>('MOTOR_MAPA', { providedIn: 'root', factory: () => () => new MapaLeaflet() });
