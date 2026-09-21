"""Application entry point: ``python -m openantenna.gui``."""

from __future__ import annotations

import sys

from .main_window import run_gui

if __name__ == "__main__":
    raise SystemExit(run_gui(sys.argv))
