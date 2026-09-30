"""
Cifra y descifra las credenciales SNMPv3 (usuario, clave de autenticación, clave de privacidad)
que se guardan en la base de datos, usando `cryptography` (Fernet) con la clave simétrica
CLAVE_CIFRADO.

Funciones:
- cifrar(texto_plano: str) -> str: devuelve el texto cifrado en base64, listo para guardar en la
  base de datos.
- descifrar(texto_cifrado: str) -> str: recupera el texto plano original a partir del valor
  guardado en la base de datos.

Dependencias: config.py (CLAVE_CIFRADO). Lo usan repositorio.py (al leer credenciales) y
snmp_cliente.py (antes de armar la sesión SNMPv3).
"""
