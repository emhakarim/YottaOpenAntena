# Distributed compute across devices (network queue) - design note

Answering the question: *can several separate machines share the work, with an easy GUI setup and the
network as the transport?* Yes - with one honest boundary drawn first, because it decides the whole design.

## 1. Two ways to split work, and which one is worth building

| Approach | Splits | Where the code must change | Verdict |
|---|---|---|---|
| **Job-level (case farm)** | whole runs: each device takes complete cases (`port_refine on/off`, `loss_fr4`, `b2_e4`, one array port, ...) | only the harness/queue + a worker daemon | **Build this first.** No physics risk, uses what already exists, linear speed-up with devices |
| **Domain decomposition (MPI)** | one single run, split by mesh region | inside the solver engine (MPI build of openEMS, halo exchange, load balancing) | Deep change, fragile on Windows, only pays when a *single* case is too big - keep as a later option |

This project's workload is a **batch of independent cases**, and one measured case costs ~40 min
(400k steps, 533k cells, 86.5 MCells/s). So job-level parallelism turns "10 h serial" into "2.5 h on four
devices" immediately; domain decomposition would not help that at all.

## 2. Architecture

```
                     +---------------------------+
                     |  Coordinator (one device)  |   holds the job list, leases jobs,
                     |  - queue + scheduler       |   collects results, keeps provenance
                     |  - result store (sqlite)   |
                     +-------------+-------------+
                                   |  HTTP/WebSocket over LAN (JSON)
        +--------------------------+--------------------------+
        |                          |                          |
+-------v--------+        +--------v-------+         +--------v-------+
| Worker A       |        | Worker B       |         | Worker C       |
| openEMS + venv |        | openEMS + venv |         | openEMS + venv |
| runs whole     |        | runs whole     |         | runs whole     |
| cases          |        | cases          |         | cases          |
+----------------+        +----------------+         +----------------+
```

* **Coordinator** = today's `yotta_tools/heavy_queue.py`, promoted from "run locally in order" to
  "hand each job to whichever worker is free". It already has the right vocabulary: fixed job list,
  per-job wall-clock limits, fail-fast classification, per-job logs, a results JSON.
* **Worker** = a small daemon per device: register, heartbeat, accept a job, run it as a subprocess with
  the *local* venv and `OPENEMS_ROOT`, stream progress, return artifacts. It is the only new binary.
* **Transport**: HTTP on the LAN. Measured artifact sizes make this easy - a deck is ~25 KB
  (`sim.py` 25 KB, `project.json` < 1 KB, `run_manifest.json` 2 KB), a result is ~10 KB per port CSV and
  a few KB of summary. **Raw field dumps (hundreds of MB) are never shipped**; the worker post-processes
  locally and returns the small CSVs. A 1 GbE LAN is overkill already.

## 3. Protocol sketch (enough to implement)

| Endpoint | Direction | Payload |
|---|---|---|
| `POST /register` | worker -> coordinator | `{name, cores, solver: {openems, csxcad, python}, free_ram_gb, can_run: true, token}` |
| `POST /heartbeat` | worker -> coordinator | `{worker_id, state: idle|busy, job_id?, progress: {step, cap, mcells_s, eta_s}}` |
| `GET /job` | worker -> coordinator | long-poll; returns `{job_id, case, deck_bundle, limits: {timeout_s, end_criteria, max_ts}}` or 204 |
| `PUT /job/<id>/progress` | worker -> coordinator | `{step, cap, energy_db, speed_mcells_s}` (same fields `progress.json` already has) |
| `POST /job/<id>/result` | worker -> coordinator | `{status: completed|failed|timeout, wall_s, s11_csv, port_csvs, summary_json, deck_hash}` |
| `GET /results` | GUI/CLI -> coordinator | aggregated table + verdicts (`two_setting_verdict` rules) |

Rules that make it safe to lose a device: every job carries a **lease** (worker must heartbeat or the job
returns to the queue), results are **idempotent** by `job_id` (re-running a case overwrites, never
duplicates), and the **deck hash** travels with the result so a stale or edited deck is detectable.

## 4. What makes the GUI setup easy (Aksara's lane, contract fixed here)

A **Devices** tab in the existing PySide6 GUI, sharing one JSON state file with the CLI so both see the
same truth:

1. **Pair**: coordinator shows a 6-digit code + `ip:port`; the other device enters it once (or scans a QR
   with the same payload). Pairing stores a per-device token - no passwords typed twice, no config files.
2. **Status row per device**: name, cores, solver version, state (idle / busy / offline), current case,
   live progress bar (the same `step/cap` numbers the local GUI already reads), last heartbeat age.
3. **Assignment**: a checkbox list of the current job presets ("port_refine A/B", "loss validation",
   "B2 e3/e4", "2x2 array"), plus a *Run* button that hands the whole list to the coordinator; jobs are
   pulled by whichever worker is free. A "this device only" toggle keeps the old single-machine flow.
4. **Start/stop worker** per device, and a "become a worker" switch so the same GUI can be the
   coordinator or a worker without editing anything.
5. **Health**: warn when a device's solver version differs from the coordinator's (results are then
   marked as cross-version), and refuse to accept a job whose deck hash does not match.

## 5. Trust and safety (must not be an afterthought)

A solver deck is **executable Python**, so a worker is trusting the coordinator with code execution.

* Pairing requires the code; every request carries the device token; the coordinator keeps an allowlist.
* The worker runs the deck in a **fixed working directory** with a path allowlist, never a shell command
  from the network, and refuses decks that are not produced by the generator (hash + manifest check).
* Results are compared (hash + one spot-check re-run) before they enter the result store.
* Field dumps stay on the worker; nothing else leaves the device without an explicit request.

## 6. Milestones, each with an acceptance test

| # | Milestone | Acceptance test | Owner |
|---|---|---|---|
| M1 | Worker daemon + coordinator leases (CLI only) | two devices finish a 4-case batch; each result byte-identical to the single-device run within 1e-6 | Yotta |
| M2 | Devices tab in the GUI (pair, status, assign, live progress) | pair a device from the GUI, watch its progress, finish a batch without a terminal | Aksara |
| M3 | Resilience | pull the network cable mid-run: job re-queued, no corrupt result; worker returns after reconnect and picks up work | Yotta |
| M4 | Optional single-run scaling (MPI domain decomposition) | only if a single case ever exceeds one device's memory/time budget | both |

Already in place and reusable: the sequential queue with per-job limits and fail-fast classification, the
live/stale status tool, the resumable array driver, `project.json` + `run_manifest.json` as the problem
IR, and the rule that runs from different solver versions are marked, never silently mixed.

## 7. Limits worth stating up front

* Speed-up is linear in **devices**, not in cores: two 20-thread machines do not beat one by 40x on a
  single case - they simply run two cases at once.
* Heterogeneous devices mean heterogeneous timing: the slowest worker sets the batch tail; the scheduler
  should prefer the fastest free worker for the longest jobs.
* Cross-version results (different openEMS/CSXCAD builds) must be labelled and never averaged into one
  conclusion without a check.
* A coordinator is a single point of failure; its state lives in the existing sqlite result store plus a
  JSON queue file, so a restart resumes rather than restarts.
