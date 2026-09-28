"""Example 5 - read a DXF board outline and see what a stroked grid would make of it.

Run:  python examples/05_dxf_outline.py
The example writes its own small DXF (a 40 x 30 mm outline with a 5 mm hole), so it needs
no file from you.  The reader is the stdlib one in geometry.cad - no new dependency.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from openantenna.geometry.cad import (  # noqa: E402
    rasterise_segments,
    read_dxf,
    stroke_fraction,
)

OUTLINE_MM = ((0.0, 0.0), (40.0, 0.0), (40.0, 30.0), (0.0, 30.0))
HOLE_MM = (20.0, 15.0, 5.0)


def _line(x0: float, y0: float, x1: float, y1: float) -> str:
    return "0\nLINE\n8\noutline\n10\n%g\n20\n%g\n11\n%g\n21\n%g\n" % (x0, y0, x1, y1)


def _circle(cx: float, cy: float, radius: float) -> str:
    return "0\nCIRCLE\n8\noutline\n10\n%g\n20\n%g\n40\n%g\n" % (cx, cy, radius)


def write_outline(path: pathlib.Path) -> None:
    """A minimal DXF: an ENTITIES section holding four LINEs and one CIRCLE."""
    body = "0\nSECTION\n2\nENTITIES\n"
    for index in range(len(OUTLINE_MM)):
        start = OUTLINE_MM[index]
        end = OUTLINE_MM[(index + 1) % len(OUTLINE_MM)]
        body += _line(start[0], start[1], end[0], end[1])
    body += _circle(*HOLE_MM)
    body += "0\nENDSEC\n0\nEOF\n"
    path.write_text(body, encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as folder:
        source = pathlib.Path(folder) / "board.dxf"
        write_outline(source)

        segments = read_dxf(source)  # drawing units - here millimetres
        to_metres = 1e-3
        segments = [
            ((a[0] * to_metres, a[1] * to_metres), (b[0] * to_metres, b[1] * to_metres))
            for a, b in segments
        ]
        xs = [x for start, end in segments for x in (start[0], end[0])]
        ys = [y for start, end in segments for y in (start[1], end[1])]

        print("segments       : %d (4 edges, plus the hole polygonised into chords)" % len(segments))
        print(
            "bounds         : x %.0f..%.0f mm, y %.0f..%.0f mm"
            % (min(xs) * 1e3, max(xs) * 1e3, min(ys) * 1e3, max(ys) * 1e3)
        )

        shape, rows = rasterise_segments(segments, 2e-3)  # a 2 mm solver cell
        print("grid at 2 mm   : %d x %d cells" % shape)
        print("stroked        : %.1f %% of the grid" % (stroke_fraction(rows) * 100.0))

    print("NOTE: DXF is an outline, not a surface - these are stroked edges, not filled metal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
