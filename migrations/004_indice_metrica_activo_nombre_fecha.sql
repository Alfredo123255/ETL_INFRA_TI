-- Ejecutar fuera de una transaccion para permitir escrituras del ETL.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_metrica_activo_nombre_fecha
    ON public.metrica_historica (activo_id, nombre_metrica, fecha_medicion);
