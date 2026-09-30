"""
Proceso de fondo que decide cuándo corresponde ejecutar la extracción de cada conexión SNMP,
usando la librería `schedule`. La frecuencia de cada conexión se lee de la tabla monitoreo_snmp
(no es fija ni vive en el código), así que se vuelve a consultar periódicamente por si cambió.

Funciones:
- iniciar_programador() -> None: arranca el bucle principal (schedule.run_pending en un loop con
  espera de TICK_SEGUNDOS) y no retorna hasta que el proceso se detiene.
- programar_conexiones(conexiones: list[dict]) -> None: da de alta (o actualiza) en `schedule` un
  job por conexión, con el intervalo que indica su frecuencia configurada.
- refrescar_programacion() -> None: vuelve a leer monitoreo_snmp y reprograma los jobs cuya
  frecuencia cambió desde la última lectura.

Dependencias: repositorio.py (conexiones activas y su frecuencia), ciclo.py (ejecuta el ciclo de
cada conexión cuando `schedule` lo dispara), config.py (TICK_SEGUNDOS).
"""
