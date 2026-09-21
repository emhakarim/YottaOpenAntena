"""Post-processing: S-parameters, matching metrics and far-field quantities."""

from __future__ import annotations

from .patterns import (
    array_pattern_product,
    dipole_element_pattern,
    directivity_from_pattern,
    efficiency_budget,
    gain_dbi,
)
from .sparams import S11Trace, read_touchstone, vswr_from_gamma

__all__ = [
    "S11Trace",
    "read_touchstone",
    "vswr_from_gamma",
    "dipole_element_pattern",
    "array_pattern_product",
    "directivity_from_pattern",
    "efficiency_budget",
    "gain_dbi",
]
