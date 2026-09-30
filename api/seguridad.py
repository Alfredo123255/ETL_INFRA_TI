"""Autenticación de API y resolución de destinos permitidos."""
import asyncio
import hmac
import ipaddress
import socket
from fastapi import Header, HTTPException, Request

async def verificar_api_key(request: Request, x_api_key: str | None = Header(default=None)):
    expected = request.app.state.config.api_key.get_secret_value()
    if x_api_key is None or not hmac.compare_digest(x_api_key.encode(), expected.encode()):
        raise HTTPException(401, "Clave de API ausente o incorrecta.")

async def resolver_destino(host, port, networks, timeout):
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        results = await asyncio.wait_for(asyncio.get_running_loop().getaddrinfo(
            host, port, type=socket.SOCK_DGRAM), timeout=timeout)
        addresses = list(dict.fromkeys(ipaddress.ip_address(r[4][0]) for r in results))
    if not addresses:
        raise OSError("Destino no resoluble")
    if networks and any(not any(a in n for n in networks) for a in addresses):
        raise HTTPException(422, detail=[{"campo": "ip_gestion",
                                         "motivo": "Destino fuera de las redes permitidas."}])
    # Fijar la IP validada evita una segunda resolución que eluda el filtro.
    return str(addresses[0])
