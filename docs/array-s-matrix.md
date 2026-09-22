# Array S-matrix (Phase 2 #4)

One element port per array element, one run per driven port, and the matrix assembled from the
per-port dumps.

## Protocol

1. Generate the model with `element_ports=True`.  The script creates one lumped port per
   element and **dumps every port** to `port_<n>.csv`
   (`freq_hz,uf_inc_re,uf_inc_im,uf_ref_re,uf_ref_im`), plus the usual `s11.csv` for the driven
   port so the existing single-port pipeline keeps working.
2. Drive one port per run with the environment variable `OPENANTENNA_EXCITE_PORT` (1-based).
   **The deck never changes between runs** - that is what makes the columns comparable.
3. Assemble:

   ```
   python -m yotta_tools.port_matrix --n-ports 4 \
       --run runs/port1 --driven 1 \
       --run runs/port2 --driven 2 \
       --run runs/port3 --driven 3 \
       --run runs/port4 --driven 4
   ```

   with `S_ij = uf_ref(i) / uf_inc(j)`, the same convention as `s11.csv`.

## Rules that keep the numbers honest

* **A missing `port_<n>.csv` is an error, never a zero.**  A zero would look like perfect
  isolation and silently fake a coupling result.
* **Every contributing run carries its convergence state** (`run_summary.json`).  Per
  `docs/convergence-policy.md` a column produced by a run that did not converge cannot be
  quoted as a result; the tool prints that warning instead of hiding it.
* **`element_ports` with a printed feed line is refused** by the generator until the corporate
  feed (Phase 2 #5) can actually feed each element: per-element lines are a different model,
  not a flag.

## What this is not

The coupling here is the full-wave coupling of the array in its own ground plane.  It is not a
circuit-model approximation and it is not a measured array: it is a simulation result with a
convergence state attached, quotable only once the runs meet the acceptance rule.
