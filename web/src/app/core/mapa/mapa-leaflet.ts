import type * as Leaflet from 'leaflet';
import { CONTORNO_COLOMBIA } from './colombia';
import { EstiloMarcador, EstiloRuta, MotorMapa, PuntoGeo } from './motor-mapa';

const CAMION = 'M3 7h11v9H3zM14 10h4l3 3v3h-7M7 19a1.7 1.7 0 1 0 0-.01M17 19a1.7 1.7 0 1 0 0-.01';
const esc = (s: string) => s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);

/** Adaptador con Leaflet + OpenStreetMap: gratis y sin clave. Si no hay internet queda el contorno de Colombia de fondo. */
export class MapaLeaflet implements MotorMapa {
  private L!: typeof Leaflet;
  private mapa?: Leaflet.Map;
  private capas = new Map<string, Leaflet.Polyline | Leaflet.Marker | Leaflet.CircleMarker>();
  private claves = new Map<string, string>();

  async montar(el: HTMLElement): Promise<void> {
    const m: any = await import('leaflet');
    this.L = m.default ?? m;
    const L = this.L;
    this.mapa = L.map(el, { zoomControl: true, scrollWheelZoom: false, attributionControl: true }).setView([6.6, -74.6], 6);
    L.polygon(CONTORNO_COLOMBIA, { color: '#7d8fa3', weight: 1, fillColor: '#dfe7ef', fillOpacity: 0.55, interactive: false }).addTo(this.mapa);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 12, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(this.mapa);
  }

  ruta(id: string, puntos: PuntoGeo[], e: EstiloRuta): void {
    if (!this.mapa) return;
    const op = { color: e.color, weight: e.ancho ?? 4, opacity: e.opacidad ?? 0.9, dashArray: e.discontinua ? '6 8' : undefined, lineJoin: 'round' as const };
    const previa = this.capas.get(id) as Leaflet.Polyline | undefined;
    if (previa) { previa.setStyle(op); if ((e.ancho ?? 4) > 4) previa.bringToFront(); return; }
    this.capas.set(id, this.L.polyline(puntos.map(p => [p.lat, p.lon]), op).addTo(this.mapa));
  }

  marcador(id: string, p: PuntoGeo, e: EstiloMarcador): void {
    if (!this.mapa) return;
    const L = this.L;
    const clave = `${e.tipo}|${e.color}|${e.activo ? 1 : 0}|${e.etiqueta ?? ''}`;
    let capa = this.capas.get(id) as Leaflet.Marker | Leaflet.CircleMarker | undefined;
    if (capa && this.claves.get(id) !== clave) { capa.remove(); this.capas.delete(id); capa = undefined; }
    if (capa) { capa.setLatLng([p.lat, p.lon]); return; }
    if (e.tipo === 'camion') {
      const html = `<span class="mapa-camion${e.activo ? ' activo' : ''}" style="--c:${e.color}"><svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="${CAMION}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></span>`;
      capa = L.marker([p.lat, p.lon], { icon: L.divIcon({ html, className: 'mapa-icono', iconSize: [30, 30], iconAnchor: [15, 15] }), keyboard: true, title: e.etiqueta, zIndexOffset: e.activo ? 1000 : 0 });
    } else {
      capa = L.circleMarker([p.lat, p.lon], { radius: e.tipo === 'ciudad' ? 4 : 5, color: e.color, weight: 2, fillColor: e.tipo === 'parada' ? e.color : '#fff', fillOpacity: 1 });
    }
    if (e.etiqueta) capa.bindTooltip(esc(e.etiqueta), { permanent: !!e.permanente, direction: 'right', offset: [8, 0], className: 'mapa-etiqueta' });
    if (e.alPulsar) capa.on('click', e.alPulsar);
    capa.addTo(this.mapa);
    this.capas.set(id, capa); this.claves.set(id, clave);
  }

  quitar(id: string): void { this.capas.get(id)?.remove(); this.capas.delete(id); this.claves.delete(id); }

  enfocar(puntos: PuntoGeo[]): void {
    if (!this.mapa || !puntos.length) return;
    this.mapa.flyToBounds(this.L.latLngBounds(puntos.map(p => [p.lat, p.lon])), { padding: [30, 30], maxZoom: 8, duration: 0.6 });
  }

  destruir(): void { this.mapa?.remove(); this.mapa = undefined; this.capas.clear(); this.claves.clear(); }
}
