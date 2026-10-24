# Paso 6 · Pruebas de casos difíciles
```
tests/test_casos.py::test_refrigerada_solo_reefer PASSED                 [ 10%]
tests/test_casos.py::test_peligrosa_solo_imo PASSED                      [ 20%]
tests/test_casos.py::test_c2_cama_baja_sin_opcion PASSED                 [ 30%]
tests/test_casos.py::test_plazo_imposible_escala PASSED                  [ 40%]
tests/test_casos.py::test_nuevo_rumbo_prudente PASSED                    [ 50%]
tests/test_casos.py::test_andina_detecta_deterioro PASSED                [ 60%]
tests/test_casos.py::test_orden_de_proveedores_no_importa PASSED         [ 70%]
tests/test_casos.py::test_determinismo PASSED                            [ 80%]
tests/test_casos.py::test_tres_niveles_cambian_razonablemente PASSED     [ 90%]
tests/test_casos.py::test_ningun_descartado_en_top3_y_contrato PASSED    [100%]
============================= 10 passed in 21.02s ==============================
```

Nota sobre Andina Cargo: en julio es Top-1 en ~82 % de los Urgentes y está en el Top-3 del ~91 % de los Estándar; no es Top-1 en la mayoría de Estándar porque TransPacífico (ya recuperado) y Económica del Sur tienen menor costo esperado *real* según la verdad oculta en esos corredores. Desde el 14 de septiembre cae a ~7 % de Top-1 en Urgente.
