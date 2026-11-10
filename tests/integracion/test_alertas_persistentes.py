"""CP-116 a CP-120 y regresiones del ciclo: PostgreSQL test, transacciones revertidas."""
import copy
from contextlib import contextmanager
from datetime import date, datetime, timedelta
import os
from urllib.parse import urlparse
from uuid import uuid4
import psycopg2
import pytest
from pydantic import SecretStr
from etl import monitoreo
from etl.alertas import evaluar_alertas
from etl.config import Configuracion

pytestmark = pytest.mark.integracion


@pytest.fixture
def entorno(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("Falta TEST_DATABASE_URL")
    assert "test" in urlparse(url).path.lower()
    db = psycopg2.connect(url)
    @contextmanager
    def conexion(_):
        with db.cursor() as c:
            c.execute("SAVEPOINT ciclo_alertas")
        try:
            yield db
        except Exception:
            with db.cursor() as c:
                c.execute("ROLLBACK TO SAVEPOINT ciclo_alertas")
            raise
        finally:
            with db.cursor() as c:
                c.execute("RELEASE SAVEPOINT ciclo_alertas")
    monkeypatch.setattr(monitoreo, "conexion_bd", conexion)
    monkeypatch.setattr(monitoreo, "CONTADORES_LECTURA", {})
    config = Configuracion(SecretStr("test"), database_url=SecretStr(url))
    class Entorno:
        def sql(self, q, p=()):
            with db.cursor() as c:
                c.execute(q,p)
                return c.fetchall() if c.description else []
        def crear(self,tipo="SERVIDOR"):
            nombre="ALERTA-TEST-"+uuid4().hex[:12]
            self.sql("INSERT INTO datacenters(nombre) VALUES (%s)",(nombre,))
            id=self.sql("INSERT INTO activo(numero_serie,hostname,ubicacion,tipo_activo,estado_operativo,ultima_actualizacion) VALUES (%s,%s,%s,%s,'Encendido',%s) RETURNING id",(nombre,nombre,nombre,tipo,datetime(2026,1,1)))[0][0]
            subtipo={"SERVIDOR":"servidor","STORAGE":"storage","SWITCH":"switch","CHASIS":"chasis_blade"}[tipo]
            datos={"tipo":"RACKEABLE"} if tipo=="SERVIDOR" else {"cantidad_slots":1} if tipo=="CHASIS" else {}
            columnas=["id",*datos]
            self.sql(f"INSERT INTO {subtipo}({','.join(columnas)}) VALUES ({','.join(['%s']*len(columnas))})",(id,*datos.values()))
            conexion_id=self.sql("INSERT INTO monitoreo_snmp(ip_gestion,usuario,clave,frecuencia_actualizacion,estado_conexion,activo_id) VALUES ('127.0.0.1:1','test','test',120,'Activo',%s) RETURNING id",(id,))[0][0]
            ref=monitoreo.ConexionMonitoreo(conexion_id,id,"127.0.0.1:1","test",SecretStr("test"))
            ficha={"activo":{"numero_serie":nombre,"hostname":nombre,"tipo_activo":tipo,"estado_operativo":"Encendido"},subtipo:datos,"componentes":{},"mediciones":[]}
            return ref,ficha
        def ciclo(self,ref,ficha,temp=None,componentes=None,estado="Encendido"):
            f=copy.deepcopy(ficha);f["activo"]["estado_operativo"]=estado
            if temp is not None:f["mediciones"].append({"nombre_metrica":"equipo_temperatura_c","valor":temp})
            if componentes is not None:f["componentes"]=componentes
            return monitoreo.guardar_iteracion(config,ref,f)
        def abiertas(self,id):
            return self.sql("SELECT componente_tipo,componente_sn,campo,severidad,id,fecha_inicio,ultima_verificacion FROM alerta WHERE activo_id=%s AND fecha_resolucion IS NULL ORDER BY id",(id,))
        def evaluar(self,id,**kwargs):return evaluar_alertas(db,id,**kwargs)
        def fallo(self,ref):return monitoreo.registrar_fallo(config,ref,"timeout")
    e=Entorno()
    e.sql("UPDATE umbral SET advertencia=NULL,critico=NULL WHERE nombre<>'dias_para_eos'")
    e.sql("UPDATE umbral SET advertencia=75,critico=85 WHERE nombre='equipo_temperatura_c'")
    e.sql("UPDATE umbral SET advertencia=30,critico=NULL WHERE nombre='dias_para_eos'")
    try:yield e
    finally:db.rollback();db.close()


@pytest.mark.parametrize("temperatura,severidad",[(74,None),(75,"Media"),(84,"Media"),(85,"Crítica")])
def test_cp116_limites_y_evento_solo_una_vez(entorno,temperatura,severidad):
    r,f=entorno.crear()
    entorno.ciclo(r,f,temperatura)
    filas=entorno.abiertas(r.activo_id)
    assert [x[3] for x in filas]==([] if severidad is None else [severidad])
    entorno.ciclo(r,f,temperatura)
    assert [x[4] for x in entorno.abiertas(r.activo_id)]==[x[4] for x in filas]
    eventos=entorno.sql("SELECT valor_nuevo FROM historico_estado WHERE activo_id=%s AND campo='umbral_equipo_temperatura_c'",(r.activo_id,))
    assert len(eventos)==(0 if severidad is None else 1)


@pytest.mark.parametrize("tipo",["SERVIDOR","STORAGE","SWITCH","CHASIS"])
def test_cp117_estado_y_fallo_sin_cambiar_fecha_del_activo(entorno,tipo):
    r,f=entorno.crear(tipo)
    entorno.ciclo(r,f,estado="Degradado")
    assert entorno.abiertas(r.activo_id)[0][3]=="Crítica"
    antes=entorno.sql("SELECT estado_operativo,ultima_actualizacion FROM activo WHERE id=%s",(r.activo_id,))
    entorno.fallo(r);entorno.fallo(r)
    assert entorno.sql("SELECT estado_operativo,ultima_actualizacion FROM activo WHERE id=%s",(r.activo_id,))==antes
    assert len(entorno.abiertas(r.activo_id))==2
    assert entorno.sql("SELECT count(*) FROM historico_estado WHERE activo_id=%s AND campo='estado_conexion' AND valor_nuevo='Sin conexión'",(r.activo_id,))[0][0]==1
    entorno.ciclo(r,f,estado="Apagado")
    assert len(entorno.abiertas(r.activo_id))==1
    entorno.ciclo(r,f)
    assert entorno.abiertas(r.activo_id)==[]


def test_no_se_chancan_y_resuelve_solo_la_condicion_recuperada(entorno):
    r,f=entorno.crear()
    componentes={"disco":[{"numero_serial":"D-1","estado":"Degradado"}],"fuente_poder":[{"numero_serial":"P-1","estado":"Degradado"}]}
    entorno.ciclo(r,f,85,componentes)
    originales=entorno.abiertas(r.activo_id)
    assert len(originales)==3
    eventos=entorno.sql("SELECT count(*) FROM historico_estado WHERE activo_id=%s",(r.activo_id,))[0][0]
    entorno.ciclo(r,f,85,componentes)
    assert entorno.sql("SELECT count(*) FROM historico_estado WHERE activo_id=%s",(r.activo_id,))[0][0]==eventos
    componentes["disco"][0]["estado"]="Encendido"
    entorno.ciclo(r,f,80,componentes)
    restantes=entorno.abiertas(r.activo_id)
    assert len(restantes)==2 and {x[2] for x in restantes}=={"estado","umbral_equipo_temperatura_c"}
    assert next(x for x in restantes if x[2].startswith('umbral'))[3]=="Media"
    assert {x[4] for x in restantes}<={x[4] for x in originales}
    componentes["fuente_poder"][0]["estado"]="Encendido"
    entorno.ciclo(r,f,74,componentes)
    assert entorno.abiertas(r.activo_id)==[]
    assert entorno.sql("SELECT count(*) FROM historico_estado WHERE activo_id=%s AND campo='estado' AND valor_nuevo='Encendido'",(r.activo_id,))[0][0]==2
    entorno.ciclo(r,f,85,componentes)
    assert entorno.abiertas(r.activo_id)[0][4] not in {x[4] for x in originales}


def test_fallo_conserva_alertas_previas_sin_revalidar_datos_antiguos(entorno):
    r,f=entorno.crear();entorno.ciclo(r,f,85,{"disco":[{"numero_serial":"D-1","estado":"Degradado"}]})
    previas=entorno.abiertas(r.activo_id);entorno.fallo(r)
    actuales={x[4]:x for x in entorno.abiertas(r.activo_id)}
    assert len(actuales)==3
    for a in previas:assert actuales[a[4]][6]==a[6]
    entorno.evaluar(r.activo_id)
    nuevas={x[4]:x for x in entorno.abiertas(r.activo_id)}
    for a in actuales.values():assert nuevas[a[4]][6]==a[6]
    entorno.ciclo(r,f,74,{"disco":[{"numero_serial":"D-1","estado":"Encendido"}]})
    assert entorno.abiertas(r.activo_id)==[]


@pytest.mark.parametrize("condicion",["mantenimiento","baja"])
def test_cp118_excluye_sin_generar_falsa_recuperacion(entorno,condicion):
    r,f=entorno.crear()
    entorno.sql("UPDATE activo SET fecha_eos=%s WHERE id=%s",(date(2020,1,1),r.activo_id))
    if condicion=="mantenimiento":entorno.sql("UPDATE activo SET mantenimiento_activo=true WHERE id=%s",(r.activo_id,))
    else:entorno.sql("UPDATE activo SET estado_operativo='Baja' WHERE id=%s",(r.activo_id,))
    entorno.evaluar(r.activo_id,lectura_snmp=True)
    assert entorno.abiertas(r.activo_id)==[]


@pytest.mark.parametrize("dias,severidad",[(31,None),(30,"Media"),(0,"Media"),(-1,"Crítica")])
def test_cp119_limites_de_eos_independientes_de_snmp(entorno,dias,severidad):
    r,f=entorno.crear();hoy=date(2026,11,8)
    entorno.sql("UPDATE activo SET fecha_eos=%s WHERE id=%s",(hoy+timedelta(days=dias),r.activo_id))
    entorno.evaluar(r.activo_id,hoy=hoy)
    assert [x[3] for x in entorno.abiertas(r.activo_id)]==([] if severidad is None else [severidad])


def test_cp120_sin_fecha_y_recuperacion_por_renovacion(entorno):
    r,f=entorno.crear();entorno.evaluar(r.activo_id)
    assert entorno.abiertas(r.activo_id)==[]
    entorno.sql("UPDATE activo SET fecha_eos='2020-01-01' WHERE id=%s",(r.activo_id,));entorno.evaluar(r.activo_id)
    assert len(entorno.abiertas(r.activo_id))==1
    entorno.sql("UPDATE activo SET fecha_eos='2099-01-01' WHERE id=%s",(r.activo_id,));entorno.evaluar(r.activo_id)
    assert entorno.abiertas(r.activo_id)==[]


def test_dos_puertos_con_el_mismo_numero_en_tarjetas_distintas(entorno):
    r,f=entorno.crear()
    componentes={"tarjeta_red":[{"numero_serial":n,"estado":"Encendido","puertos":[{"numero_puerto":"1","estado":"Degradado"}]} for n in ("NIC-1","NIC-2")]}
    entorno.ciclo(r,f,74,componentes)
    alertas=entorno.abiertas(r.activo_id)
    assert len(alertas)==2 and len({x[1] for x in alertas})==2
    assert entorno.sql("SELECT count(DISTINCT componente_sn) FROM historico_estado WHERE activo_id=%s AND componente_tipo='puerto_tarjeta_red'",(r.activo_id,))[0][0]==2


def test_rollback_atomico_si_falla_guardado_de_alertas(entorno,monkeypatch):
    r,f=entorno.crear();antes=entorno.sql("SELECT ultima_actualizacion FROM activo WHERE id=%s",(r.activo_id,))
    def fallar(*a,**k):raise RuntimeError("Prueba de rollback")
    monkeypatch.setattr(monitoreo,"evaluar_alertas",fallar)
    with pytest.raises(RuntimeError):entorno.ciclo(r,f,85)
    assert entorno.sql("SELECT ultima_actualizacion FROM activo WHERE id=%s",(r.activo_id,))==antes
    assert entorno.sql("SELECT count(*) FROM metrica_historica WHERE activo_id=%s",(r.activo_id,))[0][0]==0
    assert entorno.sql("SELECT count(*) FROM historico_estado WHERE activo_id=%s",(r.activo_id,))[0][0]==0


def test_retiro_confirmado_de_nic_cierra_sus_puertos_sin_ocultar_los_de_otra_tarjeta(entorno):
    r,f=entorno.crear()
    nics=[{"numero_serial":n,"estado":"Encendido","puertos":[{"numero_puerto":"1","estado":"Degradado"}]} for n in ("NIC-1","NIC-2")]
    entorno.ciclo(r,f,74,{"tarjeta_red":nics})
    anteriores=entorno.abiertas(r.activo_id)
    entorno.ciclo(r,f,74,{"tarjeta_red":[nics[1]]})
    restantes=entorno.abiertas(r.activo_id)
    assert len(restantes)==1 and restantes[0][4]==anteriores[1][4]
    assert entorno.sql("SELECT count(*) FROM historico_estado WHERE activo_id=%s AND campo='presencia' AND valor_nuevo='Retirado'",(r.activo_id,))[0][0]==1


def test_dos_evaluadores_concurrentes_no_duplican_alerta_ni_evento():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from datetime import timezone
    url=os.environ.get("TEST_DATABASE_URL", "")
    if not url:pytest.skip("Falta TEST_DATABASE_URL")
    assert "test" in urlparse(url).path.lower()
    nombre="ALERTA-CONC-"+uuid4().hex[:12]
    activo=None
    try:
        with psycopg2.connect(url) as db,db.cursor() as c:
            c.execute("INSERT INTO datacenters(nombre) VALUES (%s)",(nombre,))
            c.execute("INSERT INTO activo(numero_serie,hostname,ubicacion,tipo_activo,estado_operativo,ultima_actualizacion) VALUES (%s,%s,%s,'SERVIDOR','Encendido',%s) RETURNING id",(nombre,nombre,nombre,datetime.now(timezone.utc).replace(tzinfo=None)))
            activo=c.fetchone()[0]
            c.execute("INSERT INTO servidor(id,tipo) VALUES (%s,'RACKEABLE')",(activo,))
            c.execute("INSERT INTO monitoreo_snmp(ip_gestion,usuario,clave,frecuencia_actualizacion,estado_conexion,activo_id) VALUES ('127.0.0.1:1','test','test',120,'Activo',%s)",(activo,))
            c.execute("INSERT INTO disco(activo_id,numero_serial,estado) VALUES (%s,'DISCO-CONCURRENT','Degradado')",(activo,))
        barrera=Barrier(2)
        def una(_):
            with psycopg2.connect(url) as db:
                barrera.wait(timeout=10)
                return evaluar_alertas(db,activo)
        with ThreadPoolExecutor(max_workers=2) as pool:resultados=list(pool.map(una,range(2)))
        assert sum(r['creadas'] for r in resultados)==1
        with psycopg2.connect(url) as db,db.cursor() as c:
            c.execute("SELECT count(*) FROM alerta WHERE activo_id=%s",(activo,));assert c.fetchone()[0]==1
            c.execute("SELECT count(*) FROM historico_estado WHERE activo_id=%s AND campo='estado'",(activo,));assert c.fetchone()[0]==1
    finally:
        if activo is not None:
            with psycopg2.connect(url) as db,db.cursor() as c:
                for tabla in ('alerta','historico_estado','metrica_historica','disco','monitoreo_snmp'):
                    c.execute(f"DELETE FROM {tabla} WHERE activo_id=%s",(activo,))
                c.execute("DELETE FROM servidor WHERE id=%s",(activo,));c.execute("DELETE FROM activo WHERE id=%s",(activo,));c.execute("DELETE FROM datacenters WHERE nombre=%s",(nombre,))
