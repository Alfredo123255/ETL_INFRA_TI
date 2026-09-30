"""Datos leídos de los README, sin duplicar credenciales en las pruebas."""
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
EXPECTED={
 "hpe-dl380-01":"SERVIDOR","hpe-dl360-01":"SERVIDOR",
 "hpe-bl460c-01":"SERVIDOR","hpe-bl460c-02":"SERVIDOR",
 "hpe-c7000-01":"CHASIS","hpe-storage-fc-01":"STORAGE",
 "hpe-storage-fc-02":"STORAGE","aruba-cx-sw01":"SWITCH",
}

def leer_agente(name):
    text=(ROOT/"data"/name/"README.md").read_text(encoding="utf-8")
    def option(key):
        match=re.search(r"--"+re.escape(key)+r"=(?:'([^']*)'|([^\s\\]+))",text)
        if not match:
            raise ValueError("Falta parámetro en README: "+key)
        return match.group(1) or match.group(2)
    return dict(ip_gestion=option("agent-udpv4-endpoint"),usuario=option("v3-user"),
                clave=option("v3-auth-key"),clave_privacidad=option("v3-priv-key"))
