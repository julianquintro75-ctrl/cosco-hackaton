import { describe, expect, it } from 'vitest';
import { es } from './es';
import { en } from './en';
import { zh } from './zh';

describe('diccionarios', () => {
  const claves = Object.keys(es).sort();
  it.each([['en', en], ['zh', zh]])('%s tiene exactamente las claves del español', (_n, d) => {
    expect(Object.keys(d).sort()).toEqual(claves);
  });
  it.each([['en', en], ['zh', zh]])('%s no deja valores vacíos y conserva los parámetros', (_n, d) => {
    for (const [k, v] of Object.entries(d)) {
      expect(v.trim(), k).not.toBe('');
      const ps = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join();
      expect(ps(v), k).toBe(ps((es as Record<string, string>)[k]));
    }
  });
});
