#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Validador estatico de los archivos data/*/public.snmprec, pensado para
correr antes de cada commit sin levantar ningun agente.

Para cada linea que no sea un comentario (empieza con '#', ignorando
espacios) ni este en blanco, revisa:

  (a) formato exacto OID|etiqueta|valor (mismo split que usa el propio
      snmpsim: snmpsim/grammar/snmprec.py hace line.strip().split("|", 2),
      con OID y etiqueta no vacios).
  (b) etiqueta valida: 2, 4, 4x, 5, 6, 64, 65, 66, 67, 68 o 70, con o sin
      sufijo ":modulo" (p. ej. "70:numeric") para un modulo de variacion
      de snmpsim.
  (c) rango del valor segun la etiqueta (solo para lineas SIN modulo de
      variacion; con modulo el "valor" es una lista de parametros
      rate=...,initial=..., no un numero, y no se revisa aqui):
        - 2  (Integer32): -2147483648 .. 2147483647
        - 65 (Counter32), 66 (Gauge32), 67 (TimeTicks): 0 .. 4294967295
        - 70 (Counter64): 0 .. 18446744073709551615
      Las etiquetas 4, 4x, 5, 6, 64 y 68 no son numericas y no se revisan
      en rango, solo en formato/etiqueta.
  (d) los OID de un mismo archivo deben quedar en orden ascendente,
      comparando numericamente componente a componente (no como texto:
      "2" < "10", no "2" > "10" como pasaria comparando strings).
  (e) no debe haber OID repetidos dentro del mismo archivo.

Uso:
    python data/validar_snmprec.py

Termina con exit code 0 si no encontro problemas, o 1 si encontro alguno
(imprimiendo archivo, numero de linea y motivo de cada uno).
"""
import glob
import os
import sys

TAGS_VALIDAS = {"2", "4", "4x", "5", "6", "64", "65", "66", "67", "68", "70"}

RANGOS = {
    "2": (-2147483648, 2147483647),
    "65": (0, 4294967295),
    "66": (0, 4294967295),
    "67": (0, 4294967295),
    "70": (0, 18446744073709551615),
}


def es_oid_valido(oid):
    if not oid:
        return False
    partes = oid.split(".")
    return all(p.isdigit() for p in partes)


def oid_key(oid):
    return tuple(int(p) for p in oid.split("."))


def validar_archivo(ruta):
    """Devuelve una lista de (linea_no, motivo)."""
    problemas = []
    oids_vistos = {}  # oid -> primera linea donde aparecio
    prev_oid = None
    prev_oid_line = None

    with open(ruta, "r", encoding="ascii", errors="replace") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.rstrip("\n").rstrip("\r")
            stripped = line.strip()

            if not stripped or stripped.startswith("#"):
                continue

            partes = stripped.split("|", 2)
            if len(partes) != 3 or not partes[0] or not partes[1]:
                problemas.append(
                    (line_no, f'formato invalido (se esperaba "OID|etiqueta|valor"): {stripped!r}')
                )
                continue

            oid, etiqueta, valor = partes

            if not es_oid_valido(oid):
                problemas.append((line_no, f"OID invalido (no son solo digitos y puntos): {oid!r}"))
                continue

            etiqueta_base, _, modulo = etiqueta.partition(":")

            if etiqueta_base not in TAGS_VALIDAS:
                problemas.append(
                    (line_no, f'etiqueta invalida "{etiqueta_base}" en OID {oid} '
                              f'(validas: {", ".join(sorted(TAGS_VALIDAS))})')
                )
            elif not modulo and etiqueta_base in RANGOS:
                lo, hi = RANGOS[etiqueta_base]
                try:
                    valor_num = int(valor)
                except ValueError:
                    problemas.append(
                        (line_no, f'valor no numerico "{valor}" para etiqueta {etiqueta_base} en OID {oid}')
                    )
                else:
                    if not (lo <= valor_num <= hi):
                        problemas.append(
                            (line_no, f"valor {valor_num} fuera de rango para etiqueta "
                                      f"{etiqueta_base} en OID {oid} (rango valido: {lo}..{hi})")
                        )

            oid_tuple = oid_key(oid)

            if oid in oids_vistos:
                problemas.append(
                    (line_no, f"OID repetido {oid} (ya aparecia en la linea {oids_vistos[oid]})")
                )
            else:
                oids_vistos[oid] = line_no

                if prev_oid is not None and oid_tuple < prev_oid:
                    problemas.append(
                        (line_no, f"OID {oid} fuera de orden ascendente "
                                  f"(va despues de {'.'.join(str(x) for x in prev_oid)} "
                                  f"en la linea {prev_oid_line})")
                    )
                prev_oid = oid_tuple
                prev_oid_line = line_no

    return problemas


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    patron = os.path.join(repo_root, "data", "*", "public.snmprec")
    archivos = sorted(glob.glob(patron))

    if not archivos:
        print(f"No se encontraron archivos con el patron {patron}")
        return 1

    total_problemas = 0

    for ruta in archivos:
        rel = os.path.relpath(ruta, repo_root)
        problemas = validar_archivo(ruta)

        if not problemas:
            print(f"[OK] {rel}")
            continue

        for line_no, motivo in problemas:
            print(f"[ERROR] {rel}:{line_no}: {motivo}")
            total_problemas += 1

    print()
    if total_problemas:
        print(f"Total: {total_problemas} problema(s) en {len(archivos)} archivo(s) revisados.")
        return 1

    print(f"Sin problemas en {len(archivos)} archivo(s) revisados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
