from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import pytest
from etl import metricas_red as red
from etl.metricas import construir_metricas, NOMBRES_METRICAS
from etl.errores import DatosIncompletos


def puerto(bits=64, velocidad=1000):
    return {"id": "if:1", "bits": bits, "velocidad": Decimal(velocidad)}


def muestra(tiempo=0, entrada=1000000000, salida=0, **otros):
    return {"tiempo": tiempo, "entrada": entrada, "salida": salida,
            "oper": 1, "uptime": 10000, "discontinuidad": 0, "nombre": "eth0", **otros}


def test_formula_documentada_mbps_y_utilizacion_full_duplex():
    resultado = red.calcular(puerto(), muestra(), muestra(60, 1600000000, 300000000))
    assert resultado == {"red_trafico_entrada_mbps": Decimal(80),
                         "red_trafico_salida_mbps": Decimal(40),
                         "red_utilizacion_pct": Decimal(8)}


@pytest.mark.parametrize("cambio", [
    {"uptime": 1}, {"discontinuidad": 100}, {"nombre": "otra"},
    {"oper": 2}, {"tiempo": 0}, {"tiempo": -1}])
def test_reinicios_cambio_interfaz_puerto_caido_y_tiempo_invalido(cambio):
    actual = muestra(60, 1600000000)
    actual.update(cambio)
    assert red.calcular(puerto(), muestra(), actual) == {}


def test_counter64_no_inventa_un_wrap_ni_utilizacion_con_muestras_incompletas():
    assert red.calcular(puerto(), muestra(), muestra(1, 0, 0)) == {"red_trafico_salida_mbps": 0}


def test_counter32_acepta_una_vuelta_verificada():
    antes = muestra(0, 2**32-1000)
    despues = muestra(1, 1000)
    assert red.calcular(puerto(32), antes, despues)["red_trafico_entrada_mbps"] == Decimal("0.016")


def test_counter32_descarta_intervalo_ambiguo_o_wrap_sin_marcador():
    assert red.calcular(puerto(32,10000), muestra(), muestra(60,1600000000)) == {}
    r = red.calcular(puerto(32), muestra(0,2**32-1000,discontinuidad=None),
                    muestra(1,1000,discontinuidad=None))
    assert "red_trafico_entrada_mbps" not in r


def test_cero_es_una_tasa_real_y_no_un_dato_ausente():
    assert red.calcular(puerto(),muestra(),muestra(1)) == {
        "red_trafico_entrada_mbps":0,"red_trafico_salida_mbps":0,"red_utilizacion_pct":0}


def test_prefiere_counter64_y_filtra_interfaces_virtuales():
    datos = {red.IF+".3.1":6,red.IFX+".1.1":"1/1/1",red.IFX+".15.1":10000,red.IF+".10.1":10,
        red.IF+".16.1":20,red.IFX+".6.1":2**33,red.IFX+".10.1":2**34,
        red.IF+".3.2":135,red.IFX+".15.2":10000,red.IFX+".6.2":1,red.IFX+".10.2":1}
    p = red.interfaces(datos,"SWITCH")
    assert len(p)==1 and p[0]["bits"]==64 and p[0]["tipo"]=="puerto_switch"
    assert p[0]["entrada"] == red.IFX+".6.1"


async def test_dos_lecturas_por_ciclo_con_puerto_identificado(monkeypatch):
    datos = {red.IF+".3.1":6,red.IFX+".1.1":"1/1/1",red.IFX+".15.1":1000,red.IFX+".6.1":1,red.IFX+".10.1":1}
    conexion = MagicMock()
    sesion = MagicMock()
    sesion.obtener = AsyncMock(side_effect=[
        {red.IFX+".6.1":1000000000,red.IFX+".10.1":0,red.IF+".8.1":1,
         red.UPTIME:1000,red.IFX+".19.1":0,red.IFX+".1.1":"1/1/1"},
        {red.IFX+".6.1":1600000000,red.IFX+".10.1":300000000,red.IF+".8.1":1,
         red.UPTIME:7000,red.IFX+".19.1":0,red.IFX+".1.1":"1/1/1"}])
    contexto = MagicMock()
    contexto.return_value.__enter__.return_value = sesion
    monkeypatch.setattr(red,"SesionSNMP",contexto)
    monkeypatch.setattr(red.asyncio,"sleep",AsyncMock())
    reloj=iter([0,0,60,60])
    monkeypatch.setattr(red,"monotonic",lambda:next(reloj))
    ficha={"activo":{"tipo_activo":"SWITCH"},"componentes":{"puerto_switch":[{"numero_puerto":"1/1/1"}]},"mediciones":[]}
    await red.agregar_metricas_red(ficha,datos,conexion)
    assert sesion.obtener.await_count==2
    valores={m["nombre_metrica"]:m["valor"] for m in ficha["mediciones"]}
    assert valores["red_trafico_entrada_mbps"]==80
    assert valores["red_trafico_salida_mbps"]==40
    assert valores["red_utilizacion_pct"]==8
    assert valores["red_ancho_banda_mbps"]==1000
    assert all(m["componente_serial"]=="1/1/1" for m in ficha["mediciones"])


async def test_puerto_fc_convierte_gbps_a_mbps_sin_inventar_contadores():
    ficha={"activo":{"tipo_activo":"STORAGE"},"componentes":{"tarjeta_red":[{
        "puertos":[{"numero_puerto":"A0","velocidad":"16 Gbps"}]}]}}
    await red.agregar_metricas_red(ficha,{},None)
    assert ficha["mediciones"]==[{"nombre_metrica":"red_ancho_banda_mbps",
        "valor":16000,"componente_tipo":"puerto_tarjeta_red","componente_serial":"puerto:A0"}]


def test_catalogo_convierte_unidades_y_alias_sin_cambiar_campos_del_activo():
    ficha={"activo":{"temperatura":25,"consumo_electrico_w":100},
        "componentes":{"cpu":[{"velocidad_ghz":2,"cantidad_nucleos":4}],
                       "ram":[{"capacidad_gb":16}]},
        "mediciones":[{"nombre_metrica":n,"valor":v} for n,v in (
            ("temperatura",25),("consumo_electrico_w",100),("cpu_uso_pct",50),
            ("ram_uso_pct",25),("iops",1000),("latencia_ms",2))]}
    valores={m["nombre_metrica"]:m["valor"] for m in construir_metricas("SWITCH",ficha,datetime.now())}
    assert valores=={"equipo_temperatura_c":25,"equipo_consumo_w":100,
        "cpu_uso_ghz":4,"ram_uso_gb":4,"almacenamiento_iops":1000,"almacenamiento_latencia_ms":2}
    assert set(valores)<=NOMBRES_METRICAS
    assert ficha["activo"]=={"temperatura":25,"consumo_electrico_w":100}


def test_no_convierte_porcentaje_a_ghz_sin_capacidad_conocida():
    assert construir_metricas("SWITCH",{"mediciones":[{"nombre_metrica":"cpu_uso_pct","valor":40}]},datetime.now())==[]


@pytest.mark.parametrize("nombre",["CPU_uso_ghz","equipo_temperatura","red_trafico_Mbps","otra"])
def test_rechaza_nombres_fuera_de_catalogo(nombre):
    with pytest.raises(DatosIncompletos):
        construir_metricas("SERVIDOR",{"mediciones":[{"nombre_metrica":nombre,"valor":1}]},datetime.now())


def test_switch_excluye_gestion_fc_y_nombres_que_no_son_puertos():
    datos = {}
    for indice,tipo,nombre in [(42,6,"1/1/1"),(2,6,"mgmt"),(3,56,"1/1/3"),(4,6,"vlan10")]:
        datos.update({f"{red.IF}.3.{indice}":tipo, f"{red.IFX}.1.{indice}":nombre,
                      f"{red.IFX}.15.{indice}":1000})
    assert [p["etiqueta"] for p in red.interfaces(datos,"SWITCH")] == ["1/1/1"]
    assert red.interfaces(datos,"STORAGE")[0]["id"] == "if:2"


async def test_switch_excluye_interfaces_ausentes_del_inventario(monkeypatch):
    datos={red.IF+".3.42":6,red.IFX+".1.42":"1/1/42",red.IFX+".15.42":1000,
           red.IFX+".6.42":1,red.IFX+".10.42":1}
    sesion=MagicMock();monkeypatch.setattr(red,"SesionSNMP",sesion)
    ficha={"activo":{"tipo_activo":"SWITCH"},"componentes":{"puerto_switch":[{"numero_puerto":"1/1/1"}]}}
    await red.agregar_metricas_red(ficha,datos,None)
    assert ficha["mediciones"] == []
    sesion.assert_not_called()


@pytest.mark.parametrize("indice",[1,42])
async def test_switch_conserva_nombre_si_cambia_ifindex(indice):
    ficha={"activo":{"tipo_activo":"SWITCH"},"componentes":{"puerto_switch":[{"numero_puerto":"1/1/1"}]}}
    datos={f"{red.IF}.3.{indice}":6,f"{red.IFX}.1.{indice}":"1/1/1",f"{red.IFX}.15.{indice}":1000}
    await red.agregar_metricas_red(ficha,datos,None)
    assert ficha["mediciones"] == [{"nombre_metrica":"red_ancho_banda_mbps","valor":1000,
                                   "componente_tipo":"puerto_switch","componente_serial":"1/1/1"}]
