"""Read CAD meshes and turn them into something an FDTD grid can use (Phase 4, CAD import).

Scope, stated before the code: this reads **STL** - both binary and ASCII - with the standard library
only, so the package keeps its no-dependency guarantee.  STEP/IGES are a different order of problem
(they carry solids and curves, and need a CAD kernel); that stays out until there is a reason.

The honest part is what happens after reading.  An FDTD solver wants boxes on a grid, so a triangle
mesh has to be discretised, and the usual answer is a **staircase**: each cell is in or out by
whether the mesh covers its centre.  That is an approximation, and it is louder for slanted faces
than for axis-aligned ones.  Nothing here hides that: ``staircase_occupancy`` returns the grid, and
callers are expected to report the cell size they used.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

Point = Tuple[float, float, float]
Triangle = Tuple[Point, Point, Point]
BINARY_HEADER_BYTES = 84


@dataclass(frozen=True)
class Mesh:
    """A triangle soup with its bounding box."""

    triangles: Tuple[Triangle, ...]

    @property
    def triangle_count(self) -> int:
        return len(self.triangles)

    def scaled(self, factor: float) -> "Mesh":
        """The same mesh with every coordinate multiplied by ``factor``.

        STL carries no units, and CAD tools export in millimetres as often as in metres, so the
        caller states the scale instead of this module guessing.  Guessing would silently put a
        10 mm plate 10 m across the grid.
        """
        if factor <= 0.0:
            raise ValueError("scale factor must be positive")
        return Mesh(
            tuple(
                tuple((point[0] * factor, point[1] * factor, point[2] * factor) for point in triangle)
                for triangle in self.triangles
            )
        )

    def bounds(self) -> Tuple[Point, Point]:
        if not self.triangles:
            raise ValueError("an empty mesh has no bounds")
        xs = [point[0] for triangle in self.triangles for point in triangle]
        ys = [point[1] for triangle in self.triangles for point in triangle]
        zs = [point[2] for triangle in self.triangles for point in triangle]
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def size(self) -> Point:
        low, high = self.bounds()
        return (high[0] - low[0], high[1] - low[1], high[2] - low[2])


def _looks_binary(path: Path) -> bool:
    """A binary STL is 84 bytes of header/declaration plus 50 bytes per triangle."""
    size = path.stat().st_size
    if size < BINARY_HEADER_BYTES:
        return False
    with path.open("rb") as handle:
        header = handle.read(BINARY_HEADER_BYTES)
    declared = struct.unpack("<I", header[80:84])[0]
    return size == BINARY_HEADER_BYTES + 50 * declared


def read_binary_stl(path: str | Path) -> Mesh:
    """Read a binary STL.  The facet count in the header is trusted only after a size check."""
    target = Path(path)
    raw = target.read_bytes()
    if len(raw) < BINARY_HEADER_BYTES:
        raise ValueError(f"{target.name}: too short to be a binary STL")
    declared = struct.unpack("<I", raw[80:84])[0]
    expected = BINARY_HEADER_BYTES + 50 * declared
    if len(raw) != expected:
        raise ValueError(
            f"{target.name}: header declares {declared} triangles ({expected} bytes) but the file "
            f"is {len(raw)} bytes - refusing to guess which is right"
        )
    triangles: List[Triangle] = []
    offset = BINARY_HEADER_BYTES
    for _ in range(declared):
        values = struct.unpack("<12fH", raw[offset : offset + 50])
        points = tuple(
            (float(values[index]), float(values[index + 1]), float(values[index + 2]))
            for index in (3, 6, 9)
        )
        triangles.append(points)  # type: ignore[arg-type]
        offset += 50
    return Mesh(tuple(triangles))


def read_ascii_stl(path: str | Path) -> Mesh:
    """Read an ASCII STL by walking its ``vertex`` lines."""
    target = Path(path)
    text = target.read_text(encoding="utf-8", errors="replace")
    if "vertex" not in text:
        raise ValueError(f"{target.name}: no 'vertex' lines found - not an ASCII STL")
    points: List[Point] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.lower().startswith("vertex"):
            continue
        parts = stripped.split()
        if len(parts) != 4:
            raise ValueError(f"{target.name}: malformed vertex line {stripped[:40]!r}")
        points.append((float(parts[1]), float(parts[2]), float(parts[3])))
    if not points:
        raise ValueError(f"{target.name}: no vertices")
    if len(points) % 3 != 0:
        raise ValueError(
            f"{target.name}: {len(points)} vertices is not a whole number of triangles"
        )
    triangles = [tuple(points[index : index + 3]) for index in range(0, len(points), 3)]
    return Mesh(tuple(triangles))  # type: ignore[arg-type]



def _obj_indices(token: str) -> int:
    """A face token is ``v``, ``v/vt``, ``v//vn`` or ``v/vt/vn``; only the vertex index matters."""
    head = token.split("/", 1)[0]
    if not head:
        raise ValueError(f"malformed face token {token!r}")
    return int(head)


def read_obj(path: str | Path) -> Mesh:
    """Read a Wavefront OBJ as a triangle soup.

    Handles ``v`` vertices and ``f`` faces, with ``v/vt/vn`` tokens and negative (relative) indices.
    Polygons are triangulated by a **fan** from the first vertex, which is exact for convex faces -
    quads and triangles, the common cases - and an approximation for concave ones.  ``vt``, ``vn``,
    ``o``, ``g``, ``s`` and comments are ignored.
    """
    target = Path(path)
    vertices: List[Point] = []
    triangles: List[Triangle] = []
    for number, line in enumerate(target.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if parts[0] == "v":
            if len(parts) < 4:
                raise ValueError(f"{target.name}:{number}: a vertex needs three coordinates")
            vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif parts[0] == "f":
            tokens = parts[1:]
            if len(tokens) < 3:
                raise ValueError(f"{target.name}:{number}: a face needs at least three vertices")
            indices = []
            for token in tokens:
                index = _obj_indices(token)
                resolved = index - 1 if index > 0 else len(vertices) + index
                if not 0 <= resolved < len(vertices):
                    raise ValueError(
                        f"{target.name}:{number}: face refers to vertex {index}, outside the "
                        f"{len(vertices)} vertices defined so far"
                    )
                indices.append(resolved)
            for offset in range(1, len(indices) - 1):
                triangles.append(
                    (vertices[indices[0]], vertices[indices[offset]], vertices[indices[offset + 1]])
                )
    if not vertices:
        raise ValueError(f"{target.name}: no vertices found - not an OBJ")
    if not triangles:
        raise ValueError(f"{target.name}: vertices but no faces")
    return Mesh(tuple(triangles))


def read_mesh(path: str | Path) -> Mesh:
    """Read a mesh, choosing the format by inspecting the file rather than its name.

    STL announces itself by size; OBJ is text whose first meaningful lines are ``v`` or ``f``.
    A file that is neither is refused with the reason, not guessed at.
    """
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"{target} does not exist")
    if _looks_binary(target):
        return read_binary_stl(target)
    head = target.read_text(encoding="utf-8", errors="replace")[:4096]
    body = [
        line.strip()
        for line in head.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if any(line.split()[0] in ("v", "f") for line in body if line.split()):
        return read_obj(target)
    return read_ascii_stl(target)



def _dxf_pairs(text: str):
    """DXF is a flat stream of (group code, value) pairs on alternating lines."""
    lines = text.splitlines()
    for index in range(0, len(lines) - 1, 2):
        raw = lines[index].strip()
        if not raw:
            continue
        try:
            code = int(raw)
        except ValueError as exc:
            raise ValueError(f"line {index + 1}: expected a numeric group code, got {raw!r}") from exc
        yield code, lines[index + 1].strip()


def _polygonise_arc(cx: float, cy: float, radius: float, start_deg: float, end_deg: float, steps: int = 48):
    import math

    span = (end_deg - start_deg) % 360.0
    if span == 0.0:
        span = 360.0
    points = []
    for step in range(steps + 1):
        angle = math.radians(start_deg + span * step / steps)
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def read_dxf(path: str | Path) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Read a DXF's ENTITIES section as a list of 2-D segments (drawing units, mm by convention).

    Supports the entities a board outline actually uses: LINE, LWPOLYLINE (closed or open),
    CIRCLE and ARC.  Anything else - splines, text, hatches, blocks - is left alone and said so
    in the returned note rather than silently flattened.
    """
    target = Path(path)
    text = target.read_text(encoding="utf-8", errors="replace")
    segments: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
    in_entities = False
    kind: str | None = None
    values = {}
    flags = 0
    ignored: Dict[str, int] = {}

    def flush() -> None:
        nonlocal kind, values, flags
        if kind == "LINE" and 10 in values and 11 in values:
            segments.append(((values[10][0], values[20][0]), (values[11][0], values[21][0])))
        elif kind == "LWPOLYLINE":
            points = list(zip(values.get(10, []), values.get(20, [])))
            for index in range(len(points) - 1):
                segments.append((points[index], points[index + 1]))
            if flags & 1 and len(points) > 2:
                segments.append((points[-1], points[0]))
        elif kind == "CIRCLE" and 10 in values and 40 in values:
            points = _polygonise_arc(values[10][0], values[20][0], values[40][0], 0.0, 0.0)
            for index in range(len(points) - 1):
                segments.append((points[index], points[index + 1]))
        elif kind == "ARC" and 10 in values and 40 in values:
            points = _polygonise_arc(
                values[10][0], values[20][0], values[40][0],
                values.get(50, [0.0])[0], values.get(51, [0.0])[0],
            )
            for index in range(len(points) - 1):
                segments.append((points[index], points[index + 1]))
        elif kind:
            ignored[kind] = ignored.get(kind, 0) + 1
        kind, values, flags = None, {}, 0

    for code, value in _dxf_pairs(text):
        if code == 0:
            flush()
            if value == "SECTION":
                continue
            if value == "ENDSEC":
                in_entities = False
                continue
            if in_entities:
                kind = value
            continue
        if code == 2 and value == "ENTITIES":
            in_entities = True
            continue
        if not in_entities:
            continue
        if code == 70:
            try:
                flags = int(float(value))
            except ValueError:
                flags = 0
        elif code in (10, 20, 11, 21, 40, 50, 51):
            try:
                values.setdefault(code, []).append(float(value))
            except ValueError:
                raise ValueError(f"{target.name}: group code {code} carried a non-numeric value {value!r}")
    flush()

    if not segments:
        detail = ", ".join(f"{name} x{count}" for name, count in sorted(ignored.items()))
        raise ValueError(
            f"{target.name}: no LINE/LWPOLYLINE/CIRCLE/ARC entities found"
            + (f" (ignored: {detail})" if detail else "")
        )
    return segments


def rasterise_segments(
    segments, cell_m: float, *, max_cells: int = 2000, margin_m: float = 0.0
) -> Tuple[Tuple[int, int], List[List[bool]]]:
    """Stroke 2-D segments onto a square grid.  Samples at half-cell steps so a diagonal
    outline cannot slip between two rows of cells the way a single endpoint test would.
    """
    if cell_m <= 0.0:
        raise ValueError("cell size must be positive")
    xs = [x for start, end in segments for x in (start[0], end[0])]
    ys = [y for start, end in segments for y in (start[1], end[1])]
    low_x, high_x = min(xs) - margin_m, max(xs) + margin_m
    low_y, high_y = min(ys) - margin_m, max(ys) + margin_m
    width = int((high_x - low_x) / cell_m) + 1
    height = int((high_y - low_y) / cell_m) + 1
    if width > max_cells or height > max_cells:
        raise ValueError(
            f"a {width} x {height} grid exceeds the {max_cells} cells/axis cap - enlarge cell_m"
        )
    rows = [[False] * width for _ in range(height)]
    for start, end in segments:
        span = max(abs(end[0] - start[0]), abs(end[1] - start[1]))
        steps = max(1, int(span / (cell_m / 2.0)) + 1)
        for step in range(steps + 1):
            fraction = step / steps
            x = start[0] + (end[0] - start[0]) * fraction
            y = start[1] + (end[1] - start[1]) * fraction
            column = int((x - low_x) / cell_m)
            row = int((y - low_y) / cell_m)
            if 0 <= row < height and 0 <= column < width:
                rows[row][column] = True
    return (width, height), rows


def stroke_fraction(rows) -> float:
    """Fraction of the grid the outline touches - the outline analogue of occupancy_fraction."""
    total = sum(len(row) for row in rows)
    if not total:
        return 0.0
    return sum(1 for row in rows for cell in row if cell) / total


def read_stl(path: str | Path) -> Mesh:
    """Read an STL, binary or ASCII, choosing by measurement rather than by extension."""
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"{target} does not exist")
    if _looks_binary(target):
        return read_binary_stl(target)
    return read_ascii_stl(target)


def staircase_occupancy(
    mesh: Mesh,
    cell_m: float,
    *,
    plane: str = "xy",
    margin_m: float = 0.0,
) -> Tuple[Tuple[int, int], List[List[bool]]]:
    """Rasterise the mesh onto a grid of ``cell_m`` by testing each cell centre.

    Returns ``((n_x, n_y), rows)`` where ``rows[row][col]`` is True when the mesh covers that cell
    centre.  The mesh is treated as a thin surface: a cell counts as occupied when *any* triangle
    contains its projected centre, which is what a staircase discretisation of a sheet means and is
    why a coarse cell is a visible approximation for slanted faces.
    """
    if cell_m <= 0.0:
        raise ValueError("cell_m must be positive")
    if mesh.triangle_count == 0:
        raise ValueError("cannot rasterise an empty mesh")
    axes = {"xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}
    if plane not in axes:
        raise ValueError(f"plane must be one of {sorted(axes)}")
    first, second = axes[plane]

    low, high = mesh.bounds()
    low_1 = low[first] - margin_m
    low_2 = low[second] - margin_m
    n_1 = max(1, int((high[first] - low[first] + 2 * margin_m) / cell_m) + 1)
    n_2 = max(1, int((high[second] - low[second] + 2 * margin_m) / cell_m) + 1)

    projections = [
        [(point[first], point[second]) for point in triangle] for triangle in mesh.triangles
    ]

    def inside(triangle: Sequence[Tuple[float, float]], px: float, py: float) -> bool:
        (ax, ay), (bx, by), (cx, cy) = triangle
        denominator = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(denominator) < 1e-15:
            return False  # degenerate triangle contributes nothing
        weight_a = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / denominator
        weight_b = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / denominator
        weight_c = 1.0 - weight_a - weight_b
        tolerance = -1e-12
        return weight_a >= tolerance and weight_b >= tolerance and weight_c >= tolerance

    rows: List[List[bool]] = []
    for row in range(n_2):
        py = low_2 + (row + 0.5) * cell_m
        occupancy_row = []
        for column in range(n_1):
            px = low_1 + (column + 0.5) * cell_m
            occupancy_row.append(any(inside(triangle, px, py) for triangle in projections))
        rows.append(occupancy_row)
    return (n_1, n_2), rows


def occupancy_fraction(rows: Iterable[Iterable[bool]]) -> float:
    """Share of occupied cells - a cheap sanity number when reporting an import."""
    rows = [list(row) for row in rows]
    if not rows or not rows[0]:
        return 0.0
    total = sum(len(row) for row in rows)
    occupied = sum(1 for row in rows for cell in row if cell)
    return occupied / total if total else 0.0
