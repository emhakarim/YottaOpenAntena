"""Start the local web UI and (optionally) open a browser.

Usage:
    python scripts/start_webui.py [--port 8077] [--no-browser]

Sets OPENEMS_ROOT from ``tools/openEMS`` when that directory exists next to the repository
(the same layout ``run_with_openems.py`` uses), binds 127.0.0.1, and serves the page from
this process - offline, no external assets.  Refuses loudly when the port is taken by
another instance (Windows SO_REUSEADDR would otherwise split connections between two
servers and serve a stale page).
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # repo root (test_repo_paths convention)
sys.path.insert(0, str(ROOT))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="start_webui",
        description="start the OpenAntenna local web UI (offline, stdlib only)",
    )
    parser.add_argument("--port", type=int, default=8077)
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser")
    args = parser.parse_args(argv)

    tools_root = ROOT / "tools" / "openEMS"
    if tools_root.exists():
        os.environ.setdefault("OPENEMS_ROOT", str(tools_root))

    from openantenna.webui import make_server

    try:
        server = make_server("127.0.0.1", args.port)
    except OSError as exc:
        print("cannot bind 127.0.0.1:%d - %s" % (args.port, exc))
        print("another instance may already be running; stop it, or pass --port.")
        return 1
    url = "http://127.0.0.1:%d/" % args.port
    print("OpenAntenna web UI (offline, stdlib only) -> %s" % url)
    print("Ctrl+C to stop.")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
