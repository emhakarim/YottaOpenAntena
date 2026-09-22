"""Y-1: the reference table must judge every run against ONE reference type.

The tool lives outside the package (``yotta_tools/``) by the agreed work split, so
this test loads it by path and drives it on a synthetic run directory.  That keeps
the check honest: no solver, no stored data, fully reproducible in CI.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "yotta_tools" / "reference_table.py"

PROJECT = {
    "schema_version": 1,
    "kind": "openantenna.project",
    "name": "synthetic-run",
    "substrate": {"layers": [{"material": "PTFE", "thickness_m": 0.0016, "role": "dielectric"}]},
    "patch": {
        "width_m": 0.049142672841793994,
        "length_m": 0.041378916081297096,
        "feed_mode": "inset",
        "feed_inset_m": 0.01465780454343096,
    },
    "array": {"nx": 1, "ny": 1, "spacing_x_lambda0": 0.5, "spacing_y_lambda0": 0.5},
    "sweep": {"start_hz": 2.083e9, "stop_hz": 2.817e9, "points": 5},
}

S11_CSV = """freq_hz,s11_re,s11_im
2.280e9,-0.35,0.0
2.290e9,-0.30,0.0
2.300e9,-0.05,0.0
2.310e9,-0.15,0.0
2.320e9,-0.40,0.0
"""


def _load_tool():
    spec = importlib.util.spec_from_file_location("yotta_reference_table", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestReferenceTable(unittest.TestCase):
    def setUp(self):
        self.tool = _load_tool()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _make_run(self, name: str, *, csv: bool = True, converged: bool = True) -> Path:
        run = self.root / name
        run.mkdir(parents=True, exist_ok=True)
        (run / "project.json").write_text(json.dumps(PROJECT), encoding="utf-8")
        if csv:
            (run / "s11.csv").write_text(S11_CSV, encoding="utf-8")
        (run / "run_manifest.json").write_text(
            json.dumps({"mesh": {"converged": converged, "port_refine": True}}), encoding="utf-8"
        )
        return run

    def test_it_recomputes_the_same_reference_for_every_run(self):
        record = self.tool.load_run(self._make_run("run-a"))
        self.assertIsNotNone(record)
        # cavity prediction for THIS geometry (independent of any stored claim)
        self.assertAlmostEqual(record["cavity_hz"] / 1e9, 2.4007, delta=0.001)
        self.assertAlmostEqual(record["tl_hz"] / 1e9, 2.4500, delta=0.001)
        # measured = the minimum of the synthetic trace
        self.assertAlmostEqual(record["measured_hz"] / 1e9, 2.3000, delta=1e-9)
        self.assertAlmostEqual(record["delta_vs_cavity_pct"], -4.19, delta=0.05)
        self.assertTrue(record["converged"])

    def test_a_run_without_results_is_not_invented(self):
        record = self.tool.load_run(self._make_run("run-empty", csv=False))
        self.assertNotIn("measured_hz", record)
        self.assertNotIn("delta_vs_cavity_pct", record)

    def test_a_non_project_directory_is_skipped(self):
        plain = self.root / "not-a-run"
        plain.mkdir()
        self.assertIsNone(self.tool.load_run(plain))

    def test_verdict_flags_a_geometry_dependent_bias(self):
        runs = [self.tool.load_run(self._make_run("run-a")), self.tool.load_run(self._make_run("run-b"))]
        runs[1]["delta_vs_cavity_pct"] = -1.0  # 3 pp away from run-a's -4.19 %
        message = self.tool.verdict(runs)
        self.assertIn("BERGERAK", message)

    def test_verdict_accepts_a_constant_bias(self):
        runs = [self.tool.load_run(self._make_run("run-a")), self.tool.load_run(self._make_run("run-b"))]
        runs[1]["delta_vs_cavity_pct"] = runs[0]["delta_vs_cavity_pct"] - 0.2
        message = self.tool.verdict(runs)
        self.assertIn("KONSTAN", message)

    def test_collect_scans_a_directory_tree(self):
        self._make_run("run-a")
        self._make_run("run-b")
        records = self.tool.collect([self.root])
        self.assertEqual(sorted(r["run"] for r in records), ["run-a", "run-b"])

    def test_a_broken_run_becomes_an_error_row_not_a_crash(self):
        """One unreadable s11.csv must not take down the whole table."""
        run = self._make_run("run-broken", csv=False)
        (run / "s11.csv").write_text("freq_hz,s11_re\n2.400e9,\n", encoding="utf-8")
        records = self.tool.collect([self.root])
        self.assertEqual(len(records), 1)
        self.assertIn("error", records[0])
        self.assertIn("run-broken", records[0]["run"])


if __name__ == "__main__":
    unittest.main()
