"""
Extrae por SNMPv3 los datos de un servidor blade HPE ProLiant BL460c, combinando los OID propios
del blade (CPU, RAM, discos, igual que un servidor rack) con OID del chasis que lo aloja
(tarjetas de red, ventiladores y fuentes, que el blade no tiene propios). Transcribe la sección
"5.1 Servidores tipo BLADE" de mibs/hpe-real/MAPEO-SERVIDOR.md y las secciones de ventiladores,
fuentes y red de mibs/hpe-real/MAPEO-CHASIS.md.

Funciones:
- extraer_blade(host_blade: str, puerto_blade: int, credenciales_blade, host_chasis: str,
  puerto_chasis: int, credenciales_chasis) -> dict: consulta los OID propios del blade (vía
  oids/servidor.py) contra el agente del blade, y los OID de ventiladores/fuentes/red (vía
  oids/chasis.py) contra el agente del chasis, y devuelve ambos combinados en un único
  diccionario oid -> valor crudo.

Dependencias: oids/servidor.py, oids/chasis.py, snmp_cliente.py, extraccion/base.py.
"""
