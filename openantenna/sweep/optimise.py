"""Optimisation over the design space (Phase 4).

Differential evolution, written against the standard library only, so the core keeps its no-numpy
guarantee and the optimiser can run anywhere the package runs.  It is deliberately small and
explicit rather than clever: classic DE/rand/1/bin with a fixed crossover rate, plus the bookkeeping
that makes a result trustworthy - every evaluation counted, failed evaluations marked rather than
silently treated as good, and a deterministic answer for a given seed.

Honest framing: the search runs on whatever objective the caller supplies.  When that objective is
the package's own analytic model, the result is a *targeting* result - it says where the analytic
model thinks the design should sit, not that a solver run agrees.  Say so when reporting.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, Mapping, Sequence, Tuple

Objective = Callable[[Dict[str, float]], float]


@dataclass
class OptimisationResult:
    """The outcome of a search, with the bookkeeping needed to judge it."""

    best_params: Dict[str, float]
    best_value: float
    generations: int
    evaluations: int
    failed_evaluations: int
    converged: bool
    history: Tuple[float, ...] = field(default_factory=tuple)
    notes: str = ""

    @property
    def all_evaluations_failed(self) -> bool:
        return self.evaluations > 0 and self.failed_evaluations == self.evaluations


def _check_bounds(bounds: Mapping[str, Sequence[float]]) -> Dict[str, Tuple[float, float]]:
    if not bounds:
        raise ValueError("bounds must contain at least one parameter")
    cleaned: Dict[str, Tuple[float, float]] = {}
    for name, pair in bounds.items():
        if len(pair) != 2:
            raise ValueError(f"bounds for {name!r} must be (low, high)")
        low, high = float(pair[0]), float(pair[1])
        if not math.isfinite(low) or not math.isfinite(high):
            raise ValueError(f"bounds for {name!r} must be finite")
        if high <= low:
            raise ValueError(f"bounds for {name!r} must have high > low")
        cleaned[name] = (low, high)
    return cleaned


def differential_evolution(
    objective: Objective,
    bounds: Mapping[str, Sequence[float]],
    *,
    popsize: int = 15,
    max_generations: int = 100,
    crossover_rate: float = 0.9,
    differential_weight: float = 0.8,
    seed: int = 0,
    tolerance: float = 1e-9,
    patience: int = 12,
    on_generation: Callable[[int, float], None] | None = None,
) -> OptimisationResult:
    """Minimise ``objective`` over ``bounds`` with classic differential evolution.

    ``popsize`` is the multiplier on the problem dimension (DE convention): the actual population is
    ``max(8, popsize * dim)``.  The search stops when the best value stops improving by more than
    ``tolerance`` for ``patience`` generations, or at ``max_generations``.
    """
    if popsize < 3:
        raise ValueError("popsize must be at least 3 (the differential needs three vectors)")
    if max_generations < 1:
        raise ValueError("max_generations must be at least 1")
    if not 0.0 < crossover_rate <= 1.0:
        raise ValueError("crossover_rate must be in (0, 1]")
    if not 0.0 < differential_weight <= 2.0:
        raise ValueError("differential_weight must be in (0, 2]")

    cleaned = _check_bounds(bounds)
    names = list(cleaned)
    dim = len(names)
    population_size = max(8, popsize * dim)
    rng = random.Random(seed)

    evaluations = 0
    failures = 0

    def evaluate(vector: Sequence[float]) -> float:
        nonlocal evaluations, failures
        evaluations += 1
        params = {name: vector[index] for index, name in enumerate(names)}
        try:
            value = float(objective(params))
        except Exception:  # a caller objective may not exist for every point
            failures += 1
            return math.inf
        if math.isnan(value):
            failures += 1
            return math.inf
        return value

    def clamp(value: float, index: int) -> float:
        low, high = cleaned[names[index]]
        return low if value < low else high if value > high else value

    population = [
        [rng.uniform(*cleaned[name]) for name in names] for _ in range(population_size)
    ]
    scores = [evaluate(vector) for vector in population]
    best_index = min(range(population_size), key=lambda index: scores[index])
    best_vector = list(population[best_index])
    best_value = scores[best_index]
    history = [best_value]

    stagnant = 0
    generation = 0
    for generation in range(1, max_generations + 1):
        improved = False
        for target in range(population_size):
            candidates = [index for index in range(population_size) if index != target]
            a, b, c = rng.sample(candidates, 3)
            trial = []
            forced = rng.randrange(dim)
            for index in range(dim):
                if rng.random() < crossover_rate or index == forced:
                    mutated = population[a][index] + differential_weight * (
                        population[b][index] - population[c][index]
                    )
                    trial.append(clamp(mutated, index))
                else:
                    trial.append(population[target][index])
            trial_score = evaluate(trial)
            if trial_score <= scores[target]:
                population[target] = trial
                scores[target] = trial_score
                if trial_score < best_value:
                    best_value = trial_score
                    best_vector = list(trial)
                    improved = True
        history.append(best_value)
        if on_generation is not None:
            on_generation(generation, best_value)
        stagnant = 0 if improved else stagnant + 1
        if stagnant >= patience:
            break

    converged = stagnant >= patience and failures < evaluations
    notes = []
    if failures:
        notes.append(f"{failures} of {evaluations} evaluations failed and were treated as worst")
    if not converged:
        notes.append("stopped before the tolerance was met (generation cap or no improvement)")
    if evaluations and failures == evaluations:
        notes.append("every evaluation failed: do not read the returned point as a result")

    return OptimisationResult(
        best_params={name: best_vector[index] for index, name in enumerate(names)},
        best_value=best_value,
        generations=generation,
        evaluations=evaluations,
        failed_evaluations=failures,
        converged=converged,
        history=tuple(history),
        notes="; ".join(notes),
    )


def minimise_resonance_error(
    target_hz: float,
    predict_resonance_hz,
    bounds,
    **kwargs,
):
    """Minimise ``|predicted - target| / target`` for a caller-supplied predictor.

    The predictor comes from the caller on purpose.  Resonance in this package is carried by a
    specific design object with its own factory, and a later predictor may be solver-backed or
    measured - keeping the optimiser agnostic means none of those change this module.  When the
    predictor is the analytic model the result is a **targeting** result: where the model wants the
    design to sit, not evidence that a solver run agrees.
    """
    if target_hz <= 0.0:
        raise ValueError("target_hz must be positive")

    def objective(params):
        predicted = float(predict_resonance_hz(params))
        return abs(predicted - target_hz) / target_hz

    return differential_evolution(objective, bounds, **kwargs)
