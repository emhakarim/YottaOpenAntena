"""Endpoint tests for the local web UI prototype (stdlib only, ephemeral port)."""

from __future__ import annotations

import json
import sys
import threading
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
        import tempfile

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


if __name__ == "__main__":
    unittest.main()
