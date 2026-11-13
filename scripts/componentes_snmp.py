"""Retiro reversible de piezas en capturas SNMP; no accede a BD ni a la red."""
import argparse
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
H = '1.3.6.1.4.1.232'
I = '1.3.6.1.4.1.2011.2.235.1.1'
E = '1.3.6.1.4.1.2011.2.82.1.82'
D = '1.3.6.1.4.1.34774.4.1'
A = '1.3.6.1.4.1.47196.4.1.1.3'
IF = '1.3.6.1.2.1.2.2.1'
IFX = '1.3.6.1.2.1.31.1.1.1'
ENT = '1.3.6.1.2.1.47.1.1.1.1'
SENSOR = '1.3.6.1.2.1.99.1.1.1'
TIPOS = ('cpu', 'ram', 'disco', 'fuente_poder', 'ventilador', 'tarjeta_red', 'controladora_raid')
ALIASES = {'fuente': 'fuente_poder', 'psu': 'fuente_poder', 'fan': 'ventilador',
           'nic': 'tarjeta_red', 'raid': 'controladora_raid', 'memoria': 'ram'}


def orden(indice):
    return tuple(int(x) for x in indice.split('.'))


class Captura:
    def __init__(self, contenido):
        self.contenido = contenido
        self.lineas = contenido.splitlines(keepends=True)
        self.datos = {}
        self.linea_oid = {}
        previo = ()
        for n, linea in enumerate(self.lineas, 1):
            s = linea.decode('utf-8').lstrip('\ufeff').strip()
            if not s or s.startswith('#'):
                continue
            partes = s.split('|', 2)
            if len(partes) != 3 or not re.fullmatch(r'\d+(?:\.\d+)+', partes[0]):
                raise ValueError(f'Línea {n}: formato SNMPREC inválido.')
            oid, tag, valor = partes
            if oid in self.datos or orden(oid) <= previo:
                raise ValueError(f'Línea {n}: OID repetido o fuera de orden.')
            previo = orden(oid)
            base, _, modulo = tag.partition(':')
            if modulo:
                params = dict(p.split('=', 1) for p in valor.split(',') if '=' in p)
                if 'initial' not in params:
                    raise ValueError(f'No se puede validar la variación del OID {oid}: falta initial.')
                valor = params['initial']
            if base in ('2', '65', '66', '67', '70'):
                dato = int(valor)
            elif base == '4x':
                dato = bytes.fromhex(valor)
            elif base in ('4', '6', '64', '68'):
                dato = valor
            elif base == '5':
                dato = None
            else:
                raise ValueError(f'Etiqueta no admitida: {base}.')
            self.datos[oid] = dato
            self.linea_oid[oid] = n - 1

    def filas(self, raiz, columnas=None):
        filas = {}
        for oid, valor in self.datos.items():
            if not oid.startswith(raiz + '.'):
                continue
            col, _, indice = oid[len(raiz) + 1:].partition('.')
            if indice and (columnas is None or int(col) in columnas):
                filas.setdefault(indice, {})[int(col)] = valor
        return dict(sorted(filas.items(), key=lambda x: orden(x[0])))

    def oids(self, raiz, indices, columnas=None):
        return {f'{raiz}.{col}.{idx}' for idx, fila in self.filas(raiz, columnas).items()
                if idx in indices for col in fila}

    def sin(self, oids):
        posiciones = {self.linea_oid[o] for o in oids}
        return b''.join(linea for i, linea in enumerate(self.lineas) if i not in posiciones)


def perfil(c):
    objeto = str(c.datos.get('1.3.6.1.2.1.1.2.0', ''))
    if objeto.startswith('1.3.6.1.4.1.34774.'):
        return 'huawei_storage'
    if objeto.startswith('1.3.6.1.4.1.47196.'):
        return 'switch'
    if objeto.startswith('1.3.6.1.4.1.2011.'):
        return 'huawei_chasis' if any(o.startswith(E + '.') for o in c.datos) else 'huawei_servidor'
    if objeto.startswith(H + '.'):
        if c.filas(H + '.8.2.2.1.1'):
            return 'hpe_storage'
        if c.filas(H + '.22.2.3.1.1.1'):
            return 'hpe_chasis'
        return 'hpe_servidor'
    raise ValueError('Captura sin un perfil HPE, Huawei o Aruba admitido.')


def normalizar(c):
    from etl.normalizacion.servidor import normalizar_servidor
    from etl.normalizacion.storage import normalizar_storage
    from etl.normalizacion.chasis import normalizar_chasis
    from etl.normalizacion.switch import normalizar_switch
    p = perfil(c)
    fecha = datetime(2000, 1, 1, tzinfo=timezone.utc)
    if p == 'switch':
        return normalizar_switch(c.datos, fecha_actualizacion=fecha)
    fn = normalizar_storage if p.endswith('storage') else normalizar_chasis if p.endswith('chasis') else normalizar_servidor
    opciones = {'tipo': 'AUTO'} if p.endswith('servidor') else {}
    return fn(c.datos, fabricante='Huawei' if p.startswith('huawei') else 'HPE',
              fecha_actualizacion=fecha, **opciones)


@dataclass
class Pieza:
    tipo: str
    indice: str
    modelo: str
    serie: str
    oids: set = field(default_factory=set)


def texto(v):
    return v.decode('utf-8', errors='replace') if isinstance(v, bytes) else str(v) if v is not None else ''


def catalogo(c):
    """Cada conjunto incluye solo filas de la pieza, nunca raíces del activo."""
    p, ficha = perfil(c), normalizar(c)
    piezas = {t: [] for t in TIPOS}
    def tabla(tipo, raiz, modelo=None, serie=None, columnas=None):
        resultado = []
        for idx, fila in c.filas(raiz, columnas).items():
            pieza = Pieza(tipo, idx, texto(fila.get(modelo)), texto(fila.get(serie)),
                          c.oids(raiz, {idx}, columnas))
            piezas[tipo].append(pieza)
            resultado.append(pieza)
        return resultado
    def interfaces(indices):
        return c.oids(IF, indices) | c.oids(IFX, indices)
    def por_mac(valor):
        return {idx for idx, f in c.filas(IF).items() if valor and f.get(6) == valor}
    def hpe_comun():
        for pieza in tabla('cpu', H+'.1.2.2.1.1', 3, 16):
            indices = {idx for idx in c.filas(H+'.1.2.2.3.1') if idx.split('.')[0] == pieza.indice.split('.')[0]}
            pieza.oids |= c.oids(H+'.1.2.2.3.1', indices)
        tabla('ram', H+'.2.2.4.5.1', 8, 10)
        if ficha.get('servidor', {}).get('tipo') != 'BLADE':
            tabla('fuente_poder', H+'.6.2.9.3.1', 10, 11)
            tabla('ventilador', H+'.6.2.6.7.1')
            raiz = H+'.18.2.3.1.1'
            grupos = {}
            for idx, fila in c.filas(raiz).items():
                slot = fila.get(5)
                grupo = f'slot:{slot}' if slot is not None and slot >= 0 else 'indice:'+idx
                grupos.setdefault(grupo, []).append((idx, fila))
            for grupo, filas in grupos.items():
                indices = {i for i, _ in filas}
                pn = next((f.get(32) for _, f in filas if f.get(32)), None)
                entidades = {idx for idx, f in c.filas(ENT).items() if f.get(5) == 9 and
                             pn and texto(f.get(13)).upper() == texto(pn).upper()}
                # ENTITY-MIB solo se borra si la parte pertenece a una única NIC.
                if any(g != grupo and any(f.get(32) == pn for _, f in fs) for g, fs in grupos.items()):
                    entidades = set()
                serie = next((f.get(11) for idx, f in c.filas(ENT).items() if idx in entidades), '')
                oids = c.oids(raiz, indices) | c.oids(ENT, entidades)
                for _, fila in filas:
                    oids |= interfaces(por_mac(fila.get(4)))
                piezas['tarjeta_red'].append(Pieza('tarjeta_red', grupo, texto(filas[0][1].get(39)), texto(serie), oids))
    if p in ('hpe_servidor', 'hpe_storage', 'switch'):
        if p == 'switch':
            tabla('cpu', H+'.1.2.2.1.1', 3, 16)
            tabla('ram', H+'.2.2.4.5.1', 8, 10)
            tabla('fuente_poder', A+'.11.2.1.1', 5, 6)
            tabla('ventilador', A+'.11.5.1.1', 6, 7)
        else:
            hpe_comun()
            if p == 'hpe_servidor':
                tabla('disco', H+'.3.2.5.1.1', 3, 51)
                control = tabla('controladora_raid', H+'.3.2.2.1.1', 2, 15)
                logicas = H+'.3.2.3.1.1'
            else:
                tabla('disco', H+'.16.2.5.1.1', 3, 43)
                control = tabla('controladora_raid', H+'.16.2.2.1.1', 3, 9)
                logicas = H+'.16.2.3.1.1'
                for pieza in tabla('tarjeta_red', H+'.16.2.7.1.1', 3, 10):
                    f = c.filas(H+'.16.2.7.1.1')[pieza.indice]
                    indices = {idx for idx, port in c.filas(IF).items() if port.get(3) == 56 and
                               texto(c.datos.get(f'{IFX}.1.{idx}')).casefold() == ('FC'+texto(f.get(2))).casefold()}
                    pieza.oids |= interfaces(indices)
            for pieza in control:
                indices = {idx for idx in c.filas(logicas) if idx.split('.')[0] == pieza.indice.split('.')[0]}
                pieza.oids |= c.oids(logicas, indices)
    elif p == 'hpe_chasis':
        tabla('fuente_poder', H+'.22.2.5.1.1.1', 6, 5)
        tabla('ventilador', H+'.22.2.3.1.3.1', 6)
        for n, pieza in enumerate(tabla('tarjeta_red', H+'.22.2.6.1.1.1', 6, 7)):
            if n == 0:
                indices = {idx for idx, f in c.filas(IFX, {1}).items() if re.fullmatch(r'[Xd]\d+', texto(f.get(1)))}
                pieza.oids |= interfaces(indices)
    elif p == 'huawei_servidor':
        tabla('cpu', I+'.15.50.1', 4)
        tabla('ram', I+'.16.50.1', 10, 12)
        tabla('disco', I+'.18.50.1', 8, 7)
        for pieza in tabla('controladora_raid', I+'.36.50.1', 3):
            indices = {idx for idx in c.filas(I+'.37.50.1') if idx.split('.')[0] == pieza.indice.split('.')[0]}
            pieza.oids |= c.oids(I+'.37.50.1', indices)
        if ficha['servidor']['tipo'] != 'BLADE':
            tabla('fuente_poder', I+'.6.50.1', 4, 15)
            tabla('ventilador', I+'.8.50.1', 7)
        indices_if = sorted(set(c.filas(IF, {6, 8})) | set(c.filas(IFX, {1, 15})), key=orden)
        for pos, pieza in enumerate(tabla('tarjeta_red', I+'.25.50.1', 5, 7)):
            if pos < len(indices_if):
                pieza.oids |= interfaces({indices_if[pos]})
    elif p == 'huawei_chasis':
        tabla('ventilador', E+'.5.2001.1', 4)
        energia, gestion = E+'.6.2001.1', E+'.100.4.2001.1'
        for idx in sorted(set(c.filas(energia)) | set(c.filas(gestion)), key=orden):
            f = c.filas(energia).get(idx, {})
            piezas['fuente_poder'].append(Pieza('fuente_poder', idx, texto(f.get(7)), '',
                c.oids(energia, {idx}) | c.oids(gestion, {idx})))
        indices = set(c.filas(IF, {6, 8})) | set(c.filas(IFX, {1, 15}))
        if indices:
            piezas['tarjeta_red'].append(Pieza('tarjeta_red', 'uplinks', 'MM910 uplink', '', interfaces(indices)))
    elif p == 'huawei_storage':
        tabla('disco', D+'.23.5.1.1', 12, 15)
        for pieza in tabla('controladora_raid', D+'.23.5.2.1', 17):
            # CPU y memoria de Dorado pertenecen a esa controladora física.
            pieza.oids |= c.oids(D+'.19.8.12.1', {pieza.indice}, {14, 15})
        tabla('cpu', D+'.19.8.12.1', 15, columnas={15})
        tabla('ram', D+'.19.8.12.1', columnas={14})
        tabla('fuente_poder', D+'.23.5.3.1', 7, 10)
        for pieza in tabla('ventilador', D+'.23.5.4.1', 6):
            indices = {idx for idx, f in c.filas(ENT, {7}).items() if f.get(7) == f'Fan {pieza.indice} RPM'}
            pieza.oids |= c.oids(ENT, indices) | c.oids(SENSOR, indices)
        fc = D+'.19.8.7.1'
        if c.filas(fc):
            indices = {idx for idx, f in c.filas(IF).items() if f.get(3) == 56}
            piezas['tarjeta_red'].append(Pieza('tarjeta_red', 'fc', 'Fibre Channel', '',
                c.oids(fc, set(c.filas(fc))) | interfaces(indices)))
    # No se presentan como retirables tablas que el perfil no incorpora al inventario.
    return {t: ps if ficha['componentes'].get(t) else [] for t, ps in piezas.items()}


def preparar_retiro(contenido, tipo, numeros=None, todos=False):
    c = Captura(contenido)
    lista = catalogo(c)[tipo]
    if not lista:
        raise ValueError(f'El equipo no tiene componentes retirables de tipo {tipo}.')
    numeros = list(range(1, len(lista)+1)) if todos else numeros or []
    if not numeros or len(set(numeros)) != len(numeros) or any(n < 1 or n > len(lista) for n in numeros):
        raise ValueError(f'Indica números únicos entre 1 y {len(lista)}, o --todos.')
    elegidas = [lista[n-1] for n in numeros]
    oids = set().union(*(p.oids for p in elegidas))
    nuevo = c.sin(oids)
    antes = normalizar(c)
    try:
        despues = normalizar(Captura(nuevo))
    except Exception as exc:
        raise ValueError('Retiro cancelado: el perfil ETL rechazaría la captura resultante. '+str(exc)) from None
    if antes['activo'] != despues['activo']:
        raise ValueError('Retiro cancelado: cambiaría la identidad o los sensores generales del activo.')
    if len(antes['componentes'][tipo])-len(despues['componentes'][tipo]) != len(elegidas):
        raise ValueError('Retiro cancelado: los OID no identifican inequívocamente las piezas seleccionadas.')
    return nuevo, elegidas, sorted(oids, key=orden)


def sha(contenido):
    return hashlib.sha256(contenido).hexdigest()


def ruta_equipo(datos, equipo):
    if not re.fullmatch(r'[\w-]+', equipo, re.ASCII):
        raise ValueError('El equipo debe ser el nombre de su carpeta, sin rutas ni separadores.')
    datos = Path(datos).resolve()
    ruta = (datos/equipo/'public.snmprec').resolve()
    if ruta.parent.parent != datos or not ruta.is_file():
        raise ValueError('No existe data/'+equipo+'/public.snmprec dentro de la carpeta de datos.')
    return ruta


def escribir_atomico(ruta, contenido):
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(dir=ruta.parent, prefix='.snmprec-', delete=False) as f:
            temporal = Path(f.name)
            f.write(contenido)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporal, ruta)
    finally:
        if temporal and temporal.exists():
            temporal.unlink()


@contextmanager
def bloqueo(carpeta):
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta/'.bloqueo'
    try:
        fd = os.open(ruta, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError('Ya hay una operación en curso para este equipo.') from None
    try:
        os.close(fd)
        yield
    finally:
        ruta.unlink()


def retirar(ruta, tipo, numeros=None, todos=False, vista_previa=False):
    respaldos = ruta.parent.parent/'.respaldos_componentes'/ruta.parent.name
    with bloqueo(respaldos):
        original = ruta.read_bytes()
        nuevo, piezas, oids = preparar_retiro(original, tipo, numeros, todos)
        antes, despues = normalizar(Captura(original)), normalizar(Captura(nuevo))
        retirados = {t: len(fs)-len(despues['componentes'].get(t, []))
                     for t, fs in antes['componentes'].items()
                     if len(fs) > len(despues['componentes'].get(t, []))}
        detalle = {'equipo': ruta.parent.name, 'tipo': tipo, 'piezas': [p.indice for p in piezas],
                   'componentes_retirados': retirados, 'oids_retirados': len(oids)}
        if vista_previa:
            return {**detalle, 'vista_previa': True}
        nombre = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'_'+uuid.uuid4().hex[:8]
        copia = respaldos/nombre
        copia.mkdir()
        (copia/'original.snmprec').write_bytes(original)
        meta = {**detalle, 'antes': sha(original), 'despues': sha(nuevo), 'oids': oids, 'restaurado': False}
        (copia/'operacion.json').write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')
        if ruta.read_bytes() != original:
            meta['cancelado'] = True
            (copia/'operacion.json').write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')
            raise ValueError('La captura cambió durante la operación; no se sobrescribió.')
        try:
            escribir_atomico(ruta, nuevo)
        except OSError:
            meta['cancelado'] = True
            (copia/'operacion.json').write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')
            raise ValueError('No se pudo sustituir la captura. Si el agente la tiene abierta, usa el lanzador PowerShell con -Reiniciar o detén ese agente antes de editar.') from None
        return {**detalle, 'respaldo': str(copia)}


def restaurar(ruta, vista_previa=False):
    respaldos = ruta.parent.parent/'.respaldos_componentes'/ruta.parent.name
    with bloqueo(respaldos):
        pendientes = []
        for archivo in sorted(respaldos.glob('*/operacion.json'), reverse=True):
            meta = json.loads(archivo.read_text(encoding='utf-8'))
            if not meta['restaurado'] and not meta.get('cancelado'):
                pendientes.append((archivo, meta))
        if not pendientes:
            raise ValueError('No hay retiros pendientes de restaurar para este equipo.')
        archivo, meta = pendientes[0]
        actual = ruta.read_bytes()
        original = (archivo.parent/'original.snmprec').read_bytes()
        if sha(original) != meta['antes']:
            raise ValueError('El respaldo está dañado; no se modificó la captura.')
        if sha(actual) not in (meta['antes'], meta['despues']):
            raise ValueError('La captura tiene cambios posteriores ajenos al script. No se sobrescribieron; revisa el respaldo: '+str(archivo.parent))
        if vista_previa:
            return {'equipo': ruta.parent.name, 'restaurar': meta['tipo'], 'piezas': meta['piezas'], 'vista_previa': True}
        escribir_atomico(ruta, original)
        meta['restaurado'] = True
        escribir_atomico(archivo, json.dumps(meta, indent=2, ensure_ascii=False).encode('utf-8'))
        return {'equipo': ruta.parent.name, 'restaurado': meta['tipo'], 'piezas': meta['piezas']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('accion', choices=['equipos', 'listar', 'retirar', 'restaurar'])
    parser.add_argument('--equipo', help='Carpeta dentro de data, por ejemplo hpe-dl380-01')
    parser.add_argument('--tipo', choices=TIPOS+tuple(ALIASES))
    parser.add_argument('--numero', type=int, nargs='+', help='Número mostrado al listar (desde 1)')
    parser.add_argument('--todos', action='store_true')
    parser.add_argument('--vista-previa', action='store_true')
    parser.add_argument('--datos', type=Path, default=REPO/'data', help='Carpeta de capturas; por defecto data del repositorio')
    args = parser.parse_args()
    try:
        if args.accion == 'equipos':
            print('\n'.join(p.parent.name for p in sorted(args.datos.glob('*/public.snmprec')) if not p.parent.name.startswith('.')))
            return 0
        if not args.equipo:
            parser.error('Indica --equipo.')
        ruta = ruta_equipo(args.datos, args.equipo)
        tipo = ALIASES.get(args.tipo, args.tipo)
        if args.accion == 'listar':
            for t, piezas in catalogo(Captura(ruta.read_bytes())).items():
                if tipo and tipo != t:
                    continue
                print('\n'+t.upper())
                for n, pieza in enumerate(piezas, 1):
                    print(f'  {n}. índice={pieza.indice} | modelo={pieza.modelo or "—"} | serie={pieza.serie or "—"} | OID={len(pieza.oids)}')
                if not piezas:
                    print('  Sin componentes retirables en este perfil.')
            return 0
        if args.accion == 'retirar':
            if not tipo or args.todos == bool(args.numero):
                parser.error('Indica --tipo y elige --numero N [N ...] o --todos.')
            resultado = retirar(ruta, tipo, args.numero, args.todos, args.vista_previa)
        else:
            if args.tipo or args.numero or args.todos:
                parser.error('Restaurar solo necesita --equipo y opcionalmente --vista-previa.')
            resultado = restaurar(ruta, args.vista_previa)
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
        if not args.vista_previa:
            print('Reinicia solo este agente y espera la siguiente iteración ETL. No se escribió en la base de datos.')
        return 0
    except (ValueError, OSError) as exc:
        print('Error: '+str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
