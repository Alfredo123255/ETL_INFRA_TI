"""Arranca los ocho agentes de data/ sin abrir ventanas adicionales (Windows)."""
import os
from pathlib import Path
import runpy
import socket
import subprocess
import sys
import snmpsim

ROOT=Path(__file__).resolve().parents[1]
AGENTS=runpy.run_path(str(ROOT/'data/verify_agents.py'))['AGENTS']
ENGINE_IDS={
    'hpe-dl380-01':'8000000001444c333830',
    'hpe-dl360-01':'8000000001444c333630',
    'hpe-c7000-01':'80000000014337303030',
    'hpe-bl460c-01':'8000000001424c433031',
    'hpe-bl460c-02':'8000000001424c433032',
    'aruba-cx-sw01':'800000000153573031',
    'hpe-storage-fc-01':'800000000153543031',
    'hpe-storage-fc-02':'800000000153543032',
}
LOGS=ROOT/'logs'/'agentes'


def puerto_ocupado(host,port):
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        try:
            sock.bind((host,port))
            return False
        except OSError:
            return True


def main():
    for agent in AGENTS:
        name=agent['nombre']
        host,port=agent['host'],agent['puerto']
        if puerto_ocupado(host,port):
            print(f'{name}: {host}:{port} ya está ocupado; comprueba el agente con data/verify_agents.py')
            continue
        LOGS.mkdir(parents=True,exist_ok=True)
        cache=LOGS/name/'cache'
        cache.mkdir(parents=True,exist_ok=True)
        command=[sys.executable,'-B',str(ROOT/'data/run_responder.py'),
            '--v3-engine-id='+ENGINE_IDS[name],
            '--v3-user='+agent['usuario'],
            '--v3-auth-key='+agent['auth_key'],'--v3-auth-proto=SHA',
            '--v3-priv-key='+agent['priv_key'],'--v3-priv-proto=AES',
            f'--agent-udpv4-endpoint={host}:{port}',
            '--data-dir='+str(ROOT/'data'/name),
            '--cache-dir='+str(cache),
            '--variation-modules-dir='+str(Path(snmpsim.__file__).parent/'variation')]
        flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
        with (LOGS/(name+'.log')).open('a',encoding='utf-8') as log:
            process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=log,
                                     creationflags=flags)
        print(f'{name}: iniciado en {host}:{port} (PID {process.pid})')
    print('Verificación: python data/verify_agents.py')

if __name__=='__main__':
    main()
