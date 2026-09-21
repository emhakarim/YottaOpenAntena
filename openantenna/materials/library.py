"""Built-in material library for OpenAntenna Studio (stdlib only).

Units are SI throughout: ``conductivity_s_per_m`` in S/m, ``density_kg_m3`` in
kg/m^3, ``thickness_m`` in m, ``frequency_hz`` in Hz.

The built-in numbers are **engineering reference values**, not certified
measurements.  They are good enough to set up a simulation, but any design that
actually depends on a material property must be validated against measured data
for the real batch of material -- this matters most for home-made composites,
where the effective permittivity can drift by tens of percent between batches.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Union

from . import dispersion as _dispersion

EPS0 = 8.8541878128e-12  # vacuum permittivity [F/m]
SCHEMA_VERSION = 1
VALID_KINDS = ("dielectric", "conductor")
VALID_DISPERSION_MODELS = ("debye", "lorentz", "drude")

# Keys accepted by each dispersion function in openantenna.materials.dispersion
_DISPERSION_KEYS = {
    "debye": ("eps_inf", "delta_eps", "tau_s", "sigma_dc_s_per_m"),
    "lorentz": ("eps_inf", "delta_eps", "resonance_hz", "gamma_hz"),
    "drude": ("eps_inf", "plasma_freq_hz", "gamma_hz"),
}


@dataclass
class Material:
    """A homogeneous, isotropic, linear material description.

    Parameters
    ----------
    epsilon_r:
        Relative permittivity (real part) at low frequency, ``> 0``.
    mu_r:
        Relative permeability, ``> 0`` (1.0 for all non-magnetic materials).
    tan_delta:
        Dielectric loss tangent of the *bulk dielectric*, ``>= 0``.
    conductivity_s_per_m:
        Finite conductivity, ``>= 0``.  Adds a conduction loss contribution on
        top of ``tan_delta``; see :meth:`effective_tan_delta`.
    density_kg_m3:
        Optional mass density, used only for reporting / thermal notes.
    kind:
        ``"dielectric"`` or ``"conductor"``.  This is a label for the model
        layer; the physics is still carried by ``epsilon_r`` / ``tan_delta`` /
        ``conductivity_s_per_m``.  It is *not* an "ideal PEC" flag.
    dispersion:
        Optional frequency-dispersion description, e.g.
        ``{"model": "debye", "eps_inf": 2.1, "delta_eps": 0.05, "tau_s": 1e-10}``.
    """

    name: str
    epsilon_r: float = 1.0
    mu_r: float = 1.0
    tan_delta: float = 0.0
    conductivity_s_per_m: float = 0.0
    density_kg_m3: Optional[float] = None
    kind: str = "dielectric"
    dispersion: Optional[Dict[str, Any]] = None
    source_note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Material.name must be a non-empty string")
        for attr in ("epsilon_r", "mu_r"):
            value = getattr(self, attr)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"{attr} must be a number, got {value!r}")
            if value <= 0:
                raise ValueError(f"{attr} must be > 0, got {value!r}")
        if self.tan_delta < 0:
            raise ValueError("tan_delta must be >= 0")
        if self.conductivity_s_per_m < 0:
            raise ValueError("conductivity_s_per_m must be >= 0")
        if self.density_kg_m3 is not None and self.density_kg_m3 < 0:
            raise ValueError("density_kg_m3 must be >= 0 when given")
        if self.kind not in VALID_KINDS:
            raise ValueError(f"kind must be one of {VALID_KINDS}, got {self.kind!r}")
        if self.dispersion is not None:
            if not isinstance(self.dispersion, dict):
                raise ValueError("dispersion must be a dict when given")
            model = self.dispersion.get("model")
            if model not in VALID_DISPERSION_MODELS:
                raise ValueError(
                    f"dispersion['model'] must be one of {VALID_DISPERSION_MODELS}, "
                    f"got {model!r}"
                )
            unknown = set(self.dispersion) - {"model", "note"} - set(_DISPERSION_KEYS[model])
            if unknown:
                raise ValueError(
                    f"dispersion for model {model!r} has unknown keys: {sorted(unknown)}"
                )

    # ------------------------------------------------------------------ loss
    @property
    def is_conductor(self) -> bool:
        return self.kind == "conductor"

    def conduction_tan_delta(self, frequency_hz: float) -> float:
        """Loss tangent equivalent of the finite conductivity.

        ``tan_delta_c = sigma / (2*pi*f*eps0*epsilon_r)``

        This decreases with frequency: a conductor that behaves lossily at
        100 MHz can be nearly lossless at 6 GHz for the same sigma.
        """
        if frequency_hz <= 0:
            raise ValueError("frequency_hz must be > 0")
        if self.conductivity_s_per_m == 0.0:
            return 0.0
        return self.conductivity_s_per_m / (
            2.0 * math.pi * frequency_hz * EPS0 * self.epsilon_r
        )

    def effective_tan_delta(self, frequency_hz: float) -> float:
        """Total loss tangent ``tan_delta + conduction contribution``."""
        return self.tan_delta + self.conduction_tan_delta(frequency_hz)

    def loss_term(self) -> float:
        """Legacy alias of :meth:`conduction_tan_delta` at 1 GHz."""
        return self.conduction_tan_delta(1.0e9)

    # ------------------------------------------------------------- ser/de
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Material":
        if not isinstance(data, Mapping):
            raise ValueError("Material.from_dict expects a mapping")
        allowed = {
            "name", "epsilon_r", "mu_r", "tan_delta", "conductivity_s_per_m",
            "density_kg_m3", "kind", "dispersion", "source_note",
        }
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(f"unknown Material keys: {sorted(unknown)}")
        return cls(**dict(data))

    def describe(self) -> str:
        parts = [
            f"{self.name}: eps_r={self.epsilon_r:g}",
            f"mu_r={self.mu_r:g}",
            f"tan_d={self.tan_delta:g}",
        ]
        if self.conductivity_s_per_m:
            parts.append(f"sigma={self.conductivity_s_per_m:g} S/m")
        if self.dispersion:
            parts.append(f"dispersion={self.dispersion.get('model')}")
        return ", ".join(parts)


def complex_relative_permittivity(material: Material, frequency_hz: float) -> complex:
    """Complex relative permittivity at ``frequency_hz``, sign convention
    ``eps = eps' - j*eps''`` (``eps'' >= 0`` for a passive material).

    If the material has no dispersion model the static ``epsilon_r`` and the
    total loss tangent are used.  If it does, the dispersion model is evaluated
    instead; for the Debye model the DC conductivity must be supplied through
    ``dispersion["sigma_dc_s_per_m"]`` (otherwise ``conductivity_s_per_m`` is
    added here and would be counted twice).
    """
    if frequency_hz <= 0:
        raise ValueError("frequency_hz must be > 0")

    if material.dispersion is None:
        eps_imag = material.epsilon_r * material.effective_tan_delta(frequency_hz)
        return complex(material.epsilon_r, -eps_imag)

    model = material.dispersion["model"]
    params = {k: v for k, v in material.dispersion.items() if k != "note"}
    kwargs = {k: params[k] for k in _DISPERSION_KEYS[model] if k in params}
    eps = {
        "debye": _dispersion.debye_eps,
        "lorentz": _dispersion.lorentz_eps,
        "drude": _dispersion.drude_eps,
    }[model](frequency_hz, **kwargs)

    if model != "debye" and material.conductivity_s_per_m:
        eps = eps - 1j * material.conductivity_s_per_m / (
            2.0 * math.pi * frequency_hz * EPS0
        )
    return complex(eps)


# --------------------------------------------------------------------------
# Built-in library
# --------------------------------------------------------------------------
BUILTIN_MATERIALS: Dict[str, Material] = {
    "air": Material(
        name="air",
        epsilon_r=1.0,
        tan_delta=0.0,
        density_kg_m3=1.2,
        source_note="Vacuum/air, by definition eps_r = 1.",
    ),
    "PTFE": Material(
        name="PTFE",
        epsilon_r=2.1,
        tan_delta=0.0004,
        density_kg_m3=2200,
        source_note=(
            "Reference values for PTFE/teflon: Dk 2.0-2.1, tan_delta ~0.0002-0.0004 "
            "(rfcafe.com lists 0.00028 @ 3 GHz; microwaves101.com lists Dk 2.1 / "
            "tan_delta 0.0004). Verify against the datasheet of your actual sheet."
        ),
    ),
    "FR-4": Material(
        name="FR-4",
        epsilon_r=4.4,
        tan_delta=0.02,
        density_kg_m3=1850,
        source_note=(
            "Typical FR-4 laminate values. Vendor- and frequency-dependent; "
            "eps_r can be anywhere in ~4.2-4.8 and tan_delta often exceeds 0.02 "
            "above a few GHz. Treat as a starting point only."
        ),
    ),
    "RO4003C": Material(
        name="RO4003C",
        epsilon_r=3.55,
        tan_delta=0.0027,
        density_kg_m3=1790,
        source_note="Rogers RO4003C design values (Dk 3.55, tan_delta 0.0027 @ 10 GHz).",
    ),
    "RT-duroid-5880": Material(
        name="RT-duroid-5880",
        epsilon_r=2.2,
        tan_delta=0.0009,
        density_kg_m3=2200,
        source_note="Rogers RT/duroid 5880 design values (Dk 2.2, tan_delta 0.0009 @ 10 GHz).",
    ),
    "copper": Material(
        name="copper",
        epsilon_r=1.0,
        tan_delta=0.0,
        conductivity_s_per_m=5.8e7,
        density_kg_m3=8960,
        kind="conductor",
        source_note="Bulk copper conductivity 5.8e7 S/m at room temperature.",
    ),
    "PEC": Material(
        name="PEC",
        epsilon_r=1.0,
        tan_delta=0.0,
        conductivity_s_per_m=1.0e30,
        density_kg_m3=None,
        kind="conductor",
        source_note=(
            "Idealised perfect electric conductor, modelled here as an "
            "enormous finite conductivity (1e30 S/m). Solver adapters should "
            "map this to their native PEC boundary, not to a huge kappa."
        ),
    ),
}


def get_material(name: str, library: Optional[Mapping[str, Material]] = None) -> Material:
    """Case-insensitive lookup in ``library`` (default: the built-ins)."""
    source: Mapping[str, Material] = BUILTIN_MATERIALS if library is None else library
    if name in source:
        return source[name]
    wanted = name.strip().lower()
    for key, material in source.items():
        if key.strip().lower() == wanted or material.name.strip().lower() == wanted:
            return material
    raise KeyError(f"material {name!r} not found; known: {sorted(source)}")


def list_material_names(library: Optional[Mapping[str, Material]] = None) -> list[str]:
    """Sorted material names available in ``library`` (default: built-ins)."""
    source = BUILTIN_MATERIALS if library is None else library
    return sorted(source)


def save_library(
    materials: Union[Iterable[Material], Mapping[str, Material]], path: Union[str, Path]
) -> Path:
    """Write materials to a JSON file and return the resolved path."""
    if isinstance(materials, Mapping):
        items = list(materials.values())
    else:
        items = list(materials)
    for item in items:
        if not isinstance(item, Material):
            raise TypeError(f"expected Material instances, got {type(item).__name__}")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": "openantenna.material-library",
        "materials": [m.to_dict() for m in items],
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target.resolve()


def load_library(
    path: Union[str, Path], include_builtins: bool = False
) -> Dict[str, Material]:
    """Load a material library JSON file into a ``name -> Material`` mapping."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "materials" not in data:
        raise ValueError("not an OpenAntenna material library file")
    schema = data.get("schema_version")
    if schema != SCHEMA_VERSION:
        raise ValueError(f"unsupported library schema_version {schema!r}")
    library: Dict[str, Material] = dict(BUILTIN_MATERIALS) if include_builtins else {}
    for entry in data["materials"]:
        material = Material.from_dict(entry)
        library[material.name] = material
    return library
