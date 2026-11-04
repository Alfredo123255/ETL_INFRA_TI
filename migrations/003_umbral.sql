-- Ejecutar al actualizar una instalación que todavía no tiene la tabla umbral.
BEGIN;

CREATE TABLE public.umbral (
    nombre VARCHAR PRIMARY KEY,
    advertencia NUMERIC,
    critico NUMERIC,
    fecha_modificacion TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT umbral_orden_check
        CHECK (critico IS NULL OR advertencia IS NULL OR critico >= advertencia)
);

-- CPU, RAM, disco y capacidad de almacenamiento se evalúan en porcentaje.
-- Un par NULL/NULL indica que no hay umbral configurado.
-- El ancho de banda se incluye en el catálogo como dato informativo.
-- EOS: advertencia entre 0 y 30 días. Crítico fijo si quedan menos de 0 días.
INSERT INTO public.umbral (nombre, advertencia, critico) VALUES
    ('cpu_uso_ghz',                            80,   90),
    ('ram_uso_gb',                             80,   90),
    ('disco_uso_gb',                            80,   90),
    ('equipo_temperatura_c',                   75,   85),
    ('equipo_consumo_w',                       NULL, NULL),
    ('red_trafico_entrada_mbps',               NULL, NULL),
    ('red_trafico_salida_mbps',                NULL, NULL),
    ('almacenamiento_uso_tb',                  NULL, NULL),
    ('almacenamiento_iops',                    NULL, NULL),
    ('red_ancho_banda_mbps',                   NULL, NULL),
    ('almacenamiento_latencia_ms',             NULL, NULL),
    ('almacenamiento_throughput_lectura_mbps', NULL, NULL),
    ('almacenamiento_throughput_escritura_mbps',NULL, NULL),
    ('red_utilizacion_pct',                    NULL, NULL),
    ('dias_para_eos',                          30,   NULL);

COMMIT;
