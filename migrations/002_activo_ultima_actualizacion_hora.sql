-- Guardar la hora UTC de la última lectura SNMP exitosa del activo.
-- Las fechas antiguas sin conexión conservan el día con hora 00:00 (hora real desconocida).
BEGIN;

ALTER TABLE activo
    ALTER COLUMN ultima_actualizacion TYPE timestamp without time zone
    USING ultima_actualizacion::timestamp;

-- La conexión ya tiene la marca UTC de la última lectura exitosa. Recuperar esa
-- hora para los activos vinculados en vez de inventar una hora a partir del DATE.
UPDATE activo AS a
SET ultima_actualizacion = m.fecha_ultima_actualizacion
FROM monitoreo_snmp AS m
WHERE m.activo_id = a.id
  AND m.fecha_ultima_actualizacion IS NOT NULL;

COMMIT;
