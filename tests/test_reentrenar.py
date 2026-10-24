"""Reentrenamiento nocturno: ventanas móviles sin fuga, regla de publicación y registro."""
import importlib
import json


def test_dry_run_no_publica_ni_registra(db_copia, monkeypatch, tmp_path):
    monkeypatch.setenv("COSCO_DB", str(db_copia))
    monkeypatch.setenv("COSCO_LOG_REENTRENAMIENTO", str(tmp_path / "log.jsonl"))
    import scripts.reentrenar as r
    r = importlib.reload(r)
    reg = r.corrida(dry_run=True)
    c_tr, c_ca, c_va = reg["cortes"]
    assert c_tr < c_ca < c_va                      # ventanas ordenadas: entrenamiento < calibración < validación
    assert reg["M1"]["decision"] in ("usar_ml", "mantener_bayes") and reg["M2"]["decision"] in ("usar_ml", "mantener_bayes")
    assert reg["dry_run"] and not (tmp_path / "log.jsonl").exists()
    assert not (r.modelos.DIR_MODELOS / "_tmp_candidato").exists()


def test_publica_solo_si_mejora_y_deja_pendiente(db_copia, monkeypatch, tmp_path):
    monkeypatch.setenv("COSCO_DB", str(db_copia))
    monkeypatch.setenv("COSCO_LOG_REENTRENAMIENTO", str(tmp_path / "log.jsonl"))
    import scripts.reentrenar as r
    r = importlib.reload(r)
    monkeypatch.setattr(r, "CANDIDATO", tmp_path / "candidato")
    reg = r.corrida()
    linea = json.loads((tmp_path / "log.jsonl").read_text(encoding="utf8").splitlines()[-1])
    assert linea["publicado"] == reg["publicado"]
    for v in reg["publicado"]:                      # todo lo publicado exige que la decisión haya sido «usar_ml»
        assert reg["M1" if v.startswith("M1") else "M2"]["decision"] == "usar_ml"
    if not reg["publicado"]:
        assert not (tmp_path / "candidato").exists()
    import sqlite3
    filas = sqlite3.connect(db_copia).execute("SELECT aprobado_por FROM modelo_version WHERE modelo_version LIKE 'M%-20%'").fetchall()
    assert all(f[0] == "pendiente de aprobacion" for f in filas)   # nunca se activa solo
