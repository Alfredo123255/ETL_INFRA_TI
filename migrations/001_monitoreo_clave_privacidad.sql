-- SNMPv3 permite claves de autenticación y privacidad diferentes.
-- Si es NULL, el ETL sigue usando "clave" para ambas (compatibilidad previa).
ALTER TABLE monitoreo_snmp
    ADD COLUMN IF NOT EXISTS clave_privacidad varchar(255);
