"""Geometry generation: analytic element synthesis and array layout."""

from __future__ import annotations

from .array import (
    ArrayLayout,
    array_factor,
    array_factor_plane,
    build_array_layout,
    element_positions,
    wavelength0,
)
from .patch import (
    PatchDesign,
    effective_permittivity,
    ground_plane_size,
    inset_depth_for_input_resistance,
    patch_length,
    patch_width,
    resonant_frequency,
    synthesize_patch,
)

__all__ = [
    "PatchDesign",
    "synthesize_patch",
    "patch_width",
    "patch_length",
    "effective_permittivity",
    "resonant_frequency",
    "inset_depth_for_input_resistance",
    "ground_plane_size",
    "ArrayLayout",
    "build_array_layout",
    "element_positions",
    "array_factor",
    "array_factor_plane",
    "wavelength0",
]
from .feed import FeedPlan, FeedSegment, plan_corporate_feed_geometry, segment_counts  # noqa: F401
