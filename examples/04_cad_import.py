"""Example 4 - read an STL from CAD and see what the grid would make of it.

Run:  python examples/04_cad_import.py
The example writes its own small STL (a 40 x 30 mm plate), so it needs no file from you.
"""

from __future__ import annotations

import pathlib
import struct
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from openantenna.geometry.cad import (  # noqa: E402
    occupancy_fraction,
    read_stl,
    staircase_occupancy,
)

PLATE_MM = ((0.0, 0.0), (40.0, 0.0), (40.0, 30.0), (0.0, 30.0))


def write_plate(path: pathlib.Path) -> None:
    triangles = []
    for index in range(4):
        a = PLATE_MM[index]
        b = PLATE_MM[(index + 1) % 4]
        triangles.append(((a[0], a[1], 0.0), (b[0], b[1], 0.0), (0.0, 0.0, 0.0)))
    payload = b"openantenna-example".ljust(80, b"\0") + struct.pack("<I", len(triangles))
    for a, b, c in triangles:
        payload += struct.pack("<12fH", 0, 0, 1, *a, *b, *c, 0)
    path.write_bytes(payload)


def main() -> int:
    with tempfile.TemporaryDirectory() as folder:
        source = pathlib.Path(folder) / "plate.stl"
        write_plate(source)
        mesh = read_stl(source).scaled(1e-3)  # CAD exported millimetres
        low, high = mesh.bounds()
        print("triangles      : %d" % mesh.triangle_count)
        print("size           : %.1f x %.1f mm" % ((high[0] - low[0]) * 1e3, (high[1] - low[1]) * 1e3))
        shape, rows = staircase_occupancy(mesh, 5e-3)
        print("grid at 5 mm   : %d x %d cells" % shape)
        print("occupied       : %.1f %% of the grid" % (occupancy_fraction(rows) * 100.0))
    print("NOTE: staircase discretisation - quote the cell size with any result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
