"""API de prueba SNMP y registro inicial de activos mediante el ETL."""
import asyncio
import logging
from contextlib import asynccontextmanager
from time import perf_counter
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from api.dto import (ConexionExitosa, ConexionFallida, ProbarConexionRequest,
                     CrearActivoRequest, ActivoCreado, separar_destino)
from api.seguridad import resolver_destino, verificar_api_key
from etl.config import cargar_configuracion
from etl.snmp_cliente import fallo, probar_conexion, ConexionSNMP, MESSAGES
from etl.ciclo import preparar_registro_activo
from etl.carga import cargar_registro
from etl.registro_conexion import obtener_referencias
from etl.errores import (ErrorExtraccion, PerfilNoSoportado, DatosIncompletos,
                        ActivoDuplicado, BaseNoDisponible, ReferenciaNoEncontrada)

logger = logging.getLogger("etl.conexion")

def crear_app(config=None):
    config = config or cargar_configuracion()

    @asynccontextmanager
    async def lifespan(app):
        app.state.semaforo = asyncio.Semaphore(5)
        yield

    app = FastAPI(title="ETL de infraestructura TI", lifespan=lifespan,
                  docs_url="/docs" if config.api_docs else None, redoc_url=None,
                  openapi_url="/openapi.json" if config.api_docs else None)
    app.state.config = config

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        fields = set(CrearActivoRequest.model_fields) | set(ProbarConexionRequest.model_fields)
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

    @app.post("/api/etl/crear-activo", status_code=201, response_model=ActivoCreado,
              dependencies=[Depends(verificar_api_key)])
    async def crear_activo(body: CrearActivoRequest, request: Request):
        if config.database_url is None:
            raise HTTPException(503, "Falta configurar PostgreSQL para registrar activos.")
        async with request.app.state.semaforo:
            try:
                referencias = await run_in_threadpool(obtener_referencias, config, body.conexion_id, body.cluster_id)
                try:
                    host, puerto = separar_destino(referencias.ip_gestion)
                except ValueError:
                    raise DatosIncompletos("El destino guardado en la conexión es inválido.") from None
                address = await resolver_destino(host, puerto, config.redes_permitidas, config.snmp_timeout)
                conexion = ConexionSNMP(address, puerto, referencias.usuario, referencias.clave, referencias.clave_privacidad,
                    config.snmp_context_name, config.snmp_timeout, config.snmp_retries)
                ficha = await preparar_registro_activo(conexion, config,
                    ip_gestion=referencias.ip_gestion)
                return await run_in_threadpool(cargar_registro, config, ficha, referencias=referencias)
            except HTTPException:
                raise
            except ErrorExtraccion as exc:
                raise HTTPException(504 if exc.tipo == "timeout" else 502,
                    detail={"error_tipo": exc.tipo, "mensaje": MESSAGES[exc.tipo]}) from None
            except TimeoutError:
                raise HTTPException(504, "Tiempo de espera agotado al resolver el destino.") from None
            except OSError:
                raise HTTPException(502, "No se pudo resolver el destino SNMP.") from None
            except (PerfilNoSoportado, DatosIncompletos) as exc:
                raise HTTPException(422, str(exc)) from None
            except ActivoDuplicado as exc:
                raise HTTPException(409, str(exc)) from None
            except ReferenciaNoEncontrada as exc:
                raise HTTPException(404, str(exc)) from None
            except BaseNoDisponible as exc:
                raise HTTPException(503, str(exc)) from None

    return app

app = crear_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=app.state.config.api_host, port=app.state.config.api_port)
