"""Run every example as a subprocess - an example that rots becomes a test failure."""

from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXAMPLES = sorted((ROOT / "examples").glob("*.py"))


class TestExamples(unittest.TestCase):
    def test_there_are_examples_to_run(self):
        self.assertGreaterEqual(len(EXAMPLES), 3)

    def test_every_example_runs_clean(self):
        for example in EXAMPLES:
            with self.subTest(example=example.name):
                completed = subprocess.run(
                    [sys.executable, str(example)],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    f"{example.name} exited {completed.returncode}\n{completed.stdout[-600:]}"
                    f"\n{completed.stderr[-600:]}",
                )


if __name__ == "__main__":
    unittest.main()
