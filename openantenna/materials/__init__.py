"""Material library, composite mixing rules and frequency dispersion models.

Stdlib-only.  Submodules:

* :mod:`openantenna.materials.library`   - ``Material`` dataclass + built-ins
* :mod:`openantenna.materials.mixing`    - two-phase composite mixing rules
* :mod:`openantenna.materials.dispersion`- Debye / Lorentz / Drude models
"""

from __future__ import annotations

from .library import (
    BUILTIN_MATERIALS,
    Material,
    complex_relative_permittivity,
    get_material,
    list_material_names,
    load_library,
    save_library,
)

__all__ = [
    "Material",
    "BUILTIN_MATERIALS",
    "get_material",
    "list_material_names",
    "load_library",
    "save_library",
    "complex_relative_permittivity",
]
