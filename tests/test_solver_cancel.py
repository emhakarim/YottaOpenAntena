"""Cancellation test at the adapter level: a real subprocess, stopped by the event."""

from __future__ import annotations

import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from openantenna.solvers.base import SolverAdapter  # noqa: E402


class TestExecuteCancel(unittest.TestCase):
    def test_cancel_event_stops_the_process_and_reports_cancelled(self):
        script = (
            "import sys, time\n"
            "for index in range(400):\n"
            "    print('TS %d' % index)\n"
            "    sys.stdout.flush()\n"
            "    time.sleep(0.05)\n"
        )
        cancel = threading.Event()

        def cancel_soon():
            time.sleep(0.7)
            cancel.set()

        threading.Thread(target=cancel_soon, daemon=True).start()
        with tempfile.TemporaryDirectory() as folder:
            run = SolverAdapter._execute(
                [sys.executable, "-u", "-c", script],
                Path(folder),
                timeout_s=None,
                cancel_event=cancel,
            )
        self.assertEqual(run.status, "cancelled")
        self.assertIn("cancelled", run.log)
        self.assertIsNotNone(run.duration_s)
        self.assertLess(run.duration_s, 15.0)

    def test_a_run_that_finishes_before_the_event_is_not_cancelled(self):
        cancel = threading.Event()
        with tempfile.TemporaryDirectory() as folder:
            run = SolverAdapter._execute(
                [sys.executable, "-u", "-c", "print('done')"],
                Path(folder),
                timeout_s=None,
                cancel_event=cancel,
            )
        self.assertEqual(run.status, "ok")
        self.assertIn("done", run.log)


if __name__ == "__main__":
    unittest.main()
