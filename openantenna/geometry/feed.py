"""Geometry plan for the corporate feed tree (Phase 2 #5b, package half).

The electrical model lives in :mod:`openantenna.postproc.feed_network` and is verified against
scikit-rf; this module adds the missing *drawing* half: an explicit, symmetric binary-tree plan
that a generator (openEMS deck, 2-D preview, DXF export later) can render without re-deriving
anything electrical.

What this module claims: rectangle/segment data in board coordinates, with counts, symmetry and
quarter-wave section lengths taken from the verified :class:`CorporateFeed`.  What it does NOT
claim: any new electrical behaviour - every width comes from a caller-supplied width function
(e.g. ``microstrip_width_for_impedance``) so the synthesis stays in one place.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeedSegment:
    """One straight feed segment in board coordinates (metres)."""

    x0: float
    y0: float
    x1: float
    y1: float
    width_m: float
    level: int
    role: str  # "trunk" | "transformer" | "arm"


@dataclass(frozen=True)
class FeedPlan:
    """The full corporate-feed drawing plan."""

    n_elements: int
    levels: int
    segments: tuple[FeedSegment, ...]
    junctions: tuple[tuple[float, float], ...]
    notes: str = ""

    def rectangles(self) -> tuple[tuple[float, float, float, float, int, str], ...]:
        """Filled rectangles ``(x_min, y_min, x_max, y_max, level, role)`` for drawing.

        Segments are axis-aligned by construction, so the centre line plus the width gives the
        filled shape a deck builder or a 2-D preview needs.  A non-axis-aligned segment would
        mean the planner produced something the drawing half cannot honour, so it is refused
        rather than silently straightened.
        """
        rects: list[tuple[float, float, float, float, int, str]] = []
        for segment in self.segments:
            half = segment.width_m / 2.0
            if abs(segment.x1 - segment.x0) < 1e-15:  # vertical
                rects.append(
                    (
                        segment.x0 - half,
                        min(segment.y0, segment.y1),
                        segment.x0 + half,
                        max(segment.y0, segment.y1),
                        segment.level,
                        segment.role,
                    )
                )
            elif abs(segment.y1 - segment.y0) < 1e-15:  # horizontal
                rects.append(
                    (
                        min(segment.x0, segment.x1),
                        segment.y0 - half,
                        max(segment.x0, segment.x1),
                        segment.y0 + half,
                        segment.level,
                        segment.role,
                    )
                )
            else:
                raise ValueError(
                    f"segment {segment.role} (level {segment.level}) is not axis-aligned; "
                    "the drawing half only renders axis-aligned feed routing"
                )
        return tuple(rects)

    def bounds(self) -> tuple[float, float, float, float]:
        """Overall ``(x_min, y_min, x_max, y_max)`` of the drawn feed tree."""
        rects = self.rectangles()
        return (
            min(r[0] for r in rects),
            min(r[1] for r in rects),
            max(r[2] for r in rects),
            max(r[3] for r in rects),
        )


def _require_power_of_two(n_elements: int, levels: int) -> None:
    if n_elements < 2 or levels < 1:
        raise ValueError("corporate feed needs n_elements >= 2 and levels >= 1")
    if 2 ** levels != n_elements:
        raise ValueError(
            f"corporate feed supports power-of-two splits only: {n_elements} elements "
            f"need {n_elements.bit_length() - 1} levels, got {levels}"
        )


def plan_corporate_feed_geometry(
    feed,  # postproc.feed_network.CorporateFeed (import kept lazy to avoid a cycle)
    pitch_x_m: float,
    width_of,  # callable: impedance_ohm -> line width in metres
    trunk_length_m: float | None = None,
) -> FeedPlan:
    """Plan the symmetric binary feed tree for ``feed`` over element pitch ``pitch_x_m``.

    Layout convention (documented, not electrical): the tree grows in ``-y`` from the input at
    the origin; each level drops one quarter-wave transformer (vertical, stage-impedance width)
    and routes two horizontal arms of the feed impedance width to the child centres.  Arm
    routing length follows the element pitch - it is layout, not a resonance claim.
    """
    _require_power_of_two(feed.n_elements, feed.levels)
    if pitch_x_m <= 0.0:
        raise ValueError("pitch_x_m must be positive")
    if feed.section_length_m <= 0.0:
        raise ValueError("feed.section_length_m must be positive")

    w_feed = width_of(feed.z0_ohm)
    w_stage = width_of(feed.stage_impedance_ohm)
    trunk = float(trunk_length_m) if trunk_length_m is not None else feed.section_length_m

    segments: list[FeedSegment] = []
    junctions: list[tuple[float, float]] = []

    # trunk: input point straight down to the root junction
    y_root = -trunk
    segments.append(FeedSegment(0.0, 0.0, 0.0, y_root, w_feed, 0, "trunk"))
    junctions.append((0.0, y_root))

    def xs(level: int, index: int) -> float:
        spacing = pitch_x_m * (2 ** (feed.levels - level))
        return (index - (2 ** level - 1) / 2.0) * spacing

    depths = {0: y_root}
    for level in range(1, feed.levels + 1):
        y = y_root - level * feed.section_length_m
        depths[level] = y
        for parent in range(2 ** (level - 1)):
            px = xs(level - 1, parent)
            # vertical quarter-wave transformer from the parent down to this level
            segments.append(
                FeedSegment(px, depths[level - 1], px, y, w_stage, level, "transformer")
            )
            junctions.append((px, y))
            # two horizontal arms to the child centres
            for sign in (-1, 1):
                child = 2 * parent + (0 if sign < 0 else 1)
                cx = xs(level, child)
                arm_dir = 1.0 if cx >= px else -1.0
                x_end = cx
                y_end = y
                segments.append(
                    FeedSegment(
                        px + arm_dir * w_stage / 2.0,
                        y_end,
                        x_end,
                        y_end,
                        w_feed,
                        level,
                        "arm",
                    )
                )
                junctions.append((x_end, y_end))

    plan = FeedPlan(
        n_elements=feed.n_elements,
        levels=feed.levels,
        segments=tuple(segments),
        junctions=tuple(junctions),
        notes=(
            "drawing plan only; electrical behaviour is feed_network.CorporateFeed "
            "(verified against scikit-rf)"
        ),
    )
    return plan


def segment_counts(plan: FeedPlan) -> dict[str, int]:
    """Role counts, the cheap sanity check generators and tests share."""
    counts = {"trunk": 0, "transformer": 0, "arm": 0}
    for segment in plan.segments:
        counts[segment.role] += 1
    return counts
