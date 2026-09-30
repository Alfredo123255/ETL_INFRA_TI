"""
Reúne las conversiones de unidades y reglas de cálculo que se repiten entre varios tipos de
activo, para no duplicarlas en cada módulo de normalizacion/: MB/KB a GB/TB, MHz a GHz, cantidad
de hilos a partir de núcleos y de hilos por núcleo, y la regla de coherencia de capacidad de RAID
(capacidad útil según nivel RAID, documentada en mibs/hpe-real/MAPEO-STORAGE.md sección 4.3).

Funciones:
- mb_a_gb(valor_mb: float) -> float: conversión de unidades de capacidad.
- kb_a_gb(valor_kb: float) -> float: conversión de unidades de capacidad.
- mhz_a_ghz(valor_mhz: float) -> float: conversión de velocidad de CPU/RAM.
- calcular_hilos(nucleos: int, hilos_por_nucleo: int) -> int: multiplica ambos valores.
- capacidad_util_raid(capacidad_total_mb: float, nivel_raid: str, cantidad_discos: int) -> float:
  aplica la regla de capacidad útil según el nivel de tolerancia a fallas (ninguna, espejado,
  guarda de datos simple o distribuida, guarda de datos avanzada).

Dependencias: ninguna de este proyecto. Lo usan normalizacion/servidor.py, blade.py, chasis.py y
storage.py.
"""
