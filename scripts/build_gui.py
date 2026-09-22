"""Build the frozen GUI and verify it, in one step.

    python scripts/build_gui.py            # build + selftest
    python scripts/build_gui.py --no-test  # build only

The verification is the point: a build that "succeeds" but produces an application that
cannot construct its own window is worthless, so the frozen executable is run with
``--selftest`` and its **exit code** is checked (a windowed app has no console to read).
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "packaging" / "openantenna-gui.spec"
EXE = ROOT / "dist" / "OpenAntennaGUI" / "OpenAntennaGUI.exe"
LOCAL_EXE = ROOT / "dist" / "OpenAntennaGUI" / "OpenAntennaGUI"


def main(argv: list[str]) -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print(
            "PyInstaller is not installed. It is a build-time tool, not a runtime "
            "dependency:\n    python -m pip install -e .[packaging]",
            file=sys.stderr,
        )
        return 2

    print(f"building {SPEC.name} ... (this takes a couple of minutes)")
    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(SPEC)],
        cwd=str(ROOT),
        check=False,
    )
    if completed.returncode != 0:
        print(f"build FAILED with exit code {completed.returncode}", file=sys.stderr)
        return completed.returncode
    print(f"build finished in {time.perf_counter() - started:.0f} s")

    if "--no-test" in argv:
        return 0

    binary = EXE if EXE.exists() else LOCAL_EXE
    if not binary.exists():
        print(f"built, but no executable found at {EXE}", file=sys.stderr)
        return 3
    print(f"verifying {binary.name} with --selftest ...")
    probe = subprocess.run([str(binary), "--selftest"], check=False, timeout=300)
    if probe.returncode != 0:
        print(f"the frozen application failed its selftest (exit {probe.returncode})", file=sys.stderr)
        return probe.returncode
    size_mb = sum(f.stat().st_size for f in binary.parent.rglob("*") if f.is_file()) / 1e6
    print(f"OK: the frozen GUI starts, builds its window and exits cleanly ({size_mb:.0f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
