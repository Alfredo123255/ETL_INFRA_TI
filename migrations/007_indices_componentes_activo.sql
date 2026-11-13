-- Ejecutar fuera de una transacción; CONCURRENTLY permite las escrituras del ETL.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cpu_activo_id
    ON public.cpu (activo_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ram_activo_id
    ON public.ram (activo_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_disco_activo_id
    ON public.disco (activo_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tarjeta_red_activo_id
    ON public.tarjeta_red (activo_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fuente_poder_activo_id
    ON public.fuente_poder (activo_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ventilador_activo_id
    ON public.ventilador (activo_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_controladora_raid_activo_id
    ON public.controladora_raid (activo_id);
