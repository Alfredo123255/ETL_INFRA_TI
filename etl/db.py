"""
Administra la conexión a la base de datos PostgreSQL con psycopg2, sin ORM.

Regla de este módulo (y de todo el ETL): el esquema de la base de datos pertenece a otro módulo
del sistema y es transversal a toda la plataforma. El ETL nunca crea, modifica ni elimina
tablas, columnas, índices ni restricciones — solo abre conexiones y ejecuta lecturas y
escrituras de filas sobre tablas que ya existen. Ninguna sentencia DDL (CREATE, ALTER, DROP)
debe aparecer en este módulo ni en ningún otro de etl/.

Funciones:
- obtener_conexion() -> psycopg2.extensions.connection: abre una conexión nueva usando los datos
  de config.Configuracion.
- conexion_bd(): context manager que entrega una conexión abierta y la cierra (con commit o
  rollback según corresponda) al salir del bloque `with`.
- cerrar_conexion(conexion) -> None: cierra explícitamente una conexión abierta.

Dependencias: config.py (credenciales de conexión). Lo usan repositorio.py y carga.py para
obtener la conexión con la que ejecutan sus consultas.
"""
