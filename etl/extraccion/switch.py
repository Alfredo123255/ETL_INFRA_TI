"""
Extrae por SNMPv3 los OID de un switch ArubaOS-CX, transcribiendo el mapeo de
mibs/ALL-Supported-MIBs/MAPEO-SWITCH.md: identidad, puertos físicos, tráfico, temperatura,
consumo, fuentes, ventiladores y uso de CPU/RAM del propio switch, más el bloque de CPU y RAM
"prestado" de MIB de servidor HPE que documentan las secciones 10 y 11 de ese mismo mapeo.

Funciones:
- extraer_switch(host: str, puerto: int, credenciales) -> dict: consulta los OID de
  oids/switch.py y, para completar CPU/RAM, los OID prestados de oids/servidor.py que indica
  MAPEO-SWITCH.md, y devuelve todo combinado en un único diccionario oid -> valor crudo.

Dependencias: oids/switch.py, oids/servidor.py, snmp_cliente.py, extraccion/base.py.
"""
