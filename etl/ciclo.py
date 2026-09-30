"""
Orquesta un ciclo completo de extracción para una única conexión SNMP: extraer, normalizar y
cargar, en ese orden, dejando registrado el resultado (éxito o error) de la conexión.

Funciones:
- ejecutar_ciclo(conexion_datos: dict) -> dict: recibe los datos de una fila de monitoreo_snmp
  (host, puerto, credenciales cifradas, tipo de activo), ejecuta extracción → normalización →
  construcción de métricas → carga, actualiza el estado de la conexión en la base y devuelve un
  resumen del resultado (éxito/error, cantidad de campos cargados).

Dependencias: detector.py (resuelve extractor y normalizador según el tipo de activo),
snmp_cliente.py, cifrado.py, metricas.py, carga.py, repositorio.py. Lo usan programador.py (en
cada tick programado) y api/main.py (en la ruta de extracción inmediata).
"""
