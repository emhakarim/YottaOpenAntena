# Compute roadmap - making the solver faster, separable, and quantum-ready

Written 2026-09-23, after a night in which **one Python scoping defect cost ~10 h of CPU**. The ordering
below is by *measured* payoff, not by novelty. Numbers in this note come from this project's own runs;
nothing is quoted from memory.

## 0. Baseline, measured on the current machine (i7-12700F, 12C/20T, 16 GB, GTX 1650 4 GB)

| Quantity | Value | Source |
|---|---|---|
| One converged-settings arm, 400k steps, 533 120 cells | **2464.78 s at 86.52 MCells/s** (solo) | B2 probe deck, 2026-09-23 |
| Four FDTD runs sharing the machine | **16.1 MCells/s each** (5.4x slower per run), ~64 MCells/s aggregate | 22-23 Sep queue status |
| GPU vs CPU, same cavity (OpenCL) | **7.26x**, agreement 0.031 % | cavity GPU check (earlier session) |
| CPU burned on runs that produced nothing | **~10 h** (4 arms x 40-90 min x 2 attempts) | incident reports |
| Where the time goes | >99 % inside the C++ engine; Python glue is seconds | deck timings |

**Conclusion to keep in mind:** a faster *language* is not the lever. The levers are (a) not losing runs,
(b) terminating runs earlier, (c) more parallel hardware, (d) fewer cells/steps.

## 1. P0 - never lose a run again (owner: harness/Yotta, package/Aksara)

The single largest measured loss. Required properties:

1. **Pre-flight deck validation before the FDTD is launched.** Today's guard makes a malformed deck fail
   in the first second (good), but the deeper fix is to execute the deck's port-selection and
   post-processing *setup* against stubs, so no scoping/binding defect can ever reach the engine.
   Acceptance: a deliberately broken deck is rejected in < 5 s without touching the solver.
2. **Post-processing separable from the FDTD.** The raw port data (`openems_run/port_ut_*`,
   `port_it_*`) already survives on disk. Give the post-processing its own entry point
   (`sim.py --post-only`) so a crash costs seconds instead of an hour. Acceptance: delete `s11.csv`,
   re-run post-processing only, get a byte-identical file.
3. **Checkpointing / resumability.** FDTD is restartable in principle (fields are on disk in
   `openems_run`); even a coarse "resume from last written timestep" cuts the cost of an interrupted run.
4. **Per-case wall-clock limits and fail-fast classification** (already in `yotta_tools/heavy_queue.py`,
   with tests): a job that ends in seconds is `failed-fast`, never "completed".

## 2. P0 - spend fewer timesteps (owner: verification/Yotta + package)

Every arm so far hit the 400k cap, i.e. the end criteria never fired: we pay the full cap every time.

* Calibrate an energy threshold that actually terminates (the engine reports energy in dB each block):
  measure, for one reference case, the resonance **and** the energy level at which it stops moving, then
  adopt the *lowest* level that still gives `|df|/f <= 0.2 %`.
* Acceptance: a converged arm stops before 60 % of the current cap with the same resonance within 0.2 %.
  Expected payoff: **2-4x** on every future run, no hardware change.

## 3. P1 - GPU and parallel hardware (owner: harness/Yotta)

* OpenCL path already measured at **7.26x** on the GTX 1650 for a cavity. Productise it: pick fp32 where
  the geometry allows, keep fp64 for the reference runs, and record the precision in the manifest.
* VRAM (4 GB) caps model size: add automatic decomposition (chunked/MPI-style domains) so larger decks
  still fit, and a clear "too big for this GPU" refusal instead of a silent fallback.
* Scheduling: 2-3 workers for latency, more for throughput (measured aggregate 46-64 MCells/s); never
  oversubscribe threads; keep one heavy job per CCD where possible.

## 4. P1 - fewer cells and fewer solves (owner: package/Aksara + verification/Yotta)

* Mesh strategy: graded/adaptive meshing away from the current-carrying edges, with the edge-snapping
  rule already in place; cost scales as (1/dx)^4, so this dominates everything else.
* Exploit symmetry (already used for the unit cell: PEC/PMC walls) for symmetric feeds.
* S-matrices: one deck, one run per driven port (already done) - keep it; add reciprocity checks to
  halve the runs needed for a full matrix.
* Where the physics allows, switch paradigm: analytic cavity/unit-cell predictors, MoM (NEC2) for wires,
  FEM/spectral for narrow-band structures. Prediction is cheaper than simulation when the question is
  "which design is worth simulating?".

## 5. P2 - separation of compute (owner: both)

"Komputasi terpisah" = the solver becomes a *backend*, not a local process.

1. **Problem IR**: the neutral model JSON already exists - freeze it as the contract (`schema_version`).
2. **Job protocol**: `submit(deck_bundle) -> job_id`, `status(job_id)`, `fetch(artifacts)`. The current
   queue is the local implementation; the protocol must not assume a local filesystem.
3. **Bundle**: deck + manifest + mesh + a hash of every input, so a remote worker can prove it ran the
   same problem. Acceptance: a remote worker's `s11.csv` matches the local one within 1e-6.
4. **Backends behind one interface**: local CPU, OpenCL, remote worker, later a quantum backend. The
   orchestration code must not care which one is used.
5. **Containers**: pin the solver version per job (openEMS/CSXCAD versions in the manifest) so results
   stay comparable across machines.

## 6. P3 - quantum: what is honest today (owner: research/Yotta)

Quantum hardware **cannot** do 3D time-domain electromagnetics now - the mesh sizes here (10^5-10^6
cells, 10^5 timesteps) are many orders of magnitude beyond current qubit counts, coherence times, and
error rates. What is both honest and useful:

1. **Hybrid, near-term**: expose optimisation problems in a form quantum annealers / QAOA can accept -
   the discrete parts of antenna design (element selection, feed-network topology, quantised dims) as
   QUBO/Ising models. Classical solvers use the same model today; a quantum backend can be swapped in
   when it wins.
2. **Frequency-domain linear algebra**: harmonic solvers reduce to `Ax = b`; HHL-type algorithms are the
   textbook quantum candidate. Track it, do not depend on it: state the hardware requirement (fault
   tolerance, ~10^6+ logical qubits) before any claim.
3. **Keep the interface open**: make the "problem -> Hamiltonian/QUBO" export a first-class artifact
   (like `project.json`), with the classical optimum recorded as the reference to beat.
4. **Never let it block the roadmap**: every quantum item above is behind a classical acceptance test,
   and each carries the explicit note of what hardware it would need.

## 7. Suggested sequencing

| Step | Item | Measured/expected gain | Owner |
|---|---|---|---|
| 1 | Termination calibration (energy threshold) | 2-4x on every run | Yotta |
| 2 | Post-processing separated + pre-flight deck check | turns crashes from hours into seconds | Aksara (package) + Yotta |
| 3 | GPU productised (fp32 where safe, VRAM guard) | up to 7x on suitable models | Yotta |
| 4 | Job protocol + remote worker + bundle hashing | parallelism across machines | both |
| 5 | Mesh/paradigm optimisation per case class | case dependent, often >2x | Aksara + Yotta |
| 6 | QUBO export + classical reference optima | readiness, no speed claim | Yotta |

Each item above must arrive with a test that fails before it and passes after - the lesson of this week
is that structural intent without a runtime guard reads as progress but is not.
