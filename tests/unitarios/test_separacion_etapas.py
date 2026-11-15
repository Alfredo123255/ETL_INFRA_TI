"""Regresión de responsabilidades: monitoreo coordina y el repositorio ejecuta SQL."""
import ast
import inspect
import re
from pathlib import Path
from etl import monitoreo, repositorio_monitoreo


def test_monitoreo_no_ejecuta_ni_contiene_sql():
    source = inspect.getsource(monitoreo)
    assert not re.search(r"execute\(|SELECT |UPDATE |DELETE |INSERT ", source)
    tree = ast.parse(source)
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr in ("execute", "executemany", "fetchone", "fetchall")
                   for n in ast.walk(tree))


def test_repositorio_no_abre_conexiones_ni_confirma_transacciones():
    tree = ast.parse(inspect.getsource(repositorio_monitoreo))
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            name = n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id if isinstance(n.func, ast.Name) else ""
            assert name not in {"connect", "cursor", "commit", "rollback", "conexion_bd", "obtener_conexion"}
        if isinstance(n, ast.ImportFrom):
            assert n.module not in {"etl.monitoreo", "etl.alertas", "etl.db"}


def test_funciones_publicas_del_repositorio_reciben_el_cursor():
    for name, function in inspect.getmembers(repositorio_monitoreo, inspect.isfunction):
        if function.__module__ == repositorio_monitoreo.__name__ and not name.startswith("_"):
            assert next(iter(inspect.signature(function).parameters)) == "cur", name
