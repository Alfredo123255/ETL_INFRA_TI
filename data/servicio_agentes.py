"""Supervisa los 17 simuladores; --verificar realiza solo lecturas SNMP."""
import argparse
import asyncio
import json
from pathlib import Path
import signal
import subprocess
import sys
import time

DATA = Path(__file__).resolve().parent


def cargar_agentes():
    agentes = json.loads((DATA / 'agentes-docker.json').read_text(encoding='utf-8'))
    destinos = {(a['host'], a['puerto']) for a in agentes}
    if len(agentes) != 17 or len(destinos) != 17:
        raise RuntimeError('Se requieren los 17 destinos únicos del laboratorio.')
    for agente in agentes:
        if not (DATA / agente['nombre'] / 'public.snmprec').is_file():
            raise RuntimeError('Faltan datos del agente ' + agente['nombre'])
    return agentes


def comando(agente):
    return [sys.executable, '-B', str(DATA / 'run_responder.py'),
            '--v3-engine-id=' + agente['engine_id'],
            '--v3-user=' + agente['usuario'],
            '--v3-auth-key=' + agente['auth_key'], '--v3-auth-proto=SHA',
            '--v3-priv-key=' + agente['priv_key'], '--v3-priv-proto=AES',
            f"--agent-udpv4-endpoint={agente['host']}:{agente['puerto']}",
            '--data-dir=' + str(DATA / agente['nombre']),
            '--cache-dir=/tmp/snmpsim-cache/' + agente['nombre']]


async def verificar(agentes):
    from pysnmp.hlapi.asyncio import (ContextData, ObjectIdentity, ObjectType,
        SnmpEngine, UdpTransportTarget, UsmUserData, getCmd,
        usmAesCfb128Protocol, usmHMACSHAAuthProtocol)

    async def consultar(agente):
        motor = SnmpEngine()
        try:
            error, estado, _, valores = await getCmd(motor,
                UsmUserData(agente['usuario'], agente['auth_key'], agente['priv_key'],
                            authProtocol=usmHMACSHAAuthProtocol,
                            privProtocol=usmAesCfb128Protocol),
                UdpTransportTarget((agente['host'], agente['puerto']), timeout=3, retries=1),
                ContextData(contextName='public'),
                ObjectType(ObjectIdentity('1.3.6.1.2.1.1.1.0')), lookupMib=False)
            return not error and not estado and bool(valores)
        except Exception:
            return False
        finally:
            motor.closeDispatcher()

    resultados = await asyncio.gather(*(consultar(agente) for agente in agentes))
    fallidos = [a['nombre'] for a, ok in zip(agentes, resultados) if not ok]
    print(json.dumps({'agentes': len(agentes), 'responden': sum(resultados), 'fallidos': fallidos}))
    return 1 if fallidos else 0


def supervisar(agentes):
    procesos = []
    detener = False

    def terminar(_signal, _frame):
        nonlocal detener
        detener = True

    signal.signal(signal.SIGTERM, terminar)
    signal.signal(signal.SIGINT, terminar)
    try:
        for agente in agentes:
            procesos.append((agente['nombre'], subprocess.Popen(comando(agente))))
        while not detener:
            for nombre, proceso in procesos:
                if proceso.poll() is not None:
                    print('Se detuvo el simulador ' + nombre, file=sys.stderr, flush=True)
                    return 1
            time.sleep(1)
        return 0
    finally:
        for _, proceso in procesos:
            if proceso.poll() is None:
                proceso.terminate()
        limite = time.monotonic() + 10
        for _, proceso in procesos:
            try:
                proceso.wait(timeout=max(0.1, limite - time.monotonic()))
            except subprocess.TimeoutExpired:
                proceso.kill()
                proceso.wait()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verificar', action='store_true')
    args = parser.parse_args()
    agentes = cargar_agentes()
    return asyncio.run(verificar(agentes)) if args.verificar else supervisar(agentes)


if __name__ == '__main__':
    raise SystemExit(main())
