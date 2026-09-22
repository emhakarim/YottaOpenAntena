"""Guard against machine-specific absolute paths in the research scripts.

Review item S-1: the scripts under ``scripts/`` used to hardcode
``ROOT = Path(r"D:\\OpenAntenna")`` (plus absolute ``OPENEMS_ROOT`` defaults), so
the evidence quoted in ``docs/verification.md`` could not be reproduced from the
repository by anybody else.  These tests keep that from coming back.

They are deliberately textual: most of the scripts drive an external solver and
cannot run in CI, but their *portability* can still be pinned.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = sorted((REPO_ROOT / "scripts").glob("*.py"))

#: an absolute Windows drive path such as D:\OpenAntenna (not "http://...")
ABSOLUTE_DRIVE = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


#: scripts that import the package by putting the repository root on sys.path
REPO_PATH_SCRIPTS = [p for p in SCRIPTS if "sys.path.insert(0, str(ROOT))" in _text(p)]
#: scripts written to be executed (not imported), i.e. with a main() guard
GUARDED_SCRIPTS = [p for p in SCRIPTS if 'if __name__ == "__main__"' in _text(p)]

#: Third-party packages a script may legitimately use at module scope.  A *missing* one
#: means "this environment cannot run that script", not "this script requires the
#: solver" -- on a clean CI runner numpy is absent, and this test used to fail there.
#: The invariant it protects (importing a script never needs openEMS) is unchanged:
#: openEMS/CSXCAD are deliberately NOT in this set, so importing them still fails.
OPTIONAL_IMPORTS = frozenset({"numpy", "scipy", "matplotlib", "pyopencl", "PySide6", "skrf"})


class TestResearchScriptsArePortable(unittest.TestCase):
    def test_the_scripts_are_actually_there(self):
        self.assertGreaterEqual(len(SCRIPTS), 8, "expected the research scripts to be present")
        self.assertGreaterEqual(len(REPO_PATH_SCRIPTS), 8, "expected the repo-path scripts")
        self.assertGreaterEqual(len(GUARDED_SCRIPTS), 8, "expected main()-guarded scripts")

    def test_no_absolute_drive_paths(self):
        offenders = []
        for path in SCRIPTS:
            for number, line in enumerate(_text(path).splitlines(), start=1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if ABSOLUTE_DRIVE.search(stripped) and "__file__" not in stripped:
                    offenders.append(f"{path.name}:{number}: {stripped[:90]}")
        self.assertEqual(
            offenders,
            [],
            "research scripts must not hardcode absolute paths:\n" + "\n".join(offenders),
        )

    def test_root_is_derived_from_the_repository(self):
        for path in REPO_PATH_SCRIPTS:
            text = _text(path)
            self.assertIn(
                "__file__", text,
                f"{path.name} must derive ROOT from its own location, not from a fixed drive",
            )
            self.assertIn(
                "parents[1]", text,
                f"{path.name} must take parents[1] as the repository root",
            )

    def test_the_openems_launcher_is_inside_the_repository(self):
        """The scripts drive the solver through the committed launcher, not tools/."""
        launcher = REPO_ROOT / "scripts" / "run_with_openems.py"
        self.assertTrue(launcher.is_file(), "scripts/run_with_openems.py must exist")
        for path in SCRIPTS:
            text = _text(path)
            self.assertNotIn(
                '"tools" / "run_with_openems.py"', text,
                f"{path.name} points at tools/run_with_openems.py, which is not in the repository",
            )


class TestScriptsDoNotRequireTheSolverToImport(unittest.TestCase):
    """Importing a script must not need openEMS (they guard main() themselves)."""

    def test_modules_import_cleanly(self):
        import importlib.util

        for path in GUARDED_SCRIPTS:
            spec = importlib.util.spec_from_file_location(f"_yotta_{path.stem}", path)
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except SystemExit:  # pragma: no cover - a script that exits on import
                self.fail(f"{path.name} ran at import time instead of under main()")
            except ImportError as exc:
                missing = (getattr(exc, "name", None) or "").split(".")[0]
                if not missing:
                    # a hand-raised ImportError need not carry .name, so fall back to the
                    # message the import system writes: "No module named 'x'"
                    match = re.search(r"No module named '([^'.]+)", str(exc))
                    missing = match.group(1) if match else ""
                if missing in OPTIONAL_IMPORTS:
                    continue  # optional dependency absent: nothing to assert about it here
                raise
            self.assertTrue(
                hasattr(module, "ROOT") or hasattr(module, "main"),
                f"{path.name} exposes neither ROOT nor main()",
            )
            self.assertEqual(
                Path(getattr(module, "ROOT", REPO_ROOT)).resolve(),
                REPO_ROOT,
                f"{path.name} resolves its ROOT somewhere other than the repository",
            )


class TestScriptsCreateTheirOutputDirectories(unittest.TestCase):
    """A script must not assume `runs/` exists: it is gitignored, so a clean checkout has
    none.  Yotta's review found `scripts/gpu_benchmark.py` writing `runs/gpu_benchmark.json`
    without creating the directory, which fails with FileNotFoundError after all the work."""

    def test_gpu_benchmark_creates_its_output_directory_first(self):
        script = _text(REPO_ROOT / "scripts" / "gpu_benchmark.py")
        self.assertIn(
            "out.parent.mkdir(parents=True, exist_ok=True)",
            script,
            "gpu_benchmark.py must create runs/ before writing into it",
        )
        self.assertLess(
            script.index("out.parent.mkdir"),
            script.index("out.write_text"),
            "the directory has to be created before the file is written",
        )


if __name__ == "__main__":
    unittest.main()
