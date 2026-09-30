"""Fabricante por enterprise y tipo por evidencia SNMP."""
FABRICANTES = {232: "HPE", 11: "HPE", 47196: "HPE Aruba Networking", 14823: "Aruba",
               37447: "HPE (Nimble)", 12925: "HPE (3PAR)", 2011: "Huawei",
               34774: "Huawei", 9: "Cisco"}
# Confirmados en los MAPEO y en los archivos public.snmprec.
REGLAS = (("1.3.6.1.4.1.232.22", "CHASIS"),
          ("1.3.6.1.4.1.232.16", "STORAGE"),
          ("1.3.6.1.4.1.232.11", "SERVIDOR"))

def empresa(sys_object_id):
    try:
        parts = tuple(map(int, sys_object_id.strip(".").split(".")))
        if parts[:6] == (1, 3, 6, 1, 4, 1) and len(parts) > 6:
            return parts[6]
    except ValueError:
        pass
    return None

def fabricante(sys_object_id):
    return FABRICANTES.get(empresa(sys_object_id))

async def detectar_tipo(sys_object_id, existe_subarbol):
    try:
        if empresa(sys_object_id) == 47196:
            return "SWITCH" if await existe_subarbol("1.3.6.1.4.1.47196") else "DESCONOCIDO"
        for root, kind in REGLAS:
            if await existe_subarbol(root):
                return kind
    except Exception:
        # El GET inicial confirmó conexión; fallar en detección no la invalida.
        return "DESCONOCIDO"
    return "DESCONOCIDO"
