"""
Extrae por SNMPv3 los OID del chasis blade HPE BladeSystem c7000, transcribiendo el mapeo de
mibs/hpe-real/MAPEO-CHASIS.md: identidad, chasisSlots, ventiladores, fuentes de poder y módulos
de interconexión de red con sus puertos.

Funciones:
- extraer_chasis(host: str, puerto: int, credenciales) -> dict: consulta todos los OID listados
  en oids/chasis.py y devuelve el diccionario oid -> valor crudo.

Dependencias: oids/chasis.py, snmp_cliente.py, extraccion/base.py.
"""
