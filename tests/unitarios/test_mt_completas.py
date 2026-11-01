from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import pytest
from etl.normalizacion.volumenes import uso_disco, CPQ, HR
from etl.normalizacion.servidor import normalizar_servidor
from etl.normalizacion.storage import normalizar_storage
from etl.metricas import construir_metricas, NOMBRES_METRICAS
from etl.metricas_red import interfaces
from etl import metricas_storage as perf
from data.completar_metricas_agentes import completar
from tests.unitarios.test_otros_activos import captura

FECHA=datetime(2026,10,25,15)


def muestra(tiempo=0, incremento=0):
    tasas={2:1200,4:800,6:1440000,7:2000000,8:39321600,10:52428800}
    return {"tiempo":tiempo,"uptime":10000+int(tiempo*100),
            **{c:1000000000000+incremento*tasa for c,tasa in tasas.items()}}


def test_iops_latencia_ponderada_y_throughput_por_tiempo_real():
    r=perf.calcular(muestra(),muestra(2,2))
    assert r=={"almacenamiento_iops":Decimal(2000),
               "almacenamiento_latencia_ms":Decimal("1.72"),
               "almacenamiento_throughput_lectura_mbps":Decimal("314.5728"),
               "almacenamiento_throughput_escritura_mbps":Decimal("419.4304")}


@pytest.mark.parametrize("cambio",[{"uptime":1},{2:1},{8:None},{"tiempo":0},{7:-1}])
def test_storage_no_inventa_resultados_si_se_reinicia_o_faltan_contadores(cambio):
    actual=muestra(2,2);actual.update(cambio)
    assert perf.calcular(muestra(),actual)=={}


def test_sin_operaciones_guarda_cero_iops_pero_no_inventa_latencia():
    r=perf.calcular(muestra(),muestra(2,0))
    assert r["almacenamiento_iops"]==0
    assert r["almacenamiento_throughput_lectura_mbps"]==0
    assert "almacenamiento_latencia_ms" not in r


async def test_hpe_storage_realiza_dos_lecturas_y_actualiza_iops_de_ficha(monkeypatch):
    datos={f"{perf.BASE}.{c}.0":1 for c in perf.COLUMNAS}
    sesion=MagicMock()
    sesion.obtener=AsyncMock(side_effect=[
        {**{f"{perf.BASE}.{c}.0":v for c,v in muestra().items() if isinstance(c,int)},perf.UPTIME:10000},
        {**{f"{perf.BASE}.{c}.0":v for c,v in muestra(2,2).items() if isinstance(c,int)},perf.UPTIME:10200}])
    contexto=MagicMock();contexto.return_value.__enter__.return_value=sesion
    monkeypatch.setattr(perf,"SesionSNMP",contexto)
    monkeypatch.setattr(perf.asyncio,"sleep",AsyncMock())
    reloj=iter([0,0,2,2]);monkeypatch.setattr(perf,"monotonic",lambda:next(reloj))
    ficha={"activo":{"tipo_activo":"STORAGE","fabricante":"HPE"},"storage":{},"mediciones":[]}
    await perf.agregar_metricas_storage(ficha,datos,None)
    assert ficha["storage"]["iops"]==2000
    assert len(ficha["mediciones"])==4
    assert sesion.obtener.await_count==2


@pytest.mark.parametrize("nombre,marca",[("hpe-dl360-01","HPE"),("hpe-dl380-01","HPE"),
    ("hpe-bl460c-01","HPE"),("hpe-bl460c-02","HPE"),("hpe-bl460c-03","HPE"),
    ("huawei-2288h-v5-01","Huawei"),("huawei-2288h-v5-02","Huawei"),
    ("huawei-ch121-v5-01","Huawei"),("huawei-ch121-v5-02","Huawei")])
def test_volumenes_servidores_ambas_marcas_y_blades(nombre,marca):
    datos=captura(nombre)
    ficha=normalizar_servidor(datos,fabricante=marca,fecha_actualizacion=FECHA,tipo="AUTO")
    metricas={m["nombre_metrica"]:m["valor"] for m in construir_metricas("SERVIDOR",ficha,FECHA)}
    if marca=="HPE":
        esperado=sum(Decimal(v)/1024 for oid,v in datos.items() if oid.startswith(CPQ+".4."))
    else:
        esperado=sum(Decimal(v)*datos[HR+".4."+oid.rsplit(".",1)[1]]/(1024**3)
                     for oid,v in datos.items() if oid.startswith(HR+".6."))
    assert metricas["disco_uso_gb"]==esperado>0
    assert {"cpu_uso_ghz","ram_uso_gb","equipo_temperatura_c","equipo_consumo_w"}<=metricas.keys()
    puertos=interfaces(datos,"SERVIDOR")
    assert puertos
    assert all(p["bits"]==64 and p["tiene_contadores"] for p in puertos)


def test_volumenes_no_suman_ram_y_no_inventan_cero_con_informacion_incompleta():
    datos={HR+".2.1":"1.3.6.1.2.1.25.2.1.4",HR+".4.1":4096,
           HR+".5.1":100000,HR+".6.1":50000,
           HR+".2.2":"1.3.6.1.2.1.25.2.1.2",HR+".4.2":4096,
           HR+".5.2":999999,HR+".6.2":999999}
    assert uso_disco(datos,"Huawei")[0]["valor"]==Decimal(50000)*4096/(1024**3)
    datos[HR+".6.1"]=-1
    assert uso_disco(datos,"Huawei")==[]
    assert uso_disco({},"HPE")==[]
    assert uso_disco({CPQ+".3.1":100,CPQ+".4.1":0},"HPE")[0]["valor"]==0
    assert uso_disco({CPQ+".3.1":100,CPQ+".4.1":101},"HPE")==[]


@pytest.mark.parametrize("agente",["huawei-dorado-01","huawei-dorado-02"])
def test_throughput_huawei_suma_nodos_y_convierte_mb_por_segundo_a_mbps(agente):
    ficha=normalizar_storage(captura(agente),fabricante="Huawei",fecha_actualizacion=FECHA)
    valores={m["nombre_metrica"]:m["valor"] for m in construir_metricas("STORAGE",ficha,FECHA)}
    assert valores["almacenamiento_throughput_lectura_mbps"]==(420+440)*8
    assert valores["almacenamiento_throughput_escritura_mbps"]==(210+220)*8
    assert valores["almacenamiento_iops"]==25500


def test_complemento_generador_es_idempotente_y_conserva_estados():
    datos={"1.3.6.1.4.1.2011.2.235.1.1.18.50.1.12.1":("2","960"),
           "1.3.6.1.4.1.2011.2.235.1.1.1.7.0":("2","2")}
    completar("huawei-2288h-v5-01",datos)
    primera=dict(datos)
    completar("huawei-2288h-v5-01",datos)
    assert datos==primera
    assert datos["1.3.6.1.4.1.2011.2.235.1.1.1.7.0"]==("2","2")
    assert datos[HR+".5.1"]==("2",str(960*1024//4*256))


def test_catalogo_contiene_exactamente_los_14_nombres_de_los_12_mt():
    assert len(NOMBRES_METRICAS)==14
    assert all(n==n.lower() and n.isascii() for n in NOMBRES_METRICAS)
