"""Contratos de normalización frente a las capturas SNMP simuladas."""
from datetime import date
from pathlib import Path
from etl.normalizacion.switch import normalizar_switch
from etl.normalizacion.storage import normalizar_storage
from etl.normalizacion.chasis import normalizar_chasis
from etl.normalizacion.inferencias import familia_cpu, generacion_ram, corriente_desde_voltaje, corriente_fuente_hpe

DATA=Path(__file__).resolve().parents[2]/"data"
FECHA=date(2026,10,1)

def captura(nombre):
    data={}
    for line in (DATA/nombre/"public.snmprec").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        oid,kind,value=line.split("|",2)
        base=kind.split(":",1)[0]
        if ":numeric" in kind:
            value=next((piece.split("=",1)[1] for piece in value.split(",") if piece.startswith("initial=")),"0")
        if base=="4x":
            data[oid]=bytes.fromhex(value)
        elif base in ("2","65","66","67","70"):
            data[oid]=int(value)
        else:
            data[oid]=value
    return data

def test_switch_aruba_puertos_componentes_y_campos_manuales():
    ficha=normalizar_switch(captura("aruba-cx-sw01"),fecha_actualizacion=FECHA)
    assert ficha["activo"]["numero_serie"]=="SG42AR001W"
    assert ficha["switch"]["cantidad_puertos"]==52
    assert ficha["switch"]["cantidad_puertos_ocupados"]==40
    assert ficha["switch"]["tipo_red"] is ficha["switch"]["modo_operacion"] is None
    assert len(ficha["componentes"]["ventilador"])==3
    assert len(ficha["componentes"]["fuente_poder"])==2
    assert {f["consumo_w"] for f in ficha["componentes"]["fuente_poder"]}=={650}
    assert len(ficha["componentes"]["cpu"])==1
    assert ficha["componentes"]["cpu"][0]["familia"]=="MIPS64"
    assert ficha["componentes"]["ram"][0]["generacion"]=="DDR4"
    assert {f["tipo_corriente"] for f in ficha["componentes"]["fuente_poder"]}=={"AC"}


def test_switch_fuentes_dc_y_valores_no_concluyentes():
    datos=captura("aruba-cx-sw01")
    raiz="1.3.6.1.4.1.11.2.14.11.5.1.55.1.1.1.5"
    datos[raiz+".1"]="DC -48V"
    datos[raiz+".2"]="AC/DC"
    ficha=normalizar_switch(datos,fecha_actualizacion=FECHA)
    assert [f["tipo_corriente"] for f in ficha["componentes"]["fuente_poder"]]==["DC",None]
    del datos[raiz+".1"]
    del datos[raiz+".2"]
    ficha=normalizar_switch(datos,fecha_actualizacion=FECHA)
    assert {f["tipo_corriente"] for f in ficha["componentes"]["fuente_poder"]}=={None}

def test_storage_discos_del_arreglo_y_capacidad():
    ficha=normalizar_storage(captura("hpe-storage-fc-01"),fecha_actualizacion=FECHA)
    assert ficha["activo"]["numero_serie"]=="USE7300M1X"
    assert ficha["activo"]["tipo_activo"]=="STORAGE"
    assert len(ficha["componentes"]["disco"])==6
    assert ficha["componentes"]["disco"][-1]["estado"]=="Degradado"
    assert ficha["storage"]["capacidad_usada_tb"]<=ficha["storage"]["capacidad_total_tb"]
    assert ficha["storage"]["iops"] is None
    assert {cpu["familia"] for cpu in ficha["componentes"]["cpu"]}=={"Xeon E5"}
    assert {ram["generacion"] for ram in ficha["componentes"]["ram"]}=={"DDR4"}
    assert {tarjeta["marca"] for tarjeta in ficha["componentes"]["tarjeta_red"]}=={"HPE"}
    assert {tarjeta["numero_serial"] for tarjeta in ficha["componentes"]["tarjeta_red"]}=={
        "SIM-STO01-NIC-001", "SIM-STO01-NIC-002", "PWFC010001"}
    assert {fuente["tipo_corriente"] for fuente in ficha["componentes"]["fuente_poder"]}=={"AC"}

def test_inferencias_solo_con_evidencia_del_modelo():
    assert generacion_ram("DIMM DDR5-4800") == "DDR5"
    assert generacion_ram("PC5-4800 RDIMM") == "DDR5"
    assert generacion_ram("modelo desconocido") is None
    assert familia_cpu("procesador genérico") is None
    assert corriente_desde_voltaje("AC/DC universal") is None
    assert corriente_fuente_hpe("HPE Flex Slot", "865414-B21") == "AC"
    assert corriente_fuente_hpe("HPE Flex Slot", "desconocido") is None
    assert corriente_fuente_hpe("Fuente DC -48V", None) == "DC"
    assert corriente_fuente_hpe("Fuente AC/DC universal", None) is None

def test_chasis_slots_y_puertos_de_interconexion():
    ficha=normalizar_chasis(captura("hpe-c7000-01"),fecha_actualizacion=FECHA)
    assert ficha["activo"]["numero_serie"]=="CZ7000ABCD"
    assert ficha["chasis_blade"]["cantidad_slots"]==8
    assert len(ficha["componentes"]["chasis_slot"])==8
    assert sum(len(c["puertos"]) for c in ficha["componentes"]["tarjeta_red"])==12
    assert {tarjeta["marca"] for tarjeta in ficha["componentes"]["tarjeta_red"]}=={"HPE"}
    assert all(tarjeta["numero_serial"] for tarjeta in ficha["componentes"]["tarjeta_red"])
    assert ficha["componentes"]["chasis_slot"][0]["hostname_servidor"]=="hpe-bl460c-01"
    assert {f["tipo_corriente"] for f in ficha["componentes"]["fuente_poder"]}=={"AC"}
    assert {f["consumo_w"] for f in ficha["componentes"]["fuente_poder"]}=={2250}

def test_chasis_corriente_dc_desconocida_y_contradictoria():
    datos=captura("hpe-c7000-01")
    oid="1.3.6.1.4.1.232.22.2.3.3.1.1.7.1.1"
    datos[oid]=4
    ficha=normalizar_chasis(datos,fecha_actualizacion=FECHA)
    assert {f["tipo_corriente"] for f in ficha["componentes"]["fuente_poder"]}=={"DC"}

    datos[oid]=1
    ficha=normalizar_chasis(datos,fecha_actualizacion=FECHA)
    assert {f["tipo_corriente"] for f in ficha["componentes"]["fuente_poder"]}=={None}

    datos[oid]=2
    datos["1.3.6.1.4.1.232.22.2.3.3.1.1.7.1.2"]=4
    ficha=normalizar_chasis(datos,fecha_actualizacion=FECHA)
    assert {f["tipo_corriente"] for f in ficha["componentes"]["fuente_poder"]}=={None}
