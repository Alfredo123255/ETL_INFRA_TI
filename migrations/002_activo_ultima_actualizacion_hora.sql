-- Ejecutar manualmente solo al actualizar instalaciones antiguas con DATE.
-- La fecha de la última lectura exitosa pertenece únicamente al activo.
-- Los días antiguos conservan 00:00 porque se desconoce su hora original.
BEGIN;
ALTER TABLE activo
    ALTER COLUMN ultima_actualizacion TYPE timestamp without time zone
    USING ultima_actualizacion::timestamp;
COMMIT;
