"""
A partir de una ficha ya normalizada, construye las filas de métrica histórica (serie temporal)
que se guardan aparte de la ficha del activo: los valores que cambian en cada ciclo (tráfico,
errores, IOPS y latencia medidos, uso de CPU/RAM, temperatura, consumo), a diferencia de los
datos descriptivos que ya viven en la ficha (modelo, número de serie, capacidad nominal, etc.).

Funciones:
- construir_metricas(tipo_activo: str, datos_normalizados: dict, marca_tiempo) -> list[dict]:
  arma la lista de filas de métrica histórica a partir de los campos variables de la ficha
  normalizada de ese activo.

Dependencias: normalizacion/estados.py y normalizacion/reglas.py (para reutilizar las mismas
conversiones de unidades que ya aplicó la normalización). Lo usa ciclo.py antes de llamar a
carga.py.
"""
