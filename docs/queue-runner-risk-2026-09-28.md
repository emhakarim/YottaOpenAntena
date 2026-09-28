# Queue runner risk audit - 2026-09-28

Audit done directly by the reviewer of record (the dispatched review worker twice failed on a
provider error and returned nothing), reading `yotta_tools/heavy_queue.py` and the artefacts of the
runs it produced. Purpose: find how this runner can still fail quietly or record a false success
while the queue of `k2c -> b1s1 -> b2e3 -> b2e4` is in flight.

## Findings, by severity

**1. Medium - a successful exit is never checked against the artefacts.** `heavy_queue.py` contains no
reference to `s11.csv`, `run_summary.json`, or any result file; a job's status comes from the process
exit code and wall time only. A job that returns 0 without writing a result is recorded as `completed`.
This is exactly the shape of the 22 Sep incident, where three jobs were recorded `completed` with
`converged = 0` because the port-scoping bug killed post-processing after the FDTD had already run.
*Minimum fix:* after each job, assert that the expected artefact exists (e.g. `s11.csv` with >2 samples
and `run_summary.json`); if not, record `completed-without-result` and mark the job failed.

**2. Medium - the wall-clock kill does not reach grandchildren.** The expiry path calls `proc.kill()`
(line 144) on the direct child. On Windows that terminates the harness process only; solver workers it
spawned can survive as orphans and keep burning CPU. *Minimum fix:* kill the process tree
(`taskkill /PID <pid> /T /F`) or put the job in a Job Object with kill-on-close.

**3. Low - `--no-wait` disables concurrency control.** Each job carries its own concurrency wait, but
`--no-wait` bypasses it, so the harness runs two arms at once. Measured cost: ~16 MCells/s per arm
versus 86.5 MCells/s for a single arm - correct if the aim is CPU saturation, but it means each arm
takes several times longer than a solo run and a four-case job can outlive a naive estimate.

**4. Low - job tags name the run directories.** Two queue instances running the same jobs would write
into the same `--tag` directories. Checked now: only one process chain exists
(`25708 -> 26228 -> 20668 -> 11236 -> arms`), one directory per arm, so today is safe; the hazard is
real only if a second instance is ever started.

## What is already right

- Every job has a wall-clock limit; on expiry the job is recorded `terminated` and is **never** counted
  as a result (lines 141-147).
- Jobs that die in under 60 s are recorded `failed-fast` (line 158), so "it ran and stopped" cannot be
  mistaken for a finished case.
- A corrupt summary file does not kill the queue (line 181).

## What this means for tonight's queue

The queue is healthy and progressing (k2c arms writing FDTD progress at 09:23, engine settled on 2
threads per arm). Finding 1 is the one that matters for interpretation: when the queue says
`completed`, that will mean "the process exited zero", not "a result exists". Each claimed result must
be confirmed against `<run dir>/s11.csv` before it is read - which is what `yotta_tools/two_setting_verdict.py`
does when it refuses a run without convergent data.
