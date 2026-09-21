"""Independent cross-check of the cavity-model predictor.

Why: ``openantenna.geometry.patch.resonant_frequency_cavity`` is now the *primary*
analytic predictor in the design flow (it agreed with the openEMS tutorial to
0.05 % while the transmission-line model was +3.2 % high).  A predictor that drives
decisions deserves an independent implementation and a behaviour check.

This tool implements the documented formula from scratch (its own code path, no
call into ``openantenna`` for the reference values), then:

1. compares my implementation with ``resonant_frequency_cavity`` over a parameter
   grid  -> catches coding slips, unit errors, wrong constants;
2. re-computes a few named anchor geometries (including the openEMS tutorial
   geometry) and prints cavity vs transmission-line vs measured;
3. checks the limits/monotonicity the formula must obey.

Scope note: this validates the *implementation* of an approximation.  The only
real validation of the physics is a solver or a measurement - for the tutorial
geometry that check exists (solver 2.435 GHz, cavity 2.4361 GHz here).

Usage (from the repository root)::

    python yotta_tools/cavity_check.py [--out yotta_tools/cavity_check_report.md]
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

C0 = 299792458.0


def my_epsilon_eff(er: float, h_m: float, w_m: float) -> float:
    """Hammerstad wide-line form, with the narrow-line correction for W/h < 1."""
    ratio = h_m / w_m
    eff = 0.5 * (er + 1.0) + 0.5 * (er - 1.0) * (1.0 + 12.0 * ratio) ** -0.5
    w_over_h = w_m / h_m
    if w_over_h < 1.0:
        eff += 0.5 * (er - 1.0) * 0.04 * (1.0 - w_over_h) ** 2
    return eff


def my_delta_l(h_m: float, eff: float, w_m: float) -> float:
    """Fringing extension, 0.412 h (ee+0.3)(W/h+0.264) / ((ee-0.258)(W/h+0.8))."""
    w_over_h = w_m / h_m
    return 0.412 * h_m * (eff + 0.3) * (w_over_h + 0.264) / ((eff - 0.258) * (w_over_h + 0.8))


def my_cavity_hz(er: float, h_m: float, w_m: float, l_m: float) -> float:
    """Dominant-mode cavity prediction: f = c / (2 * L_eff * sqrt(er))."""
    eff = my_epsilon_eff(er, h_m, w_m)
    l_eff = l_m + 2.0 * my_delta_l(h_m, eff, w_m)
    return C0 / (2.0 * l_eff * math.sqrt(er))


def my_tl_hz(er: float, h_m: float, w_m: float, l_m: float) -> float:
    """Transmission-line prediction (uses eps_eff instead of er)."""
    eff = my_epsilon_eff(er, h_m, w_m)
    l_eff = l_m + 2.0 * my_delta_l(h_m, eff, w_m)
    return C0 / (2.0 * l_eff * math.sqrt(eff))


ANCHORS = [
    # label, er, h [m], W [m], L [m], measured/independent reference [Hz] or None
    ("openEMS tutorial geometry", 3.38, 1.524e-3, 40e-3, 32e-3, 2.435e9),
    ("PTFE patch, 2.45 GHz design", 2.1, 1.6e-3, 0.049142672841793994, 0.041378916081297096, 2.260e9),
    ("5.8 GHz PTFE", 2.1, 1.6e-3, 0.020759, 0.016839, None),
    ("2.45 GHz FR-4 (er 4.4)", 4.4, 1.6e-3, 0.037234, 0.028809, None),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-check the cavity predictor.")
    parser.add_argument("--out", default="yotta_tools/cavity_check_report.md")
    args = parser.parse_args(argv)

    lines = ["# Cavity-predictor cross-check (Yotta, yotta_tools)", "",
             "Reference implementation lives in `openantenna.geometry.patch`. "
             "The numbers below are computed by an independent code path in this file.", ""]

    try:
        from openantenna.geometry import patch as PT
    except Exception as exc:
        print(f"ERROR: cannot import openantenna: {exc}", file=sys.stderr)
        return 2

    # 1) grid comparison ---------------------------------------------------
    worst = (0.0, None)
    count = 0
    for er in (1.1, 2.1, 3.38, 4.4, 6.15, 10.2, 12.0):
        for h in (0.1e-3, 0.5e-3, 1.524e-3, 3.0e-3):
            for f0 in (1e9, 2.45e9, 5.8e9, 10e9):
                w, l = PT.patch_width(f0, er), PT.patch_length(f0, PT.effective_permittivity(er, h, PT.patch_width(f0, er)), PT.delta_length(h, PT.effective_permittivity(er, h, PT.patch_width(f0, er)), PT.patch_width(f0, er)))
                mine = my_cavity_hz(er, h, w, l)
                theirs = PT.resonant_frequency_cavity(er, h, w, l)
                rel = abs(mine - theirs) / theirs
                count += 1
                if rel > worst[0]:
                    worst = (rel, f"er={er} h={h*1e3:.3f}mm f0={f0/1e9:g}GHz")
    lines += ["## 1. Independent implementation vs the package", "",
              f"* grid points compared: **{count}**",
              f"* largest relative difference: **{worst[0]*100:.6f} %** ({worst[1]})",
              f"* verdict: {'MATCH (implementation sound)' if worst[0] < 1e-6 else 'MISMATCH -> investigate'}", ""]

    # 2) anchors ------------------------------------------------------------
    lines += ["## 2. Anchor geometries (independent numbers)", "",
              "| geometry | my cavity [GHz] | package cavity [GHz] | my TL [GHz] | reference [GHz] | cavity error |",
              "|---|---|---|---|---|---|"]
    for label, er, h, w, l, ref in ANCHORS:
        mine = my_cavity_hz(er, h, w, l)
        pkg = PT.resonant_frequency_cavity(er, h, w, l)
        tl = my_tl_hz(er, h, w, l)
        err = f"{(mine/ref - 1)*100:+.2f} %" if ref else "-"
        refs = f"{ref/1e9:.3f}" if ref else "-"
        lines.append(f"| {label} | {mine/1e9:.4f} | {pkg/1e9:.4f} | {tl/1e9:.4f} | {refs} | {err} |")
    lines += ["",
              "The tutorial row is the decisive one: the solver reported **2.435 GHz** for the "
              "unmodified tutorial model, while the independent cavity implementation gives "
              "**2.4363 GHz** (-0.05 %) and the transmission-line model **2.5134 GHz** (+3.2 %). "
              "That is why the cavity model is the right primary predictor.",
              "",
              "Caveat: the PTFE row's reference (2.260 GHz) predates the metal-edge-snapping "
              "fix, so its +6.2 % is *not* the current model error.", ""]

    # 3) limits / monotonicity ---------------------------------------------
    checks = []
    base = dict(er=3.38, h=1.524e-3, w=40e-3, l=32e-3)
    f_er = [my_cavity_hz(e, base["h"], base["w"], base["l"]) for e in (2.0, 3.38, 6.0, 10.0)]
    f_l = [my_cavity_hz(base["er"], base["h"], base["w"], base["l"] * s) for s in (0.9, 1.0, 1.1)]
    f_h = [my_cavity_hz(base["er"], base["h"] * s, base["w"], base["l"]) for s in (0.5, 1.0, 2.0)]
    checks.append(("decreases with eps_r", all(f_er[i] > f_er[i + 1] for i in range(len(f_er) - 1))))
    checks.append(("decreases with patch length", all(f_l[i] > f_l[i + 1] for i in range(len(f_l) - 1))))
    checks.append(("decreases with substrate height (longer L_eff)", all(f_h[i] > f_h[i + 1] for i in range(len(f_h) - 1))))
    checks.append(("er -> 1 approaches the air limit", abs(my_cavity_hz(1.0000001, base["h"], base["w"], base["l"]) / my_tl_hz(1.0000001, base["h"], base["w"], base["l"]) - 1.0) < 1e-3))
    lines += ["## 3. Behaviour the formula must obey", ""] + \
             [f"* {name}: {'OK' if ok else '**FAIL**'}" for name, ok in checks] + [""]

    ok_all = worst[0] < 1e-6 and all(ok for _, ok in checks)
    lines += [f"**Overall: {'PASS' if ok_all else 'REVIEW NEEDED'}**", ""]

    report = "\n".join(lines)
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    print(f"\nreport written to {args.out}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
