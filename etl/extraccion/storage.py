"""
Extrae por SNMPv3 los datos de una unidad de storage con arreglo Fibre Channel, combinando los
OID propios del arreglo (controladora RAID, discos, HBA) con los del servidor que lo administra
(CPU, RAM, temperatura, consumo, ventiladores, fuentes y tarjetas Ethernet, que el arreglo no
expone por sí mismo). Transcribe mibs/hpe-real/MAPEO-STORAGE.md completo, incluida su nota de
limitación sobre qué campos provienen del servidor.

Funciones:
- extraer_storage(host: str, puerto: int, credenciales) -> dict: consulta, contra el mismo
  agente (que responde ambos conjuntos de OID), los OID de oids/storage.py y los OID de
  oids/servidor.py que corresponden según la nota de limitación, y devuelve todo combinado en un
  único diccionario oid -> valor crudo.

Dependencias: oids/storage.py, oids/servidor.py, snmp_cliente.py, extraccion/base.py.
"""
