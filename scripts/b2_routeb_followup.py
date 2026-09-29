"""Step D of the optimization plan: give the overlap-sweep winner its Route B pair.

The sweep (step A) is screening only - its numbers are not quotable by themselves.  This driver
takes the provisional winner from ``runs_b2/overlap/winner.txt``, re-runs it at a larger timestep
cap (400k against the sweep's 300k - 25 % apart, Route B wants >= 5 %), and turns the two
cap-limited runs into a verdict via ``yotta_tools.two_setting_verdict`` (``--truncation-pair``).

    python scripts/b2_routeb_followup.py --run

Guard rails: refuses without a winner or without the sweep run's s11.csv; refuses out-of-range
deltas; skips the 400k engine run when its s11.csv already exists (idempotent) and goes straight
to the verdict; kills the process tree on timeout.  If the 400k run reaches the end criteria
while the sweep run was capped, the verdict reports "mixed stop conditions" - that is a rejected
pair under the policy, recorded as such.

Artifacts: ``runs_b2/overlap/followup/<tag>/`` (run dir + follow-up engine log), the pair verdict
JSON, and the sentinel ``runs_b2/overlap_followup_done.txt``.
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
from yotta_tools.two_setting_verdict import RunData, render, verdict  # noqa: E402

SWEEP_CAP = 300000  # the cap the sweep ran at (step A)
FOLLOWUP_CAP = 400000  # the second, larger cap for the Route B truncation pair


def delta_from_tag(tag: str) -> float:
    """m100 -> -1.0, p050 -> +0.5, p000 -> 0.0 (same convention as the sweep's tag_for)."""
    sign_char = tag[:1]
    rest = tag[1:]
    if sign_char not in ("m", "p") or not rest.isdigit():
        raise ValueError(f"unrecognised tag: {tag!r}")
    return (-1.0 if sign_char == "m" else 1.0) * int(rest) / 100.0


def read_winner(base_out: Path) -> tuple[str, float]:
    """Read the winner tag; take the delta from the sweep summary, falling back to the tag."""
    winner_file = base_out / "winner.txt"
    if not winner_file.is_file():
        raise FileNotFoundError(
            f"{winner_file} not found - the sweep has not picked a winner yet")
    tag = winner_file.read_text(encoding="utf-8").strip()
    if not tag:
        raise ValueError(f"{winner_file} is empty")
    summary_file = base_out / "sweep_summary.json"
    summary = json.loads(summary_file.read_text(encoding="utf-8-sig")) if summary_file.is_file() else {}
    row = next((r for r in summary.get("points", []) if r.get("tag") == tag), None)
    delta = float(row["delta_mm"]) if row and row.get("delta_mm") is not None else delta_from_tag(tag)
    if not -20.0 <= delta <= 20.0:
        raise ValueError(f"winner delta {delta} mm is outside the sane range")
    return tag, delta


def build_cmd(delta: float, out_dir: Path, max_ts: int, end_criteria: float) -> list[str]:
    """The b2 invocation for the follow-up run, identical to the sweep's per-point command."""
    return [
        sys.executable, str(ROOT / "scripts" / "b2_coplanar_ab_test.py"),
        "--out", str(out_dir), "--arm", "line", "--run",
        "--inset-delta-mm", str(delta),
        "--end-criteria", str(end_criteria), "--max-ts", str(max_ts),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", action="store_true", help="actually run the 400k point")
    parser.add_argument("--base-out", default=str(Path("runs_b2") / "overlap"))
    parser.add_argument("--max-ts", type=int, default=FOLLOWUP_CAP)
    parser.add_argument("--end-criteria", type=float, default=1e-4)
    parser.add_argument("--timeout-s", type=float, default=10800.0,
                        help="wall-clock limit; the process tree is killed on timeout")
    parser.add_argument("--force", action="store_true",
                        help="re-run even when the follow-up s11.csv exists")
    args = parser.parse_args(argv)

    base_out = Path(args.base_out)
    try:
        tag, delta = read_winner(base_out)
    except (OSError, ValueError) as exc:
        print(f"refusing: {exc}", file=sys.stderr)
        return 2

    sweep_run = base_out / tag / "line"
    follow_dir = base_out / "followup" / tag
    follow_run = follow_dir / "line"
    cmd = build_cmd(delta, follow_dir, args.max_ts, args.end_criteria)

    print(f"step D: winner {tag} (inset delta {delta:+.2f} mm)")
    print(f"  sweep run : {sweep_run} (cap {SWEEP_CAP})")
    print(f"  follow run: {follow_run} (cap {args.max_ts})")
    if not args.run:
        print("write-only mode (no --run); would execute:")
        print("  " + " ".join(cmd))
        return 0

    if not (sweep_run / "s11.csv").is_file():
        print(f"refusing: sweep run s11.csv missing in {sweep_run}", file=sys.stderr)
        return 2

    if (follow_run / "s11.csv").is_file() and not args.force:
        print(f"[{tag}] follow-up s11.csv already present - engine run skipped (idempotent)")
        exit_code = 0
    else:
        follow_dir.mkdir(parents=True, exist_ok=True)
        log_path = follow_dir / "followup.log"
        handle = log_path.open("w", encoding="utf-8")
        proc = subprocess.Popen(cmd, stdout=handle, stderr=subprocess.STDOUT, cwd=str(ROOT))
        print(f"[{tag}] started (pid {proc.pid}) -> {log_path}", flush=True)
        started = time.time()
        exit_code = None
        while exit_code is None:
            time.sleep(10.0)
            exit_code = proc.poll()
            elapsed = time.time() - started
            if exit_code is None and elapsed > args.timeout_s:
                method = kill_process_tree(proc)
                try:
                    exit_code = proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    exit_code = -999
                print(f"[{tag}] TIMEOUT after {elapsed:.0f}s - killed ({method})", flush=True)
        handle.close()
        print(f"[{tag}] finished exit={exit_code} ({time.time() - started:.0f}s)", flush=True)

    result: dict | None = None
    if exit_code == 0 or (follow_run / "s11.csv").is_file():
        try:
            a = RunData(sweep_run)
            b = RunData(follow_run)
        except (OSError, ValueError) as exc:
            print(f"verdict skipped: {exc}", file=sys.stderr)
        else:
            result = verdict(a, b, truncation_pair=True, differing_setting="truncation")
            out_json = base_out / "followup" / f"verdict_{tag}_sweep{SWEEP_CAP}_vs_{args.max_ts}.json"
            out_json.parent.mkdir(parents=True, exist_ok=True)
            out_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(render(result))
            print(f"\nwritten: {out_json}")

    state = "accepted" if (result and result["quotable"]) else ("rejected" if result else "none")
    sentinel = base_out.parent / "overlap_followup_done.txt"
    sentinel.write_text(f"tag={tag} exit={exit_code} verdict={state}\n", encoding="utf-8")
    print(f"sentinel: {sentinel}")
    return 0 if (exit_code == 0 and result is not None) else 1


if __name__ == "__main__":
    sys.exit(main())
