"""Example 1 - synthesise a 2.45 GHz patch and tune it against the cavity predictor.

Run:  python examples/01_patch_tuning.py
Needs: nothing beyond the package (no solver, no optional dependencies).
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from openantenna.geometry.patch import (
    delta_length,
    effective_permittivity,
    patch_length,
    patch_width,
    resonant_frequency_cavity,
)
from openantenna.sweep.optimise import minimise_resonance_error

TARGET_HZ = 2.45e9
EPSILON_R = 3.4
HEIGHT_M = 1.6e-3


def main() -> int:
    width_m = patch_width(TARGET_HZ, EPSILON_R)
    epsilon_eff = effective_permittivity(EPSILON_R, HEIGHT_M, width_m)
    length0 = patch_length(TARGET_HZ, epsilon_eff, delta_length(HEIGHT_M, epsilon_eff, width_m))
    print(f"substrate      : eps_r {EPSILON_R}, h {HEIGHT_M * 1e3:.2f} mm")
    print(f"width          : {width_m * 1e3:.4f} mm")
    print(f"length (synth) : {length0 * 1e3:.4f} mm")
    print(f"cavity f0      : {resonant_frequency_cavity(EPSILON_R, HEIGHT_M, width_m, length0) / 1e9:.6f} GHz")

    def predict(params):
        return resonant_frequency_cavity(EPSILON_R, HEIGHT_M, width_m, params["length_m"])

    result = minimise_resonance_error(
        TARGET_HZ,
        predict,
        {"length_m": (length0 * 0.75, length0 * 1.25)},
        seed=0,
        max_generations=150,
    )
    print(f"length (tuned) : {result.best_params['length_m'] * 1e3:.4f} mm")
    print(f"error          : {result.best_value * 100.0:.6f} %  (converged={result.converged})")
    print("NOTE: this is a targeting result from an analytic model, not a solver measurement.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
