"""Execute the rendered deck's port path against stub solvers - the guard text tests cannot be.

Yotta's handover note (docs/handover-2026-09-23.md, item 6.5) puts it exactly right: the shipped
guard only makes a bad deck fail *fast*, it does not prove the port path runs.  Text assertions pin
the shape; an unbound local or a wrong branch only shows up when the code executes.

So this test renders real decks (probe, printed line, corporate 1-by-n, corporate 2-D), then runs
them with `CSXCAD`/`openEMS` replaced by a numeric stub.  The stub behaves like 1.0 in arithmetic,
so the deck's post-processing - including `port.CalcPort(...)` and `s11 = uf_ref / uf_inc` - runs to
completion for every feed realisation.  No solver, no FDTD, a fraction of a second per deck.
"""

from __future__ import annotations

import contextlib
import io
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from openantenna.solvers.openems import OpenEMSSolver

try:
    from test_openems_gen import make_project
except ImportError:  # pragma: no cover - direct execution
    from tests.test_openems_gen import make_project  # type: ignore


class _Num(float):
    """A number that answers any attribute or call, so arbitrary solver API runs."""

    def __new__(cls, value: float = 1.0):
        return super().__new__(cls, value)

    # arithmetic on a float subclass returns a plain float, which would strip the stub's
    # behaviour the moment the deck adds or divides anything - keep every result a _Num
    def __add__(self, other):
        return _Num(1.0)

    def __radd__(self, other):
        return _Num(1.0)

    def __sub__(self, other):
        return _Num(1.0)

    def __rsub__(self, other):
        return _Num(1.0)

    def __mul__(self, other):
        return _Num(1.0)

    def __rmul__(self, other):
        return _Num(1.0)

    def __truediv__(self, other):
        return _Num(1.0)

    def __rtruediv__(self, other):
        return _Num(1.0)

    def __pow__(self, other):
        return _Num(1.0)

    def __neg__(self):
        return _Num(1.0)

    def __abs__(self):
        return _Num(1.0)

    def __getattr__(self, name):  # pragma: no cover - exercised through the deck
        if name.startswith("__"):
            raise AttributeError(name)
        return _Num(1.0)

    def __call__(self, *args, **kwargs):
        return _Num(1.0)

    def __getitem__(self, item):
        return _Num(1.0)

    def __iter__(self):
        return iter([_Num(1.0), _Num(2.0)])

    def __len__(self):
        return 1


def _stub_environment() -> dict[str, types.ModuleType]:
    """Fake CSXCAD and openEMS modules that hand out :class:`_Num` at every level."""

    def make(name: str) -> types.ModuleType:
        module = types.ModuleType(name)

        def __getattr__(attribute: str, _name=name):
            if attribute.startswith("__"):
                raise AttributeError(attribute)
            # every attribute, class or function or constant, becomes the same numeric stub:
            # returning a bare type here breaks arithmetic the deck does on solver results
            return _Num(1.0)

        module.__getattr__ = __getattr__  # type: ignore[attr-defined]
        return module

    return {"CSXCAD": make("CSXCAD"), "openEMS": make("openEMS")}


def _run_deck(script: str) -> str:
    """Execute a rendered deck with stubbed solvers and return whatever it printed."""
    stdout = io.StringIO()
    with TemporaryDirectory() as folder:
        import numpy as np

        installed: list[str] = []
        for name, module in _stub_environment().items():
            sys.modules[name] = module
            installed.append(name)
        environment = {"__name__": "__main__", "np": np, "__file__": str(Path(folder) / "sim.py")}
        try:
            with contextlib.redirect_stdout(stdout):
                for _attempt in range(16):
                    try:
                        exec(compile(script, "sim.py", "exec"), environment)
                        break
                    except ImportError as exc:
                        missing = getattr(exc, "name", None) or ""
                        if not missing or missing in sys.modules:
                            raise
                        sys.modules[missing] = _stub_environment()["CSXCAD"]
                        installed.append(missing)
                    except SystemExit as exc:  # the deck may refuse by exiting
                        stdout.write(f"\n[SystemExit {exc.code}]")
                        break
        finally:
            for name in installed:
                sys.modules.pop(name, None)
    return stdout.getvalue()


def _corporate(nx: int, ny: int):
    project = make_project(nx=nx, ny=ny)
    project.patch.feed_mode = "corporate"
    project.patch.feed_inset_m = 0.0
    project.patch.feed_line_width_m = 0.0
    return project


class TestDeckPortPathExecutes(unittest.TestCase):
    def _check(self, project, label: str) -> str:
        script = OpenEMSSolver().render_script(project)
        output = _run_deck(script)
        for failure in ("UnboundLocalError", "NameError", "TypeError"):
            self.assertNotIn(failure, output, f"{label}: the deck died with {failure}: {output[-400:]}")
        return output

    def test_probe_feed_deck_runs(self):
        project = make_project()
        project.patch.feed_mode = "probe"
        project.patch.feed_line_width_m = 0.0
        self._check(project, "probe")

    def test_printed_line_deck_runs(self):
        project = make_project()
        project.patch.feed_mode = "inset"
        project.patch.feed_line_width_m = 2.9e-3
        output = self._check(project, "printed line")
        self.assertIn("FEED:", output)

    def test_array_probe_deck_runs(self):
        project = make_project(nx=2, ny=2)
        project.patch.feed_mode = "probe"
        project.patch.feed_line_width_m = 0.0
        self._check(project, "array probe")

    def test_corporate_1byN_deck_runs(self):
        output = self._check(_corporate(1, 4), "corporate 1xN")
        self.assertIn("FEED TREE:", output)

    def test_corporate_2d_deck_runs(self):
        output = self._check(_corporate(2, 2), "corporate 2x2")
        self.assertIn("FEED TREE 2D:", output)


if __name__ == "__main__":
    unittest.main()
