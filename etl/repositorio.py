"""
Concentra todas las consultas SQL parametrizadas (con psycopg2, sin ORM) contra las tablas ya
existentes del esquema: tanto la lectura de la configuración de monitoreo como la escritura de
fichas de activos y métricas.

Funciones:
- obtener_conexiones_activas(conexion) -> list[dict]: lee de monitoreo_snmp las conexiones SNMP
  habilitadas, con su tipo de activo, host, puerto, credenciales cifradas y frecuencia
  configurada.
- obtener_frecuencia_segundos(conexion, id_conexion: int) -> int: lee la frecuencia configurada
  de una conexión puntual.
- obtener_credenciales(conexion, id_conexion: int) -> dict: lee usuario y claves SNMPv3 de una
  conexión, todavía cifradas (el descifrado lo hace quien llama, vía cifrado.py).
- guardar_ficha(conexion, tipo_activo: str, datos: dict) -> None: inserta o actualiza (upsert) la
  fila de la ficha del activo correspondiente.
- guardar_metricas(conexion, tipo_activo: str, metricas: list[dict]) -> None: inserta las filas
  de métrica histórica generadas por metricas.py.
- actualizar_estado_conexion(conexion, id_conexion: int, estado: str, mensaje: str = "") -> None:
  registra el resultado (éxito o error) del último intento de extracción de esa conexión.

Dependencias: db.py (conexión a la base). Lo usan carga.py, programador.py y ciclo.py.
"""
