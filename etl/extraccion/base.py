"""
Define la interfaz común que siguen los módulos de extracción por tipo de activo, para que
ciclo.py y detector.py puedan tratarlos de manera uniforme.

Clases:
- ExtractorBase: clase base con el método extraer(host: str, puerto: int, credenciales) -> dict,
  cuya firma siguen las funciones extraer_* de cada módulo (servidor.py, blade.py, chasis.py,
  storage.py, switch.py), devolviendo siempre un diccionario oid -> valor crudo tal como lo
  entrega snmp_cliente.py, sin normalizar todavía.

Dependencias: snmp_cliente.py (para las consultas SNMP). Lo extienden, o siguen como referencia
de firma, extraccion/servidor.py, blade.py, chasis.py, storage.py y switch.py.
"""
