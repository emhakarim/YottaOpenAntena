"""Named parameters with small expressions - the "add parameter" idea from CST.

A parameter list is what lets a drawing be *defined* rather than merely drawn: a block's
thickness can be ``h_sub``, and ``h_sub`` can be ``1.6`` or ``L/8`` where ``L`` is another
parameter.  Changing a parameter changes everything that references it - that is the whole
point, and it is why the sketch stores expressions instead of copied numbers.

The expression language is deliberately tiny: numbers, parameter names, ``+ - * / **``,
parentheses and unary signs.  No calls, no attributes, no subscripts, no strings, no
booleans - a drawing file (or a sketch table cell) must never be able to execute anything.
"""

from __future__ import annotations

import ast
import math

from typing import Dict, Iterable, List, Tuple


class ParameterError(ValueError):
    """A parameter or expression that cannot be evaluated; the message carries the reason."""


class UnknownName(ParameterError):
    """A name that is not (yet) defined - kept separate so resolution can retry."""


_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)


def evaluate_expression(expression: str, names: Dict[str, float]) -> float:
    """Evaluate a small arithmetic expression with the given parameter values.

    Raises :class:`UnknownName` for a name that is not in ``names`` (so a parameter table
    can retry forward references) and :class:`ParameterError` for everything else.
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ParameterError("cannot parse %r: %s" % (expression, exc.msg)) from None
    except RecursionError:
        raise ParameterError("expression is nested too deeply to parse") from None
    try:
        result = _evaluate(tree.body, names)
    except RecursionError:
        raise ParameterError("expression is nested too deeply to evaluate") from None
    except OverflowError:
        raise ParameterError("the expression overflows to an unrepresentable number") from None
    if not math.isfinite(result):
        raise ParameterError(
            "the expression evaluates to %r; only finite numbers are allowed" % (result,)
        )
    return result


def _evaluate(node: ast.AST, names: Dict[str, float]) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ParameterError("only numbers are allowed; got %r" % (node.value,))
        try:
            as_float = float(node.value)
        except OverflowError:
            raise ParameterError(
                "numeric literal %s... is out of range" % str(node.value)[:16]
            ) from None
        if not math.isfinite(as_float):
            raise ParameterError("literal numbers must be finite; got %r" % (node.value,))
        return as_float
    if isinstance(node, ast.Name):
        if node.id in names:
            return float(names[node.id])
        raise UnknownName("unknown name %r" % node.id)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _evaluate(node.operand, names)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
        left = _evaluate(node.left, names)
        right = _evaluate(node.right, names)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0.0:
                raise ParameterError("division by zero")
            return left / right
        try:
            result = left ** right
        except (OverflowError, ValueError) as exc:
            raise ParameterError("power failed: %s" % exc) from None
        if isinstance(result, complex):
            raise ParameterError("negative base with a fractional exponent is not a real number")
        return float(result)
    raise ParameterError("unsupported syntax: %s" % type(node).__name__)


class ParameterTable:
    """An ordered list of ``(name, expression)`` with iterative resolution.

    References may point forward (``h`` may be defined before ``L``), so resolution retries
    until a fixpoint; anything still unresolved afterwards is reported as unknown or
    circular rather than guessed.
    """

    def __init__(self, entries: Iterable[Tuple[str, str]] | None = None):
        self.entries: List[Tuple[str, str]] = []
        for name, expression in entries or ():
            self.set(name, expression)

    def set(self, name: str, expression: str) -> None:
        """Add or replace a parameter, in place, keeping definition order stable."""
        for index, (existing, _) in enumerate(self.entries):
            if existing == name:
                self.entries[index] = (name, expression)
                return
        self.entries.append((name, expression))

    def remove(self, name: str) -> None:
        self.entries = [(existing, expression) for existing, expression in self.entries if existing != name]

    def resolve(self) -> Tuple[Dict[str, float], Dict[str, str]]:
        """Return ``(values, errors)`` - every parameter, evaluated as far as the table allows."""
        values: Dict[str, float] = {}
        errors: Dict[str, str] = {}
        pending: List[Tuple[str, str]] = []
        for name, expression in self.entries:
            if not name.isidentifier():
                errors[name] = "invalid parameter name"
                continue
            pending.append((name, expression))

        for _ in range(len(pending) + 1):
            if not pending:
                break
            unresolved: List[Tuple[str, str]] = []
            progressed = False
            for name, expression in pending:
                try:
                    values[name] = evaluate_expression(expression, values)
                except UnknownName:
                    unresolved.append((name, expression))
                except ParameterError as exc:
                    errors[name] = str(exc)
                else:
                    progressed = True
            pending = unresolved
            if not progressed:
                break
        for name, expression in pending:
            errors[name] = "unresolved - unknown name or circular reference in %r" % expression
        return values, errors
