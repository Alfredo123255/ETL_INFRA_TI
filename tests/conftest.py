import os
# Solo para la importación de app durante pytest; nunca se usa fuera de las pruebas.
os.environ.setdefault("ETL_API_KEY", "api-key-exclusiva-de-tests")
