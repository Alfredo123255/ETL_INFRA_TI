"""
Persiste en PostgreSQL, a través de repositorio.py, la ficha normalizada de un activo y sus
métricas históricas de un ciclo de extracción. Como el resto del ETL, no crea, modifica ni
elimina tablas ni restricciones: solo inserta o actualiza filas del esquema ya existente.

Funciones:
- cargar_ficha(tipo_activo: str, datos_normalizados: dict) -> None: guarda (o actualiza) la fila
  de la ficha del activo.
- cargar_metricas(tipo_activo: str, metricas: list[dict]) -> None: guarda las filas de métrica
  histórica generadas por metricas.py.

Dependencias: repositorio.py (ejecuta el SQL parametrizado), db.py (conexión). Lo usa ciclo.py al
final de cada ciclo de extracción.
"""
