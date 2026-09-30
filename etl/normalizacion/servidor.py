"""
Convierte el diccionario oid -> valor crudo de un servidor rack (extraccion/servidor.py) a la
estructura de la ficha de Servidor del esquema, usando pandas, transcribiendo
mibs/hpe-real/MAPEO-SERVIDOR.md: qué campo sale de qué OID, qué campos son manuales o sin fuente
y no se completan, y cuáles genera el propio ETL (como ultima_actualizacion).

Funciones:
- normalizar_servidor(datos_crudos: dict) -> dict: aplica las conversiones y traducciones de
  estado (normalizacion/estados.py, normalizacion/reglas.py) y arma un único diccionario con los
  nombres de campo de la ficha de Servidor (numero_serie, hostname, modelo, cpuTotalGhz,
  ramTotalGb, discos, controladorasRAID, tarjetasRED, ventiladores, fuentes, etc.).

Dependencias: normalizacion/estados.py, normalizacion/reglas.py, pandas.
"""
