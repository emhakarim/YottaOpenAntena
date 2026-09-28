"""Sketch polygons: what a drawing is worth to a solver, in one place.

The GUI sketch tab draws traces, polygons, rectangles, circles and blocks; a solver needs
*metal regions*, and the only shape the drawing pipeline can hand over unambiguously is a
closed polygon (docs/sketch-to-deck.md).  This module validates those polygons, and it is
where the conversion rules will live when the GUI pushes a sketch into a project:

* a closed polygon / rectangle / block footprint is a polygon;
* a circle is polygonised into chords, the way the DXF reader does it;
* an open trace is refused - a stroked line is not a filled region, and pretending it is
  would silently change the metal;
* a block's thickness is not used by the v1 bridge: the deck draws zero-thickness PEC
  sheets, so the footprint is what travels.

Validation is strict on purpose.  A self-intersecting or degenerate polygon would be
rasterised by the FDTD mesh into *something*, and the mistake would surface hours later as
a wrong number; refusing it at construction is the only honest option.
"""

from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

Point = Tuple[float, float]
Polygon = Tuple[Point, ...]

#: A cap on vertices (interactive drawings are small), and a sanity bound in metres: the
#: sketch draws millimetres, so a coordinate beyond a few metres is a unit error.
MAX_POINTS = 256
LIMIT_M = 5.0

#: Points closer than this (metres) count as the same point: a near-duplicate on a drawn
#: edge would otherwise reach AddPolygon as a zero-length edge (review note, Yotta §6o).
EPSILON_M = 1e-9


def _point(value, where: str) -> Point:
    try:
        x, y = value
    except (TypeError, ValueError):
        raise ValueError(
            "%s: each point must be an (x, y) pair, got %r" % (where, value)
        ) from None
    numbers: List[float] = []
    for number in (x, y):
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            raise ValueError("%s: coordinates must be numbers, got %r" % (where, number))
        as_float = float(number)
        if as_float != as_float or as_float in (float("inf"), float("-inf")):
            raise ValueError("%s: coordinates must be finite, got %r" % (where, number))
        if abs(as_float) > LIMIT_M:
            raise ValueError(
                "%s: coordinate %.6g m is beyond the +/- %.1f m sanity limit - units are "
                "metres (the sketch draws millimetres)" % (where, as_float, LIMIT_M)
            )
        numbers.append(as_float)
    return (numbers[0], numbers[1])


def _close(a: Point, b: Point, eps: float = EPSILON_M) -> bool:
    return abs(a[0] - b[0]) <= eps and abs(a[1] - b[1]) <= eps


def _orientation(a: Point, b: Point, c: Point) -> int:
    value = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if value > 0.0:
        return 1
    if value < 0.0:
        return -1
    return 0


def _within_box(a: Point, b: Point, p: Point) -> bool:
    return (
        min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
        and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
    )


def _segments_cross(a1: Point, a2: Point, b1: Point, b2: Point) -> bool:
    """True when the two segments touch or cross (touching counts - see the module note)."""
    o1 = _orientation(a1, a2, b1)
    o2 = _orientation(a1, a2, b2)
    o3 = _orientation(b1, b2, a1)
    o4 = _orientation(b1, b2, a2)
    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and _within_box(a1, a2, b1):
        return True
    if o2 == 0 and _within_box(a1, a2, b2):
        return True
    if o3 == 0 and _within_box(b1, b2, a1):
        return True
    if o4 == 0 and _within_box(b1, b2, a2):
        return True
    return False


def polygon_self_intersects(polygon: Sequence[Point]) -> bool:
    """True when any two non-adjacent edges touch or cross (a self-intersecting outline)."""
    count = len(polygon)
    for i in range(count):
        a1 = polygon[i]
        a2 = polygon[(i + 1) % count]
        for j in range(i + 1, count):
            if (j - i) == 1 or (j - i) == count - 1:
                continue  # adjacent edges share a vertex by construction
            b1 = polygon[j]
            b2 = polygon[(j + 1) % count]
            if _segments_cross(a1, a2, b1, b2):
                return True
    return False


def polygon_area(polygon: Sequence[Point]) -> float:
    """Absolute area of a simple polygon (shoelace)."""
    total = 0.0
    count = len(polygon)
    for index in range(count):
        x1, y1 = polygon[index]
        x2, y2 = polygon[(index + 1) % count]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def validate_polygon(
    points: Iterable, *, where: str = "polygon", max_points: int = MAX_POINTS
) -> Polygon:
    """Coerce and validate one closed polygon; raises ValueError naming the problem.

    Consecutive duplicate points (including the closing one) are normalised away rather
    than refused - an interactive canvas produces them, and they do not change the shape.
    Near-duplicates within ``EPSILON_M`` are treated the same way, so no zero-length edge
    can reach the solver (review note, Yotta §6o).
    """
    coerced = [_point(item, where) for item in points]
    deduped: List[Point] = []
    for point in coerced:
        if not deduped or not _close(point, deduped[-1]):
            deduped.append(point)
    if len(deduped) > 1 and _close(deduped[0], deduped[-1]):
        deduped.pop()
    if len(deduped) < 3:
        raise ValueError(
            "%s: a polygon needs at least 3 distinct points, got %d" % (where, len(deduped))
        )
    if len(deduped) > max_points:
        raise ValueError(
            "%s: %d points exceed the %d-point cap" % (where, len(deduped), max_points)
        )
    polygon = tuple(deduped)
    if polygon_self_intersects(polygon):
        raise ValueError("%s: the outline crosses itself" % where)
    if polygon_area(polygon) == 0.0:
        raise ValueError("%s: the polygon has zero area (all points on one line?)" % where)
    return polygon
