"""Run a Python script with the openEMS native DLL directory registered.

The openEMS Windows package ships CSXCAD.dll / openEMS.dll next to the
executables.  Python extension modules do not search PATH for those DLLs since
Python 3.8, so os.add_dll_directory() is required before importing CSXCAD.

The openEMS location comes from the environment only - there is deliberately no
built-in absolute default, so this file stays usable on any machine (review S-1).
Set the variable once, e.g. with ``setx OPENEMS_ROOT <folder holding openEMS.exe>``
and then open a new shell.

Usage:
    python scripts/run_with_openems.py <generated_sim.py> [args ...]
"""

import os
import runpy
import sys

ROOT = os.environ.get("OPENEMS_ROOT")
if not ROOT:
    sys.exit(
        "ERROR: OPENEMS_ROOT is not set. Point it at the folder that holds\n"
        "openEMS.exe / CSXCAD.dll, for example with:\n"
        "    setx OPENEMS_ROOT <folder holding openEMS.exe>\n"
        "(then open a new shell so the variable is visible)."
    )
if not os.path.isdir(ROOT):
    sys.exit(f"ERROR: OPENEMS_ROOT points to a folder that does not exist: {ROOT}")

os.add_dll_directory(ROOT)
os.environ["PATH"] = ROOT + os.pathsep + os.environ.get("PATH", "")

if len(sys.argv) < 2:
    sys.exit(f"usage: {os.path.basename(sys.argv[0])} <script.py> [args ...]")

target = sys.argv[1]
sys.argv = sys.argv[1:]
runpy.run_path(target, run_name="__main__")
