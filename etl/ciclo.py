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


async def preparar_registro_servidor(conexion, config, *, tipo="AUTO", ip_gestion=None, prueba=None):
    """Prueba y detecta el equipo antes de seleccionar su perfil de extracción."""
    if prueba is None:
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


async def preparar_registro_activo(conexion, config, *, ip_gestion=None):
    """Detecta el tipo por SNMP y prepara una ficha compatible con su subtipo SQL."""
    prueba = await probar_conexion(conexion.host, conexion.puerto, conexion.usuario,
        conexion.clave, conexion.clave_privacidad, config)
    if not prueba["ok"]:
        raise ErrorExtraccion(prueba["error_tipo"])
    tipo = prueba["tipo_detectado"]
    if tipo == "SERVIDOR":
        return await preparar_registro_servidor(conexion,config,ip_gestion=ip_gestion,prueba=prueba)
    if (tipo == "SWITCH" and prueba["fabricante"] != "HPE Aruba Networking") or \
       (tipo in ("STORAGE","CHASIS") and prueba["fabricante"] != "HPE"):
        raise PerfilNoSoportado("No hay perfil de registro para este fabricante.")
    from etl.extraccion.switch import extraer_switch
    from etl.extraccion.storage import extraer_storage
    from etl.extraccion.chasis import extraer_chasis
    from etl.normalizacion.switch import normalizar_switch
    from etl.normalizacion.storage import normalizar_storage
    from etl.normalizacion.chasis import normalizar_chasis
    perfiles={"SWITCH":(extraer_switch,normalizar_switch),
             "STORAGE":(extraer_storage,normalizar_storage),
             "CHASIS":(extraer_chasis,normalizar_chasis)}
    if tipo not in perfiles:
        raise PerfilNoSoportado("El tipo de equipo no tiene perfil de registro implementado.")
    extractor, normalizador=perfiles[tipo]
    datos=await extractor(conexion)
    if str(datos.get(OIDS_IDENTIDAD["sys_object_id"])) != prueba["sys_object_id"]:
        raise DatosIncompletos("La identidad del equipo cambió durante la extracción.")
    fecha=datetime.now(timezone(timedelta(hours=-5))).date()
    ficha=normalizador(datos,fecha_actualizacion=fecha)
    ficha["activo"]["ip_gestion"]=ip_gestion or (
        f"[{conexion.host}]:{conexion.puerto}" if ":" in conexion.host
        else f"{conexion.host}:{conexion.puerto}")
    return ficha
