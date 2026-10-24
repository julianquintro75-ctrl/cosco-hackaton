export interface ConfigApp {
  apiUrl: string;
  demo: { usuario: string; clave: string } | null;
}
export const CONFIG: ConfigApp = { apiUrl: 'http://localhost:8000', demo: null };

/** Lee /config.json al arrancar: permite cambiar la API o apagar el acceso de demostración sin recompilar. */
export async function cargarConfig(): Promise<void> {
  try {
    const r = await fetch('config.json', { cache: 'no-store' });
    if (r.ok) Object.assign(CONFIG, await r.json());
  } catch { /* se usan los valores por defecto */ }
}
