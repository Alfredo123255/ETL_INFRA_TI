"""
Convierte el diccionario oid -> valor crudo de una unidad de storage (extraccion/storage.py) a
la estructura de la ficha de Storage del esquema, usando pandas, transcribiendo
mibs/hpe-real/MAPEO-STORAGE.md completo: sus reglas de coherencia de capacidad
(capacidad_total_TB, capacidad_usada_TB y volumen lógico según nivel RAID) y su nota de
limitación sobre qué campos provienen del servidor que administra el arreglo.

Funciones:
- normalizar_storage(datos_crudos: dict) -> dict: aplica las conversiones, la traducción de
  estados y la regla de capacidad útil de RAID (normalizacion/reglas.py) y arma el diccionario
  con los campos de la ficha de Storage, sus discos y sus controladorasRAID.

Dependencias: normalizacion/estados.py, normalizacion/reglas.py, pandas.
"""
