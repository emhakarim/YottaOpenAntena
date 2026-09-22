"""One-command live status of the heavy runs.

Scans every ``runs/batch_*/run.stdout.log`` (the sequential queue's jobs) plus any extra
engine logs passed with ``--log``, pulls the last timestep / speed out of the openEMS
output, and prints one table. Also writes ``runs/status_snapshot.json`` so the state can
be read later without this tool.

Why this exists: the pyopenEMS extension runs the C++ engine *inside* the python process,
so there is no ``openEMS.exe`` to count - the only reliable progress signal is the engine's
own log lines. (Both wrong probes tried before are documented in docs/heavy-run-queue.md.)

Usage:
    python yotta_tools/status_snapshot.py
    python yotta_tools/status_snapshot.py --log path\\to\\b2_e3.out.log --log path\\to\\e4.out.log
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TIMESTEP_RE = re.compile(r"Timestep:\s*([\d,]+)")
SPEED_RE = re.compile(r"Speed:\s*([\d.]+)\s*MC/s")
B2_STEP_RE = re.compile(r"step\s+([\d,]+)/([\d,]+)")
B2_SPEED_RE = re.compile(r"([\d.]+)\s*MCells/s")
B2_ETA_RE = re.compile(r"(\d+h\d+m|\d+m\d+s)\s+more")


def tail_lines(path: Path, count: int = 60) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-count:]
    except OSError:
        return []


def engine_state(lines: list[str]) -> dict[str, object]:
    """Last timestep / speed seen in an openEMS engine log (queue-generated runs)."""
    step: int | None = None
    speed: float | None = None
    for line in lines:
        if match := TIMESTEP_RE.search(line):
            step = int(match.group(1).replace(",", ""))
        if match := SPEED_RE.search(line):
            speed = float(match.group(1))
    return {"step": step, "speed_mc_s": speed}


def b2_state(lines: list[str]) -> dict[str, object]:
    """Last progress line from a parallel_batch-driven engine log (the B2 batches)."""
    step: int | None = None
    cap: int | None = None
    speed: float | None = None
    eta: str | None = None
    for line in lines:
        if match := B2_STEP_RE.search(line):
            step = int(match.group(1).replace(",", ""))
            cap = int(match.group(2).replace(",", ""))
        if match := B2_SPEED_RE.search(line):
            speed = float(match.group(1))
        if match := B2_ETA_RE.search(line):
            eta = match.group(1)
    return {"step": step, "cap": cap, "speed_mc_s": speed, "eta_left": eta}


def pct(step: int | None, cap: int | None) -> str:
    if not step or not cap:
        return "-"
    return f"{100.0 * step / cap:.1f} %"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--log", action="append", default=[],
                        help="extra engine log to report (repeatable), e.g. the B2 batches")
    args = parser.parse_args(argv)

    rows: list[dict[str, object]] = []
    for log in sorted(REPO.glob("runs/batch_*/run.stdout.log")):
        state = engine_state(tail_lines(log))
        if state["step"] is None:
            continue
        cap = 400_000  # the queue's converged-setting cap; 1e-3 jobs stop earlier on their own
        rows.append({
            "run": log.parent.name, "step": state["step"], "cap": cap,
            "progress": pct(state["step"], cap),
            "speed_mc_s": state["speed_mc_s"],
            "source": str(log),
        })
    for raw in args.log:
        path = Path(raw)
        state = b2_state(tail_lines(path))
        if state["step"] is None:
            continue
        rows.append({
            "run": path.stem.replace(".out", ""), "step": state["step"], "cap": state["cap"],
            "progress": pct(state["step"], state["cap"]),
            "speed_mc_s": state["speed_mc_s"], "eta_left": state["eta_left"],
            "source": str(path),
        })

    snapshot = {
        "generated_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "note": "progress is relative to the timestep cap; a run may finish earlier via EndCriteria",
        "runs": rows,
    }
    out = REPO / "runs" / "status_snapshot.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    print(f"live status ({snapshot['generated_utc']}):")
    for row in rows:
        speed = row.get("speed_mc_s")
        eta = f"  sisa ~{row['eta_left']}" if row.get("eta_left") else ""
        print(f"  {row['run']:<26} {row['progress']:>7}  "
              f"step {row['step']}/{row['cap']}  "
              f"{speed if speed else '-'} MC/s{eta}")
    if not rows:
        print("  (no engine progress lines found - nothing is running, or logs are elsewhere)")
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
