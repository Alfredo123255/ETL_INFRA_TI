--
-- PostgreSQL database dump
--

\restrict oeQgBe2PRczwsy23XjIPfWFFLBY8kHVcbyRqo3fpEDqwYcjrRj9cCLvsCekHkyr

-- Dumped from database version 17.11
-- Dumped by pg_dump version 17.11

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA IF NOT EXISTS public;


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS 'standard public schema';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: activo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.activo (
    id integer NOT NULL,
    numero_serie character varying NOT NULL,
    hostname character varying NOT NULL,
    fabricante character varying,
    modelo character varying,
    generacion character varying,
    ubicacion character varying NOT NULL,
    ip_gestion character varying,
    tipo_activo character varying NOT NULL,
    estado_operativo character varying NOT NULL,
    cluster character varying,
    responsable character varying,
    orden_compra character varying,
    fecha_eos date,
    version_firmware character varying,
    ultima_actualizacion timestamp without time zone,
    temperatura numeric(5,2),
    consumo_electrico_w numeric(8,2),
    mantenimiento_activo boolean DEFAULT false NOT NULL,
    CONSTRAINT activo_estado_operativo_check CHECK (((estado_operativo)::text = ANY ((ARRAY['Encendido'::character varying, 'Apagado'::character varying, 'Degradado'::character varying, 'Baja'::character varying])::text[]))),
    CONSTRAINT activo_tipo_activo_check CHECK (((tipo_activo)::text = ANY ((ARRAY['SERVIDOR'::character varying, 'STORAGE'::character varying, 'SWITCH'::character varying, 'CHASIS'::character varying])::text[])))
);


--
-- Name: activo_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.activo ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.activo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: chasis_blade; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chasis_blade (
    id integer NOT NULL,
    cantidad_slots integer NOT NULL
);


--
-- Name: chasis_slot; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chasis_slot (
    id integer NOT NULL,
    chasis_id integer NOT NULL,
    numero_slot integer NOT NULL,
    estado character varying,
    hostname_servidor character varying,
    servidor_id integer,
    CONSTRAINT chasis_slot_estado_check CHECK (((estado)::text = ANY ((ARRAY['OCUPADO'::character varying, 'LIBRE'::character varying, 'DEGRADADO'::character varying])::text[])))
);


--
-- Name: chasis_slot_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.chasis_slot ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.chasis_slot_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: clusters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clusters (
    nombre character varying NOT NULL,
    ambiente character varying NOT NULL,
    datacenter character varying,
    CONSTRAINT clusters_ambiente_check CHECK (((ambiente)::text = ANY ((ARRAY['PRODUCCION'::character varying, 'QA'::character varying, 'DESARROLLO'::character varying])::text[])))
);


--
-- Name: controladora_raid; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.controladora_raid (
    id integer NOT NULL,
    activo_id integer NOT NULL,
    modelo character varying,
    raid character varying,
    numero_serial character varying,
    estado character varying NOT NULL,
    CONSTRAINT controladora_raid_estado_check CHECK (((estado)::text = ANY ((ARRAY['Encendido'::character varying, 'Apagado'::character varying, 'Degradado'::character varying, 'Baja'::character varying])::text[])))
);


--
-- Name: controladora_raid_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.controladora_raid ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.controladora_raid_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: cpu; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cpu (
    id integer NOT NULL,
    activo_id integer NOT NULL,
    numero_serial character varying,
    familia character varying,
    marca character varying,
    modelo character varying,
    velocidad_ghz numeric(4,2),
    cantidad_nucleos integer,
    cantidad_hilos integer,
    cache_l1_mb numeric(6,2),
    cache_l2_mb numeric(6,2),
    cache_l3_mb numeric(6,2),
    estado character varying NOT NULL,
    CONSTRAINT cpu_estado_check CHECK (((estado)::text = ANY ((ARRAY['Encendido'::character varying, 'Apagado'::character varying, 'Degradado'::character varying, 'Baja'::character varying])::text[])))
);


--
-- Name: cpu_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.cpu ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.cpu_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: datacenters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.datacenters (
    nombre character varying NOT NULL,
    latitud character varying,
    longitud character varying
);


--
-- Name: disco; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.disco (
    id integer NOT NULL,
    activo_id integer NOT NULL,
    numero_serial character varying,
    marca character varying,
    tipo character varying,
    capacidad_gb numeric(10,2),
    velocidad_rpm integer,
    estado character varying NOT NULL,
    modelo character varying,
    CONSTRAINT disco_estado_check CHECK (((estado)::text = ANY ((ARRAY['Encendido'::character varying, 'Apagado'::character varying, 'Degradado'::character varying, 'Baja'::character varying])::text[])))
);


--
-- Name: disco_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.disco ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.disco_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: fuente_poder; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fuente_poder (
    id integer NOT NULL,
    activo_id integer NOT NULL,
    numero_serial character varying,
    modelo character varying,
    consumo_w numeric(8,2),
    tipo_corriente character varying,
    estado character varying NOT NULL,
    CONSTRAINT fuente_poder_estado_check CHECK (((estado)::text = ANY ((ARRAY['Encendido'::character varying, 'Apagado'::character varying, 'Degradado'::character varying, 'Baja'::character varying])::text[]))),
    CONSTRAINT fuente_poder_tipo_corriente_check CHECK (((tipo_corriente)::text = ANY ((ARRAY['AC'::character varying, 'DC'::character varying])::text[])))
);


--
-- Name: fuente_poder_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.fuente_poder ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.fuente_poder_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: historico_estado; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.historico_estado (
    id integer NOT NULL,
    activo_id integer NOT NULL,
    componente_tipo character varying,
    componente_sn character varying,
    campo character varying NOT NULL,
    valor_nuevo character varying NOT NULL,
    descripcion character varying,
    fecha_cambio timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: historico_estado_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.historico_estado ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.historico_estado_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: metrica_historica; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.metrica_historica (
    id integer NOT NULL,
    activo_id integer NOT NULL,
    componente_tipo character varying,
    componente_serial character varying,
    nombre_metrica character varying NOT NULL,
    valor numeric NOT NULL,
    fecha_medicion timestamp without time zone NOT NULL
);


--
-- Name: metrica_historica_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.metrica_historica ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.metrica_historica_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: modelos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.modelos (
    nombre_modelo character varying NOT NULL,
    fecha_eol date
);


--
-- Name: monitoreo_snmp; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.monitoreo_snmp (
    id integer NOT NULL,
    ip_gestion character varying NOT NULL,
    usuario character varying NOT NULL,
    clave character varying NOT NULL,
    frecuencia_actualizacion integer NOT NULL,
    estado_conexion character varying,
    fecha_ultima_actualizacion timestamp without time zone,
    activo_id integer,
    clave_privacidad character varying(255),
    CONSTRAINT monitoreo_snmp_estado_conexion_check CHECK (((estado_conexion)::text = ANY ((ARRAY['Activo'::character varying, 'Inactivo'::character varying, 'Sin conexión'::character varying])::text[])))
);


--
-- Name: monitoreo_snmp_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.monitoreo_snmp ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.monitoreo_snmp_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: puerto_switch; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.puerto_switch (
    id integer NOT NULL,
    switch_id integer NOT NULL,
    numero_puerto character varying,
    velocidad character varying,
    estado character varying NOT NULL,
    CONSTRAINT puerto_switch_estado_check CHECK (((estado)::text = ANY ((ARRAY['Encendido'::character varying, 'Apagado'::character varying, 'Degradado'::character varying, 'Baja'::character varying])::text[])))
);


--
-- Name: puerto_switch_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.puerto_switch ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.puerto_switch_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: puerto_tarjeta_red; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.puerto_tarjeta_red (
    id integer NOT NULL,
    tarjeta_red_id integer NOT NULL,
    numero_puerto character varying,
    mac_address character varying,
    velocidad character varying,
    estado character varying NOT NULL,
    CONSTRAINT puerto_tarjeta_red_estado_check CHECK (((estado)::text = ANY ((ARRAY['Encendido'::character varying, 'Apagado'::character varying, 'Degradado'::character varying, 'Baja'::character varying])::text[])))
);


--
-- Name: puerto_tarjeta_red_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.puerto_tarjeta_red ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.puerto_tarjeta_red_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: ram; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ram (
    id integer NOT NULL,
    activo_id integer NOT NULL,
    numero_serial character varying,
    marca character varying,
    modelo character varying,
    generacion character varying,
    velocidad_mhz integer,
    capacidad_gb numeric(6,2),
    estado character varying NOT NULL,
    CONSTRAINT ram_estado_check CHECK (((estado)::text = ANY ((ARRAY['Encendido'::character varying, 'Apagado'::character varying, 'Degradado'::character varying, 'Baja'::character varying])::text[])))
);


--
-- Name: ram_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.ram ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.ram_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: servidor; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.servidor (
    id integer NOT NULL,
    ip_sistema_operativo character varying,
    version_so character varying,
    fecha_soporte_so date,
    id_chasis_slot integer,
    tipo character varying NOT NULL,
    CONSTRAINT servidor_tipo_check CHECK (((tipo)::text = ANY ((ARRAY['RACKEABLE'::character varying, 'BLADE'::character varying])::text[])))
);


--
-- Name: storage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.storage (
    id integer NOT NULL,
    protocolo_comunicacion character varying,
    capacidad_total_tb numeric(8,2),
    capacidad_usada_tb numeric(8,2),
    iops integer
);


--
-- Name: switch; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.switch (
    id integer NOT NULL,
    tipo_red character varying,
    cantidad_puertos integer,
    cantidad_puertos_ocupados integer,
    modo_operacion character varying
);


--
-- Name: tarjeta_red; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tarjeta_red (
    id integer NOT NULL,
    activo_id integer NOT NULL,
    numero_serial character varying,
    marca character varying,
    modelo character varying,
    estado character varying NOT NULL,
    cantidad_puertos integer,
    CONSTRAINT tarjeta_red_estado_check CHECK (((estado)::text = ANY ((ARRAY['Encendido'::character varying, 'Apagado'::character varying, 'Degradado'::character varying, 'Baja'::character varying])::text[])))
);


--
-- Name: tarjeta_red_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.tarjeta_red ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.tarjeta_red_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: ventilador; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ventilador (
    id integer NOT NULL,
    activo_id integer NOT NULL,
    numero_serial character varying,
    velocidad_rpm integer,
    modelo character varying,
    estado character varying NOT NULL,
    CONSTRAINT ventilador_estado_check CHECK (((estado)::text = ANY ((ARRAY['Encendido'::character varying, 'Apagado'::character varying, 'Degradado'::character varying, 'Baja'::character varying])::text[])))
);


--
-- Name: ventilador_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.ventilador ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.ventilador_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: activo activo_hostname_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activo
    ADD CONSTRAINT activo_hostname_key UNIQUE (hostname);


--
-- Name: activo activo_numero_serie_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activo
    ADD CONSTRAINT activo_numero_serie_key UNIQUE (numero_serie);


--
-- Name: activo activo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activo
    ADD CONSTRAINT activo_pkey PRIMARY KEY (id);


--
-- Name: chasis_blade chasis_blade_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chasis_blade
    ADD CONSTRAINT chasis_blade_pkey PRIMARY KEY (id);


--
-- Name: chasis_slot chasis_slot_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chasis_slot
    ADD CONSTRAINT chasis_slot_pkey PRIMARY KEY (id);


--
-- Name: clusters clusters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clusters
    ADD CONSTRAINT clusters_pkey PRIMARY KEY (nombre);


--
-- Name: controladora_raid controladora_raid_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.controladora_raid
    ADD CONSTRAINT controladora_raid_pkey PRIMARY KEY (id);


--
-- Name: cpu cpu_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cpu
    ADD CONSTRAINT cpu_pkey PRIMARY KEY (id);


--
-- Name: datacenters datacenters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.datacenters
    ADD CONSTRAINT datacenters_pkey PRIMARY KEY (nombre);


--
-- Name: disco disco_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disco
    ADD CONSTRAINT disco_pkey PRIMARY KEY (id);


--
-- Name: fuente_poder fuente_poder_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fuente_poder
    ADD CONSTRAINT fuente_poder_pkey PRIMARY KEY (id);


--
-- Name: historico_estado historico_estado_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historico_estado
    ADD CONSTRAINT historico_estado_pkey PRIMARY KEY (id);


--
-- Name: metrica_historica metrica_historica_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metrica_historica
    ADD CONSTRAINT metrica_historica_pkey PRIMARY KEY (id);


--
-- Name: modelos modelos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.modelos
    ADD CONSTRAINT modelos_pkey PRIMARY KEY (nombre_modelo);


--
-- Name: monitoreo_snmp monitoreo_snmp_activo_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.monitoreo_snmp
    ADD CONSTRAINT monitoreo_snmp_activo_id_key UNIQUE (activo_id);


--
-- Name: monitoreo_snmp monitoreo_snmp_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.monitoreo_snmp
    ADD CONSTRAINT monitoreo_snmp_pkey PRIMARY KEY (id);


--
-- Name: puerto_switch puerto_switch_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.puerto_switch
    ADD CONSTRAINT puerto_switch_pkey PRIMARY KEY (id);


--
-- Name: puerto_tarjeta_red puerto_tarjeta_red_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.puerto_tarjeta_red
    ADD CONSTRAINT puerto_tarjeta_red_pkey PRIMARY KEY (id);


--
-- Name: ram ram_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ram
    ADD CONSTRAINT ram_pkey PRIMARY KEY (id);


--
-- Name: servidor servidor_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.servidor
    ADD CONSTRAINT servidor_pkey PRIMARY KEY (id);


--
-- Name: storage storage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.storage
    ADD CONSTRAINT storage_pkey PRIMARY KEY (id);


--
-- Name: switch switch_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.switch
    ADD CONSTRAINT switch_pkey PRIMARY KEY (id);


--
-- Name: tarjeta_red tarjeta_red_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tarjeta_red
    ADD CONSTRAINT tarjeta_red_pkey PRIMARY KEY (id);


--
-- Name: ventilador ventilador_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ventilador
    ADD CONSTRAINT ventilador_pkey PRIMARY KEY (id);


--
-- Name: idx_historico_estado_activo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_historico_estado_activo ON public.historico_estado USING btree (activo_id);


--
-- Name: idx_metrica_historica_activo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_metrica_historica_activo ON public.metrica_historica USING btree (activo_id);


--
-- Name: idx_metrica_historica_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_metrica_historica_fecha ON public.metrica_historica USING btree (fecha_medicion);


--
-- Name: activo activo_cluster_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activo
    ADD CONSTRAINT activo_cluster_fkey FOREIGN KEY (cluster) REFERENCES public.clusters(nombre);


--
-- Name: activo activo_modelo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activo
    ADD CONSTRAINT activo_modelo_fkey FOREIGN KEY (modelo) REFERENCES public.modelos(nombre_modelo);


--
-- Name: activo activo_ubicacion_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activo
    ADD CONSTRAINT activo_ubicacion_fkey FOREIGN KEY (ubicacion) REFERENCES public.datacenters(nombre);


--
-- Name: chasis_blade chasis_blade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chasis_blade
    ADD CONSTRAINT chasis_blade_id_fkey FOREIGN KEY (id) REFERENCES public.activo(id);


--
-- Name: chasis_slot chasis_slot_chasis_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chasis_slot
    ADD CONSTRAINT chasis_slot_chasis_id_fkey FOREIGN KEY (chasis_id) REFERENCES public.chasis_blade(id);


--
-- Name: clusters clusters_datacenter_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clusters
    ADD CONSTRAINT clusters_datacenter_fkey FOREIGN KEY (datacenter) REFERENCES public.datacenters(nombre);


--
-- Name: controladora_raid controladora_raid_activo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.controladora_raid
    ADD CONSTRAINT controladora_raid_activo_id_fkey FOREIGN KEY (activo_id) REFERENCES public.activo(id);


--
-- Name: cpu cpu_activo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cpu
    ADD CONSTRAINT cpu_activo_id_fkey FOREIGN KEY (activo_id) REFERENCES public.activo(id);


--
-- Name: disco disco_activo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disco
    ADD CONSTRAINT disco_activo_id_fkey FOREIGN KEY (activo_id) REFERENCES public.activo(id);


--
-- Name: servidor fk_servidor_chasis_slot; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.servidor
    ADD CONSTRAINT fk_servidor_chasis_slot FOREIGN KEY (id_chasis_slot) REFERENCES public.chasis_slot(id);


--
-- Name: fuente_poder fuente_poder_activo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fuente_poder
    ADD CONSTRAINT fuente_poder_activo_id_fkey FOREIGN KEY (activo_id) REFERENCES public.activo(id);


--
-- Name: historico_estado historico_estado_activo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historico_estado
    ADD CONSTRAINT historico_estado_activo_id_fkey FOREIGN KEY (activo_id) REFERENCES public.activo(id);


--
-- Name: metrica_historica metrica_historica_activo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metrica_historica
    ADD CONSTRAINT metrica_historica_activo_id_fkey FOREIGN KEY (activo_id) REFERENCES public.activo(id);


--
-- Name: monitoreo_snmp monitoreo_snmp_activo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.monitoreo_snmp
    ADD CONSTRAINT monitoreo_snmp_activo_id_fkey FOREIGN KEY (activo_id) REFERENCES public.activo(id);


--
-- Name: puerto_switch puerto_switch_switch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.puerto_switch
    ADD CONSTRAINT puerto_switch_switch_id_fkey FOREIGN KEY (switch_id) REFERENCES public.switch(id);


--
-- Name: puerto_tarjeta_red puerto_tarjeta_red_tarjeta_red_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.puerto_tarjeta_red
    ADD CONSTRAINT puerto_tarjeta_red_tarjeta_red_id_fkey FOREIGN KEY (tarjeta_red_id) REFERENCES public.tarjeta_red(id);


--
-- Name: ram ram_activo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ram
    ADD CONSTRAINT ram_activo_id_fkey FOREIGN KEY (activo_id) REFERENCES public.activo(id);


--
-- Name: servidor servidor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.servidor
    ADD CONSTRAINT servidor_id_fkey FOREIGN KEY (id) REFERENCES public.activo(id);


--
-- Name: storage storage_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.storage
    ADD CONSTRAINT storage_id_fkey FOREIGN KEY (id) REFERENCES public.activo(id);


--
-- Name: switch switch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.switch
    ADD CONSTRAINT switch_id_fkey FOREIGN KEY (id) REFERENCES public.activo(id);


--
-- Name: tarjeta_red tarjeta_red_activo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tarjeta_red
    ADD CONSTRAINT tarjeta_red_activo_id_fkey FOREIGN KEY (activo_id) REFERENCES public.activo(id);


--
-- Name: ventilador ventilador_activo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ventilador
    ADD CONSTRAINT ventilador_activo_id_fkey FOREIGN KEY (activo_id) REFERENCES public.activo(id);


--
-- PostgreSQL database dump complete
--

\unrestrict oeQgBe2PRczwsy23XjIPfWFFLBY8kHVcbyRqo3fpEDqwYcjrRj9cCLvsCekHkyr

