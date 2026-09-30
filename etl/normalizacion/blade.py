"""
Convierte el diccionario oid -> valor crudo de un servidor blade (extraccion/blade.py) a la
estructura de la ficha de Servidor/ChasisSlot del esquema, usando pandas, transcribiendo la
sección "5.1 Servidores tipo BLADE" de mibs/hpe-real/MAPEO-SERVIDOR.md: qué campos son propios
del blade y cuáles vienen del chasis.

Funciones:
- normalizar_blade(datos_crudos: dict) -> dict: igual que normalizar_servidor, pero separando los
  campos que se originan en el agente del blade de los que se originan en el agente del chasis
  (ventiladores, fuentes, tarjetas de red) antes de armar la ficha final.

Dependencias: normalizacion/estados.py, normalizacion/reglas.py, pandas.
"""
