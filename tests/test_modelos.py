"""Paso 10 · las variables de los modelos no usan informacion posterior a la solicitud."""
import numpy as np
import pandas as pd
from engine.datos import Base
from engine.modelos import construir_dataset


def test_sin_fuga(db_copia):
    b = Base(db_copia)
    df = construir_dataset(b)
    e = b.entregados
    for r in df.sample(60, random_state=1).itertuples():
        prev = e[(e.proveedor_id == r.proveedor_id) & (e.entrega_real <= r.fecha_solicitud)]
        assert r.n_365 == ((r.fecha_solicitud - prev.entrega_real).dt.total_seconds() / 86400 <= 365).sum()
        assert r.exp_corredor == (prev.corredor_id == r.corredor_id).sum()
        # el propio servicio nunca esta en sus variables (se entrega despues de solicitarse)
        assert not (prev.servicio_id == r.servicio_id).any()
