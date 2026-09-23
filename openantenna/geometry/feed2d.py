"""Two-layer corporate tree for a planar feed (Phase 2 #5b, 2-D half).

The 1-D planner in :mod:`openantenna.geometry.feed` cannot be stacked into a 2-D grid: its growth
axis is also its spread axis, so a second stage has nowhere to grow.  Measured consequence, recorded
in ``docs/feed-network-2d-design.md``: a single-layer recursive H-tree overlaps itself by 7 pairs on
a 2x2 and 19 on a 4x4, *identically* at 60, 90 and 120 mm pitch.  The collisions are structural, not
a spacing problem.

This module splits the problem by plane instead:

* ``feed`` layer - the column tree (spread along x, growing away from the array) plus the routing
  channel that carries each column's feed out to that column's row-tree input;
* ``patch`` layer - one rotated row tree per column (spread along y, growing sideways in x), whose
  leaves sit on the element feed line;
* ``via`` - the vertical riser joining the channel to each row-tree input.

Collision-freedom is a property of the construction: the column tree is entirely below the array,
each row tree plus its riser lives inside its own column band of width ``depth_row_m``, and the
channel runs below every row tree.  The two conditions that make it hold are checked and refused
rather than assumed.

Honest scope: this is drawing geometry.  The row segments follow the element grid, so turning them
into exactly lambda/4 sections needs meander padding and a real synthesis pass - that stays open, and
``docs/feed-network-2d-design.md`` says so.
"""

from __future__ import annotations

from dataclasses import dataclass

from .feed import plan_corporate_feed_geometry

LAYERS = ("feed", "patch", "via")


@dataclass(frozen=True)
class Tree2DSegment:
    """One straight segment on one conductor layer."""

    x0: float
    y0: float
    x1: float
    y1: float
    width_m: float
    layer: str
    role: str


@dataclass(frozen=True)
class Tree2DPlan:
    rows: int
    cols: int
    segments: tuple[Tree2DSegment, ...]
    leaves: tuple[tuple[float, float], ...]
    input_point: tuple[float, float]
    channel_y_m: float
    depth_row_m: float
    notes: str = ""

    def rectangles(self, layer: str | None = None):
        """``(x0, y0, x1, y1, layer, role)`` filled rectangles, optionally one layer only."""
        rects = []
        for segment in self.segments:
            if layer is not None and segment.layer != layer:
                continue
            half = segment.width_m / 2.0
            if abs(segment.x1 - segment.x0) < 1e-15:
                rects.append(
                    (
                        segment.x0 - half,
                        min(segment.y0, segment.y1),
                        segment.x0 + half,
                        max(segment.y0, segment.y1),
                        segment.layer,
                        segment.role,
                    )
                )
            elif abs(segment.y1 - segment.y0) < 1e-15:
                rects.append(
                    (
                        min(segment.x0, segment.x1),
                        segment.y0 - half,
                        max(segment.x0, segment.x1),
                        segment.y0 + half,
                        segment.layer,
                        segment.role,
                    )
                )
            else:
                raise ValueError("every tree segment must be axis-aligned")
        return tuple(rects)

    def collisions(self, layer: str | None = None):
        """Pairs of rectangles lying on top of each other within a layer.

        A junction is not a collision: where an arm meets the foot of the next level the rectangles
        overlap by about one line width, which is the intended connection.  A pair is counted only
        when the overlap is deeper than 1.5 line widths on *both* axes.  Known limitation, stated
        rather than hidden: two parallel strips touching along their length share only one width on
        the thin axis and are not flagged here; the two-layer construction avoids that structurally.
        """
        rects = self.rectangles(layer)
        widths = [max(r[2] - r[0], r[3] - r[1]) for r in rects]
        limit = 1.5 * (max(widths) if widths else 0.0)
        hits = []
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                a, b = rects[i], rects[j]
                dx = min(a[2], b[2]) - max(a[0], b[0])
                dy = min(a[3], b[3]) - max(a[1], b[1])
                if dx > limit and dy > limit:
                    hits.append((i, j))
        return tuple(hits)

    def layers_present(self) -> tuple[str, ...]:
        present = {segment.layer for segment in self.segments}
        return tuple(name for name in LAYERS if name in present)

    def bounds(self) -> tuple[float, float, float, float]:
        rects = self.rectangles()
        return (
            min(r[0] for r in rects),
            min(r[1] for r in rects),
            max(r[2] for r in rects),
            max(r[3] for r in rects),
        )


def _stage_feed(count: int, frequency_hz: float, epsilon_eff: float, z0_ohm: float):
    from ..postproc.feed_network import synthesise_corporate_feed

    if count < 2 or (count & (count - 1)) != 0:
        raise ValueError(
            "corporate feed needs a power-of-two element count per axis, got %d." % count
        )
    return synthesise_corporate_feed(
        n_elements=count, frequency_hz=frequency_hz, epsilon_eff=epsilon_eff, z0_ohm=z0_ohm
    )


def _stage_segments(feed, pitch_m: float, width_of, trunk_m: float):
    """The 1-D plan a stage is built from: one source of truth for stage geometry."""
    return plan_corporate_feed_geometry(
        feed, pitch_m, width_of, trunk_length_m=trunk_m
    ).segments


def plan_h_tree_2d(
    rows: int,
    cols: int,
    pitch_x_m: float,
    pitch_y_m: float,
    width_of,
    section_length_m: float,
    epsilon_eff: float,
    frequency_hz: float,
    leaf_offset_y_m: float = 0.0,
    channel_clearance_m: float | None = None,
    z0_ohm: float = 50.0,
) -> Tree2DPlan:
    """Plan the two-layer tree for a ``rows`` by ``cols`` element grid.

    ``leaf_offset_y_m`` moves the row-tree leaf line relative to the element centres - typically
    ``-patch_length/2``, i.e. onto the elements' feed edge.
    """
    if rows < 1 or cols < 1:
        raise ValueError("rows and cols must be positive")
    if rows * cols < 2:
        raise ValueError("a corporate tree needs at least two elements")
    if pitch_x_m <= 0.0 or pitch_y_m <= 0.0:
        raise ValueError("pitches must be positive")
    if section_length_m <= 0.0:
        raise ValueError("section_length_m must be positive")

    feed_cols = _stage_feed(cols, frequency_hz, epsilon_eff, z0_ohm)
    feed_rows = _stage_feed(rows, frequency_hz, epsilon_eff, z0_ohm)

    w0 = width_of(z0_ohm)
    short_trunk = max(2.0 * w0, 1.0e-3)

    # row stage depth: short trunk + one quarter-wave section per level
    row_segments = _stage_segments(feed_rows, pitch_y_m, width_of, short_trunk)
    row_depth_m = abs(min(min(s.y0, s.y1) for s in row_segments))
    if row_depth_m >= pitch_x_m:
        raise ValueError(
            "the row tree needs %.3f mm of depth but the column pitch is %.3f mm: a two-layer tree "
            "still needs each row tree to fit inside its own column band."
            % (row_depth_m * 1e3, pitch_x_m * 1e3)
        )

    column_segments = _stage_segments(feed_cols, pitch_x_m, width_of, short_trunk)
    column_depth = abs(min(min(s.y0, s.y1) for s in column_segments))
    half_y = rows * pitch_y_m / 2.0
    clearance = (
        channel_clearance_m
        if channel_clearance_m is not None
        else max(4.0 * w0, 2.0e-3)
    )
    channel_y = -(half_y + clearance)

    # the column tree is mirrored in y so it grows *up* from the input at the board edge: the
    # input sits below the routing channel, the leaves land in it
    base_y = channel_y - column_depth
    segments: list[Tree2DSegment] = []
    for segment in column_segments:
        segments.append(
            Tree2DSegment(
                segment.x0,
                base_y - segment.y0,
                segment.x1,
                base_y - segment.y1,
                segment.width_m,
                "feed",
                segment.role,
            )
        )
    input_point = (0.0, base_y)

    leaves: list[tuple[float, float]] = []
    for index in range(cols):
        column_x = (index - (cols - 1) / 2.0) * pitch_x_m
        x_in = column_x + row_depth_m
        # routing channel out to this column's riser, then the riser itself
        segments.append(
            Tree2DSegment(column_x, channel_y, x_in, channel_y, w0, "feed", "route")
        )
        segments.append(Tree2DSegment(x_in, channel_y, x_in, 0.0, w0, "via", "riser"))
        # the row tree, rotated: natural (a, b) -> (b, a), moved so leaves land at column_x
        for segment in row_segments:
            segments.append(
                Tree2DSegment(
                    column_x + row_depth_m + segment.y0,
                    segment.x0 + leaf_offset_y_m,
                    column_x + row_depth_m + segment.y1,
                    segment.x1 + leaf_offset_y_m,
                    segment.width_m,
                    "patch",
                    segment.role,
                )
            )
        for row_index in range(rows):
            leaves.append(
                (
                    column_x,
                    (row_index - (rows - 1) / 2.0) * pitch_y_m + leaf_offset_y_m,
                )
            )

    return Tree2DPlan(
        rows=rows,
        cols=cols,
        segments=tuple(segments),
        leaves=tuple(leaves),
        input_point=input_point,
        channel_y_m=channel_y,
        depth_row_m=row_depth_m,
        notes=(
            "Two-layer tree: column tree and routing channel on the feed layer, rotated row trees "
            "on the patch layer, vertical risers between them. Drawing geometry only - lambda/4 "
            "padding of the row segments is still open (docs/feed-network-2d-design.md)."
        ),
    )
