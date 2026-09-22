# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the OpenAntenna Studio GUI.

What is *not* bundled, on purpose:

* **openEMS / CSXCAD** — GPL/LGPL, and the project's architecture keeps the solver in a
  separate process so the MIT core never links it.  The frozen GUI therefore still needs an
  openEMS installation of its own plus ``OPENEMS_ROOT``; the Simulate tab reports the solver
  as unavailable until then, which is the honest behaviour the package already has.
* **tools/** — the local solver, its zip and the introspection helpers are development
  material (hundreds of MB), not part of the application.

Build with::

    python scripts/build_gui.py           # one-folder, into dist/OpenAntennaGUI
"""

from pathlib import Path

# ``SPECPATH`` is the folder holding this spec (…/packaging), so the repository root is its
# parent - not ``parents[1]``, which lands one level too high (a real failure: the first
# build reported "script 'D:\\packaging\\gui_launcher.py' not found").
ROOT = Path(SPECPATH).resolve().parent

analysis = Analysis(  # noqa: F821 - provided by PyInstaller
    [str(ROOT / "packaging" / "gui_launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # a defence in depth: nothing in the GUI imports the solver, and it must stay that way
    excludes=["openEMS", "CSXCAD", "tools"],
    noarchive=False,
)

pyz = PYZ(analysis.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="OpenAntennaGUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # a windowed application; --selftest is verified through the exit code
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

collection = COLLECT(  # noqa: F821
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="OpenAntennaGUI",
)
