-- Acceso al sistema. No contiene usuarios, contraseñas ni hashes.
BEGIN;
CREATE TABLE IF NOT EXISTS public.rol (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR NOT NULL UNIQUE,
    ver_inventario BOOLEAN NOT NULL DEFAULT false,
    gestionar_conexiones BOOLEAN NOT NULL DEFAULT false,
    editar_ciclo_vida BOOLEAN NOT NULL DEFAULT false,
    gestionar_mantenimiento BOOLEAN NOT NULL DEFAULT false,
    dar_baja BOOLEAN NOT NULL DEFAULT false,
    configurar_umbrales BOOLEAN NOT NULL DEFAULT false,
    gestionar_ubicaciones BOOLEAN NOT NULL DEFAULT false,
    exportar BOOLEAN NOT NULL DEFAULT false,
    administrar_usuarios BOOLEAN NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS public.usuario (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    correo VARCHAR NOT NULL UNIQUE,
    contrasena_hash VARCHAR NOT NULL,
    nombre VARCHAR NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT true,
    rol_id INTEGER NOT NULL REFERENCES public.rol(id),
    fecha_creacion TIMESTAMP NOT NULL DEFAULT NOW()
);
INSERT INTO public.rol (nombre, ver_inventario, gestionar_conexiones, editar_ciclo_vida,
    gestionar_mantenimiento, dar_baja, configurar_umbrales, gestionar_ubicaciones,
    exportar, administrar_usuarios)
VALUES
    ('Administrador', true, true, true, true, true, true, true, true, true),
    ('Operador', true, true, true, true, true, false, true, true, false),
    ('Consulta', true, false, false, false, false, false, false, true, false)
ON CONFLICT (nombre) DO NOTHING;
COMMIT;
