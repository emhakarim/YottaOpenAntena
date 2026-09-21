"""Run a Python script with the openEMS native DLL directory registered.

The openEMS Windows package ships CSXCAD.dll / openEMS.dll next to its executables.
Python extension modules do not search PATH for their dependent DLLs since Python
3.8, so ``os.add_dll_directory()`` is required before importing CSXCAD.

There is deliberately **no** absolute fallback for ``OPENEMS_ROOT``: the folder is
taken from the environment so this file, and every script that calls it, stays
reproducible from the repository on any machine (review item S-1).

Usage:
    python scripts/run_with_openems.py <target_script.py> [args...]
"""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def register_openems_dlls() -> str:
    """Register the native DLL directory; return the root that was used ('' if any)."""
    root = os.environ.get("OPENEMS_ROOT", "")
    if not root:
        print(
            "WARNING: OPENEMS_ROOT is not set; importing CSXCAD will probably fail on "
            "Windows. Point it at the folder containing openEMS.exe and CSXCAD.dll.",
            file=sys.stderr,
        )
        return ""
    if not os.path.isdir(root):
        print(f"WARNING: OPENEMS_ROOT does not exist: {root}", file=sys.stderr)
        return ""
    os.add_dll_directory(root)
    os.environ["PATH"] = root + os.pathsep + os.environ.get("PATH", "")
    return root


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: run_with_openems.py <target_script.py> [args...]", file=sys.stderr)
        return 2
    register_openems_dlls()
    sys.argv = args
    runpy.run_path(args[0], run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
