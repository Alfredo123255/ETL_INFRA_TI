# syntax=docker/dockerfile:1
FROM python:3.13-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    API_HOST=0.0.0.0 API_PORT=8001 API_DOCS=0
WORKDIR /app
COPY requirements-runtime.txt requirements-constraints.txt ./
RUN pip install --no-cache-dir -r requirements-runtime.txt \
    && groupadd --gid 10001 infra \
    && useradd --uid 10001 --gid 10001 --no-create-home infra
COPY --chown=10001:10001 api ./api
COPY --chown=10001:10001 etl ./etl
COPY --chown=10001:10001 docker/entrypoint.py ./docker/entrypoint.py
COPY --chown=10001:10001 docker/preflight.py ./docker/preflight.py
USER 10001:10001
ENTRYPOINT ["python", "/app/docker/entrypoint.py"]

FROM runtime AS fastapi
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/healthz', timeout=3).read()"
CMD ["python", "-B", "-m", "api.main"]

FROM runtime AS periodico
# El programador es un proceso continuo. Docker reinicia el contenedor si termina.
CMD ["python", "-B", "-m", "etl.programador"]
