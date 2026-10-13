"""Perfiles Huawei sobre las capturas generadas con los MIB recibidos."""
from datetime import datetime
from decimal import Decimal

import pytest

from etl.normalizacion.servidor import normalizar_servidor_huawei, IBMC
from etl.normalizacion.chasis import normalizar_chasis_huawei, E9000
from etl.normalizacion.storage import normalizar_storage_huawei
from etl.errores import DatosIncompletos
from etl import monitoreo
from tests.unitarios.test_otros_activos import captura

FECHA = datetime(2026, 10, 8, 12)


def test_nics_huawei_existentes_conservan_sus_ids_al_recibir_serie(monkeypatch):
    existentes = [
        {"id": 41, "numero_serial": None, "modelo": "Huawei 10Gb Ethernet Adapter"},
        {"id": 42, "numero_serial": None, "modelo": "Huawei 10Gb Ethernet Adapter"},
    ]
    actualizadas = []
    monkeypatch.setattr(monitoreo, "_filas", lambda cur, tabla, relacion, padre: existentes if tabla == "tarjeta_red" else [])
    monkeypatch.setattr(monitoreo, "_actualizar_fila", lambda cur, tabla, fila_id, anterior, datos:
                        actualizadas.append((fila_id, datos["numero_serial"])) or {"numero_serial": datos["numero_serial"]})
    nuevas = [{"numero_serial": f"HWNIC0000{i}", "modelo": "Huawei 10Gb Ethernet Adapter"}
              for i in (1, 2)]
    cambios, eventos = monitoreo._reconciliar(None, 1, "tarjeta_red", 1, nuevas, FECHA)
    assert actualizadas == [(41, "HWNIC00001"), (42, "HWNIC00002")]
    assert (cambios, eventos) == (2, 0)


@pytest.mark.parametrize("tabla,prefijo,modelo,serie", [
    ("controladora_raid", "Controller ", "Dorado 5000 V6 Controller (simulado)", "HWDCTRL0001"),
    ("ventilador", "Fan ", "Dorado Fan Module (simulado)", "HWDFAN0001"),
])
def test_dorado_conserva_id_al_recibir_etiqueta(monkeypatch, tabla, prefijo, modelo, serie):
    existente = {"id": 41, "numero_serial": None, "modelo": prefijo + "1", "estado": "Encendido"}
    actualizadas = []
    monkeypatch.setattr(monitoreo, "_filas", lambda cur, nombre, relacion, padre: [existente])
    monkeypatch.setattr(monitoreo, "_actualizar_fila", lambda cur, nombre, fila_id, anterior, datos:
                        actualizadas.append((fila_id, datos["numero_serial"])) or {"numero_serial": serie})
    cambios, eventos = monitoreo._reconciliar(None, 1, tabla, 1,
        [{"numero_serial": serie, "modelo": modelo, "estado": "Encendido"}], FECHA)
    assert actualizadas == [(41, serie)]
    assert (cambios, eventos) == (1, 0)


def test_rack_y_blade_se_distinguen_por_evidencia_ibmc():
    rack = normalizar_servidor_huawei(captura("huawei-2288h-v5-01"), fecha_actualizacion=FECHA)
    blade = normalizar_servidor_huawei(captura("huawei-ch121-v5-01"), fecha_actualizacion=FECHA)
    assert rack["servidor"]["tipo"] == "RACKEABLE"
    assert blade["servidor"]["tipo"] == "BLADE"
    assert rack["activo"]["fabricante"] == blade["activo"]["fabricante"] == "Huawei"
    assert len(rack["componentes"]["cpu"]) == 2
    assert len(blade["componentes"]["disco"]) == 2
    assert rack["componentes"]["ram"][0]["generacion"] == "DDR4"
    assert {f["tipo_corriente"] for f in rack["componentes"]["fuente_poder"]} == {"AC"}
    assert {f["consumo_w"] for f in rack["componentes"]["fuente_poder"]} == {900}
    assert {f["modelo"] for f in rack["componentes"]["ventilador"]} == {"BC1M05FAN"}
    assert {t["numero_serial"] for t in rack["componentes"]["tarjeta_red"]} == {"HWNIC00001", "HWNIC00002"}
    assert {t["numero_serial"] for t in blade["componentes"]["tarjeta_red"]} == {"HWNIC10001", "HWNIC10002"}
    assert blade["componentes"]["fuente_poder"] == []
    assert rack["servidor"]["version_so"] is None
    assert rack["activo"]["temperatura"] == Decimal("50")
    assert blade["activo"]["temperatura"] == Decimal("45")
    assert rack["componentes"]["controladora_raid"] == [{
        "numero_serial": None, "modelo": "Huawei RAID Controller 2288H V5",
        "raid": "RAID1, RAID5", "estado": "Encendido"}]
    assert blade["componentes"]["controladora_raid"] == [{
        "numero_serial": None, "modelo": "Huawei RAID Controller CH121 V5",
        "raid": "RAID1", "estado": "Encendido"}]
    assert {m["nombre_metrica"] for m in rack["mediciones"]} == {
        "temperatura", "consumo_electrico_w", "cpu_uso_ghz", "ram_uso_gb"}
    datos = captura("huawei-ch121-v5-01")
    del datos[IBMC + ".44.7.0"]
    with pytest.raises(DatosIncompletos):
        normalizar_servidor_huawei(datos, fecha_actualizacion=FECHA)
    with pytest.raises(DatosIncompletos):
        normalizar_servidor_huawei(captura("huawei-ch121-v5-01"),
                                  fecha_actualizacion=FECHA, tipo="RACKEABLE")


def test_temperatura_ibmc_ignora_lectura_no_disponible():
    datos = captura("huawei-ch121-v5-01")
    datos[IBMC + ".26.50.1.3.2"] = 65535
    ficha = normalizar_servidor_huawei(datos, fecha_actualizacion=FECHA)
    assert ficha["activo"]["temperatura"] == Decimal("43")


def test_estado_raid_huawei_refleja_salud_de_controladora():
    datos = captura("huawei-ch121-v5-01")
    datos[IBMC + ".36.50.1.7.1"] = 1
    ficha = normalizar_servidor_huawei(datos, fecha_actualizacion=FECHA)
    assert ficha["componentes"]["controladora_raid"][0]["estado"] == "Degradado"


def test_chasis_y_serie_de_blade_en_bahia():
    ficha = normalizar_chasis_huawei(captura("huawei-e9000-01"), fecha_actualizacion=FECHA)
    assert ficha["activo"]["tipo_activo"] == "CHASIS"
    assert ficha["chasis_blade"]["cantidad_slots"] == 2
    assert ficha["componentes"]["chasis_slot"][0]["serie_servidor"] == "HWCH121V5001"
    assert ficha["componentes"]["chasis_slot"][1]["estado"] == "LIBRE"
    assert ficha["componentes"]["ventilador"][0]["velocidad_rpm"] is None
    assert {v["modelo"] for v in ficha["componentes"]["ventilador"]} == {"Huawei E9000 fan module (simulado)"}
    sin_info = captura("huawei-e9000-01")
    sin_info.pop(E9000 + ".5.2001.1.4.1")
    assert normalizar_chasis_huawei(sin_info, fecha_actualizacion=FECHA)["componentes"]["ventilador"][0]["modelo"] is None
    assert {f["consumo_w"] for f in ficha["componentes"]["fuente_poder"]} == {2000}
    assert {f["tipo_corriente"] for f in ficha["componentes"]["fuente_poder"]} == {"AC"}
    datos = captura("huawei-e9000-01")
    datos[E9000 + ".4.1.8.0"] = 2
    assert normalizar_chasis_huawei(datos, fecha_actualizacion=FECHA)["componentes"]["chasis_slot"][0]["estado"] == "DEGRADADO"


def test_oceanstor_capacidad_componentes_y_metricas():
    ficha = normalizar_storage_huawei(captura("huawei-dorado-01"), fecha_actualizacion=FECHA)
    assert ficha["activo"]["tipo_activo"] == "STORAGE"
    assert ficha["activo"]["numero_serie"] == "HWDORADO5000V6001"
    assert ficha["storage"]["capacidad_total_tb"] == Decimal(20)
    assert ficha["storage"]["capacidad_usada_tb"] == Decimal(10)
    assert ficha["storage"]["iops"] == 25500
    assert len(ficha["componentes"]["disco"]) == 6
    assert ficha["componentes"]["disco"][0]["tipo"] == "NVMe"
    assert len(ficha["componentes"]["controladora_raid"]) == 2
    assert {c["numero_serial"] for c in ficha["componentes"]["controladora_raid"]} == {
        "HWDCTRL0001", "HWDCTRL0002"}
    assert {c["modelo"] for c in ficha["componentes"]["controladora_raid"]} == {
        "Dorado 5000 V6 Controller (simulado)"}
    assert {f["numero_serial"] for f in ficha["componentes"]["ventilador"]} == {
        "HWDFAN0001", "HWDFAN0002", "HWDFAN0003", "HWDFAN0004"}
    assert {f["modelo"] for f in ficha["componentes"]["ventilador"]} == {
        "Dorado Fan Module (simulado)"}
    assert [f["velocidad_rpm"] for f in ficha["componentes"]["ventilador"]] == [
        6200, 6300, 6150, 6250]
    assert ficha["activo"]["consumo_electrico_w"] == 1180
    assert ficha["componentes"]["cpu"] == [
        {"numero_serial": None, "marca": "Huawei", "familia": "OceanStor",
         "modelo": "Dorado Controller CPU (simulado)", "velocidad_ghz": Decimal("2.4"),
         "cantidad_nucleos": None, "cantidad_hilos": None, "cache_l1_mb": None,
         "cache_l2_mb": None, "cache_l3_mb": None, "estado": "Encendido"}
        for _ in (1, 2)
    ]
    assert {f["consumo_w"] for f in ficha["componentes"]["fuente_poder"]} == {2000}
    assert ficha["componentes"]["ram"] == [
        {"numero_serial": None, "marca": None, "modelo": f"Memoria de controladora {indice}",
         "generacion": None, "velocidad_mhz": None, "capacidad_gb": Decimal(128),
         "estado": "Encendido"}
        for indice in (1, 2)
    ]
    assert {m["nombre_metrica"] for m in ficha["mediciones"]} == {
        "temperatura", "consumo_electrico_w", "iops", "latencia_ms"}


def test_oceanstor_no_inventa_watts_ni_rpm_sin_sensores():
    datos = {oid: valor for oid, valor in captura("huawei-dorado-01").items()
             if not oid.startswith(("1.3.6.1.2.1.47.", "1.3.6.1.2.1.99."))}
    ficha = normalizar_storage_huawei(datos, fecha_actualizacion=FECHA)
    assert ficha["activo"]["consumo_electrico_w"] is None
    assert all(f["velocidad_rpm"] is None for f in ficha["componentes"]["ventilador"])


def test_tipo_de_corriente_oceanstor_respeta_valores_del_mib():
    datos = captura("huawei-dorado-01")
    datos["1.3.6.1.4.1.34774.4.1.23.5.3.1.5.1"] = 0
    datos["1.3.6.1.4.1.34774.4.1.23.5.3.1.5.2"] = 2
    fuentes = normalizar_storage_huawei(datos, fecha_actualizacion=FECHA)["componentes"]["fuente_poder"]
    assert fuentes[0]["tipo_corriente"] == "DC"
    assert fuentes[1]["tipo_corriente"] is None  # HV no existe en el enum de la BD.


def test_segundas_instancias_huawei_son_independientes_y_blade_coincide_con_chasis():
    rack = normalizar_servidor_huawei(captura("huawei-2288h-v5-02"), fecha_actualizacion=FECHA)
    blade = normalizar_servidor_huawei(captura("huawei-ch121-v5-02"), fecha_actualizacion=FECHA)
    chasis = normalizar_chasis_huawei(captura("huawei-e9000-02"), fecha_actualizacion=FECHA)
    storage = normalizar_storage_huawei(captura("huawei-dorado-02"), fecha_actualizacion=FECHA)
    assert [ficha["activo"]["numero_serie"] for ficha in (rack, blade, chasis, storage)] == [
        "HW2288HV5002", "HWCH121V5002", "HWE9000LAB002", "HWDORADO5000V6002"]
    assert blade["servidor"]["tipo"] == "BLADE"
    assert blade["componentes"]["ram"][0]["numero_serial"] == "HWRAM30001"
    assert chasis["componentes"]["chasis_slot"][0]["serie_servidor"] == "HWCH121V5002"
    assert storage["componentes"]["disco"][0]["numero_serial"] == "HWDSSD20001"
    assert storage["activo"]["consumo_electrico_w"] == 1240


def test_disco_huawei_solo_se_retira_con_ausencia_explicita_y_serie():
    raiz = "1.3.6.1.4.1.2011.2.235.1.1.18.50.1"
    datos = captura("huawei-2288h-v5-01")
    serie = datos[raiz + ".7.4"]
    datos[raiz + ".2.4"] = 1  # absence(1), presencia instalada es presence(2)
    ficha = normalizar_servidor_huawei(datos, fecha_actualizacion=FECHA)
    assert serie in ficha["discos_ausentes"]
    assert serie not in {d["numero_serial"] for d in ficha["componentes"]["disco"]}
    assert len(ficha["componentes"]["disco"]) == 3
    datos.pop(raiz + ".2.4")
    ficha_sin_prueba = normalizar_servidor_huawei(datos, fecha_actualizacion=FECHA)
    assert ficha_sin_prueba["discos_ausentes"] == []
    assert len(ficha_sin_prueba["componentes"]["disco"]) == 4
