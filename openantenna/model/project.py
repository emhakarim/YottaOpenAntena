"""Neutral design model for OpenAntenna Studio (stdlib only).

The neutral model is the single source of truth for one design.  It contains no
solver-specific concept: substrate stackup, patch geometry, array layout and the
frequency sweep are described once, and solver adapters translate it.

Validation is deliberately split in two levels:

* construction errors raise :class:`ValueError` (a negative thickness is never
  meaningful);
* engineering warnings are returned as a list of strings by :meth:`Project.check`
  (a 4x4 array at 0.9 lambda spacing is legal but will grating-lobe).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional

SCHEMA_VERSION = 1

FEED_MODES = ("inset", "edge", "probe", "corporate")

C0 = 299792458.0  # speed of light in vacuum [m/s]


def _positive(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {value!r}")
    if value <= 0:
        raise ValueError(f"{name} must be > 0, got {value!r}")
    return float(value)


@dataclass
class LayerSpec:
    """One layer of the substrate stackup."""

    material: str
    thickness_m: float
    role: str = "dielectric"

    def __post_init__(self) -> None:
        if not isinstance(self.material, str) or not self.material.strip():
            raise ValueError("LayerSpec.material must be a non-empty material name")
        self.thickness_m = _positive(self.thickness_m, "thickness_m")
        if self.role not in ("dielectric", "conductor"):
            raise ValueError("LayerSpec.role must be 'dielectric' or 'conductor'")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LayerSpec":
        return cls(**dict(data))


@dataclass
class SubstrateStackup:
    """Ordered list of layers, bottom -> top."""

    layers: List[LayerSpec] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.layers:
            raise ValueError("SubstrateStackup.layers must not be empty")
        converted: List[LayerSpec] = []
        for layer in self.layers:
            converted.append(layer if isinstance(layer, LayerSpec) else LayerSpec.from_dict(layer))
        self.layers = converted

    @property
    def total_thickness_m(self) -> float:
        return sum(layer.thickness_m for layer in self.layers)

    def dielectric_layers(self) -> List[LayerSpec]:
        return [layer for layer in self.layers if layer.role == "dielectric"]

    def to_dict(self) -> Dict[str, Any]:
        return {"layers": [layer.to_dict() for layer in self.layers]}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SubstrateStackup":
        return cls(layers=[LayerSpec.from_dict(entry) for entry in data["layers"]])

    @classmethod
    def single(cls, material: str, thickness_m: float) -> "SubstrateStackup":
        """Convenience constructor for the common single-layer substrate."""
        return cls(layers=[LayerSpec(material=material, thickness_m=thickness_m)])


@dataclass
class PatchGeometry:
    """Rectangular patch radiator.

    ``width_m`` / ``length_m`` may be ``None``, meaning "not synthesised yet";
    :func:`openantenna.geometry.patch.synthesize_patch` fills them in from the
    target frequency and substrate.
    """

    width_m: Optional[float] = None
    length_m: Optional[float] = None
    feed_mode: str = "inset"
    feed_inset_m: Optional[float] = None
    feed_edge_offset_m: Optional[float] = None
    slot_depth_m: Optional[float] = None

    def __post_init__(self) -> None:
        for name in ("width_m", "length_m", "feed_inset_m", "feed_edge_offset_m", "slot_depth_m"):
            value = getattr(self, name)
            if value is not None:
                setattr(self, name, _positive(value, name))
        if self.feed_mode not in FEED_MODES:
            raise ValueError(f"feed_mode must be one of {FEED_MODES}, got {self.feed_mode!r}")

    def is_synthesised(self) -> bool:
        return self.width_m is not None and self.length_m is not None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PatchGeometry":
        return cls(**dict(data))


@dataclass
class ArrayConfig:
    """Rectangular ``nx`` x ``ny`` array of identical elements."""

    nx: int = 1
    ny: int = 1
    spacing_x_lambda0: float = 0.5
    spacing_y_lambda0: float = 0.5
    feed_mode: str = "corporate"

    def __post_init__(self) -> None:
        for name in ("nx", "ny"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be an integer >= 1, got {value!r}")
        self.spacing_x_lambda0 = _positive(self.spacing_x_lambda0, "spacing_x_lambda0")
        self.spacing_y_lambda0 = _positive(self.spacing_y_lambda0, "spacing_y_lambda0")
        if self.feed_mode not in FEED_MODES:
            raise ValueError(f"feed_mode must be one of {FEED_MODES}, got {self.feed_mode!r}")

    @property
    def element_count(self) -> int:
        return self.nx * self.ny

    @property
    def is_single_element(self) -> bool:
        return self.element_count == 1

    def spacing_m(self, frequency_hz: float) -> tuple[float, float]:
        """Element spacing in metres at ``frequency_hz``."""
        lam0 = C0 / _positive(frequency_hz, "frequency_hz")
        return self.spacing_x_lambda0 * lam0, self.spacing_y_lambda0 * lam0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ArrayConfig":
        return cls(**dict(data))


@dataclass
class FrequencySweep:
    """Linear frequency sweep."""

    start_hz: float
    stop_hz: float
    points: int = 201

    def __post_init__(self) -> None:
        self.start_hz = _positive(self.start_hz, "start_hz")
        self.stop_hz = _positive(self.stop_hz, "stop_hz")
        if self.stop_hz <= self.start_hz:
            raise ValueError("stop_hz must be greater than start_hz")
        if isinstance(self.points, bool) or not isinstance(self.points, int) or self.points < 2:
            raise ValueError("points must be an integer >= 2")

    @property
    def center_hz(self) -> float:
        return 0.5 * (self.start_hz + self.stop_hz)

    @property
    def bandwidth_hz(self) -> float:
        return self.stop_hz - self.start_hz

    @property
    def step_hz(self) -> float:
        return self.bandwidth_hz / (self.points - 1)

    def frequencies(self) -> List[float]:
        return [self.start_hz + i * self.step_hz for i in range(self.points)]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FrequencySweep":
        return cls(**dict(data))

    @classmethod
    def fractional(cls, center_hz: float, fraction: float, points: int = 201) -> "FrequencySweep":
        """Sweep spanning ``center * (1 -+ fraction)`` (e.g. 0.1 for +-10 %)."""
        center_hz = _positive(center_hz, "center_hz")
        fraction = _positive(fraction, "fraction")
        if fraction >= 1.0:
            raise ValueError("fraction must be < 1 so that start_hz stays > 0")
        return cls(
            start_hz=center_hz * (1.0 - fraction),
            stop_hz=center_hz * (1.0 + fraction),
            points=points,
        )


@dataclass
class Project:
    """A complete design that a solver adapter can translate."""

    name: str = "untitled"
    substrate: SubstrateStackup = field(
        default_factory=lambda: SubstrateStackup.single("PTFE", 0.0016)
    )
    patch: PatchGeometry = field(default_factory=PatchGeometry)
    array: ArrayConfig = field(default_factory=ArrayConfig)
    sweep: FrequencySweep = field(default_factory=lambda: FrequencySweep.fractional(2.45e9, 0.15))
    notes: str = ""
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Project.name must be a non-empty string")
        if isinstance(self.substrate, Mapping):
            self.substrate = SubstrateStackup.from_dict(self.substrate)
        if isinstance(self.patch, Mapping):
            self.patch = PatchGeometry.from_dict(self.patch)
        if isinstance(self.array, Mapping):
            self.array = ArrayConfig.from_dict(self.array)
        if isinstance(self.sweep, Mapping):
            self.sweep = FrequencySweep.from_dict(self.sweep)

    # ------------------------------------------------------------ helpers
    @property
    def center_frequency_hz(self) -> float:
        return self.sweep.center_hz

    def substrate_material_name(self) -> str:
        layers = self.substrate.dielectric_layers()
        return layers[0].material if layers else self.substrate.layers[0].material

    def check(self) -> List[str]:
        """Return engineering warnings (never raises)."""
        warnings: List[str] = []

        if len(self.substrate.dielectric_layers()) > 1:
            warnings.append(
                "Stackup has multiple dielectric layers: the single-layer patch "
                "synthesis formulas do not apply; use an effective-medium estimate "
                "for eps_r and document it."
            )

        spacing_x = self.array.spacing_x_lambda0
        spacing_y = self.array.spacing_y_lambda0
        if max(spacing_x, spacing_y) > 0.5:
            warnings.append(
                f"Element spacing is {max(spacing_x, spacing_y):g} lambda0 (> 0.5): "
                "expect grating lobes inside the visible region for wide scan angles."
            )
        if self.array.element_count >= 16:
            warnings.append(
                f"{self.array.nx}x{self.array.ny} = {self.array.element_count} elements: "
                "a full-wave model of the whole array is expensive. Prefer a unit-cell "
                "(periodic boundary) study plus an array-factor post-processing step, "
                "and use a small finite model only to check mutual coupling."
            )
        if not self.patch.is_synthesised():
            warnings.append(
                "Patch width/length are not set; run the patch synthesis step before "
                "generating solver input."
            )

        substrate_thickness = self.substrate.total_thickness_m
        lam0 = C0 / self.sweep.center_hz
        h_over_lambda = substrate_thickness / lam0
        if h_over_lambda > 0.01:
            warnings.append(
                f"Substrate is electrically thick (h/lambda0 = {h_over_lambda:.4f} > 0.01): "
                "surface-wave excitation and a shift away from the transmission-line "
                "model are likely; verify with a full-wave run. (Same criterion as "
                "geometry.patch.substrate_is_electrically_thick - review item Y-11.)"
            )
        return warnings

    def summary(self) -> str:
        layers = ", ".join(
            f"{layer.role}:{layer.material}@{layer.thickness_m * 1e3:g}mm"
            for layer in self.substrate.layers
        )
        patch = (
            f"{self.patch.width_m * 1e3:.2f} x {self.patch.length_m * 1e3:.2f} mm"
            if self.patch.is_synthesised()
            else "not synthesised"
        )
        return "\n".join(
            [
                f"project        : {self.name}",
                f"stackup        : {layers}",
                f"patch          : {patch} (feed: {self.patch.feed_mode})",
                (
                    f"array          : {self.array.nx} x {self.array.ny}"
                    f" ({self.array.element_count} elements)"
                    f" spacing {self.array.spacing_x_lambda0:g}/{self.array.spacing_y_lambda0:g} lambda0"
                    f" feed {self.array.feed_mode}"
                ),
                (
                    f"sweep          : {self.sweep.start_hz / 1e9:.3f} - "
                    f"{self.sweep.stop_hz / 1e9:.3f} GHz, {self.sweep.points} points"
                ),
            ]
        )

    # ------------------------------------------------------------- ser/de
    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "kind": "openantenna.project",
            "name": self.name,
            "substrate": self.substrate.to_dict(),
            "patch": self.patch.to_dict(),
            "array": self.array.to_dict(),
            "sweep": self.sweep.to_dict(),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Project":
        if not isinstance(data, Mapping):
            raise ValueError("Project.from_dict expects a mapping")
        schema = data.get("schema_version", SCHEMA_VERSION)
        if schema != SCHEMA_VERSION:
            raise ValueError(f"unsupported project schema_version {schema!r}")
        return cls(
            name=data.get("name", "untitled"),
            substrate=SubstrateStackup.from_dict(data["substrate"]),
            patch=PatchGeometry.from_dict(data.get("patch", {})),
            array=ArrayConfig.from_dict(data.get("array", {})),
            sweep=FrequencySweep.from_dict(data["sweep"]),
            notes=data.get("notes", ""),
        )

    def to_json(self, indent: int = 2) -> str:
        import json

        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, text: str) -> "Project":
        import json

        return cls.from_dict(json.loads(text))
