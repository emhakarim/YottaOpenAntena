"""Desktop GUI for OpenAntenna Studio.

The GUI is a *client* of the package: it calls the same functions the CLI calls
and never reaches into generated solver scripts.  Form factor is a desktop
application (Qt via PySide6) rather than a web dashboard, because the workflow is
local and compute-heavy: the FDTD solver runs as a local subprocess, the 3-D and
S-parameter views are native plots, and there is no server to deploy or secure.

Run it with:

    python -m openantenna.gui
"""

from __future__ import annotations

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    from .main_window import run_gui

    return run_gui(argv)
