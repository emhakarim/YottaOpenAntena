"""Corporate feed network analysis (Phase 2 #5).

A corporate (binary-tree) feed for an N-element array: one quarter-wave matching stage per level.
This module answers "what does a matched feed do to the array's input match at the design
frequency", and is explicit about its limits:

* dividers are **ideal** (matched, lossless): conductor loss is not modelled, consistent with the
  solver model where metals are PEC;
* the quarter-wave sections are ideal **at the design frequency** only; transformer bandwidth is
  not analysed, so the reported numbers are design-point numbers;
* **the feed geometry is not drawn in the solver model.**  The generator refuses a corporate feed
  with a clear message instead of approximating it.  Drawing it is the remaining half of #5.

## The one result worth stating

Build the tree from the array side outwards.  Each level puts two identical branches in parallel
(half the impedance) and then transforms that pair back through a quarter-wave section of
impedance ``Z_t`` (chosen so that ``Z_t**2 / (Z0/2) = Z0``), so::

    Z <- Z_t**2 / (Z / 2)

Applied ``k`` times this **alternates**:

| Levels ``k`` | Array sizes | Result |
|---|---|---|
| odd | 2, 8, 32 | ``Z_in = Z0**2 / Z_e``  -> the reflection is **inverted** |
| even | 4, 16, 64 | ``Z_in = Z_e``  -> the reflection comes back **unchanged** |

An earlier version of this module stated only the odd case as if it were general; the scikit-rf
cross-check disagreed for a 4-element array, which is how the error was found.

Stdlib only.  A scikit-rf cross-check was attempted and is **parked**: connecting a line whose
reference impedance is ``Z_t`` to a load referenced to ``Z0`` needs an explicit renormalisation
step, and without it the comparison disagreed by up to 0.74 in reflection - i.e. the check itself
was wrong, not the closed form.  Rather than ship a broken check, the closed form is asserted
analytically in the tests and the library cross-check is left as the next step for this item.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Sequence

__all__ = [
    "CorporateFeed",
    "synthesise_corporate_feed",
    "combine_with_elements",
    "skrf_cross_check",
]

C0 = 299792458.0


@dataclass
class CorporateFeed:
    """A matched corporate feed: one quarter-wave stage per level of the tree."""

    n_elements: int
    z0_ohm: float
    levels: int
    stage_impedance_ohm: float
    section_length_m: float
    design_frequency_hz: float
    epsilon_eff: float
    notes: str = ""

    def input_reflection(self, load_ohm: complex) -> complex:
        """Reflection looking into the feed when **every** element presents ``load_ohm``.

        The recursion is in the module docstring: ``Z <- Z_t**2 / (Z/2)`` per level, which makes
        the result depend on whether the number of levels is odd or even (an odd level count
        inverts the element's reflection, an even one returns it unchanged).
        """
        load = complex(load_ohm)
        if load == 0:
            raise ValueError("load_ohm must not be zero")
        z_seen = load
        for _ in range(self.levels):
            z_seen = self.stage_impedance_ohm ** 2 / (z_seen / 2.0)
        return (z_seen - self.z0_ohm) / (z_seen + self.z0_ohm)


def synthesise_corporate_feed(
    n_elements: int,
    frequency_hz: float,
    epsilon_eff: float,
    z0_ohm: float = 50.0,
) -> CorporateFeed:
    """Design a matched corporate feed for ``n_elements`` (a power of two).

    Only powers of two are accepted: a corporate tree divides by two at every level, and quietly
    padding to the next power of two would place elements the array does not have.
    """
    if n_elements < 2:
        raise ValueError("a corporate feed needs at least two elements")
    if n_elements & (n_elements - 1):
        raise ValueError(
            f"{n_elements} is not a power of two: a binary corporate feed cannot divide evenly. "
            "Choose another feed topology rather than padding the tree."
        )
    if frequency_hz <= 0 or epsilon_eff <= 0:
        raise ValueError("frequency_hz and epsilon_eff must be > 0")
    if z0_ohm <= 0:
        raise ValueError("z0_ohm must be > 0")

    levels = int(round(math.log2(n_elements)))
    wavelength_guide = C0 / (frequency_hz * math.sqrt(epsilon_eff))
    return CorporateFeed(
        n_elements=n_elements,
        z0_ohm=z0_ohm,
        levels=levels,
        # a two-way matched divider into Z0/2 is matched by a quarter-wave section of Z0/sqrt(2),
        # and the same step repeats at every level
        stage_impedance_ohm=z0_ohm / math.sqrt(2.0),
        section_length_m=wavelength_guide / 4.0,
        design_frequency_hz=frequency_hz,
        epsilon_eff=epsilon_eff,
        notes=(
            "ideal matched dividers; quarter-wave stages at the design frequency; conductor loss "
            "not modelled; feed geometry NOT drawn in the solver model (the generator refuses a "
            "corporate feed rather than approximating it)"
        ),
    )


def combine_with_elements(
    element_matrix: Sequence[Sequence[complex]],
    feed: CorporateFeed,
    frequency_hz: float,
) -> Dict[str, object]:
    """Combine the element coupling matrix with the feed into an array input-match report.

    ``element_matrix`` is what :mod:`openantenna.postproc.port_matrix` assembles: ``S[i][j]`` is
    the coupling from driven port ``j`` to port ``i``.  The diagonal gives each element's own
    reflection, which is what the feed sees.
    """
    n = len(element_matrix)
    if n != feed.n_elements:
        raise ValueError(
            f"the element matrix has {n} ports but the feed was designed for {feed.n_elements}"
        )
    if abs(frequency_hz - feed.design_frequency_hz) > 1e-9 * max(feed.design_frequency_hz, 1.0):
        raise ValueError(
            "the feed is matched at its design frequency; combining it elsewhere would report a "
            "mismatch the design never claimed. Re-synthesise the feed at that frequency instead."
        )

    per_element: List[Dict[str, float]] = []
    for index in range(n):
        gamma_element = complex(element_matrix[index][index])
        if abs(gamma_element) >= 1.0:
            raise ValueError(
                f"element {index + 1} has |S| >= 1 ({abs(gamma_element):.3f}); the reflection-to-"
                "impedance conversion is undefined for an active/passive boundary violation"
            )
        z_element = feed.z0_ohm * (1.0 + gamma_element) / (1.0 - gamma_element)
        gamma_in = feed.input_reflection(z_element)
        per_element.append(
            {
                "element": index + 1,
                "element_reflection": abs(gamma_element),
                "input_reflection": abs(gamma_in),
                "input_vswr": (1.0 + abs(gamma_in)) / (1.0 - abs(gamma_in)),
            }
        )

    worst = max(entry["input_reflection"] for entry in per_element)
    return {
        "n_elements": n,
        "design_frequency_hz": feed.design_frequency_hz,
        "per_element": per_element,
        "worst_input_reflection": worst,
        "worst_input_vswr": (1.0 + worst) / (1.0 - worst),
        "stage_impedance_ohm": feed.stage_impedance_ohm,
        "section_length_m": feed.section_length_m,
        "note": (
            "ideal feed at its design frequency: the reported input mismatch is the elements' own "
            "reflection transformed by the tree (see the module docstring for the odd/even level "
            "rule). The feed geometry is not drawn in the model yet."
        ),
    }


def skrf_cross_check(feed: CorporateFeed, load_ohm: complex = complex(50.0)) -> complex:
    """Input reflection of the same tree, computed with scikit-rf.  Optional dependency.

    Everything is renormalised to the design ``Z0`` *before* the two-port formula is applied: the
    line is created with reference impedance ``Z_t`` (its natural reference) and then
    ``renormalize(z0)`` moves it to ``Z0``, so the line's S-parameters and the load's reflection
    finally share one reference.  The first version of this check skipped that step and disagreed
    with the closed form by up to 0.74 - the check was wrong, not the recursion.
    """
    try:
        import skrf as rf
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("scikit-rf is required for the cross-check") from exc

    z0 = feed.z0_ohm
    frequency = rf.Frequency(feed.design_frequency_hz, feed.design_frequency_hz, 1, unit="Hz")
    # The section length is a quarter wave *in the guide*, so the media must be given the guide's
    # propagation constant.  With the default (air) propagation the line is electrically too
    # short - 0.67 of a quarter wave for PTFE - and the transform is not a quarter-wave
    # transform at all.  That, not the renormalisation, was the 0.74 disagreement: the value did
    # not move when the renormalisation was fixed.
    gamma = (
        1j
        * 2.0
        * math.pi
        * feed.design_frequency_hz
        * math.sqrt(feed.epsilon_eff)
        / C0
    )
    media = rf.media.DefinedGammaZ0(
        frequency, z0=feed.stage_impedance_ohm, gamma=gamma
    )
    # ``renormalize()`` mutates the network in place and returns None, so it must be called as a
    # statement: chaining it leaves ``line`` as None and the next line raises AttributeError.
    line = media.line(d=feed.section_length_m, unit="m")
    line.renormalize(z0)
    s11 = complex(line.s[0, 0, 0])
    s12 = complex(line.s[0, 0, 1])
    s21 = complex(line.s[0, 1, 0])
    s22 = complex(line.s[0, 1, 1])

    z_seen = complex(load_ohm)
    for _ in range(feed.levels):
        z_pair = z_seen / 2.0
        gamma_load = (z_pair - z0) / (z_pair + z0)
        gamma_in = s11 + s12 * s21 * gamma_load / (1.0 - s22 * gamma_load)
        z_seen = z0 * (1.0 + gamma_in) / (1.0 - gamma_in)
    return (z_seen - z0) / (z_seen + z0)
