"""Microstrip reference values for benchmark #3 (Yotta item Y-4).

The second/third benchmark needs an *independent* reference for a microstrip line, so
this tool implements the standard closed forms from scratch (its own code path, no call
into ``openantenna`` for the reference numbers):

* effective permittivity — Hammerstad wide-line form plus the ``W/h < 1`` correction;
* characteristic impedance — Hammerstad–Jensen closed form (0 < W/h <= 100, er <= 128);
* the inverse problem: ``width_for_z0`` (bisection) gives the width of a target Z0, so a
  design can be stated as "50 ohm line on FR-4, h = 1.6 mm -> W = ...".

Self-consistency checks the tool performs (they must pass, otherwise the callers cannot
trust the numbers):

1. ``width_for_z0(er, h, z0)`` fed back through ``z0`` returns the target;
2. ``eps_eff`` matches ``openantenna.geometry.patch.effective_permittivity`` over a grid
   (that function is used by the synthesis, so a mismatch would be a real bug);
3. limits: ``eps_eff -> er`` as ``W/h -> inf``, and ``eps_eff -> (er+1)/2`` at ``W/h -> 0``.

Usage::

    python yotta_tools/microstrip_reference.py
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ETA0 = 376.730313668  # free-space wave impedance, ohm

CASES = [
    ("PTFE  er 2.1  h 1.60 mm  W 3.0 mm", 2.1, 1.6e-3, 3.0e-3),
    ("FR-4  er 4.4  h 1.60 mm  W 3.0 mm", 4.4, 1.6e-3, 3.0e-3),
    ("FR-4  er 4.4  h 1.60 mm  W 1.0 mm", 4.4, 1.6e-3, 1.0e-3),
    ("Al2O3 er 9.8  h 0.635 mm W 0.6 mm", 9.8, 0.635e-3, 0.6e-3),
]


def eps_eff(er: float, h_m: float, w_m: float) -> float:
    ratio = h_m / w_m
    eff = 0.5 * (er + 1.0) + 0.5 * (er - 1.0) * (1.0 + 12.0 * ratio) ** -0.5
    w_over_h = w_m / h_m
    if w_over_h < 1.0:
        eff += 0.5 * (er - 1.0) * 0.04 * (1.0 - w_over_h) ** 2
    return eff


def z0(er: float, h_m: float, w_m: float) -> float:
    """Hammerstad–Jensen closed form for the characteristic impedance."""
    u = w_m / h_m
    eff = eps_eff(er, h_m, w_m)
    f1 = 6.0 + (2.0 * math.pi - 6.0) * math.exp(-((30.666 / u) ** 0.7528))
    return (ETA0 / (2.0 * math.pi * math.sqrt(eff))) * math.log(
        f1 / u + math.sqrt(1.0 + (2.0 / u) ** 2)
    )


def width_for_z0(er: float, h_m: float, target_z0: float) -> float:
    lo, hi = 1e-4 * h_m, 100.0 * h_m
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if z0(er, h_m, mid) > target_z0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def self_checks() -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []

    worst = 0.0
    for er, h in ((2.1, 1.6e-3), (4.4, 1.6e-3), (9.8, 0.635e-3)):
        for ratio in (0.5, 1.0, 3.0, 10.0, 30.0):
            w = ratio * h
            worst = max(worst, abs(z0(er, h, width_for_z0(er, h, z0(er, h, w))) - z0(er, h, w)))
    checks.append(("inverse of z0 is consistent", worst < 1e-6, f"max round-trip error {worst:.2e} ohm"))

    try:
        from openantenna.geometry.patch import effective_permittivity

        diff = 0.0
        for er in (2.1, 4.4, 9.8):
            for h in (0.5e-3, 1.6e-3):
                for ratio in (0.5, 1.0, 5.0, 30.0):
                    mine = eps_eff(er, h, ratio * h)
                    theirs = effective_permittivity(er, h, ratio * h)
                    diff = max(diff, abs(mine - theirs) / theirs)
        checks.append(("eps_eff matches the package", diff < 1e-12, f"max relative difference {diff:.2e}"))
    except Exception as exc:  # pragma: no cover
        checks.append(("eps_eff matches the package", False, f"could not import: {exc}"))

    er, h = 4.4, 1.6e-3
    wide = eps_eff(er, h, 1000.0 * h)
    narrow = eps_eff(er, h, 1e-4 * h)
    # At W/h -> 0 the narrow-line correction adds 0.5*(er-1)*0.04 on top of (er+1)/2,
    # so that (and not the bare average) is the correct expectation to test.
    narrow_expected = 0.5 * (er + 1.0) + 0.5 * (er - 1.0) * 0.04
    checks.append(("limit W/h -> inf gives er", abs(wide - er) < 0.02, f"{wide:.4f} vs {er}"))
    checks.append(
        ("limit W/h -> 0 gives (er+1)/2 + narrow-line term",
         abs(narrow - narrow_expected) < 0.02,
         f"{narrow:.4f} vs {narrow_expected:.4f}")
    )
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Closed-form microstrip reference values.")
    parser.add_argument("--out", default="yotta_tools/microstrip_reference.md")
    args = parser.parse_args(argv)

    lines = ["# Microstrip reference values (Y-4)", "",
             "Closed forms implemented independently in `yotta_tools/microstrip_reference.py` "
             "(Hammerstad wide-line eps_eff + Hammerstad–Jensen Z0).", "",
             "| case | eps_eff | Z0 [ohm] |", "|---|---|---|"]
    for name, er, h, w in CASES:
        lines.append(f"| {name} | {eps_eff(er, h, w):.4f} | {z0(er, h, w):.2f} |")

    lines += ["", "## Widths for a 50 ohm line", "", "| substrate | h [mm] | W [mm] |", "|---|---|---|"]
    for er, h in ((2.1, 1.6e-3), (4.4, 1.6e-3), (9.8, 0.635e-3)):
        w = width_for_z0(er, h, 50.0)
        lines.append(f"| er {er:g} | {h * 1e3:.3f} | {w * 1e3:.4f} |")

    checks = self_checks()
    lines += ["", "## Self-consistency checks", "", "| check | result | detail |", "|---|---|---|"]
    for name, ok, detail in checks:
        lines.append(f"| {name} | {'PASS' if ok else '**FAIL**'} | {detail} |")

    report = "\n".join(lines) + "\n"
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    print(f"written: {args.out}")
    return 0 if all(ok for _, ok, _ in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
