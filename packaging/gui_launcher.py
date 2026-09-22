"""Entry script for the frozen GUI build.

PyInstaller needs a real script to analyse, and this one keeps the frozen entry point
identical to the installed console script: it calls ``openantenna.gui:main``, nothing more.
"""

from __future__ import annotations

import sys

from openantenna.gui import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
