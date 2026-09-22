# Packaging the desktop GUI (PyInstaller)

The GUI can be frozen into a self-contained Windows application.  PyInstaller is a
**build-time** tool, not a runtime dependency:

```powershell
python -m pip install -e .[packaging]     # or: pip install pyinstaller
python scripts/build_gui.py               # build + verify, one step
```

Output: `dist/OpenAntennaGUI/` (one folder; the executable inside is `OpenAntennaGUI.exe`).

## What the frozen app contains - and what it deliberately does not

| Bundled | Not bundled, on purpose |
|---|---|
| The whole `openantenna` package (stdlib-only core + GUI) | **openEMS / CSXCAD** - GPL/LGPL, and the architecture keeps the solver in a separate process so the MIT core never links it |
| PySide6 (Qt) and matplotlib | **`tools/`** - the local solver, its zip and the introspection helpers are development material |
| Qt platform plugins needed to start | Any solver binary, licence or token |

The spec excludes `openEMS`, `CSXCAD` and `tools` explicitly as a defence in depth: nothing
in the GUI imports them, and that must stay true.

**Consequence, stated plainly:** the frozen GUI still needs an openEMS installation on the
machine, with `OPENEMS_ROOT` set.  Without it the Simulate tab reports the solver as
unavailable and refuses to run - the same honest behaviour as the source build, not a
degraded one.

## Verifying a build

`scripts/build_gui.py` does not just build; it runs the frozen executable with
`--selftest`, which constructs the window, evaluates the material tab, synthesises the
design with the 3-D preview, queues a case and exits **without** entering the event loop.
A windowed executable has no console, so the **exit code** is the evidence:

| Exit code | Meaning |
|---|---|
| 0 | the frozen application starts and is functional |
| non-zero | the build is broken; the traceback is printed by `--selftest` when run from a console build |

The same `--selftest` flag works on a source checkout, which is what the test suite uses.

## Notes

* The build is one-folder by design (faster start-up, inspectable).  For a single-file
  build, add `--onefile` variants to the spec; expect a slower first launch because Qt and
  matplotlib data are unpacked to a temporary directory.
* Qt plugin paths inside the frozen app are handled by PyInstaller's PySide6 hooks; if a
  build starts but shows no window, the usual cause is a missing platform plugin, and
  `QT_DEBUG_PLUGINS=1` names it.
* Code signing, installers (MSI/Inno) and an auto-update channel are not part of this
  project; the deliverable here is a reproducible, verified build of the application.
