import json, pathlib
from contracts import SolicitudIn, RecomendacionOut, DecisionIn, CierreServicioIn
out = pathlib.Path(__file__).parent / "json_schema"; out.mkdir(exist_ok=True)
for m in (SolicitudIn, RecomendacionOut, DecisionIn, CierreServicioIn):
    (out / f"{m.__name__}.json").write_text(json.dumps(m.model_json_schema(), indent=2, ensure_ascii=False), encoding="utf8")
print("JSON Schemas en", out)
