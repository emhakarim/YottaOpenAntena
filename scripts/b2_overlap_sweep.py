"""Overlap sweep for the B2 line feed (docs/optimization-plan.md, step A).

Runs the line arm at several inset-depth offsets, each point in its own run directory, up to
``--workers`` at a time.  Defaults match the campaign plan: cap 300k at EndCriteria 1e-4, points
at -1.0 / -0.5 / 0 / +0.5 / +1.0 mm around the synthesised inset.  After the points finish, each
result is read back from its ``s11.csv``; a summary JSON and a ``winner.txt`` are written.  The
winner rule (plan step A): the deepest |S11| whose resonance sits inside [2.40, 2.50] GHz.

The sweep is **screening**: its numbers are NOT quotable by themselves.  The winner still needs
its Route B truncation pair (step D of the plan).

    python scripts/b2_overlap_sweep.py --run --deltas=-1.0,-0.5,0,0.5,1.0 --workers 2
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from yotta_tools.heavy_queue import kill_process_tree  # noqa: E402  (path set above)

DEFAULT_DELTAS = (-1.0, -0.5, 0.0, 0.5, 1.0)
WIN_BAND_GHZ = (2.40, 2.50)


def tag_for(delta_mm: float) -> str:
    """Directory tag for a delta: -1.0 -> m100, -0.5 -> m050, 0 -> p000, +0.5 -> p050."""
    hundredths = int(round(abs(delta_mm) * 100))
    return ("m" if delta_mm < 0 else "p") + f"{hundredths:03d}"


def parse_deltas(text: str) -> tuple[float, ...]:
    pieces = [piece.strip() for piece in text.split(",")]
    return tuple(float(piece) for piece in pieces if piece)


def pick_winner(rows: list[dict], band: tuple[float, float] = WIN_BAND_GHZ) -> dict | None:
    """Deepest |S11| among rows whose resonance is inside the band; None when nobody qualifies."""
    candidates = [
        row for row in rows
        if row.get("resonance_ghz") is not None
        and row.get("s11_db") is not None
        and band[0] <= row["resonance_ghz"] <= band[1]
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda row: row["s11_db"])


def read_point(out_dir: Path) -> dict:
    """Read one finished point back: resonance, depth, convergence state."""
    from yotta_tools.two_setting_verdict import RunData

    run = RunData(out_dir / "line")
    return {
        "resonance_ghz": round(run.resonance_hz / 1e9, 4),
        "s11_db": run.s11_db[run.min_index],
        "vswr": run.vswr[run.min_index],
        "converged": run.converged,
        "timesteps": run.timesteps,
        "index": run.min_index,
        "samples": len(run.freq_hz),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", action="store_true", help="actually run the decks")
    parser.add_argument("--deltas", default=",".join(str(d) for d in DEFAULT_DELTAS),
                        help="inset offsets in mm, comma separated (default: campaign plan)")
    parser.add_argument("--base-out", default=str(Path("runs_b2") / "overlap"))
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--end-criteria", type=float, default=1e-4)
    parser.add_argument("--max-ts", type=int, default=300000)
    parser.add_argument("--timeout-s", type=float, default=7200.0,
                        help="per-point wall-clock limit; the process tree is killed on timeout")
    parser.add_argument("--force", action="store_true",
                        help="re-run points that already have an s11.csv")
    args = parser.parse_args(argv)

    deltas = parse_deltas(args.deltas)
    base_out = Path(args.base_out)
    base_out.mkdir(parents=True, exist_ok=True)
    logs = base_out / "logs"
    logs.mkdir(exist_ok=True)

    pending = []
    for delta in deltas:
        tag = tag_for(delta)
        out_dir = base_out / tag
        if (out_dir / "line" / "s11.csv").is_file() and not args.force:
            print(f"[{tag}] s11.csv already present - skipped (idempotent)")
            continue
        pending.append({"tag": tag, "delta_mm": delta, "out_dir": out_dir})

    print(f"sweep: {len(pending)} point(s) to run, {args.workers} worker(s), "
          f"cap {args.max_ts}, EndCriteria {args.end_criteria:g}, band {WIN_BAND_GHZ[0]}-{WIN_BAND_GHZ[1]} GHz")
    for point in pending:
        print(f"  plan {point['tag']}: inset delta {point['delta_mm']:+.2f} mm -> {point['out_dir']}")
    if not args.run:
        print("write-only mode (no --run); nothing executed.")
        return 0

    running: list[dict] = []
    failures: list[str] = []
    while pending or running:
        while pending and len(running) < args.workers:
            point = pending.pop(0)
            cmd = [
                sys.executable, str(ROOT / "scripts" / "b2_coplanar_ab_test.py"),
                "--out", str(point["out_dir"]), "--arm", "line", "--run",
                "--inset-delta-mm", str(point["delta_mm"]),
                "--end-criteria", str(args.end_criteria), "--max-ts", str(args.max_ts),
            ]
            log_path = logs / f"{point['tag']}.log"
            handle = log_path.open("w", encoding="utf-8")
            proc = subprocess.Popen(cmd, stdout=handle, stderr=subprocess.STDOUT, cwd=str(ROOT))
            point.update({"proc": proc, "log": log_path, "handle": handle, "started": time.time()})
            running.append(point)
            print(f"[{point['tag']}] started (pid {proc.pid}) -> {log_path}", flush=True)

        time.sleep(5.0)
        for point in list(running):
            proc = point["proc"]
            code = proc.poll()
            elapsed = time.time() - point["started"]
            if code is None and elapsed > args.timeout_s:
                method = kill_process_tree(proc)
                failures.append(f"{point['tag']} (timeout)")
                try:
                    code = proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    code = -999
                print(f"[{point['tag']}] TIMEOUT after {elapsed:.0f}s - killed ({method})", flush=True)
            if code is not None:
                point["handle"].close()
                running.remove(point)
                print(f"[{point['tag']}] finished exit={code} ({elapsed:.0f}s)", flush=True)

    rows = []
    for delta in deltas:
        tag = tag_for(delta)
        out_dir = base_out / tag
        row: dict = {"tag": tag, "delta_mm": delta, "out_dir": str(out_dir)}
        try:
            row.update(read_point(out_dir))
        except (OSError, ValueError) as exc:
            row.update({"resonance_ghz": None, "s11_db": None, "error": str(exc)})
        rows.append(row)

    winner = pick_winner(rows)
    summary = {
        "what": "B2 line-feed overlap sweep (optimization plan step A) - screening only",
        "caps": {"max_ts": args.max_ts, "end_criteria": args.end_criteria},
        "win_band_ghz": list(WIN_BAND_GHZ),
        "points": rows,
        "winner": winner,
        "failed": failures,
        "note": "sweep numbers are not quotable; the winner needs its Route B pair (step D)",
    }
    summary_path = base_out / "sweep_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"summary: {summary_path}")
    if winner:
        (base_out / "winner.txt").write_text(winner["tag"] + "\n", encoding="utf-8")
        print(f"provisional winner: {winner['tag']} (f {winner['resonance_ghz']} GHz, "
              f"|S11| {winner['s11_db']:.2f} dB)")
    else:
        print("no point inside the win band - no winner.")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
