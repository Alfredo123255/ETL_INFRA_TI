"""Contrato de entrada/salida y validación sintáctica."""
import ipaddress
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, SecretStr, Field, field_validator

def separar_destino(value: str) -> tuple[str, int]:
    if not value or value != value.strip():
        raise ValueError("Destino inválido")
    port = "161"
    if value.startswith("["):
        match = re.fullmatch(r"\[([^\]]+)\](?::([0-9]+))?", value)
        if not match:
            raise ValueError("Destino IPv6 inválido")
        host, explicit_port = match.groups()
        port = explicit_port or port
        if "%" in host or ipaddress.ip_address(host).version != 6:
            raise ValueError("Dirección IPv6 inválida")
    elif value.count(":") > 1:
        host = value
        if "%" in host or ipaddress.ip_address(host).version != 6:
            raise ValueError("Dirección IPv6 inválida")
    else:
        host, sep, explicit_port = value.partition(":")
        if sep:
            port = explicit_port
        try:
            ipaddress.ip_address(host)
        except ValueError:
            labels = host.rstrip(".").split(".")
            if (len(host) > 253 or re.fullmatch(r"[0-9.]+", host)
                or not all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", s)
                           for s in labels)):
                raise ValueError("IP o nombre de host inválido") from None
    if not re.fullmatch(r"[0-9]{1,5}", port) or not 1 <= int(port) <= 65535:
        raise ValueError("Puerto inválido")
    return host, int(port)

class ProbarConexionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    ip_gestion: str
    usuario: str
    clave: SecretStr
    clave_privacidad: SecretStr | None = None

    @field_validator("ip_gestion")
    @classmethod
    def destino_valido(cls, value):
        separar_destino(value)
        return value

    @field_validator("usuario")
    @classmethod
    def usuario_valido(cls, value):
        if not value.strip() or len(value.encode("utf-8")) > 32 or any(ord(c) < 32 for c in value):
            raise ValueError("Usuario inválido")
        return value

    @field_validator("clave", "clave_privacidad")
    @classmethod
    def clave_valida(cls, value):
        if value is not None and not value.get_secret_value().strip():
            raise ValueError("La clave no puede estar vacía")
        return value

class ConexionExitosa(BaseModel):
    ok: Literal[True] = True
    descripcion: str
    sys_object_id: str
    sys_name: str
    fabricante: str | None
    tipo_detectado: Literal["SERVIDOR", "CHASIS", "STORAGE", "SWITCH", "DESCONOCIDO"]
    milisegundos: int

class ConexionFallida(BaseModel):
    ok: Literal[False] = False
    error_tipo: Literal["timeout", "usuario_desconocido", "clave_autenticacion",
                        "clave_privacidad", "nivel_seguridad", "otro"]
    mensaje: str
    milisegundos: int


class CrearActivoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    conexion_id: int = Field(gt=0, strict=True)
    cluster_id: str = Field(min_length=1, max_length=100)

    @field_validator("cluster_id")
    @classmethod
    def cluster_valido(cls, value):
        if not value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError("Identificador de clúster inválido")
        return value.strip()


class ActivoCreado(BaseModel):
    ok: Literal[True] = True
    activo_id: int
    numero_serie: str
    hostname: str
    fabricante: str
    tipo_activo: Literal["SERVIDOR", "SWITCH", "STORAGE", "CHASIS"]
    estado_operativo: Literal["Encendido", "Apagado", "Degradado", "Baja"]
    modelo: str
    ubicacion: str
    componentes: dict[str, int]
    metricas_guardadas: int
    conexion_id: int
    cluster_id: str
