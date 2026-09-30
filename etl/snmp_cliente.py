"""Prueba SNMPv3 SHA/AES; un motor por petición, cerrado incluso al cancelar."""
from time import perf_counter
from dataclasses import dataclass, field
from pydantic import SecretStr
from pysnmp.hlapi.asyncio import (
    ContextData, ObjectIdentity, ObjectType, SnmpEngine, UdpTransportTarget,
    Udp6TransportTarget, UsmUserData, getCmd, nextCmd, bulkCmd,
    usmAesCfb128Protocol, usmHMACSHAAuthProtocol,
)
from pysnmp.proto import rfc1905
from etl.detector import detectar_tipo, fabricante
from etl.errores import ErrorExtraccion

SYSTEM_OIDS = ("1.3.6.1.2.1.1.1.0", "1.3.6.1.2.1.1.2.0", "1.3.6.1.2.1.1.5.0")
MESSAGES = {
    "timeout": "El equipo no respondió dentro del tiempo de espera.",
    "usuario_desconocido": "El equipo no reconoce el usuario SNMPv3.",
    "clave_autenticacion": "No se pudo autenticar la solicitud SNMPv3.",
    "clave_privacidad": "No se pudo descifrar la comunicación SNMPv3.",
    "nivel_seguridad": "El equipo no admite el nivel de seguridad solicitado.",
    "otro": "No se pudo completar la consulta SNMPv3.",
}

def mapear_error(error):
    text = str(error).lower()
    patterns = {
        "timeout": ("timeout", "timed out", "no snmp response"),
        "usuario_desconocido": ("unknown usm user", "unknownusername", "unknown user"),
        "clave_autenticacion": ("wrong snmp pdu digest", "wrongdigest", "authenticator mismatched",
                               "authenticationfailure", "authentication failure"),
        "clave_privacidad": ("ciphering services", "decryptionerror", "decryption error"),
        "nivel_seguridad": ("unsupported snmp security level", "unsupportedsecuritylevel"),
    }
    for kind, phrases in patterns.items():
        if any(s in text for s in phrases):
            return kind
    return "otro"

def fallo(tipo, milliseconds):
    return dict(ok=False, error_tipo=tipo, mensaje=MESSAGES[tipo], milisegundos=milliseconds)

def valor_ausente(value):
    return isinstance(value, (rfc1905.NoSuchObject, rfc1905.NoSuchInstance, rfc1905.EndOfMibView))

async def probar_conexion(host, puerto, usuario, clave, clave_privacidad, config):
    start = perf_counter()
    elapsed = lambda: round((perf_counter() - start) * 1000)
    engine = SnmpEngine()
    try:
        auth = UsmUserData(usuario, authKey=clave.get_secret_value(),
                           privKey=(clave_privacidad if clave_privacidad is not None else clave).get_secret_value(),
                           authProtocol=usmHMACSHAAuthProtocol, privProtocol=usmAesCfb128Protocol)
        transport_class = Udp6TransportTarget if ":" in host else UdpTransportTarget
        target = transport_class((host, puerto), timeout=config.snmp_timeout, retries=config.snmp_retries)
        context = ContextData(contextName=config.snmp_context_name)
        error, status, _, bindings = await getCmd(
            engine, auth, target, context,
            *(ObjectType(ObjectIdentity(oid)) for oid in SYSTEM_OIDS), lookupMib=False)
        if error or status:
            return fallo(mapear_error(error or status), elapsed())
        if len(bindings) != 3 or any(valor_ausente(v) for _, v in bindings):
            return fallo("otro", elapsed())
        description, object_id, name = [v.prettyPrint() for _, v in bindings]

        async def exists(root):
            err, stat, _, rows = await nextCmd(
                engine, auth, target, context, ObjectType(ObjectIdentity(root)), lookupMib=False)
            if err or stat:
                raise RuntimeError("Detección no disponible")
            if not rows or not rows[0]:
                return False
            oid, value = rows[0][0]
            prefix = tuple(map(int, root.split(".")))
            actual = tuple(oid)
            return not valor_ausente(value) and len(actual) > len(prefix) and actual[:len(prefix)] == prefix

        kind = await detectar_tipo(object_id, exists)
        return dict(ok=True, descripcion=description, sys_object_id=object_id,
                    sys_name=name, fabricante=fabricante(object_id), tipo_detectado=kind,
                    milisegundos=elapsed())
    except Exception as exc:
        return fallo(mapear_error(exc), elapsed())
    finally:
        engine.closeDispatcher()


@dataclass(frozen=True)
class ConexionSNMP:
    host: str
    puerto: int
    usuario: str = field(repr=False)
    clave: SecretStr = field(repr=False)
    clave_privacidad: SecretStr | None = field(default=None, repr=False)
    contexto: str = ""
    timeout: float = 3
    reintentos: int = 1


class SesionSNMP:
    """Motor reutilizable para un ciclo; usar dentro del bucle asíncrono activo."""

    def __init__(self, conexion):
        self.conexion = conexion

    def __enter__(self):
        self.motor = SnmpEngine()
        try:
            c = self.conexion
            self.auth = UsmUserData(c.usuario, authKey=c.clave.get_secret_value(),
                privKey=(c.clave_privacidad or c.clave).get_secret_value(),
                authProtocol=usmHMACSHAAuthProtocol, privProtocol=usmAesCfb128Protocol)
            transport = Udp6TransportTarget if ":" in c.host else UdpTransportTarget
            self.destino = transport((c.host, c.puerto), timeout=c.timeout, retries=c.reintentos)
            self.contexto = ContextData(contextName=c.contexto)
        except Exception:
            self.motor.closeDispatcher()
            raise ErrorExtraccion() from None
        return self

    def __exit__(self, *exc):
        self.motor.closeDispatcher()

    async def _consultar(self, comando, *args):
        try:
            error, status, _, valores = await comando(
                self.motor, self.auth, self.destino, self.contexto, *args, lookupMib=False)
        except Exception as exc:
            raise ErrorExtraccion(mapear_error(exc)) from None
        if error or status:
            raise ErrorExtraccion(mapear_error(error or status))
        return valores

    async def obtener(self, oids):
        resultado = {}
        for inicio in range(0, len(oids), 12):
            lote = oids[inicio:inicio + 12]
            valores = await self._consultar(getCmd,
                *(ObjectType(ObjectIdentity(oid)) for oid in lote))
            if len(valores) != len(lote):
                raise ErrorExtraccion()
            for esperado, (oid, valor) in zip(lote, valores):
                if str(oid) != esperado:
                    raise ErrorExtraccion()
                if not valor_ausente(valor):
                    resultado[str(oid)] = valor
        return resultado

    async def recorrer(self, raiz, limite=10000):
        """GETBULK acotado al subárbol; rechaza OID repetidos o decrecientes."""
        prefijo = tuple(map(int, raiz.split(".")))
        anterior = prefijo
        resultado = {}
        while True:
            filas = await self._consultar(bulkCmd, 0, 25,
                ObjectType(ObjectIdentity(".".join(map(str, anterior)))))
            if not filas:
                raise ErrorExtraccion()
            for fila in filas:
                if len(fila) != 1:
                    raise ErrorExtraccion()
                oid, valor = fila[0]
                actual = tuple(oid)
                if valor_ausente(valor) or actual[:len(prefijo)] != prefijo:
                    return resultado
                if actual <= anterior:
                    raise ErrorExtraccion()
                resultado[str(oid)] = valor
                if len(resultado) > limite:
                    raise ErrorExtraccion()
                anterior = actual
