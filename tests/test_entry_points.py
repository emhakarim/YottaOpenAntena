"""Guard the declared entry points: a console script that names a missing symbol only
fails after installation, which is exactly the kind of breakage a test should catch.
"""

from __future__ import annotations

import importlib
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"

#: name = "module:attribute" occurrences under any [project.*scripts] table
ENTRY_POINT = re.compile(r'^([a-z0-9][a-z0-9-]*)\s*=\s*"([\w.]+):(\w+)"', re.M)


class TestEntryPoints(unittest.TestCase):
    def test_the_cli_and_gui_scripts_are_declared(self):
        text = PYPROJECT.read_text(encoding="utf-8")
        self.assertIn('openantenna = "openantenna.cli:main"', text)
        self.assertIn('openantenna-gui = "openantenna.gui:main"', text)

    def test_every_declared_target_resolves_to_a_callable(self):
        text = PYPROJECT.read_text(encoding="utf-8")
        targets = [(m.group(2), m.group(3)) for m in ENTRY_POINT.finditer(text)]
        self.assertGreaterEqual(len(targets), 2, "expected the CLI and GUI entry points")
        for module_name, attribute in targets:
            with self.subTest(target=f"{module_name}:{attribute}"):
                module = importlib.import_module(module_name)
                self.assertTrue(
                    callable(getattr(module, attribute, None)),
                    f"{module_name}:{attribute} is not callable",
                )

    def test_the_gui_package_imports_without_pyside(self):
        """`openantenna.gui:main` must import lazily: PySide6 is an optional extra, and a
        console script that cannot even be imported is worse than no console script."""
        source = (REPO_ROOT / "openantenna" / "gui" / "__init__.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def main(", source)
        # the Qt import lives inside main(), not at module scope
        module_level = [
            line
            for line in source.splitlines()
            if line.startswith(("import ", "from ")) and "PySide6" in line
        ]
        self.assertEqual(module_level, [], module_level)


if __name__ == "__main__":
    unittest.main()
