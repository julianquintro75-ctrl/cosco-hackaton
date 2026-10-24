import { describe, expect, it } from 'vitest';
import { traducir } from './motor';
import type { I18n } from './i18n.service';

const falso = (idioma: 'es' | 'en' | 'zh') => ({
  idioma: () => idioma,
  cop: (n: number) => `COP ${n.toLocaleString('en-US')}`,
  num: (n: number) => String(n),
  t: (k: string) => k,
}) as unknown as I18n;

describe('traducir (texto del motor)', () => {
  it('en español no toca el texto', () => {
    expect(traducir('Poco historial: 7 servicios en el corredor', falso('es'))).toBe('Poco historial: 7 servicios en el corredor');
  });
  it('traduce alertas y reformatea el dinero', () => {
    expect(traducir('Plazo en riesgo: P90 del tránsito 85 h > plazo 32 h', falso('en'))).toBe('Deadline at risk: P90 transit 85 h > deadline 32 h');
    expect(traducir('Costo esperado $1.250.000 menor que #2 (TransPacifico)', falso('zh'))).toContain('COP 1,250,000');
  });
  it('traduce la explicación completa oración por oración', () => {
    const es = 'Se recomienda Caribe Express con costo esperado $10.405.456 y P(a tiempo) 77% (30 servicios en el corredor). Nivel Urgente: un retraso cuesta $6.000.000.';
    expect(traducir(es, falso('en'))).toBe('Caribe Express is recommended, with an expected cost of COP 10,405,456 and 77% on-time probability (30 services on this corridor). Urgent level: a delay costs COP 6,000,000.');
  });
  it('lo desconocido se muestra tal cual', () => {
    expect(traducir('Texto nuevo que ninguna plantilla conoce', falso('zh'))).toBe('Texto nuevo que ninguna plantilla conoce');
  });
});
