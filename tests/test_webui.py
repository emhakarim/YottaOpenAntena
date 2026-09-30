"""Endpoint tests for the local web UI (stdlib only, ephemeral port, no solver needed)."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from openantenna.webui import make_server  # noqa: E402


def _post(base, path, payload):
    request = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class TestWebUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server("127.0.0.1", 0)
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_the_page_is_served_and_stays_offline(self):
        with urllib.request.urlopen(self.base + "/", timeout=10) as response:
            self.assertEqual(response.status, 200)
            html = response.read().decode("utf-8")
        self.assertIn("OpenAntenna", html)
        # offline contract: the page must not pull anything from outside this process
        self.assertNotIn('src="http', html)
        self.assertNotIn('href="http', html)
        self.assertIn("127.0.0.1", html)
        for view in ("Modeling", "Simulate", "Results"):
            self.assertIn(view, html)

    def test_parameters_resolve_with_warnings_as_data(self):
        status, body = _post(
            self.base,
            "/api/resolve",
            {
                "parameters": [["L", "30"], ["W", "L / 2"], ["bad", "2 +"]],
                "expressions": ["L", "nope"],
            },
        )
        self.assertEqual(status, 200)
        self.assertAlmostEqual(body["values"]["W"], 15.0)
        self.assertIn("bad", body["errors"])
        self.assertAlmostEqual(body["evaluated"][0], 30.0)
        self.assertIsNone(body["evaluated"][1])
        self.assertTrue(body["evaluate_errors"][0])

    def test_dxf_export_round_trips_and_notes_skips(self):
        shapes = [
            {"kind": "block", "points": [[0, 0], [20, 0], [20, 10], [0, 10]], "thickness": "h_sub"},
            {"kind": "polyline", "points": [[0, 12], [5, 15]], "closed": False},
        ]
        status, body = _post(self.base, "/api/dxf", {"shapes": shapes, "layer": "sketch"})
        self.assertEqual(status, 200)
        self.assertIn("SECTION", body["dxf"])
        self.assertTrue(any("skipped" in note for note in body["notes"]))
        from openantenna.geometry.cad import read_dxf

        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "web.dxf"
            target.write_text(body["dxf"], encoding="utf-8")
            segments = read_dxf(target)
        self.assertEqual(len(segments), 4)

    def test_grid_view_rasterises(self):
        shapes = [{"kind": "block", "points": [[0, 0], [20, 0], [20, 10], [0, 10]], "thickness": "1.6"}]
        status, body = _post(self.base, "/api/grid", {"shapes": shapes, "cell_mm": 2.0})
        self.assertEqual(status, 200)
        self.assertEqual(body["cols"], 11)
        self.assertEqual(body["rows"], 6)
        self.assertGreater(body["stroke_fraction"], 0.0)
        self.assertTrue(any("1" in row for row in body["cells"]))

    def test_patch_synthesis_reports_numbers(self):
        status, body = _post(
            self.base,
            "/api/patch",
            {"frequency_ghz": 2.45, "epsilon_r": 2.1, "height_mm": 1.6, "feed": "inset"},
        )
        self.assertEqual(status, 200)
        self.assertGreater(body["width_mm"], 20.0)
        self.assertLess(body["width_mm"], 60.0)
        self.assertIsInstance(body["warnings"], list)

    def test_a_broken_polygon_is_an_error_not_a_500(self):
        shapes = [{"kind": "polyline", "points": [[0, 0], [10, 10], [10, 0], [0, 10]], "closed": True}]
        status, body = _post(self.base, "/api/dxf", {"shapes": shapes})
        self.assertEqual(status, 400)
        self.assertIn("skipped", body["error"])

    def test_generate_writes_a_deck_with_sketch_polygons(self):
        shapes = [{"kind": "block", "points": [[0, 0], [20, 0], [20, 10], [0, 10]], "thickness": "h_sub"}]
        with tempfile.TemporaryDirectory() as folder:
            rundir = Path(folder) / "web_run"
            status, body = _post(
                self.base,
                "/api/generate",
                {
                    "rundir": str(rundir),
                    "frequency_ghz": 2.45,
                    "material": "PTFE",
                    "height_mm": 1.6,
                    "feed": "probe",
                    "sweep_points": 51,
                    "shapes": shapes,
                },
            )
            self.assertEqual(status, 200, body)
            self.assertTrue((rundir / "sim.py").exists())
            self.assertTrue((rundir / "run_manifest.json").exists())
            self.assertEqual(body["sketch_polygons"], 1)
            manifest = json.loads((rundir / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["sketch_polygons"], 1)
            script = (rundir / "sim.py").read_text(encoding="utf-8")
            self.assertIn("AddPolygon", script)

    def test_run_refuses_without_a_generated_deck(self):
        with tempfile.TemporaryDirectory() as folder:
            status, body = _post(self.base, "/api/run", {"rundir": folder})
        self.assertEqual(status, 400)
        self.assertIn("generate", body["error"])

    def test_the_run_state_machine_with_an_injected_runner(self):
        from openantenna import webui as webui_module

        seen = []

        def fake_runner(rundir, solver_kwargs, on_progress, cancel_event):
            seen.append((str(rundir), solver_kwargs.get("max_timesteps")))
            snapshot = type(
                "Snap", (), {"timestep": 250, "energy_db": -35.0, "elapsed_s": 1.5}
            )()
            on_progress(snapshot)
            time.sleep(0.6)
            return {"resonance_hz": 2.45e9, "worst_match_db": -20.0, "vswr_at_resonance": 1.2}

        webui_module.set_run_runner(fake_runner)
        try:
            with tempfile.TemporaryDirectory() as folder:
                Path(folder, "sim.py").write_text("# stub\n", encoding="utf-8")
                status, first = _post(self.base, "/api/run", {"rundir": folder, "max_timesteps": 1000})
                self.assertEqual(status, 200, first)
                self.assertEqual(first["status"], "running")
                status, busy = _post(self.base, "/api/run", {"rundir": folder})
                self.assertEqual(status, 400)
                self.assertIn("already", busy["error"])
                deadline = time.time() + 6
                body = None
                while time.time() < deadline:
                    status, body = _post(self.base, "/api/run_status", {})
                    if body["status"] == "done":
                        break
                    time.sleep(0.1)
                self.assertIsNotNone(body)
                self.assertEqual(body["status"], "done")
                self.assertAlmostEqual(body["summary"]["resonance_hz"], 2.45e9)
                self.assertEqual(seen, [(folder, 1000)])
        finally:
            webui_module.set_run_runner(None)

    def test_results_reads_a_synthetic_run(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            (run / "s11.csv").write_text(
                "freq_hz,s11_re,s11_im\n"
                "2200000000,0.4,-0.1\n"
                "2450000000,0.05,-0.01\n"
                "2700000000,0.3,-0.2\n",
                encoding="utf-8",
            )
            (run / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "solver": "openEMS",
                        "generator_version": "test",
                        "boundary": "PML",
                        "substrate": {"material": "PTFE", "thickness_m": 1.6e-3},
                        "mesh": {
                            "cells_per_wavelength": 15,
                            "substrate_cells": 8,
                            "port_refine": True,
                            "converged": True,
                        },
                        "dielectric_loss": {"model": "kappa"},
                        "max_timesteps": 400000,
                        "warnings": [],
                    }
                ),
                encoding="utf-8",
            )
            status, body = _post(self.base, "/api/results", {"rundir": str(run)})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["points"], 3)
        self.assertAlmostEqual(body["resonance_ghz"], 2.45, places=6)
        self.assertEqual(body["provenance"]["substrate"], "PTFE")
        self.assertIsNone(body["farfield"])


    def test_solver_status_endpoint_reports_a_shape(self):
        status, body = _post(self.base, "/api/solver", {})
        self.assertEqual(status, 200)
        self.assertIsInstance(body["available"], bool)
        self.assertIn("detail", body)


    def test_an_injected_run_can_be_cancelled(self):
        from openantenna import webui as webui_module

        def fake_runner(rundir, solver_kwargs, on_progress, cancel_event):
            cancel_event.wait(5)
            raise webui_module._RunCancelled()

        webui_module.set_run_runner(fake_runner)
        try:
            with tempfile.TemporaryDirectory() as folder:
                Path(folder, "sim.py").write_text("# stub\n", encoding="utf-8")
                status, first = _post(self.base, "/api/run", {"rundir": folder})
                self.assertEqual(status, 200, first)
                status, body = _post(self.base, "/api/run_cancel", {})
                self.assertEqual(status, 200, body)
                self.assertEqual(body["status"], "cancelling")
                deadline = time.time() + 6
                body = None
                while time.time() < deadline:
                    status, body = _post(self.base, "/api/run_status", {})
                    if body["status"] == "cancelled":
                        break
                    time.sleep(0.1)
                self.assertIsNotNone(body)
                self.assertEqual(body["status"], "cancelled")
                status, body = _post(self.base, "/api/run_cancel", {})
                self.assertEqual(status, 400)
        finally:
            webui_module.set_run_runner(None)

    # --- canvas slice + review findings F1/F2 (2026-09-30) -----------------

    def test_a_non_object_json_body_is_a_clean_400(self):
        request = urllib.request.Request(
            self.base + "/api/generate",
            data=b"[1,2,3]",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                status, body = response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            status, body = exc.code, json.loads(exc.read().decode("utf-8"))
        self.assertEqual(status, 400)
        self.assertIn("JSON object", body["error"])

    def test_generate_accepts_a_feed_inset_override(self):
        with tempfile.TemporaryDirectory() as folder:
            rundir = Path(folder) / "web_override"
            status, body = _post(
                self.base,
                "/api/generate",
                {
                    "rundir": str(rundir),
                    "frequency_ghz": 2.45,
                    "material": "PTFE",
                    "height_mm": 1.6,
                    "feed": "inset",
                    "length_mm": 41.379,
                    "sweep_points": 51,
                    "feed_inset_mm": 5.0,
                    "feed_line_width_mm": 5.1,
                    "feed_x_offset_mm": 2.5,
                    "shapes": [],
                },
            )
            self.assertEqual(status, 200, body)
            project = json.loads((rundir / "project.json").read_text(encoding="utf-8"))
            self.assertAlmostEqual(project["patch"]["feed_inset_m"], 0.005, places=9)
            self.assertAlmostEqual(project["patch"]["feed_line_width_m"], 0.0051, places=9)
            self.assertAlmostEqual(project["patch"]["feed_x_offset_m"], 0.0025, places=9)

    def test_feed_inset_override_beyond_the_patch_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            status, body = _post(
                self.base,
                "/api/generate",
                {"rundir": str(Path(folder) / "over"), "length_mm": 41.0,
                 "feed_inset_mm": 99.0, "shapes": []},
            )
        self.assertEqual(status, 400)
        self.assertIn("must not exceed", body["error"])

    def test_a_lateral_offset_off_the_patch_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            status, body = _post(
                self.base,
                "/api/generate",
                {"rundir": str(Path(folder) / "off"), "width_mm": 49.14, "length_mm": 41.38,
                 "feed_x_offset_mm": 40.0, "shapes": []},
            )
        self.assertEqual(status, 400)
        self.assertIn("inside the patch width", body["error"])

    def test_the_deck_cap_is_read_from_the_manifest(self):
        from openantenna import webui as webui_module

        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            (run / "run_manifest.json").write_text(
                json.dumps({"max_timesteps": 12345}), encoding="utf-8"
            )
            self.assertEqual(webui_module._deck_cap(run), 12345)
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(webui_module._deck_cap(Path(folder)))

    def test_the_page_now_carries_the_drawing_canvas(self):
        with urllib.request.urlopen(self.base + "/", timeout=10) as response:
            html = response.read().decode("utf-8")
        self.assertNotIn("__MATERIALS__", html)
        for needle in ("onCanvasDown", "pfInset", "matSel", "MATERIALS = {", "Port &amp; feed"):
            self.assertIn(needle, html)


if __name__ == "__main__":
    unittest.main()
