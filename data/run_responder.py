#!/usr/bin/env python
"""Wrapper para snmpsim-command-responder.

En Python 3.12+/3.14, asyncio.get_event_loop() ya no crea un event loop
implicito cuando se llama fuera de una coroutine en el hilo principal, y
snmpsim (via pysnmp.carrier.asyncio) todavia depende de ese comportamiento
implicito. Este wrapper crea y fija el event loop explicitamente antes de
invocar el punto de entrada real, y no cambia ningun otro comportamiento.
"""
import asyncio
import sys

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from snmpsim.commands.responder import main

if __name__ == "__main__":
    sys.exit(main())
