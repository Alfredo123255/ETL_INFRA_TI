"""Contratos de normalización frente a las capturas SNMP simuladas."""
from datetime import date
from pathlib import Path
from etl.normalizacion.switch import normalizar_switch
from etl.normalizacion.storage import normalizar_storage
from etl.normalizacion.chasis import normalizar_chasis

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
    assert len(ficha["componentes"]["cpu"])==1

def test_storage_discos_del_arreglo_y_capacidad():
    ficha=normalizar_storage(captura("hpe-storage-fc-01"),fecha_actualizacion=FECHA)
    assert ficha["activo"]["numero_serie"]=="USE7300M1X"
    assert ficha["activo"]["tipo_activo"]=="STORAGE"
    assert len(ficha["componentes"]["disco"])==6
    assert ficha["componentes"]["disco"][-1]["estado"]=="Degradado"
    assert ficha["storage"]["capacidad_usada_tb"]<=ficha["storage"]["capacidad_total_tb"]
    assert ficha["storage"]["iops"] is None

def test_chasis_slots_y_puertos_de_interconexion():
    ficha=normalizar_chasis(captura("hpe-c7000-01"),fecha_actualizacion=FECHA)
    assert ficha["activo"]["numero_serie"]=="CZ7000ABCD"
    assert ficha["chasis_blade"]["cantidad_slots"]==8
    assert len(ficha["componentes"]["chasis_slot"])==8
    assert sum(len(c["puertos"]) for c in ficha["componentes"]["tarjeta_red"])==12
    assert ficha["componentes"]["chasis_slot"][0]["hostname_servidor"]=="hpe-bl460c-01"
