"""
Extrae por SNMPv3 los OID de un servidor rack HPE ProLiant (DL380/DL360), transcribiendo el
mapeo de mibs/hpe-real/MAPEO-SERVIDOR.md: identidad, CPU, RAM, discos internos y controladora
RAID, tarjetas de red, ventiladores, fuentes de poder, temperatura y consumo.

Funciones:
- extraer_servidor(host: str, puerto: int, credenciales) -> dict: consulta todos los OID
  listados en oids/servidor.py para un servidor rack y devuelve el diccionario oid -> valor
  crudo.

Dependencias: oids/servidor.py (lista de OID a consultar), snmp_cliente.py (ejecuta las
consultas), extraccion/base.py (firma común).
"""
