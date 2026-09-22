"""Command line interface for OpenAntenna Studio (stdlib argparse only).

Phase 1 is headless: this CLI is the only user entry point.  Every command is
read-only with respect to the project *except* the ``gen-openems`` and
``sweep dry-run`` commands, which write into an explicit output directory.

Nothing here runs an electromagnetic solver except ``solver probe``/``run``,
and those report honestly when no solver is installed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List, Optional

from . import __version__
from .geometry.array import build_array_layout
from .geometry.patch import synthesize_patch
from .materials import mixing
from .materials.library import (
    BUILTIN_MATERIALS,
    Material,
    get_material,
    list_material_names,
    load_library,
)
from .model.project import ArrayConfig, FrequencySweep, PatchGeometry, Project, SubstrateStackup
from .solvers.openems import OpenEMSSolver
from .sweep.engine import ParameterSweep, SweepAxis

EXIT_OK = 0
EXIT_ERROR = 1


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _dump(payload: Any) -> str:
    """JSON dump that survives tuples/complex numbers coming from the maths."""
    return json.dumps(payload, indent=2, default=str)


def _csv_values(text: str) -> List[float]:
    values: List[float] = []
    for token in text.split(","):
        token = token.strip()
        if token:
            values.append(float(token))
    if not values:
        raise argparse.ArgumentTypeError("expected at least one numeric value")
    return values


def _base_project(args: argparse.Namespace) -> Project:
    stackup = SubstrateStackup.single(args.material, args.h)
    design = synthesize_patch(
        frequency_hz=args.freq,
        epsilon_r=get_material(args.material).epsilon_r,
        height_m=args.h,
        feed_mode=args.feed,
    )
    patch = PatchGeometry(
        width_m=design.width_m,
        length_m=design.length_m,
        feed_mode=args.feed,
        feed_inset_m=design.inset_depth_m or None,
    )
    array = ArrayConfig(
        nx=getattr(args, "nx", 1),
        ny=getattr(args, "ny", 1),
        spacing_x_lambda0=getattr(args, "spacing_lambda", 0.5),
        spacing_y_lambda0=getattr(args, "spacing_lambda", 0.5),
        feed_mode="corporate" if getattr(args, "nx", 1) * getattr(args, "ny", 1) > 1 else args.feed,
    )
    sweep = FrequencySweep(
        start_hz=args.start,
        stop_hz=args.stop,
        points=args.points,
    )
    return Project(name=args.name, substrate=stackup, patch=patch, array=array, sweep=sweep)


def _add_design_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name", default="design", help="project name")
    parser.add_argument("--freq", type=float, default=2.45e9, help="design frequency [Hz]")
    parser.add_argument(
        "--material", default="PTFE", help="substrate material name from the library"
    )
    parser.add_argument("--er", type=float, default=None, help="override substrate epsilon_r")
    parser.add_argument("--h", type=float, default=0.0016, help="substrate thickness [m]")
    parser.add_argument(
        "--feed", choices=("inset", "edge", "probe"), default="inset", help="feed style"
    )
    parser.add_argument("--start", type=float, default=None, help="sweep start [Hz]")
    parser.add_argument("--stop", type=float, default=None, help="sweep stop [Hz]")
    parser.add_argument("--points", type=int, default=201, help="sweep points")


def _resolve_sweep(args: argparse.Namespace) -> None:
    """Fill in default sweep start/stop around the design frequency (+-15 %)."""
    if args.start is None:
        args.start = args.freq * 0.85
    if args.stop is None:
        args.stop = args.freq * 1.15
    if args.start <= 0 or args.stop <= args.start:
        raise ValueError("sweep start/stop are inconsistent")


def _material_epsilon(args: argparse.Namespace) -> float:
    """Substrate epsilon_r, honouring an explicit --er override."""
    if getattr(args, "er", None) is not None:
        return float(args.er)
    return float(get_material(args.material).epsilon_r)


# --------------------------------------------------------------------------
# command handlers
# --------------------------------------------------------------------------
def cmd_material_list(args: argparse.Namespace) -> int:
    library = load_library(args.library, include_builtins=False) if args.library else None
    names = list_material_names(library)
    if args.library:
        names = names + [n for n in list_material_names(BUILTIN_MATERIALS) if n not in names]
    print(f"{len(names)} material(s)" + (f" from {args.library}" if args.library else " (built-in)"))
    print(f"{'name':<18}{'eps_r':>8}{'mu_r':>7}{'tan_d':>10}{'sigma [S/m]':>14}  kind")
    for name in names:
        material = get_material(name, library) if library and name in library else get_material(name)
        print(
            f"{material.name:<18}{material.epsilon_r:>8.4g}{material.mu_r:>7.3g}"
            f"{material.tan_delta:>10.4g}{material.conductivity_s_per_m:>14.4g}  {material.kind}"
        )
    return EXIT_OK


def cmd_material_show(args: argparse.Namespace) -> int:
    library = load_library(args.library, include_builtins=True) if args.library else None
    try:
        material: Material = get_material(args.name, library)
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(_dump(material.to_dict()))
    if material.source_note:
        print(f"\nsource: {material.source_note}")
    print(
        f"\neffective tan_delta @ {args.freq / 1e9:g} GHz: "
        f"{material.effective_tan_delta(args.freq):.6g}"
        f"  (bulk {material.tan_delta:g} + conduction "
        f"{material.conduction_tan_delta(args.freq):.6g})"
    )
    return EXIT_OK


def cmd_mix(args: argparse.Namespace) -> int:
    table = mixing.compare_models(
        args.matrix, args.filler, args.vf, frequency_hz=args.freq
    )
    print("composite effective permittivity (quasi-static mixing rules)")
    print(f"matrix eps_r={args.matrix:g}, filler eps_r={args.filler:g}, vf={args.vf:g}")
    print()
    print(mixing.format_comparison_table(table))

    print("\neffective loss tangent (order-of-magnitude estimate, two bounds)")
    print(
        _dump(
            mixing.estimate_effective_tan_delta(
                args.matrix,
                args.filler,
                args.vf,
                tan_delta_matrix=args.tan_matrix,
                tan_delta_filler=args.tan_filler,
            )
        )
    )

    warnings = [
        mixing.percolation_warning(args.vf),
        mixing.maxwell_wagner_warning(args.freq),
        mixing.quasi_static_warning(args.freq, args.particle_size, args.filler),
    ]
    relevant = [w for w in warnings if w]
    if relevant:
        print("\nwarnings (these limit how much the numbers above can be trusted):")
        for warning in relevant:
            print(f"  - {warning}")
    else:
        print("\nno validity warnings triggered for these inputs.")
    return EXIT_OK


def cmd_design_patch(args: argparse.Namespace) -> int:
    _resolve_sweep(args)
    project = _base_project(args)
    design = synthesize_patch(
        frequency_hz=args.freq,
        epsilon_r=_material_epsilon(args),
        height_m=args.h,
        feed_mode=args.feed,
    )
    print(design.summary())
    project_warnings = project.check()
    if project_warnings:
        print()
        for warning in project_warnings:
            print(f"project note     : {warning}")
    if args.json:
        print()
        print(_dump(design.to_dict()))
    if args.project_out:
        target = Path(args.project_out)
        target.write_text(project.to_json() + "\n", encoding="utf-8")
        print(f"\nproject written  : {target.resolve()}")
    print(
        "\nreminder: transmission-line synthesis only -- confirm with a full-wave "
        "solver before fabrication."
    )
    return EXIT_OK


def cmd_design_array(args: argparse.Namespace) -> int:
    _resolve_sweep(args)
    design = synthesize_patch(
        frequency_hz=args.freq,
        epsilon_r=_material_epsilon(args),
        height_m=args.h,
        feed_mode=args.feed,
    )
    array = ArrayConfig(
        nx=args.nx,
        ny=args.ny,
        spacing_x_lambda0=args.spacing_lambda,
        spacing_y_lambda0=args.spacing_lambda,
        feed_mode="corporate" if args.nx * args.ny > 1 else args.feed,
    )
    layout = build_array_layout(array, args.freq, design)
    print(layout.summary())
    if args.json:
        print()
        print(_dump(layout.to_dict()))
    print(
        "\nreminder: element count, spacing and aperture are geometry only. Coupling, "
        "scan blindness and feed-network behaviour need a full-wave run."
    )
    return EXIT_OK


def cmd_solver_status(args: argparse.Namespace) -> int:
    solver = OpenEMSSolver()
    status = solver.available()
    print(f"solver           : {status.name}")
    print(f"available        : {status.available}")
    print(f"binary           : {status.binary_path or '-'}")
    print(f"detail           : {status.detail}")
    if not status.available:
        print(
            "\nModel generation still works. To run simulations, install openEMS/CSXCAD "
            "(separate process, GPLv3/LGPLv3 - see docs/licensing.md) and re-check."
        )
    return EXIT_OK


def cmd_gen_openems(args: argparse.Namespace) -> int:
    _resolve_sweep(args)
    project = _base_project(args)
    solver = OpenEMSSolver(
        mesh_cells_per_wavelength=args.mesh_cells,
        substrate_cells=args.substrate_cells,
        loss_model=args.loss_model,
        ground_margin_lambda=args.ground_margin_lambda,
        boundary=args.boundary,
        pml_cells=args.pml_cells,
        mesh_smoothing_ratio=args.smoothing,
        port_refine=args.port_refine,
        metal_edge_snapping=args.edge_snapping,
        nf2ff=args.nf2ff,
        unit_cell=args.unit_cell,
        numthreads=args.numthreads,
        max_timesteps=args.max_timesteps,
        end_criteria=args.end_criteria,
    )
    rundir = Path(args.out)
    prepared = solver.prepare(project, rundir)
    status = solver.available()

    print(project.summary())
    print()
    print(
        f"mesh             : {solver.mesh_cells_per_wavelength} cells/lambda "
        f"(min), {solver.substrate_cells} cells across the substrate"
    )
    print(f"dielectric loss  : {solver.loss_model} (kappa = {solver.last_kappa:.6g} S/m)")
    print(f"ground margin    : {solver.ground_margin_lambda:g} lambda0 per side")
    print(
        f"boundary         : {solver.boundary}"
        + (f" ({solver.pml_cells} cells)" if solver.boundary == "PML" else "")
        + f", smoothing {solver.mesh_smoothing_ratio:g}"
    )
    print(
        f"construction     : port_refine={solver.port_refine}, "
        f"edge_snapping={solver.metal_edge_snapping}, nf2ff={solver.nf2ff}"
        + (", unit_cell=broadside" if solver.unit_cell else "")
        + f", numthreads={solver.numthreads or 'auto'}"
    )
    print(f"run directory    : {prepared}")
    print(f"generated        : {solver.script_name}, {solver.project_name}, run_manifest.json")
    print(f"solver available : {status.available} ({status.detail})")
    for warning in project.check():
        print(f"project note     : {warning}")
    print(
        "\nIMPORTANT: the generated script has not been executed and the model is NOT "
        "verified. Run it on a machine with openEMS/CSXCAD installed:\n"
        f"  python {prepared / solver.script_name}"
    )
    return EXIT_OK


def cmd_sweep_run(args: argparse.Namespace) -> int:
    """Execute a sweep for real: one solver run per job, recorded in the store."""
    _resolve_sweep(args)
    project = _base_project(args)
    axes = [SweepAxis.parse(text) for text in args.axis]
    if not axes:
        print("error: sweep run needs at least one --axis", file=sys.stderr)
        return EXIT_ERROR

    from .sweep.runner import run_sweep

    print(project.summary())
    print()
    summary = run_sweep(
        project,
        axes,
        Path(args.out),
        solver_kwargs={
            "mesh_cells_per_wavelength": args.mesh_cells,
            "substrate_cells": args.substrate_cells,
            "loss_model": args.loss_model,
            "ground_margin_lambda": args.ground_margin_lambda,
            "boundary": args.boundary,
            "pml_cells": args.pml_cells,
            "mesh_smoothing_ratio": args.smoothing,
            "port_refine": args.port_refine,
            "metal_edge_snapping": args.edge_snapping,
            "nf2ff": args.nf2ff,
            "numthreads": args.numthreads,
            "max_timesteps": args.max_timesteps,
            "end_criteria": args.end_criteria,
        },
        store_path=args.store or None,
        stop_on_error=args.stop_on_error,
    )
    print(summary.table())
    print(f"\nresults : {Path(args.out) / 'sweep_results.json'}")
    print(f"csv     : {Path(args.out) / 'sweep_results.csv'}")
    if summary.store_path:
        print(f"store   : {summary.store_path}")
    print(
        "NOTE: every job is a full solver run; these are model outputs under test, "
        "not measurements."
    )
    return EXIT_OK if summary.failed == 0 else EXIT_ERROR


def cmd_sweep_dry_run(args: argparse.Namespace) -> int:
    _resolve_sweep(args)
    project = _base_project(args)
    axes = [SweepAxis.parse(text) for text in args.axis]
    sweep = ParameterSweep(project, axes)
    print(sweep.describe())
    manifest = sweep.dry_run_manifest(Path(args.out) / "sweep_manifest.json")
    print(f"\nmanifest written : {manifest}")
    print("DRY RUN: no solver was executed and no results exist yet.")
    return EXIT_OK


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openantenna",
        description=(
            "OpenAntenna Studio (Phase 1, headless): material/composite exploration, "
            "patch and array synthesis, solver-input generation. No GUI, and no "
            "verified solver integration yet."
        ),
    )
    parser.add_argument("--version", action="version", version=f"openantenna {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    material = sub.add_parser("material", help="inspect the material library")
    material_sub = material.add_subparsers(dest="material_command", required=True)

    p = material_sub.add_parser("list", help="list known materials")
    p.add_argument("--library", default=None, help="extra material library JSON file")
    p.set_defaults(handler=cmd_material_list)

    p = material_sub.add_parser("show", help="show one material")
    p.add_argument("--name", required=True)
    p.add_argument("--library", default=None)
    p.add_argument("--freq", type=float, default=1.0e9, help="frequency for loss terms [Hz]")
    p.set_defaults(handler=cmd_material_show)

    p = sub.add_parser("mix", help="composite mixing rules for a two-phase material")
    p.add_argument("--matrix", type=float, required=True, help="host relative permittivity")
    p.add_argument("--filler", type=float, required=True, help="filler relative permittivity")
    p.add_argument("--vf", type=float, required=True, help="filler volume fraction [0,1]")
    p.add_argument("--freq", type=float, default=1.0e9, help="frequency for validity warnings [Hz]")
    p.add_argument("--tan-matrix", type=float, default=0.0, help="matrix loss tangent")
    p.add_argument("--tan-filler", type=float, default=0.0, help="filler loss tangent")
    p.add_argument("--particle-size", type=float, default=1e-6, help="filler particle size [m]")
    p.set_defaults(handler=cmd_mix)

    design = sub.add_parser("design", help="element and array geometry synthesis")
    design_sub = design.add_subparsers(dest="design_command", required=True)

    p = design_sub.add_parser("patch", help="synthesise a rectangular patch")
    _add_design_arguments(p)
    p.add_argument("--json", action="store_true", help="also print the design as JSON")
    p.add_argument("--project-out", default=None, help="write the neutral project JSON here")
    p.set_defaults(handler=cmd_design_patch)

    p = design_sub.add_parser("array", help="lay out an NxM array of patches")
    _add_design_arguments(p)
    p.add_argument("--nx", type=int, default=4)
    p.add_argument("--ny", type=int, default=4)
    p.add_argument("--spacing-lambda", type=float, default=0.5, help="element pitch in lambda0")
    p.add_argument("--json", action="store_true", help="also print the layout as JSON")
    p.set_defaults(handler=cmd_design_array)

    solver = sub.add_parser("solver", help="external solver status")
    solver_sub = solver.add_subparsers(dest="solver_command", required=True)
    p = solver_sub.add_parser("status", help="probe the openEMS/CSXCAD runtime")
    p.set_defaults(handler=cmd_solver_status)

    p = sub.add_parser("gen-openems", help="write an openEMS model script (does not run it)")
    _add_design_arguments(p)
    p.add_argument("--nx", type=int, default=1)
    p.add_argument("--ny", type=int, default=1)
    p.add_argument("--spacing-lambda", type=float, default=0.5)
    p.add_argument(
        "--mesh-cells",
        type=int,
        default=15,
        metavar="N",
        help=(
            "mesh resolution in cells per wavelength at the highest sweep "
            "frequency; raise it in steps to check mesh convergence (default 15, "
            "a fast setting, not a converged one)"
        ),
    )
    p.add_argument(
        "--substrate-cells",
        type=int,
        default=8,
        metavar="N",
        help="mesh cells across the substrate thickness (default 8)",
    )
    p.add_argument(
        "--loss-model",
        choices=("kappa", "none"),
        default="kappa",
        help=(
            "how to represent the substrate loss tangent: 'kappa' maps it to an "
            "equivalent constant conductivity (exact at the sweep centre, drifts "
            "as 1/f), 'none' builds a lossless substrate (default kappa)"
        ),
    )
    p.add_argument(
        "--ground-margin-lambda",
        type=float,
        default=0.25,
        metavar="L",
        help=(
            "ground-plane margin per side in lambda0 (default 0.25). The ground plane "
            "is part of the radiating structure and this margin has never been "
            "swept - review item N-01"
        ),
    )
    p.add_argument(
        "--boundary",
        choices=("PML", "MUR"),
        default="PML",
        help="absorbing boundary: PML (default) or MUR as used by the openEMS tutorial",
    )
    p.add_argument("--pml-cells", type=int, default=8, metavar="N")
    p.add_argument(
        "--smoothing",
        type=float,
        default=1.4,
        metavar="R",
        help="SmoothMeshLines growth ratio (default 1.4)",
    )
    p.add_argument("--max-timesteps", type=int, default=400000, metavar="N")
    p.add_argument(
        "--end-criteria",
        type=float,
        default=1e-4,
        metavar="E",
        help="stop when the residual energy falls below this level (default 1e-4)",
    )
    p.add_argument(
        "--port-refine",
        dest="port_refine",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="refine the mesh around the lumped port (review item A4/A-7)",
    )
    p.add_argument(
        "--edge-snapping",
        dest="edge_snapping",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="snap metal edges onto the mesh with AddEdges2Grid (A-7); turning it off reproduces the -4.31 %% baseline",
    )
    p.add_argument(
        "--nf2ff",
        dest="nf2ff",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="record a near-to-far-field box and dump directivity + radiation efficiency (A-2)",
    )
    p.add_argument(
        "--unit-cell",
        dest="unit_cell",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "model an infinite array as one unit cell at broadside (PEC/PMC symmetry "
            "walls). openEMS exposes no periodic boundary, so oblique scan angles are "
            "not representable this way"
        ),
    )
    p.add_argument(
        "--numthreads",
        type=int,
        default=0,
        metavar="N",
        help=(
            "threads for the FDTD kernel: 0 lets openEMS measure and decide (default), "
            "N forces N threads. Use scripts/thread_benchmark.py to find the best value "
            "for this machine"
        ),
    )
    p.add_argument("--out", required=True, help="run directory to write into")
    p.set_defaults(handler=cmd_gen_openems)

    p = sub.add_parser("sweep", help="parameter sweep utilities")
    sweep_sub = p.add_subparsers(dest="sweep_command", required=True)
    p = sweep_sub.add_parser("dry-run", help="enumerate sweep jobs without running anything")
    _add_design_arguments(p)
    p.add_argument("--nx", type=int, default=4)
    p.add_argument("--ny", type=int, default=4)
    p.add_argument("--spacing-lambda", type=float, default=0.5)
    p.add_argument(
        "--axis",
        action="append",
        default=[],
        metavar="PATH=V1,V2,...",
        help="swept scalar, e.g. substrate.layers.0.thickness_m=0.0008,0.0016",
    )
    p.add_argument("--out", required=True, help="output directory for the manifest")
    p.set_defaults(handler=cmd_sweep_dry_run)

    p = sweep_sub.add_parser(
        "run", help="execute a parameter sweep for real (one solver run per job)"
    )
    _add_design_arguments(p)
    p.add_argument("--nx", type=int, default=1)
    p.add_argument("--ny", type=int, default=1)
    p.add_argument("--spacing-lambda", type=float, default=0.5)
    p.add_argument(
        "--axis",
        action="append",
        default=[],
        metavar="PATH=V1,V2,...",
        help=(
            "swept value; numeric or a library name, e.g. "
            "substrate.layers.0.material=PTFE,RO4003C,FR-4"
        ),
    )
    p.add_argument("--out", required=True, help="output directory for the sweep")
    p.add_argument("--store", default=None, help="sqlite file to record every run into")
    p.add_argument("--mesh-cells", type=int, default=15, metavar="N")
    p.add_argument("--substrate-cells", type=int, default=8, metavar="N")
    p.add_argument("--loss-model", choices=("kappa", "none"), default="kappa")
    p.add_argument(
        "--ground-margin-lambda",
        type=float,
        default=0.25,
        metavar="L",
        help="ground-plane margin per side in lambda0 (review item N-01)",
    )
    p.add_argument("--boundary", choices=("PML", "MUR"), default="PML")
    p.add_argument("--pml-cells", type=int, default=8, metavar="N")
    p.add_argument("--smoothing", type=float, default=1.4, metavar="R")
    p.add_argument("--max-timesteps", type=int, default=400000, metavar="N")
    p.add_argument("--end-criteria", type=float, default=1e-4, metavar="E")
    p.add_argument(
        "--port-refine",
        dest="port_refine",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    p.add_argument(
        "--edge-snapping",
        dest="edge_snapping",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    p.add_argument(
        "--nf2ff",
        dest="nf2ff",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    p.add_argument("--numthreads", type=int, default=0, metavar="N")
    p.add_argument(
        "--stop-on-error", action="store_true", help="abort the sweep at the first failure"
    )
    p.set_defaults(handler=cmd_sweep_run)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:  # pragma: no cover - argparse enforces a subcommand
        parser.print_help()
        return EXIT_ERROR
    try:
        return handler(args)
    except (ValueError, KeyError, TypeError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
