"""Paso 4 · Estadisticas bayesianas con decaimiento temporal por proveedor x corredor x tipo de carga.

Para cada combinacion, usando SOLO servicios con entrega_real <= as_of:
  peso de cada servicio  w = 0.5 ** (edad_dias / vida_media)
  p_tarde = (tarde_ponderado + beta0) / (n_ponderado + alfa0 + beta0)       prior Beta(17, 3) = 85 % a tiempo, fuerza 20
  IC 90 % de p_tarde con scipy.stats.beta; P50/P90 del transito (horas, ponderados); tasa de incidentes y de rechazo con prior;
  Indice de Dureza (seccion 6 del PDF):
     10 x [0.50 x limite inferior IC puntualidad + 0.20 x (1 - variabilidad normalizada)
           + 0.15 x (1 - incidentes normalizados) + 0.15 x (1 - tasa de rechazo)]
Respaldo cuando no hay datos: 'corredor' (la combinacion exacta) -> 'corredor_cualquier_carga' -> 'proveedor' -> 'global'.
Nunca lee verdad_oculta.csv."""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import beta as beta_dist

from engine.datos import Base, base_compartida, cargar_config

CARGAS = ("general", "refrigerada", "peligrosa", "sobredimensionada")
CERT_CARGA = {"refrigerada": "REEFER", "peligrosa": "IMO", "sobredimensionada": "SOBREDIMENSIONADA"}


def cuantil_ponderado(x: np.ndarray, w: np.ndarray, q: float) -> float:
    if len(x) == 0:
        return float("nan")
    o = np.argsort(x, kind="stable"); x, w = x[o], w[o]
    cw = np.cumsum(w) - 0.5 * w
    cw /= w.sum()
    return float(np.interp(q, cw, x))


def banda(dureza: float | None, cfg: dict) -> str | None:
    if dureza is None or np.isnan(dureza):
        return None
    for lim, nombre in cfg["dureza_bandas"]:
        if dureza >= lim:
            return nombre
    return cfg["dureza_bandas"][-1][1]


class Estadisticas:
    """Estadisticas con as_of. Implementacion con indices numpy por grupo (rapida para backtest y API)."""

    def __init__(self, base: Base | None = None, cfg: dict | None = None):
        self.base = base or base_compartida()
        self.cfg = cfg or cargar_config()
        self._cache: dict = {}
        self._idx_version = None

    # ---------- indices precalculados (se rehacen si cambian los datos) ----------
    def _indices(self):
        b = self.base
        if self._idx_version == b.version_datos:
            return
        e = b.entregados                      # ordenado por entrega_real
        self._t = e.entrega_real.values.astype("datetime64[m]")
        self._dias = (e.entrega_real - pd.Timestamp("2000-01-01")).dt.total_seconds().values / 86400
        self._late = 1.0 - e.a_tiempo.values.astype(float)
        self._inc = e.incidente.values.astype(float)
        self._tr = e.transito_h.values.astype(float)
        self._plan = e.plan_h.values.astype(float)
        self._cor = e.corredor_id.values
        self._g3 = {k: np.asarray(v) for k, v in e.groupby(["proveedor_id", "corredor_id", "tipo_carga"]).indices.items()}
        self._g2 = {k: np.asarray(v) for k, v in e.groupby(["proveedor_id", "corredor_id"]).indices.items()}
        self._g1 = {k: np.asarray(v) for k, v in e.groupby("proveedor_id").indices.items()}
        self._gc = {k: np.asarray(v) for k, v in e.groupby("corredor_id").indices.items()}
        a = b.servicios_todos.sort_values("fecha_cargue").reset_index(drop=True)
        self._a_t = a.fecha_cargue.values.astype("datetime64[m]")
        self._a_dias = (a.fecha_cargue - pd.Timestamp("2000-01-01")).dt.total_seconds().values / 86400
        self._a_canc = np.isin(a.estado.values, ["CANCELADO", "RECHAZADO"]).astype(float)
        self._a_g = {k: np.asarray(v) for k, v in a.groupby("proveedor_id").indices.items()}
        self._idx_version = b.version_datos
        self._cache.clear()

    def _k(self, as_of, t):
        return int(np.searchsorted(t, np.datetime64(pd.Timestamp(as_of).to_datetime64(), "m"), side="right"))

    @staticmethod
    def _antes(idx, k):
        return idx[: np.searchsorted(idx, k)] if idx is not None else np.empty(0, int)

    def _w(self, idx, as_of_dias, hl, dias):
        if not hl:
            return np.ones(len(idx))
        return 0.5 ** (np.maximum(as_of_dias - dias[idx], 0) / hl)

    def _ctx(self, as_of):
        """Lo que no depende del proveedor: corte k, medianas de transito y de plan por corredor hasta as_of."""
        self._indices()
        key = ("ctx", pd.Timestamp(as_of).floor("min"))
        if key not in self._cache:
            if len(self._cache) > 20000:
                self._cache.clear()
            k = self._k(as_of, self._t)
            med, plan = {}, {}
            for c, idx in self._gc.items():
                ii = self._antes(idx, k)
                if len(ii):
                    med[c] = float(np.median(self._tr[ii])); plan[c] = float(np.median(self._plan[ii]))
            as_d = (pd.Timestamp(as_of) - pd.Timestamp("2000-01-01")).total_seconds() / 86400
            self._cache[key] = dict(k=k, med=med, plan=plan, as_d=as_d, ka=self._k(as_of, self._a_t))
        return self._cache[key]

    def indices_corredor(self, as_of, corredor):
        """Indices de servicios del corredor hasta as_of (para P(no cumplir plazo) en el motor)."""
        X = self._ctx(as_of)
        return self._antes(self._gc.get(corredor), X["k"])

    # ---------- estadistica de una combinacion ----------
    def combo(self, as_of, pid: str, corredor: str, carga: str = "general", vida_media=None) -> dict:
        cfg = self.cfg
        hl = cfg["vida_media_dias"] if vida_media is None else vida_media
        X = self._ctx(as_of)
        key = ("c", pd.Timestamp(as_of).floor("min"), hl, pid, corredor, carga)
        if key in self._cache:
            return self._cache[key]
        A0, B0 = cfg["prior_alfa"], cfg["prior_beta"]
        k, as_d = X["k"], X["as_d"]
        nivel, idx = "global", np.empty(0, int)
        for nv, ii in (("corredor", self._g3.get((pid, corredor, carga))), ("corredor_cualquier_carga", self._g2.get((pid, corredor))),
                       ("proveedor", self._g1.get(pid))):
            ii = self._antes(ii, k)
            if len(ii):
                nivel, idx = nv, ii; break
        w = self._w(idx, as_d, hl, self._dias)
        n_w, late_w, inc_w, n_raw = float(w.sum()), float((w * self._late[idx]).sum()), float((w * self._inc[idx]).sum()), len(idx)
        p_tarde = (late_w + B0) / (n_w + A0 + B0)
        if nivel in ("corredor", "corredor_cualquier_carga"):
            a_post, b_post = B0 + late_w, A0 + (n_w - late_w)          # distribucion de p_tarde
        else:  # sin evidencia en el corredor: incertidumbre de la previa (fuerza 20) centrada en la estimacion de respaldo
            f = A0 + B0
            a_post, b_post = f * p_tarde, f * (1 - p_tarde)
        lo, hi = beta_dist.ppf([0.05, 0.95], a_post, b_post)
        tasa_inc = (inc_w + cfg["prior_incidente_tasa"] * cfg["prior_incidente_fuerza"]) / (n_w + cfg["prior_incidente_fuerza"])

        # transito: percentiles ponderados en el corredor; si hay pocos, razon del proveedor x mediana del corredor
        med_c = X["med"].get(corredor)
        if med_c is None:
            med_c = float(self.base.corredores.loc[corredor].distancia_km / 42 + 6)   # referencia fisica si nunca se sirvio
        if nivel != "proveedor" and len(idx) >= cfg["min_obs_transito"]:
            p50 = cuantil_ponderado(self._tr[idx], w, 0.5); p90 = cuantil_ponderado(self._tr[idx], w, 0.9)
            transito_fuente = "corredor"
        else:
            sp = self._antes(self._g1.get(pid), k)
            if len(sp) >= cfg["min_obs_transito"]:
                ratio = self._tr[sp] / np.array([X["med"].get(c, np.nan) for c in self._cor[sp]])
                ws = self._w(sp, as_d, hl, self._dias)
                r50, r90 = cuantil_ponderado(ratio, ws, 0.5), cuantil_ponderado(ratio, ws, 0.9)
                transito_fuente = "proveedor"
            else:
                ec = self.indices_corredor(as_of, corredor)
                if len(ec) >= cfg["min_obs_transito"]:
                    r50, r90 = 1.0, cuantil_ponderado(self._tr[ec] / med_c, self._w(ec, as_d, hl, self._dias), 0.9)
                else:
                    r50, r90 = 1.0, 1.6
                transito_fuente = "global"
            p50, p90 = r50 * med_c, r90 * med_c

        # rechazo por proveedor (se conoce al cargue)
        ia = self._antes(self._a_g.get(pid), X["ka"])
        wa = self._w(ia, as_d, hl, self._a_dias)
        cw, ww = float((wa * self._a_canc[ia]).sum()), float(wa.sum())
        tasa_rech = (cw + cfg["prior_rechazo_tasa"] * cfg["prior_rechazo_fuerza"]) / (ww + cfg["prior_rechazo_fuerza"])

        # Indice de Dureza
        pw, nm = cfg["dureza_pesos"], cfg["dureza_norm"]
        li_punt = 1 - hi
        cv = (p90 - p50) / p50 if p50 > 0 else 1.0
        var_n = float(np.clip(cv / nm["cv_transito_max"], 0, 1))
        inc_n = float(np.clip(tasa_inc / nm["incidente_max"], 0, 1))
        dureza = 10 * (pw["puntualidad_li"] * li_punt + pw["variabilidad"] * (1 - var_n) + pw["incidentes"] * (1 - inc_n) + pw["rechazo"] * (1 - tasa_rech))
        dureza = float(np.clip(dureza, 0, 10))
        g1 = self._antes(self._g1.get(pid), k)
        out = dict(proveedor_id=pid, corredor_id=corredor, tipo_carga=carga, alfa=A0 + (n_w - late_w), beta=B0 + late_w,
                   p_tarde=float(p_tarde), ic90_p_tarde=(float(lo), float(hi)), ic90_ancho=float(hi - lo),
                   transito_p50_h=float(p50), transito_p90_h=float(p90), transito_fuente=transito_fuente,
                   n_servicios=n_raw if nivel in ("corredor", "corredor_cualquier_carga") else 0,
                   n_ponderado=n_w, n_proveedor=len(g1),
                   tasa_incidente=float(tasa_inc), tasa_rechazo=float(tasa_rech), indice_dureza=round(dureza, 2),
                   banda_dureza=banda(dureza, cfg), nivel_respaldo=nivel, vida_media=hl)
        self._cache[key] = out
        return out

    def tendencia(self, as_of, pid, corredor=None, carga="general") -> float:
        """Cambio de P(tarde) del proveedor: ultimos N dias frente al ano anterior (todos sus corredores).
        Devuelve la diferencia (positivo = empeora) solo si es estadisticamente significativa (binomial unilateral p<0.05);
        si no, 0. Es una alerta: el ranking usa la estimacion bayesiana, no esta cifra."""
        from scipy.stats import binomtest
        cfg = self.cfg
        X = self._ctx(as_of)
        key = ("t", pd.Timestamp(as_of).floor("min"), pid)
        if key in self._cache:
            return self._cache[key]
        ii = self._antes(self._g1.get(pid), X["k"])
        edad = X["as_d"] - self._dias[ii]
        ventana = cfg.get("tendencia_ventana_dias", 30)
        rec, ant = ii[edad <= ventana], ii[(edad > ventana) & (edad <= 365)]
        out = 0.0
        if len(rec) >= 10 and len(ant) >= 20:
            p_rec, p_ant = self._late[rec].mean(), self._late[ant].mean()
            if p_rec - p_ant >= cfg["tendencia_umbral"]:
                if binomtest(int(self._late[rec].sum()), len(rec), max(p_ant, 0.01), alternative="greater").pvalue < 0.05:
                    out = float(p_rec - p_ant)
        self._cache[key] = out
        return out

    def tabla(self, as_of, vida_media=None) -> pd.DataFrame:
        """Todas las combinaciones proveedor x corredor (con tarifa) x tipo de carga (que puede atender)."""
        b = self.base
        filas = []
        for (pid, cor) in sorted(set(zip(b.tarifas.proveedor_id, b.tarifas.corredor_id))):
            certs = set(b.certs[b.certs.proveedor_id == pid].tipo)
            for carga in CARGAS:
                if carga != "general" and CERT_CARGA[carga] not in certs:
                    continue
                filas.append(self.combo(as_of, pid, cor, carga, vida_media))
        return pd.DataFrame(filas)


# ---------- API del paso 4 ----------
COLS_TABLA = ["proveedor_id", "corredor_id", "tipo_carga", "alfa", "beta", "p_tarde", "ic90_ancho", "transito_p50_h", "transito_p90_h",
              "n_servicios", "tasa_incidente", "indice_dureza", "actualizado", "nivel_respaldo"]


def calcular(as_of, vida_media=None, db=None, escribir=True, base: Base | None = None) -> pd.DataFrame:
    """Recalcula y (por defecto) escribe la tabla estadistica_proveedor con lo que se sabia en as_of."""
    base = base or (Base(db) if db else base_compartida())
    est = Estadisticas(base)
    df = est.tabla(as_of, vida_media)
    df["actualizado"] = pd.Timestamp(as_of).isoformat(timespec="minutes")
    if escribir:
        base.repo.reemplazar_estadisticas(df[COLS_TABLA])
    return df


def actualizar_con_servicio(cierre, db=None, base: Base | None = None, cfg: dict | None = None) -> dict:
    """Aprendizaje instantaneo: al cerrar un servicio, decae la evidencia guardada hasta la fecha del cierre y suma la nueva.
    `cierre` es un CierreServicioIn (o dict con servicio_id, entrega_real, a_tiempo, hubo_incidente)."""
    from scipy.stats import beta as B
    cfg = cfg or cargar_config()
    c = cierre if isinstance(cierre, dict) else cierre.model_dump()
    base = base or (Base(db) if db else base_compartida())
    repo = base.repo
    ctx = repo.contexto_servicio(c["servicio_id"])
    if ctx is None:
        raise KeyError(f"servicio {c['servicio_id']} no existe")
    pid, cor, carga = ctx
    t = pd.Timestamp(c["entrega_real"])
    A0, B0, hl = cfg["prior_alfa"], cfg["prior_beta"], cfg["vida_media_dias"]
    fila = repo.estadistica(pid, cor, carga)
    if fila:
        alfa, bet, n, tinc, act = fila["alfa"], fila["beta"], fila["n_servicios"], fila["tasa_incidente"], fila["actualizado"]
        dec = 0.5 ** (max((t - pd.Timestamp(act)).total_seconds() / 86400, 0) / hl)
        ev_ok, ev_late = (alfa - A0) * dec, (bet - B0) * dec
    else:
        ev_ok = ev_late = 0.0; n = 0; tinc = cfg["prior_incidente_tasa"]
    ev_ok += int(bool(c["a_tiempo"])); ev_late += int(not c["a_tiempo"])
    alfa, bet = A0 + ev_ok, B0 + ev_late
    p = bet / (alfa + bet)
    lo, hi = B.ppf([0.05, 0.95], bet, alfa)
    nw = ev_ok + ev_late; F = cfg["prior_incidente_fuerza"]
    inc_prev = max(tinc * (nw - 1 + F) - cfg["prior_incidente_tasa"] * F, 0)
    tinc = (inc_prev + int(bool(c.get("hubo_incidente"))) + cfg["prior_incidente_tasa"] * F) / (nw + F)
    repo.guardar_estadistica(dict(proveedor_id=pid, corredor_id=cor, tipo_carga=carga, alfa=alfa, beta=bet, p_tarde=p, ic90_ancho=hi - lo,
                                  n_servicios=(n or 0) + 1, tasa_incidente=tinc, actualizado=t.isoformat(timespec="minutes")))
    return dict(proveedor_id=pid, corredor_id=cor, tipo_carga=carga, p_tarde=p, ic90_ancho=hi - lo, n_servicios=(n or 0) + 1)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--as-of", default="2026-09-30"); ap.add_argument("--vida-media", type=float)
    a = ap.parse_args()
    df = calcular(a.as_of, a.vida_media)
    print(f"{len(df)} filas escritas en estadistica_proveedor (as_of={a.as_of})")
    print(df[df.tipo_carga == "general"].groupby("proveedor_id")[["p_tarde", "indice_dureza"]].mean().round(3).to_string())
