from copy import deepcopy
from datetime import datetime
from unittest.mock import MagicMock
from pydantic import SecretStr
from etl.normalizacion.servidor import normalizar_servidor_hpe
from etl.carga import cargar_registro
from etl.config import Configuracion
from etl import db
from etl.repositorio import COLUMNAS
from data.servicio_agentes import cargar_agentes
from tests.unitarios.test_otros_activos import captura, DATA


def test_dl380_nuevo_conserva_todos_los_oid_del_original():
    original=captura("hpe-dl380-01");nuevo=captura("hpe-dl380-02")
    ip_antes=next(str(v) for k,v in original.items() if k.startswith("1.3.6.1.2.1.4.20.1.1."))
    ip_despues=next(str(v) for k,v in nuevo.items() if k.startswith("1.3.6.1.2.1.4.20.1.1."))
    esperados={k[:-len(ip_antes)]+ip_despues if k.startswith("1.3.6.1.2.1.4.20.1.") and k.endswith("."+ip_antes) else k for k in original}
    assert set(nuevo)==esperados
    assert len(nuevo)==len(original)
    def etiquetas(nombre):
        return {l.split("|",2)[0]:l.split("|",2)[1] for l in (DATA/nombre/"public.snmprec").read_text().splitlines() if l and not l.startswith("#")}
    tipos=etiquetas("hpe-dl380-02")
    for k,t in etiquetas("hpe-dl380-01").items():
        destino=k[:-len(ip_antes)]+ip_despues if k.startswith("1.3.6.1.2.1.4.20.1.") and k.endswith("."+ip_antes) else k
        assert tipos[destino]==t


def sin_identidad(obj):
    if isinstance(obj,list):return [sin_identidad(x) for x in obj]
    if isinstance(obj,dict):return {k:sin_identidad(v) for k,v in obj.items() if k not in ("numero_serie","numero_serial","hostname","ip_sistema_operativo","mac_address")}
    return obj


def test_inventario_mismos_campos_y_valores_salvo_identidad():
    ahora=datetime(2026,10,25)
    anterior=normalizar_servidor_hpe(captura("hpe-dl380-01"),fecha_actualizacion=ahora)
    nuevo=normalizar_servidor_hpe(captura("hpe-dl380-02"),fecha_actualizacion=ahora)
    assert sin_identidad(anterior)==sin_identidad(nuevo)
    assert nuevo["activo"]["numero_serie"]=="CZ38020ABC"
    assert nuevo["activo"]["hostname"]=="hpe-dl380-02"
    for tabla,filas in anterior["componentes"].items():
        antiguos={f["numero_serial"] for f in filas if f.get("numero_serial")}
        nuevos={f["numero_serial"] for f in nuevo["componentes"][tabla] if f.get("numero_serial")}
        assert len(antiguos)==len(nuevos)
        assert not antiguos & nuevos


def test_carga_completa_sin_necesitar_nuevas_columnas_ni_bd(monkeypatch):
    ficha=normalizar_servidor_hpe(captura("hpe-dl380-02"),fecha_actualizacion=datetime(2026,10,25))
    conexion=MagicMock();cursor=conexion.cursor.return_value.__enter__.return_value
    identificador=100
    def ejecutar(sql,params):
        nonlocal identificador
        if sql.startswith("SELECT nombre"):cursor.fetchone.return_value=("DC-LAB-LOCAL",)
        elif sql.startswith("SELECT tipo"):cursor.fetchone.return_value=("RACKEABLE",)
        elif "RETURNING id" in sql:
            identificador+=1;cursor.fetchone.return_value=(identificador,)
    cursor.execute.side_effect=ejecutar
    monkeypatch.setattr(db,"obtener_conexion",lambda cfg:conexion)
    resultado=cargar_registro(Configuracion(SecretStr("test")),ficha,ubicacion="DC-LAB-LOCAL")
    assert resultado["hostname"]=="hpe-dl380-02"
    assert resultado["metricas_guardadas"]==5
    for tabla,filas in ficha["componentes"].items():
        assert resultado["componentes"][tabla]==len(filas)
        for fila in filas:
            assert set(fila)-{"puertos"}<=set(COLUMNAS[tabla])
    assert resultado["componentes"]["puerto_tarjeta_red"]==sum(len(f.get("puertos",[])) for f in ficha["componentes"]["tarjeta_red"])
    conexion.commit.assert_called_once()
    conexion.rollback.assert_not_called()


def test_manifiesto_admite_el_nuevo_agente_y_no_duplica_destinos():
    agentes=cargar_agentes()
    nuevo=next(a for a in agentes if a["nombre"]=="hpe-dl380-02")
    assert nuevo["usuario"]=="HPE"
    assert nuevo["auth_key"]==nuevo["priv_key"]=="Enterprise"
    assert nuevo["host"]=="127.0.0.17" and nuevo["puerto"]==17800
    assert len({(a["host"],a["puerto"]) for a in agentes})==len(agentes)
