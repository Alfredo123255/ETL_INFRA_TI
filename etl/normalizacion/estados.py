"""Estados HPE por objeto; valores desconocidos se conservan como Degradado."""
CONDICION_HPE = {1: "Degradado", 2: "Encendido", 3: "Degradado", 4: "Apagado"}
ESTADO_CPU_HPE = {**CONDICION_HPE, 5: "Apagado"}
ESTADO_RAM_HPE = {1: "Degradado", 2: "Encendido", 3: "Degradado", 4: "Degradado"}
ESTADO_NIC_HPE = {1: "Degradado", 2: "Encendido", 3: "Apagado", 4: "Apagado"}

def normalizar_estado(valor_origen, tabla_traduccion):
    if valor_origen is None:
        return "Degradado"
    return tabla_traduccion.get(int(valor_origen), "Degradado")
