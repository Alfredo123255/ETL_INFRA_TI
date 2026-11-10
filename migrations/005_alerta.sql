-- Crear el registro persistente de alertas en una instalacion existente.
BEGIN;

CREATE TABLE public.alerta (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    activo_id INTEGER NOT NULL
        REFERENCES public.activo(id) ON DELETE RESTRICT,

    componente_tipo VARCHAR,
    componente_sn VARCHAR,
    campo VARCHAR NOT NULL,
    severidad VARCHAR NOT NULL
        CHECK (severidad IN ('Media', 'Crítica')),
    descripcion VARCHAR NOT NULL,

    fecha_inicio TIMESTAMP WITHOUT TIME ZONE NOT NULL
        DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    ultima_verificacion TIMESTAMP WITHOUT TIME ZONE NOT NULL
        DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    fecha_resolucion TIMESTAMP WITHOUT TIME ZONE,

    CONSTRAINT alerta_componente_check CHECK (
        (componente_tipo IS NULL AND componente_sn IS NULL)
        OR (
            componente_tipo IS NOT NULL AND componente_sn IS NOT NULL
            AND LENGTH(TRIM(componente_tipo)) > 0
            AND LENGTH(TRIM(componente_sn)) > 0
        )
    ),
    CONSTRAINT alerta_resolucion_check CHECK (
        fecha_resolucion IS NULL OR fecha_resolucion >= fecha_inicio
    )
);

-- Una condicion puede tener varios episodios resueltos, pero solo uno abierto.
-- COALESCE incluye en la unicidad las condiciones del equipo (sin componente).
CREATE UNIQUE INDEX alerta_condicion_abierta_uq
    ON public.alerta (
        activo_id,
        COALESCE(componente_tipo, ''),
        COALESCE(componente_sn, ''),
        campo
    )
    WHERE fecha_resolucion IS NULL;

COMMIT;
