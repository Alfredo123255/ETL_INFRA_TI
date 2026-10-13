from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr
from pysnmp.proto import rfc1902, rfc1905

import etl.snmp_cliente as snmp
import etl.extraccion.servidor as extraccion
from etl.errores import DatosIncompletos, ErrorExtraccion, PerfilNoSoportado
from etl.normalizacion.servidor import normalizar_servidor_hpe
from etl.oids.servidor import OIDS_IDENTIDAD, OIDS_CPU, OIDS_USO_CPU

FECHA = date(2026, 9, 30)
RAIZ = Path(__file__).resolve().parents[2]


def registros(agente):
    tipos = {"2": rfc1902.Integer, "4": rfc1902.OctetString,
             "6": rfc1902.ObjectIdentifier, "64": rfc1902.IpAddress,
             "65": rfc1902.Counter32, "66": rfc1902.Gauge32, "67": rfc1902.TimeTicks}
    datos = {}
    for linea in (RAIZ / "data" / agente / "public.snmprec").read_text().splitlines():
        oid, etiqueta, valor = linea.split("|", 2)
        if etiqueta == "4x":
            dato = rfc1902.OctetString(hexValue=valor)
        else:
            tipo, _, variacion = etiqueta.partition(":")
            if variacion:
                valor = dict(item.split("=") for item in valor.split(","))["initial"]
            dato = tipos[tipo](int(valor) if tipo in ("2", "65", "66", "67") else valor)
        datos[oid] = dato
    return datos


@pytest.mark.parametrize("agente,cpus,memorias,discos,tarjetas,uso", [
    ("hpe-dl380-01", 2, 4, 4, 2, Decimal(74)),
    ("hpe-dl360-01", 1, 4, 2, 1, None),
])
def test_ficha_real_simulada(agente, cpus, memorias, discos, tarjetas, uso):
    ficha = normalizar_servidor_hpe(registros(agente), fecha_actualizacion=FECHA)
    c = ficha["componentes"]
    assert ficha["activo"]["hostname"] == agente
    assert ficha["activo"]["ultima_actualizacion"] == FECHA
    assert ficha["ubicacion_snmp"].startswith("DataCenter-1 / ")
    assert len(c["cpu"]) == cpus
    assert len(c["ram"]) == memorias
    assert len(c["disco"]) == discos
    assert len(c["tarjeta_red"]) == tarjetas
    assert {tarjeta["marca"] for tarjeta in c["tarjeta_red"]} == {"HPE"}
    assert {tarjeta["numero_serial"] for tarjeta in c["tarjeta_red"]} == (
        {"SIM-DL380-NIC-001", "SIM-DL380-NIC-002"} if cpus == 2
        else {"SIM-DL360-NIC-001"})
    assert c["ram"][0]["numero_serial"].startswith("MEM")
    assert c["disco"][0]["numero_serial"].startswith("SN")
    assert c["controladora_raid"][0]["numero_serial"]
    assert c["cpu"][0]["cantidad_hilos"] == c["cpu"][0]["cantidad_nucleos"] * 2
    assert c["cpu"][0]["familia"] == ("Xeon Gold" if cpus == 2 else "Xeon Silver")
    assert {ram["generacion"] for ram in c["ram"]} == {"DDR4"}
    assert {fuente["tipo_corriente"] for fuente in c["fuente_poder"]} == {"AC"}
    assert {fuente["consumo_w"] for fuente in c["fuente_poder"]} == ({800} if cpus == 2 else {500})
    assert c["cpu"][0]["cache_l1_mb"] == (Decimal(1) if cpus == 2 else Decimal("0.625"))
    assert c["tarjeta_red"][0]["puertos"][0]["mac_address"].count(":") == 5
    assert "cpuTotalGhz" not in ficha["servidor"]
    if uso is not None:
        assert next(m["valor"] for m in ficha["mediciones"] if m["nombre_metrica"] == "ram_uso_gb") == uso


def test_tablas_y_estados_especificos():
    ficha = normalizar_servidor_hpe(registros("hpe-dl380-01"), fecha_actualizacion=FECHA)
    c = ficha["componentes"]
    assert c["ram"][-1]["estado"] == "Degradado"
    assert c["fuente_poder"][-1]["estado"] == "Apagado"
    assert c["fuente_poder"][-1]["consumo_w"] == 800
    assert c["controladora_raid"][0]["modelo"] == "p408i-a"
    assert c["controladora_raid"][0]["raid"] == "RAID10"
    assert c["tarjeta_red"][1]["puertos"][0]["velocidad"] == "10000 Mbps"
    assert ficha["activo"]["temperatura"] == 22
    assert ficha["servidor"]["ip_sistema_operativo"] == "10.10.12.11"
    assert ficha["servidor"]["version_so"] == "Microsoft Windows Server 2019 Standard 10.0.17763"
    assert next(m["valor"] for m in ficha["mediciones"] if m["nombre_metrica"] == "cpu_uso_ghz") == Decimal("35.28")


@pytest.mark.parametrize("agente,esperado", [
    ("hpe-dl360-01", "Red Hat Enterprise Linux Server 8.6 (Ootpa)"),
    ("hpe-bl460c-01", "Microsoft Windows Server 2022 Standard 10.0.20348"),
    ("hpe-bl460c-02", "Ubuntu 22.04.3 LTS (Jammy Jellyfish)"),
    ("hpe-bl460c-03", "Ubuntu 22.04.3 LTS (Jammy Jellyfish)"),
])
def test_nombre_y_version_del_so_para_servidor_y_blade(agente, esperado):
    ficha = normalizar_servidor_hpe(registros(agente), fecha_actualizacion=FECHA, tipo="AUTO")
    assert ficha["servidor"]["version_so"] == esperado


def test_nic_sin_entidad_o_con_parte_ambigua_no_recibe_serial_inventado():
    datos = registros("hpe-dl380-01")
    for oid in list(datos):
        if oid.startswith("1.3.6.1.2.1.47.1.1.1.1."):
            del datos[oid]
    ficha = normalizar_servidor_hpe(datos, fecha_actualizacion=FECHA)
    assert {t["numero_serial"] for t in ficha["componentes"]["tarjeta_red"]} == {None}

    datos = registros("hpe-dl380-01")
    datos["1.3.6.1.2.1.47.1.1.1.1.13.1002"] = datos["1.3.6.1.2.1.47.1.1.1.1.13.1001"]
    ficha = normalizar_servidor_hpe(datos, fecha_actualizacion=FECHA)
    assert ficha["componentes"]["tarjeta_red"][0]["numero_serial"] is None


@pytest.mark.parametrize("porcentaje,uso_esperado", [(0, "0"), (25, "16"), (100, "64")])
def test_uso_cpu_comparte_base_del_backend(porcentaje, uso_esperado):
    datos = registros("hpe-dl380-01")
    # CPU 1: 2.5 GHz y 16 núcleos; CPU 2: 3 GHz y 8 núcleos. Total: 64 GHz.
    datos[OIDS_CPU["velocidad_mhz"] + ".1"] = rfc1902.Integer(2500)
    datos[OIDS_CPU["cantidad_nucleos"] + ".1"] = rfc1902.Integer(16)
    datos[OIDS_CPU["velocidad_mhz"] + ".2"] = rfc1902.Integer(3000)
    datos[OIDS_CPU["cantidad_nucleos"] + ".2"] = rfc1902.Integer(8)
    datos[OIDS_USO_CPU["porcentaje"] + ".1"] = rfc1902.Integer(porcentaje)
    ficha = normalizar_servidor_hpe(datos, fecha_actualizacion=FECHA)
    metricas = {m["nombre_metrica"]: m["valor"] for m in ficha["mediciones"]}
    assert metricas["cpu_uso_ghz"] == Decimal(uso_esperado)
    assert metricas["cpu_uso_ghz"] / Decimal(64) * 100 == porcentaje
    assert metricas["ram_uso_gb"] == 74


@pytest.mark.parametrize("nucleos", [None, 0, -1])
def test_sin_nucleos_validos_no_inventa_uso_cpu(nucleos):
    datos = registros("hpe-dl380-01")
    oid = OIDS_CPU["cantidad_nucleos"] + ".1"
    if nucleos is None:
        datos.pop(oid)
    else:
        datos[oid] = rfc1902.Integer(nucleos)
    ficha = normalizar_servidor_hpe(datos, fecha_actualizacion=FECHA)
    metricas = {m["nombre_metrica"]: m["valor"] for m in ficha["mediciones"]}
    assert "cpu_uso_ghz" not in metricas
    assert "ram_uso_gb" in metricas


def test_blade_no_duplica_componentes_del_chasis():
    datos = registros("hpe-bl460c-01")
    with pytest.raises(DatosIncompletos):
        normalizar_servidor_hpe(datos, fecha_actualizacion=FECHA)
    ficha = normalizar_servidor_hpe(datos, fecha_actualizacion=FECHA, tipo="BLADE")
    for nombre in ("tarjeta_red", "fuente_poder", "ventilador"):
        assert ficha["componentes"][nombre] == []


def test_identidad_incompleta_no_registra():
    datos = registros("hpe-dl380-01")
    datos.pop(OIDS_IDENTIDAD["numero_serie"])
    with pytest.raises(DatosIncompletos):
        normalizar_servidor_hpe(datos, fecha_actualizacion=FECHA)


def test_no_inventa_campos_opcionales():
    datos = {oid: valor for oid, valor in registros("hpe-dl380-01").items()
             if oid in OIDS_IDENTIDAD.values()}
    ficha = normalizar_servidor_hpe(datos, fecha_actualizacion=FECHA)
    assert all(not lista for lista in ficha["componentes"].values())
    assert ficha["servidor"]["ip_sistema_operativo"] is None


CONEXION = snmp.ConexionSNMP("127.0.0.1", 161, "monitor", SecretStr("auth-secreta"))


def binding(oid, valor=1):
    return (rfc1902.ObjectName(oid), rfc1902.Integer(valor))


@pytest.fixture
def sesion(monkeypatch):
    motor = MagicMock()
    monkeypatch.setattr(snmp, "SnmpEngine", lambda: motor)
    monkeypatch.setattr(snmp, "UdpTransportTarget", MagicMock())
    return motor


async def test_walk_respeta_subarbol_y_paginacion(monkeypatch, sesion):
    consulta = AsyncMock(side_effect=[
        (None, 0, 0, [[binding("1.3.6.1.4.1.232.1")], [binding("1.3.6.1.4.1.232.2")]]),
        (None, 0, 0, [[binding("1.3.6.1.4.1.2320.1")]])])
    monkeypatch.setattr(snmp, "bulkCmd", consulta)
    with snmp.SesionSNMP(CONEXION) as cliente:
        datos = await cliente.recorrer("1.3.6.1.4.1.232")
    assert list(datos) == ["1.3.6.1.4.1.232.1", "1.3.6.1.4.1.232.2"]
    assert consulta.await_count == 2
    sesion.closeDispatcher.assert_called_once()


async def test_walk_rechaza_repeticiones(monkeypatch, sesion):
    monkeypatch.setattr(snmp, "bulkCmd", AsyncMock(return_value=(None, 0, 0,
        [[binding("1.3.6.1.4.1.232.1")], [binding("1.3.6.1.4.1.232.1")]])))
    with pytest.raises(ErrorExtraccion):
        with snmp.SesionSNMP(CONEXION) as cliente:
            await cliente.recorrer("1.3.6.1.4.1.232")
    sesion.closeDispatcher.assert_called_once()


async def test_get_omite_objetos_no_disponibles(monkeypatch, sesion):
    oid = "1.3.6.1.2.1.1.6.0"
    monkeypatch.setattr(snmp, "getCmd", AsyncMock(return_value=(None, 0, 0,
        [(rfc1902.ObjectName(oid), rfc1905.NoSuchInstance())])))
    with snmp.SesionSNMP(CONEXION) as cliente:
        assert await cliente.obtener([oid]) == {}


async def test_extraccion_rechaza_fabricante_sin_perfil():
    with pytest.raises(PerfilNoSoportado):
        await extraccion.extraer_servidor(CONEXION, "Cisco")


async def test_extraccion_reutiliza_sesion_y_filtra_columnas(monkeypatch):
    datos = registros("hpe-dl380-01")
    cliente = MagicMock()
    cliente.obtener = AsyncMock(return_value={oid: v for oid, v in datos.items() if oid in OIDS_IDENTIDAD.values()})
    cliente.recorrer = AsyncMock(side_effect=lambda raiz: {oid: v for oid, v in datos.items() if oid.startswith(raiz + ".")})
    contexto = MagicMock()
    contexto.__enter__.return_value = cliente
    monkeypatch.setattr(extraccion, "SesionSNMP", lambda conexion: contexto)
    resultado = await extraccion.extraer_servidor_hpe(CONEXION)
    assert "1.3.6.1.4.1.232.3.2.5.1.1.51.1.1" in resultado
    assert "1.3.6.1.4.1.232.3.2.5.1.1.25.1.1" not in resultado
    assert "1.3.6.1.2.1.47.1.1.1.1.11.1001" in resultado
    assert cliente.recorrer.await_count == 13
    contexto.__exit__.assert_called_once()


async def test_cancelacion_de_extraccion_cierra_motor(monkeypatch, sesion):
    import asyncio
    monkeypatch.setattr(snmp, "bulkCmd", AsyncMock(side_effect=asyncio.CancelledError))
    with pytest.raises(asyncio.CancelledError):
        with snmp.SesionSNMP(CONEXION) as cliente:
            await cliente.recorrer("1.3.6.1.4.1.232")
    sesion.closeDispatcher.assert_called_once()


async def test_registro_rechaza_storage_antes_de_extraer(monkeypatch):
    import etl.ciclo as ciclo
    monkeypatch.setattr(ciclo, "probar_conexion", AsyncMock(return_value={
        "ok": True, "fabricante": "HPE", "tipo_detectado": "STORAGE"}))
    query = AsyncMock()
    monkeypatch.setattr(ciclo, "extraer_servidor", query)
    with pytest.raises(PerfilNoSoportado):
        await ciclo.preparar_registro_servidor(CONEXION, MagicMock())
    query.assert_not_awaited()


async def test_registro_prepara_ficha_sin_credenciales(monkeypatch):
    import etl.ciclo as ciclo
    datos = registros("hpe-dl380-01")
    monkeypatch.setattr(ciclo, "probar_conexion", AsyncMock(return_value={
        "ok": True, "fabricante": "HPE", "tipo_detectado": "SERVIDOR",
        "sys_object_id": str(datos[OIDS_IDENTIDAD["sys_object_id"]])}))
    monkeypatch.setattr(ciclo, "extraer_servidor", AsyncMock(return_value=datos))
    ficha = await ciclo.preparar_registro_servidor(CONEXION, MagicMock(), ip_gestion="equipo.local:161")
    assert ficha["activo"]["ip_gestion"] == "equipo.local:161"
    assert isinstance(ficha["activo"]["ultima_actualizacion"], date)
    assert "auth-secreta" not in str(ficha)


def test_tipo_servidor_se_infiere_del_modelo():
    rack = normalizar_servidor_hpe(registros("hpe-dl380-01"), fecha_actualizacion=FECHA, tipo="AUTO")
    blade = normalizar_servidor_hpe(registros("hpe-bl460c-01"), fecha_actualizacion=FECHA, tipo="AUTO")
    assert rack["servidor"]["tipo"] == "RACKEABLE"
    assert blade["servidor"]["tipo"] == "BLADE"


@pytest.mark.parametrize("agente", [
    "hpe-dl380-01", "hpe-dl360-01", "hpe-bl460c-01", "hpe-bl460c-02", "hpe-bl460c-03",
])
@pytest.mark.parametrize("energia,salud,esperado", [
    (3, 2, "Encendido"), (3, 3, "Degradado"), (3, 4, "Degradado"),
    (2, 2, "Apagado"), (2, 3, "Apagado"), (2, 4, "Apagado"),
    (1, 2, "Degradado"), (4, 2, "Degradado"), (None, 2, "Degradado"),
    (3, 1, "Degradado"), (3, None, "Degradado"),
])
def test_energia_y_salud_servidores_hpe(agente, energia, salud, esperado):
    datos = registros(agente)
    for campo, valor in (("estado_energia", energia), ("estado_operativo", salud)):
        oid = OIDS_IDENTIDAD[campo]
        if valor is None:
            datos.pop(oid, None)
        else:
            datos[oid] = rfc1902.Integer(valor)
    ficha = normalizar_servidor_hpe(datos, fecha_actualizacion=FECHA, tipo="AUTO")
    assert ficha["activo"]["estado_operativo"] == esperado


def test_fallo_energia_servidor_no_cambia_estado_del_storage():
    from etl.normalizacion.storage import normalizar_storage_hpe, SS
    from tests.unitarios.test_otros_activos import captura
    datos = captura("hpe-storage-fc-01")
    salud_arreglo = next(oid for oid in datos if oid.startswith(SS + ".11."))
    datos[salud_arreglo] = rfc1902.Integer(4)
    datos[OIDS_IDENTIDAD["estado_energia"]] = rfc1902.Integer(3)
    ficha = normalizar_storage_hpe(datos, fecha_actualizacion=FECHA)
    assert ficha["activo"]["estado_operativo"] == "Apagado"
