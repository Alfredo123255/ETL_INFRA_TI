"""Configuración de la API de prueba, sin base de datos."""
import math
import os
from dataclasses import dataclass, field
from ipaddress import ip_network
from pathlib import Path
from dotenv import load_dotenv
from pydantic import SecretStr

@dataclass(frozen=True)
class Configuracion:
    api_key: SecretStr = field(repr=False)
    snmp_context_name: str = ""
    snmp_timeout: float = 3
    snmp_retries: int = 1
    api_host: str = "127.0.0.1"
    api_port: int = 8001
    api_docs: bool = False
    redes_permitidas: tuple = ()

def cargar_configuracion():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    key = os.getenv("ETL_API_KEY", "")
    if not key.strip():
        raise RuntimeError("ETL_API_KEY es obligatoria; la API no puede arrancar.")
    try:
        timeout = float(os.getenv("SNMP_TIMEOUT", "3"))
        retries = int(os.getenv("SNMP_RETRIES", "1"))
        port = int(os.getenv("API_PORT", "8001"))
        networks = tuple(ip_network(s.strip()) for s in
                         os.getenv("SNMP_REDES_PERMITIDAS", "").split(",") if s.strip())
        if not math.isfinite(timeout) or timeout <= 0 or retries < 0 or not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise RuntimeError("Configuración de tiempos, puerto o redes inválida.") from None
    return Configuracion(SecretStr(key), os.getenv("SNMP_CONTEXT_NAME", ""), timeout,
                         retries, os.getenv("API_HOST", "127.0.0.1"), port,
                         os.getenv("API_DOCS", "0") == "1", networks)
