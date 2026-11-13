"""Pruebas sobre copias temporales; nunca editan los agentes ni usan PostgreSQL."""
from pathlib import Path
import pytest
from scripts.componentes_snmp import (Captura, catalogo, normalizar, preparar_retiro,
    retirar, restaurar, ruta_equipo)
from scripts import componentes_snmp

REPO = Path(__file__).resolve().parents[2]
CAPTURAS = sorted((REPO/'data').glob('*/public.snmprec'))


@pytest.mark.parametrize('ruta', CAPTURAS, ids=lambda p: p.parent.name)
def test_retirar_piezas_por_perfil_sin_perder_identidad_energia_y_otras_tablas(ruta):
    original = ruta.read_bytes()
    captura = Captura(original)
    antes = normalizar(captura)
    for tipo, piezas in catalogo(captura).items():
        if not piezas:
            continue
        # Discos y controladoras de storage son obligatorios para el perfil.
        if antes['activo']['tipo_activo'] == 'STORAGE' and tipo in ('disco','controladora_raid') and len(piezas) == 1:
            with pytest.raises(ValueError, match='perfil ETL rechazaría'):
                preparar_retiro(original, tipo, [1])
            continue
        nuevo, _, oids = preparar_retiro(original, tipo, [1])
        despues = normalizar(Captura(nuevo))
        assert antes['activo'] == despues['activo']
        assert len(despues['componentes'][tipo]) == len(antes['componentes'][tipo])-1
        for otro, filas in antes['componentes'].items():
            if otro != tipo:
                if ruta.parent.name.startswith('huawei-dorado') and tipo == 'controladora_raid' and otro in ('cpu','ram'):
                    # Estas piezas son de la controladora que se está retirando.
                    assert despues['componentes'][otro] == filas[1:]
                else:
                    assert despues['componentes'][otro] == filas, (ruta.parent.name, tipo, otro)
        # Todas las líneas ajenas se conservan byte a byte, incluso variaciones de métricas.
        assert Captura(nuevo).datos == {o:v for o,v in captura.datos.items() if o not in oids}
        assert ruta.read_bytes() == original


def copiar(tmp_path, equipo='hpe-dl380-01'):
    ruta = tmp_path/'data'/equipo/'public.snmprec'
    ruta.parent.mkdir(parents=True)
    ruta.write_bytes((REPO/'data'/equipo/'public.snmprec').read_bytes())
    return ruta


def test_restauracion_exacta_en_orden_inverso(tmp_path):
    ruta = copiar(tmp_path)
    original = ruta.read_bytes()
    retirar(ruta, 'disco', [1])
    sin_disco = ruta.read_bytes()
    retirar(ruta, 'ram', [1])
    assert ruta.read_bytes() != sin_disco
    restaurar(ruta)
    assert ruta.read_bytes() == sin_disco
    restaurar(ruta)
    assert ruta.read_bytes() == original
    with pytest.raises(ValueError, match='No hay retiros'):
        restaurar(ruta)


def test_restauracion_no_sobrescribe_cambios_posteriores(tmp_path):
    ruta = copiar(tmp_path)
    retirar(ruta, 'disco', [1])
    cambiado = ruta.read_bytes()+b'# cambio manual posterior\r\n'
    ruta.write_bytes(cambiado)
    with pytest.raises(ValueError, match='cambios posteriores'):
        restaurar(ruta)
    assert ruta.read_bytes() == cambiado


def test_previsualizar_restauracion_no_cambia_archivo_ni_consume_respaldo(tmp_path):
    ruta = copiar(tmp_path)
    original = ruta.read_bytes()
    retirar(ruta, 'disco', [1])
    modificado = ruta.read_bytes()
    assert restaurar(ruta, vista_previa=True)['vista_previa']
    assert ruta.read_bytes() == modificado
    restaurar(ruta)
    assert ruta.read_bytes() == original


def test_archivo_bloqueado_no_deja_retiro_pendiente(tmp_path, monkeypatch):
    ruta = copiar(tmp_path)
    original = ruta.read_bytes()
    def bloqueado(*_):
        raise PermissionError('Archivo abierto por el agente')
    monkeypatch.setattr(componentes_snmp, 'escribir_atomico', bloqueado)
    with pytest.raises(ValueError, match='-Reiniciar'):
        retirar(ruta, 'disco', [1])
    assert ruta.read_bytes() == original
    with pytest.raises(ValueError, match='No hay retiros'):
        restaurar(ruta)


def test_vista_previa_y_numero_invalido_no_modifican_captura(tmp_path):
    ruta = copiar(tmp_path)
    original = ruta.read_bytes()
    retirar(ruta, 'fuente_poder', [1], vista_previa=True)
    assert ruta.read_bytes() == original
    assert not list((ruta.parent.parent/'.respaldos_componentes').glob('**/original.snmprec'))
    for numeros in ([0], [999], [1,1]):
        with pytest.raises(ValueError, match='números únicos'):
            retirar(ruta, 'disco', numeros)
        assert ruta.read_bytes() == original


@pytest.mark.parametrize('equipo', ['hpe-storage-fc-01','huawei-dorado-01'])
@pytest.mark.parametrize('tipo', ['disco','controladora_raid'])
def test_no_invalida_storage_quitando_todas_las_piezas_obligatorias(tmp_path, equipo, tipo):
    ruta = copiar(tmp_path, equipo)
    original = ruta.read_bytes()
    with pytest.raises(ValueError, match='perfil ETL rechazaría'):
        retirar(ruta, tipo, todos=True)
    assert ruta.read_bytes() == original


def test_cpu_y_ram_dorado_comparten_tabla_pero_no_se_borran_mutuamente(tmp_path):
    ruta = copiar(tmp_path, 'huawei-dorado-01')
    original = normalizar(Captura(ruta.read_bytes()))
    retirar(ruta, 'cpu', [1])
    assert normalizar(Captura(ruta.read_bytes()))['componentes']['ram'] == original['componentes']['ram']
    restaurar(ruta)
    retirar(ruta, 'ram', [1])
    assert normalizar(Captura(ruta.read_bytes()))['componentes']['cpu'] == original['componentes']['cpu']


@pytest.mark.parametrize('equipo', ['../hpe-dl380-01','..','C:\\Windows','/tmp/otro'])
def test_no_acepta_rutas_fuera_de_data(tmp_path, equipo):
    with pytest.raises(ValueError):
        ruta_equipo(tmp_path, equipo)
