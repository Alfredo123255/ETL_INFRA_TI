"""Errores del ETL con mensajes públicos independientes de datos del equipo."""

class ErrorExtraccion(Exception):
    def __init__(self, tipo="otro"):
        self.tipo = tipo
        super().__init__("No se pudo completar la extracción SNMP.")

class PerfilNoSoportado(Exception):
    pass

class DatosIncompletos(Exception):
    pass

class BaseNoDisponible(Exception):
    pass

class ActivoDuplicado(Exception):
    pass
