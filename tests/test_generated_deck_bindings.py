"""Sweep the generated deck for the class of bug that cost 54 minutes per B2 arm.

B2's `probe` arms ran a full 400k-step FDTD and then died on

    UnboundLocalError: cannot access local variable 'port'

because the name was bound only inside one branch and read unconditionally afterwards.  Yotta's
incident note puts the lesson plainly: *text tests cannot see an unbound local - only running the
rendered script exposes it*.  A structural check can, without running anything:

* a name **read** at function-body level (indentation 4) must be bound by an assignment at module
  level (indentation 0), at function-body level (indentation 4), or by an ``if``/``else`` pair
  whose two branches both assign it (that is an unconditional binding too);
* a name bound **only** deeper, on one side of a branch, and then read at function-body level is
  exactly the unbound-local pattern.

The pair rule is what keeps this from flagging `_s11_port`, which is assigned on both sides of an
``if/else`` and is therefore safe.  It is still an indentation-based approximation rather than a
full dataflow analysis - deliberately conservative and cheap - and it runs over a matrix of
configurations, because the original bug appeared in only one of them.
"""

from __future__ import annotations

import re
import unittest

from openantenna.solvers.openems import OpenEMSSolver

try:
    from test_openems_gen import make_project
except ImportError:  # pragma: no cover - direct execution
    from tests.test_openems_gen import make_project  # type: ignore

ASSIGN_ANY = re.compile(r"^\s+([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)")
ASSIGN_TOP = re.compile(r"^(?:    )?([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)")
USE_TOP = re.compile(r"^(?:    )?(?!import\b|from\b)([A-Za-z_][A-Za-z0-9_]*)\s*[.\[]")
IMPORT = re.compile(r"^(?:import|from)\s")
IF_LINE = re.compile(r"^(\s*)if\b.*:\s*$")
ELSE_LINE = re.compile(r"^(\s*)else\s*:\s*$")

WHITELIST = {
    "self", "print", "open", "range", "len", "enumerate", "str", "int", "float", "complex",
    "list", "dict", "sum", "max", "min", "abs", "isinstance", "Exception", "SystemExit",
    "TypeError", "AssertionError", "OSError", "ValueError",
}


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _block_range(lines: list[str], start: int, indent: int) -> range:
    end = start
    while end < len(lines):
        if lines[end].strip() and _indent(lines[end]) <= indent:
            break
        end += 1
    return range(start, end)


def _assigned_in(lines: list[str], start: int, indent: int) -> set[str]:
    names = set()
    for index in _block_range(lines, start, indent):
        match = ASSIGN_ANY.match(lines[index])
        if match:
            names.add(match.group(1))
    return names


def _if_else_pairs(lines: list[str]) -> set[str]:
    """Names bound on both sides of an ``if``/``else``: unconditional in effect."""
    unconditional: set[str] = set()
    for index, line in enumerate(lines):
        match = IF_LINE.match(line)
        if not match:
            continue
        indent = len(match.group(1))
        body = _assigned_in(lines, index + 1, indent)
        if not body:
            continue
        # the ``else`` sits at the same indent as the ``if``, i.e. just AFTER the if-body, so the
        # search must continue past the block range rather than inside it
        for other in range(_block_range(lines, index + 1, indent).stop, len(lines)):
            candidate = lines[other]
            if not candidate.strip():
                continue
            if _indent(candidate) < indent:
                break
            else_match = ELSE_LINE.match(candidate)
            if else_match and len(else_match.group(1)) == indent:
                unconditional |= body & _assigned_in(lines, other + 1, indent)
                break
            if _indent(candidate) == indent:
                break  # another statement at the same level: no else for this if
    return unconditional


def _bound_and_used(script: str) -> tuple[set[str], set[str]]:
    lines = script.splitlines()
    bound: set[str] = set()
    used: set[str] = set()
    for line in lines:
        if not line.strip() or IMPORT.match(line) or _indent(line) > 4:
            continue
        match = ASSIGN_TOP.match(line)
        if match:
            bound.add(match.group(1))
            continue
        match = USE_TOP.match(line)
        if match:
            used.add(match.group(1))
    bound |= _if_else_pairs(lines)
    return bound, used


def _configurations():
    """The matrix that matters: feed realisations crossed with the port modes."""
    for element_ports in (False, True):
        for line_width in (0.0, 5.0e-3):
            for unit_cell in (False, True):
                project = make_project(
                    nx=2 if element_ports else 1,
                    ny=2 if element_ports else 1,
                )
                project.patch.feed_line_width_m = line_width
                project.patch.feed_inset_m = project.patch.feed_inset_m or 1.0e-2
                solver = OpenEMSSolver(element_ports=element_ports, unit_cell=unit_cell)
                label = (
                    f"element_ports={element_ports}, line_width={line_width}, "
                    f"unit_cell={unit_cell}"
                )
                try:
                    yield label, solver.render_script(project), None
                except ValueError as exc:
                    yield label, None, str(exc)


class TestGeneratedDeckBindings(unittest.TestCase):
    def test_no_name_is_used_at_function_level_without_a_function_level_binding(self):
        checked = 0
        refused = 0
        for label, script, refusal in _configurations():
            if script is None:
                refused += 1
                self.assertIn("Phase 2 #5", refusal or "", label)
                continue
            checked += 1
            bound, used = _bound_and_used(script)
            risky = sorted(used - bound - WHITELIST)
            self.assertEqual(
                risky,
                [],
                f"{label}: name(s) used at function level but never bound there: {risky}. "
                "That is the unbound-local pattern that killed B2's FDTD arms.",
            )
            compile(script, "sim.py", "exec")
        self.assertGreaterEqual(checked, 4, "the matrix must render real decks")
        self.assertGreaterEqual(refused, 1, "the element-ports + printed-line refusal must fire")

    def test_the_pair_rule_actually_recognises_both_sided_bindings(self):
        """A guard on the guard: the if/else rule is what prevents a false positive."""
        script = "\n".join(
            [
                "def main():",
                "    if CONDITION:",
                "        value = 1",
                "    else:",
                "        value = 2",
                "    print(value)",
            ]
        )
        bound, used = _bound_and_used(script)
        self.assertIn("value", bound)
        self.assertEqual(sorted(used - bound - WHITELIST), [])

    def test_a_one_sided_binding_is_still_reported(self):
        """The failing pattern must still fail: the rule must not have gone blind."""
        script = "\n".join(
            [
                "def main():",
                "    if CONDITION:",
                "        value = 1",
                "    value.emit()",
            ]
        )
        bound, used = _bound_and_used(script)
        self.assertEqual(sorted(used - bound - WHITELIST), ["value"])


if __name__ == "__main__":
    unittest.main()
