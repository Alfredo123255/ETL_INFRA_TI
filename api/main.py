"""API sin persistencia: únicamente prueba de conexión SNMPv3."""
import asyncio
import logging
from contextlib import asynccontextmanager
from time import perf_counter
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from api.dto import ConexionExitosa, ConexionFallida, ProbarConexionRequest, separar_destino
from api.seguridad import resolver_destino, verificar_api_key
from etl.config import cargar_configuracion
from etl.snmp_cliente import fallo, probar_conexion

logger = logging.getLogger("etl.conexion")

def crear_app(config=None):
    config = config or cargar_configuracion()

    @asynccontextmanager
    async def lifespan(app):
        app.state.semaforo = asyncio.Semaphore(5)
        yield

    app = FastAPI(title="Validación SNMPv3", lifespan=lifespan,
                  docs_url="/docs" if config.api_docs else None, redoc_url=None,
                  openapi_url="/openapi.json" if config.api_docs else None)
    app.state.config = config

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        fields = set(ProbarConexionRequest.model_fields)
        detail = []
        for error in exc.errors():
            name = next((part for part in error["loc"] if part in fields), "cuerpo")
            reason = "Campo obligatorio." if error["type"] == "missing" else "Formato o valor inválido."
            detail.append({"campo": name, "motivo": reason})
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.post("/api/etl/probar-conexion", response_model=ConexionExitosa | ConexionFallida,
              dependencies=[Depends(verificar_api_key)])
    async def probar(body: ProbarConexionRequest, request: Request):
        host, port = separar_destino(body.ip_gestion)
        start = perf_counter()
        async with request.app.state.semaforo:
            try:
                address = await resolver_destino(host, port, config.redes_permitidas, config.snmp_timeout)
                result = await probar_conexion(address, port, body.usuario, body.clave,
                                               body.clave_privacidad, config)
            except HTTPException:
                raise
            except TimeoutError:
                result = fallo("timeout", 0)
            except OSError:
                result = fallo("otro", 0)
        result["milisegundos"] = round((perf_counter() - start) * 1000)
        logger.info("host=%s puerto=%s usuario=%s resultado=%s milisegundos=%s",
                    host, port, body.usuario, result["ok"], result["milisegundos"])
        return result

    return app

app = crear_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=app.state.config.api_host, port=app.state.config.api_port)
