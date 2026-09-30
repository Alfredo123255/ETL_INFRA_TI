"""Orquestación reutilizable para preparar el registro inicial de un servidor.

No programa ciclos ni guarda credenciales. La API entrega la ficha preparada a
carga.py para persistir el registro inicial en una sola transacción.
"""
from datetime import datetime, timedelta, timezone
from etl.errores import PerfilNoSoportado, DatosIncompletos
from etl.extraccion.servidor import extraer_servidor
from etl.normalizacion.servidor import normalizar_servidor
from etl.oids.servidor import OIDS_IDENTIDAD
from etl.snmp_cliente import probar_conexion, ErrorExtraccion


async def preparar_registro_servidor(conexion, config, *, tipo="RACKEABLE", ip_gestion=None):
    """Prueba y detecta el equipo antes de seleccionar su perfil de extracción."""
    prueba = await probar_conexion(conexion.host, conexion.puerto, conexion.usuario,
        conexion.clave, conexion.clave_privacidad, config)
    if not prueba["ok"]:
        raise ErrorExtraccion(prueba["error_tipo"])
    if prueba["tipo_detectado"] != "SERVIDOR" or prueba["fabricante"] != "HPE":
        raise PerfilNoSoportado("El registro inicial solo admite servidores HPE con perfil compatible.")
    datos = await extraer_servidor(conexion, prueba["fabricante"])
    if str(datos.get(OIDS_IDENTIDAD["sys_object_id"])) != prueba["sys_object_id"]:
        raise DatosIncompletos("La identidad del equipo cambió durante la extracción.")
    # Fecha de Lima antes de la carga; schema.sql almacena DATE.
    fecha = datetime.now(timezone(timedelta(hours=-5))).date()
    ficha = normalizar_servidor(datos, fabricante=prueba["fabricante"],
        fecha_actualizacion=fecha, tipo=tipo)
    ficha["activo"]["ip_gestion"] = ip_gestion or (
        f"[{conexion.host}]:{conexion.puerto}" if ":" in conexion.host
        else f"{conexion.host}:{conexion.puerto}")
    return ficha
