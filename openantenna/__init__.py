"""OpenAntenna Studio - an open-source antenna analysis and design toolkit.

Phase 1 status: headless, standard-library-only core.
There is no GUI, no third-party dependency and **no verified EM solver** in
this phase.  The openEMS/CSXCAD adapter can *generate* a solver script but
cannot run it here; see ``openantenna.solvers.openems``.

Public surface is intentionally small in Phase 1; import submodules directly
(``openantenna.materials.library``, ``openantenna.geometry.patch``, ...).
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
