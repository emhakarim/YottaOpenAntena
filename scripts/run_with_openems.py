"""Run a Python script with the openEMS native DLL directory registered.

The openEMS Windows package ships CSXCAD.dll / openEMS.dll next to the
executables.  Python extension modules do not search PATH for those DLLs since
Python 3.8, so os.add_dll_directory() is required before importing CSXCAD.
"""
import os, runpy, sys

ROOT = os.environ.get("OPENEMS_ROOT", r"D:\OpenAntenna\tools\openEMS")
if os.path.isdir(ROOT):
    os.add_dll_directory(ROOT)
    os.environ["PATH"] = ROOT + os.pathsep + os.environ.get("PATH", "")
else:
    print("WARNING: OPENEMS_ROOT not found:", ROOT, file=sys.stderr)

target = sys.argv[1]
sys.argv = sys.argv[1:]
runpy.run_path(target, run_name="__main__")
