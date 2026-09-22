"""Assemble an array S-matrix from per-port openEMS runs (Phase 2 #4).

Every run dumps `port_<n>.csv` for all element ports; the driven port is chosen with
`OPENANTENNA_EXCITE_PORT`.  One run therefore gives one column of S, S_ij = uf_ref(i)/uf_inc(j),
and N runs give the whole matrix - with the deck unchanged between runs.

The module also keeps the honest part: a missing per-port file is an error (never a zero,
which would fake perfect isolation) and every contributing run carries its convergence state,
because docs/convergence-policy.md forbids quoting a number from a run that did not converge.
Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

__all__ = ["load_port", "assemble", "coupling_summary"]

HEADER = ["freq_hz", "uf_inc_re", "uf_inc_im", "uf_ref_re", "uf_ref_im"]


def load_port(path: str | Path) -> Tuple[List[float], List[complex], List[complex]]:
    """Read a ``port_<n>.csv`` file -> (frequencies, uf_inc, uf_ref)."""
    freqs: List[float] = []
    inc: List[complex] = []
    ref: List[complex] = []
    with open(path, "r", encoding="utf-8") as handle:
        header = handle.readline().strip().split(",")
        if header != HEADER:
            raise ValueError(f"{path}: unexpected header {header}, expected {HEADER}")
        for line in handle:
            if not line.strip():
                continue
            parts = [float(x) for x in line.split(",")]
            freqs.append(parts[0])
            inc.append(complex(parts[1], parts[2]))
            ref.append(complex(parts[3], parts[4]))
    if not freqs:
        raise ValueError(f"{path}: no data rows")
    return freqs, inc, ref


def assemble(runs: Sequence[Tuple[Path, int]], n_ports: int) -> Dict[str, object]:
    """Assemble the S-matrix from ``(run_dir, driven_port)`` pairs."""
    if not runs:
        raise ValueError("no runs given")
    freqs: List[float] | None = None
    matrix: List[List[List[complex]]] = [[[] for _ in range(n_ports)] for _ in range(n_ports)]
    meta: List[Dict[str, object]] = []
    for run_dir, driven in runs:
        run_dir = Path(run_dir)
        if not 1 <= driven <= n_ports:
            raise ValueError(f"driven port {driven} outside 1..{n_ports}")
        converged = None
        runtime = None
        summary_path = run_dir / "run_summary.json"
        if summary_path.is_file():
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                converged = summary.get("converged")
                runtime = summary.get("runtime_s")
            except Exception:
                converged = None
        f_driven, inc_driven, _ref_driven = load_port(run_dir / f"port_{driven}.csv")
        for i in range(1, n_ports + 1):
            port_path = run_dir / f"port_{i}.csv"
            if not port_path.is_file():
                raise FileNotFoundError(
                    f"{port_path} missing: this run has no per-port dumps "
                    "(regenerate the model with element_ports=True)"
                )
            f_i, _inc_i, ref_i = load_port(port_path)
            if freqs is None:
                freqs = f_i
            elif len(f_i) != len(freqs):
                raise ValueError(f"{port_path}: {len(f_i)} points, expected {len(freqs)}")
            matrix[i - 1][driven - 1] = [
                r / inc if abs(inc) > 0 else complex(float("nan"))
                for r, inc in zip(ref_i, inc_driven)
            ]
        meta.append(
            {"run_dir": str(run_dir), "driven_port": driven, "converged": converged,
             "runtime_s": runtime, "points": len(f_driven)}
        )
    return {"freqs": freqs, "s": matrix, "runs": meta, "n_ports": n_ports}


def coupling_summary(result: Dict[str, object], index: int | None = None) -> Dict[str, float]:
    """|S11| minimum and the worst off-diagonal coupling, in dB, at one frequency index."""
    s = result["s"]
    freqs = result["freqs"]
    n = result["n_ports"]
    assert isinstance(freqs, list) and isinstance(s, list)
    if index is None:
        index = min(range(len(freqs)), key=lambda k: abs(s[0][0][k]))
    on = abs(s[0][0][index])
    off = max(abs(s[i][j][index]) for i in range(n) for j in range(n) if i != j)
    to_db = lambda v: 20.0 * math.log10(v) if v > 0 else float("-inf")
    return {
        "index": float(index),
        "frequency_hz": float(freqs[index]),
        "s11_db": to_db(on),
        "worst_coupling_db": to_db(off),
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assemble an array S-matrix from per-port runs.")
    parser.add_argument("--n-ports", type=int, required=True)
    parser.add_argument("--run", action="append", required=True, help="run directory (repeat per driven port)")
    parser.add_argument("--driven", type=int, action="append", required=True, help="excited port for the matching --run")
    args = parser.parse_args(argv)
    if len(args.run) != len(args.driven):
        print("error: --run and --driven must be given the same number of times", file=sys.stderr)
        return 1
    try:
        result = assemble(list(zip(args.run, args.driven)), args.n_ports)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for entry in result["runs"]:
        print(f"  run {entry['run_dir']} (driven port {entry['driven_port']}): "
              f"converged={entry['converged']}, runtime={entry['runtime_s']} s, {entry['points']} points")
    summary = coupling_summary(result)
    print(f"  |S11| minimum           : {summary['frequency_hz'] / 1e9:.4f} GHz, {summary['s11_db']:.2f} dB")
    print(f"  worst off-diagonal      : {summary['worst_coupling_db']:.2f} dB")
    if any(entry["converged"] is False for entry in result["runs"]):
        print("  NOTE: at least one contributing run did not converge; per "
              "docs/convergence-policy.md these numbers may not be quoted as results.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
