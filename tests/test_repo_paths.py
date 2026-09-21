"""Guard against machine-specific absolute paths in the research scripts.

Review item S-1: every script under ``scripts/`` used to hardcode
``ROOT = Path(r"D:\\OpenAntenna")`` (plus an absolute ``OPENEMS_ROOT``), so the
evidence quoted in ``docs/verification.md`` could not be reproduced from the
repository by anybody else.  These tests keep that from coming back.

They are deliberately textual: the scripts drive an external solver and cannot be
executed in CI, but their *portability* can still be pinned.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = sorted((REPO_ROOT / "scripts").glob("*.py"))

#: an absolute Windows drive path such as D:\OpenAntenna (not "http://...")
ABSOLUTE_DRIVE = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]")


class TestResearchScriptsArePortable(unittest.TestCase):
    def test_the_scripts_are_actually_there(self):
        self.assertGreaterEqual(len(SCRIPTS), 8, "expected the research scripts to be present")

    def test_no_absolute_drive_paths(self):
        offenders = []
        for path in SCRIPTS:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
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
        for path in SCRIPTS:
            text = path.read_text(encoding="utf-8")
            self.assertIn(
                "__file__", text,
                f"{path.name} must derive ROOT from its own location, not from a fixed drive",
            )
            self.assertIn(
                "parents[1]", text,
                f"{path.name} must take parents[1] as the repository root",
            )


class TestScriptsDoNotRequireTheSolverToImport(unittest.TestCase):
    """Importing a script must not need openEMS (they guard main() themselves)."""

    def test_modules_import_cleanly(self):
        import importlib.util

        for path in SCRIPTS:
            spec = importlib.util.spec_from_file_location(f"_yotta_{path.stem}", path)
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except SystemExit:  # pragma: no cover - a script that exits on import
                self.fail(f"{path.name} ran at import time instead of under main()")
            self.assertTrue(
                hasattr(module, "ROOT") or hasattr(module, "main"),
                f"{path.name} exposes neither ROOT nor main()",
            )
            self.assertEqual(
                Path(getattr(module, "ROOT", REPO_ROOT)).resolve(),
                REPO_ROOT,
                f"{path.name} resolves its ROOT somewhere other than the repository",
            )


if __name__ == "__main__":
    unittest.main()
