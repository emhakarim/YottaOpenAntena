"""Static sweep for conditional-binding hazards inside the generator itself.

Why this exists: three bugs in a row landed in `openems.py` - `lam0`, `_width_of` and `section` were
each stored only inside one branch and then read somewhere that the branch does not cover.  The deck
probe caught them, but only by rendering a deck, and the earlier sweep in
`tests/test_generated_deck_bindings.py` looks at names bound at function-body level (indentation 4),
so it could never see them.

The rule here is the one that actually describes the class: inside one function, if an ``if`` body
stores a name, and that name is read by a statement the ``if`` does not cover (a later sibling, or the
``else`` when only the body stores it), the binding is conditional and the read is a latent
`UnboundLocalError`.  Function arguments, module-level bindings, imports, loop targets and
``with``/``except`` aliases are not stores of this kind and are excluded.
"""

from __future__ import annotations

import ast
import pathlib
import unittest

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "openantenna"
SOURCES = sorted(PACKAGE.rglob("*.py"))

# names that are legitimately bound by the surrounding Python machinery
IGNORED = {"__name__", "__file__", "__doc__", "self", "cls"}


def _stored_names(nodes) -> set[str]:
    """Names stored by simple assignment anywhere inside ``nodes``."""
    found: set[str] = set()
    for node in nodes:
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                found.add(child.id)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # a nested function's body binds its own locals
                pass
            elif isinstance(child, (ast.For, ast.AsyncFor)):
                for target in ast.walk(child.target):
                    if isinstance(target, ast.Name):
                        found.add(target.id)
            elif isinstance(child, ast.withitem) and child.optional_vars is not None:
                for target in ast.walk(child.optional_vars):
                    if isinstance(target, ast.Name):
                        found.add(target.id)
            elif isinstance(child, ast.ExceptHandler) and child.name:
                found.add(child.name)
    return found


def _loaded_names(nodes) -> set[str]:
    """Names read by ``nodes``, not counting the ones read only as assignment targets."""
    found: set[str] = set()
    for node in nodes:
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                found.add(child.id)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for sub in ast.walk(child):
                    if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                        found.add(sub.id)
    return found


def _function_locals(function: ast.AST) -> tuple[set[str], set[str]]:
    arguments: set[str] = set()
    args = getattr(function, "args", None)
    if args is not None:
        for group in (args.posonlyargs, args.args, args.kwonlyargs):
            for argument in group:
                arguments.add(argument.arg)
        if args.vararg:
            arguments.add(args.vararg.arg)
        if args.kwarg:
            arguments.add(args.kwarg.arg)
    return arguments, _loaded_names(function.body)


def hazards(path: pathlib.Path) -> list[tuple[str, int]]:
    """``(name, lineno)`` for every conditional binding read outside its branch."""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    found: list[tuple[str, int]] = []

    def inspect_sequence(statements: list[ast.stmt], unconditional: set[str]) -> None:
        for index, statement in enumerate(statements):
            if isinstance(statement, ast.If):
                body = _stored_names(statement.body)
                orelse = _stored_names(statement.orelse)
                after = _loaded_names(statements[index + 1 :]) | _loaded_names(statement.orelse)
                for name in sorted(body - orelse - unconditional - IGNORED):
                    if name in after:
                        found.append((name, statement.lineno))
                inspect_sequence(statement.body, unconditional | (body & orelse))
                if statement.orelse:
                    inspect_sequence(statement.orelse, unconditional | (body & orelse))
            elif isinstance(statement, (ast.For, ast.AsyncFor, ast.While, ast.With, ast.Try)):
                inspect_sequence(getattr(statement, "body", []), unconditional)
                for extra in (
                    getattr(statement, "orelse", []),
                    getattr(statement, "finalbody", []),
                ):
                    inspect_sequence(extra, unconditional)
                for handler in getattr(statement, "handlers", []):
                    inspect_sequence(handler.body, unconditional)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments, _ = _function_locals(node)
            # names bound before any branch in this function body count as unconditional
            prelude: set[str] = set()
            for statement in node.body:
                if isinstance(statement, ast.If):
                    break
                prelude |= _stored_names([statement])
            inspect_sequence(node.body, arguments | prelude | IGNORED)
    return found


class TestGeneratorBindings(unittest.TestCase):
    def test_no_new_conditional_binding_hazards_appear(self):
        """A ratchet, not a clean bill of health.

        This rule is a heuristic: it flags any name stored inside an ``if`` body and read outside it,
        which includes ordinary ``try``-heavy code that is fine in practice.  The point is that it
        caught the three real bugs in ``openems.py`` (``lam0``, ``_width_of``, ``section``) that the
        rendered-deck sweep could not see, so the count must not grow.  Triage happens when it does.
        """
        findings: list[str] = []
        for source in SOURCES:
            findings.extend(f"{source.name}:{line}:{name}" for name, line in hazards(source))
        self.assertLessEqual(
            len(findings),
            40,
            "conditional-binding findings grew past the documented baseline of 40; triage these: "
            + ", ".join(sorted(findings)[:12]),
        )

    def test_the_sweep_covers_the_whole_package_without_error(self):
        scanned = 0
        for source in SOURCES:
            hazards(source)  # must not raise on any module
            scanned += 1
        self.assertGreater(scanned, 10)

    def test_the_rule_actually_flags_the_pattern_it_exists_for(self):
        """Guard on the guard: a synthetic fixture with the exact lam0/port shape must be flagged."""
        import tempfile

        sample = "\n".join(
            [
                "def render(project):",
                "    if project.unit_cell:",
                "        lam0 = 1.0",
                "    if project.two_d:",
                "        width = lam0",
                "    return width",
            ]
        )
        with tempfile.TemporaryDirectory() as folder:
            target = pathlib.Path(folder) / "sample.py"
            target.write_text(sample, encoding="utf-8")
            flagged = {name for name, _line in hazards(target)}
        self.assertIn("lam0", flagged)

    def test_a_binding_present_on_both_sides_is_not_flagged(self):
        import tempfile

        sample = "\n".join(
            [
                "def render(flag, other):",
                "    if flag:",
                "        value = 1",
                "    else:",
                "        value = 2",
                "    return value",
            ]
        )
        with tempfile.TemporaryDirectory() as folder:
            target = pathlib.Path(folder) / "sample.py"
            target.write_text(sample, encoding="utf-8")
            self.assertEqual(hazards(target), [])


if __name__ == "__main__":
    unittest.main()
