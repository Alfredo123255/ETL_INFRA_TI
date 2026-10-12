"""Load only snmpsim's built-in numeric variation for local agents.

snmpsim executes variation files in an isolated global namespace. Execute the
installed numeric module in that same namespace so its handlers stay available
without copying or modifying the installed package.
"""

from pathlib import Path

import snmpsim

_numeric_path = Path(snmpsim.__file__).resolve().parent / "variation" / "numeric.py"
exec(compile(_numeric_path.read_bytes(), str(_numeric_path), "exec"), globals())
