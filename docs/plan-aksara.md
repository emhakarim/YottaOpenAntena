# Aksara's work plan (2026-09-22, after Yotta's latest push)

Scope: package changes (`openantenna/`) and the desktop GUI. Yotta owns Phase 1 & 2 verification
and the solver runs themselves. Re-planned after reading Yotta's §38 (claim list), §39 (TE10
benchmark passed), §40 (mandate) and the two new commits `bcaddc4` and `0de11a7`.

## What changed since the previous plan

* **Phase 2 #4 is no longer mine alone.** Yotta implemented the per-port dump (`port_<n>.csv`)
  and the S-matrix assembly in `yotta_tools/port_matrix.py`, and fixed a `NameError` in my
  `element_ports` template. My part stands: the `element_ports` option itself and the
  ground-plane fix that keeps a 4x4 on its own ground.
* Their assembly lives on the **verification** side. The **package** still has no reader, so the
  CLI and the GUI cannot show coupling at all. That gap is a package change, therefore mine, and
  it is the first item below.
* Yotta's K-1 (port_refine A/B) was **rejected** on evidence (edge artefact + transient at
  60k/120k steps), and B2 (coplanar inset differential) is **running** on the two-setting
  protocol.

## Plan, ordered, with acceptance criteria

| # | Item | Why it is mine | Acceptance |
|---|---|---|---|
| **1** | **Package S-matrix reader** `openantenna/postproc/port_matrix.py` + CLI `openantenna coupling` | package change; the user-facing half of #4 | parses runs that contain `port_<n>.csv`; **refuses to guess** when a file is missing (never a silent zero); CLI prints the coupling at the design frequency, worst and mean coupling, and the trend against element spacing; tests on synthetic run directories |
| **2** | **GUI: coupling panel** in the Results tab | the GUI is mine; same data as (1) | load a matrix directory, show the coupling table and the same summary, with the "a shift only means something if one variable changed" caveat |
| **3** | **Selected-pair mode** for the coupling run | the full 4x4 is ~44x one element run; 3-6 runs give the trend | a script that prepares only the chosen pairs, records the choice in the manifest, and prints the cost before running |
| **4** | **Phase 2 #5**: corporate feed + scikit-rf | unclaimed on both sides; package change (scikit-rf is installed) | feed-network S-parameters computed with scikit-rf and combined with the element S-matrix; tests; the generator refuses a corporate feed it cannot yet build |
| **5** | **B1 tooling**: construction-bias bisection (diff-and-swap) | Yotta has not started it; the *runs* need their machine, the tool does not | a harness that proposes a geometry change, compares against the tutorial model, and writes a protocol; the runs are scheduled, not claimed here |

## Explicitly not mine - do not start

* **K-1 / K-2**: A-1 A/B and loss validation - Yotta's runs, in flight.
* **B2 differential** (coplanar inset feed): handed over, protocol in
  [`docs/experiment-coplanar-inset.md`](experiment-coplanar-inset.md).
* **A-5** (ground-plane sweep) and any other long-run item: better on Yotta's machine.
* **A-4** (claim correction) depends on Yotta's generalisation table; do it after that lands.

## Standing rules I am working under

1. Sync order: `pull` -> **mirror repo to the staging copy** -> edit -> copy **only** the touched
   files back -> verify both sides' markers and the suite -> push. Mirroring *after* writing a new
   file deletes it, which happened once; mirror first. (Learned the hard way twice: a stale staging
   copy once clobbered Yotta's Debye work.)
2. Never `git pull -X theirs`; resolve conflicts by merging both sides.
3. No number is quoted without a converged run and its stop criteria, per
   [`docs/convergence-policy.md`](convergence-policy.md).
