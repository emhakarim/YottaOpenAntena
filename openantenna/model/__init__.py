"""Neutral, solver-independent design model.

Everything in this package is JSON-serialisable and free of solver-specific
detail.  Solver adapters are responsible for translating this model into their
own input format -- never the other way round.
"""

from __future__ import annotations

from .project import (
    FEED_MODES,
    ArrayConfig,
    FrequencySweep,
    LayerSpec,
    PatchGeometry,
    Project,
    SubstrateStackup,
)

__all__ = [
    "Project",
    "SubstrateStackup",
    "LayerSpec",
    "PatchGeometry",
    "ArrayConfig",
    "FrequencySweep",
    "FEED_MODES",
]
