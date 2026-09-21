"""Parameter sweep engine (stdlib only).

A sweep is a Cartesian product of ``SweepAxis`` objects.  Each axis writes one
scalar into the neutral project document at a dotted path, e.g.
``substrate.layers.0.thickness_m`` or ``array.spacing_x_lambda0`` -- so a sweep
definition stays a plain JSON document and is not tied to any solver.

Phase 1 implements the *enumeration* and a ``dry_run`` manifest: the list of
jobs is written down and can be inspected before anything expensive is
executed.  Running the jobs requires a solver adapter that reports
``available() == True``.
"""

from __future__ import annotations

import copy
import datetime as _dt
import itertools
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from ..model.project import Project


@dataclass(frozen=True)
class SweepAxis:
    """One swept scalar, addressed by a dotted path into the project document."""

    path: str
    values: tuple

    def __post_init__(self) -> None:
        if not isinstance(self.path, str) or not self.path.strip():
            raise ValueError("SweepAxis.path must be a non-empty dotted path")
        if not self.values:
            raise ValueError("SweepAxis.values must not be empty")

    @classmethod
    def parse(cls, text: str) -> "SweepAxis":
        """Parse ``path=v1,v2,v3`` (as accepted on the command line).

        Values are read as int when possible, then float, then left as strings -
        so a material sweep such as ``substrate.layers.0.material=PTFE,FR-4``
        works with the same syntax as a numeric sweep.
        """
        if "=" not in text:
            raise ValueError(f"axis {text!r} must look like path=v1,v2,v3")
        path, raw_values = text.split("=", 1)
        values: List[Any] = []
        for token in raw_values.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                values.append(int(token))
                continue
            except ValueError:
                pass
            try:
                values.append(float(token))
                continue
            except ValueError:
                values.append(token)
        if not values:
            raise ValueError(f"axis {path!r} has no values")
        return cls(path=path.strip(), values=tuple(values))

    def to_dict(self) -> Dict[str, Any]:
        return {"path": self.path, "values": list(self.values)}


@dataclass
class SweepJob:
    """One point of the sweep."""

    job_id: str
    overrides: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"job_id": self.job_id, "overrides": dict(self.overrides)}


def _set_dotted(document: Dict[str, Any], path: str, value: Any) -> None:
    """Set ``value`` at a dotted ``path``, which must already exist."""
    parts = path.split(".")
    node: Any = document
    for index, part in enumerate(parts[:-1]):
        if isinstance(node, list):
            position = int(part)
            try:
                node = node[position]
            except (IndexError, ValueError):
                raise KeyError(
                    f"cannot resolve {part!r} in path {path!r} (list index out of range)"
                ) from None
        elif isinstance(node, dict):
            if part not in node:
                raise KeyError(f"unknown path segment {part!r} in {path!r}")
            node = node[part]
        else:
            raise KeyError(f"path {path!r} descends into a scalar at {part!r}")

    last = parts[-1]
    if isinstance(node, list):
        try:
            node[int(last)] = value
        except (IndexError, ValueError):
            raise KeyError(f"cannot set list index {last!r} in {path!r}") from None
    elif isinstance(node, dict):
        if last not in node:
            raise KeyError(f"unknown path segment {last!r} in {path!r}")
        node[last] = value
    else:
        raise KeyError(f"path {path!r} does not resolve to a mapping or list")


def _job_id(overrides: Mapping[str, Any]) -> str:
    if not overrides:
        return "job000"
    chunks = []
    for path, value in overrides.items():
        label = path.split(".")[-1]
        chunks.append(f"{label}={value}")
    return "job_" + "__".join(chunks).replace(" ", "")


class ParameterSweep:
    """Cartesian product of axes applied to a base project."""

    def __init__(
        self, project: Project, axes: Sequence[SweepAxis] = (), base_name: str = "sweep"
    ) -> None:
        if not isinstance(project, Project):
            raise TypeError("project must be a Project instance")
        self.project = project
        self.axes: List[SweepAxis] = list(axes)
        self.base_name = base_name
        # Fail fast on a malformed axis rather than after hours of simulation.
        template = project.to_dict()
        for axis in self.axes:
            _set_dotted(copy.deepcopy(template), axis.path, axis.values[0])

    @property
    def job_count(self) -> int:
        total = 1
        for axis in self.axes:
            total *= len(axis.values)
        return total

    def jobs(self) -> List[SweepJob]:
        if not self.axes:
            return [SweepJob(job_id="job000", overrides={})]
        job_list: List[SweepJob] = []
        for index, combination in enumerate(
            itertools.product(*[axis.values for axis in self.axes])
        ):
            overrides = {
                axis.path: value for axis, value in zip(self.axes, combination)
            }
            job_list.append(
                SweepJob(job_id=f"{_job_id(overrides)}__{index:04d}", overrides=overrides)
            )
        return job_list

    def project_for(self, job: SweepJob) -> Project:
        """Materialise the concrete project for one job."""
        document = self.project.to_dict()
        for path, value in job.overrides.items():
            _set_dotted(document, path, value)
        # Keep the datum label out of the name field of the stored project.
        resolved = Project.from_dict(document)
        resolved.name = f"{self.base_name}:{job.job_id}"
        return resolved

    def dry_run_manifest(self, out_path: str | Path) -> Path:
        """Write the enumeration to JSON without running any solver."""
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "kind": "openantenna.sweep-manifest",
            "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "base_project": self.project.to_dict(),
            "axes": [axis.to_dict() for axis in self.axes],
            "job_count": self.job_count,
            "jobs": [job.to_dict() for job in self.jobs()],
            "executed": False,
            "note": (
                "DRY RUN: no solver was executed. This manifest enumerates the jobs "
                "only; results are not simulated."
            ),
        }
        target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return target.resolve()

    def describe(self) -> str:
        lines = [
            f"base project     : {self.project.name}",
            f"axes             : {len(self.axes)}",
        ]
        for axis in self.axes:
            values = ", ".join(str(v) for v in axis.values)
            lines.append(f"  - {axis.path} in [{values}]")
        lines.append(f"job count        : {self.job_count}")
        return "\n".join(lines)
