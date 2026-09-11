## Context

The rescue landing decision does not read raw GPS. In `gps_rescue_multirotor.c`, `sensorUpdate()` sets `distanceToHomeCm = |positionEstimatorGetEstimate().position|`, anchored to `armLocationGps` (latched at arming). The landing gate is `distanceToHome < descentDistanceM (20 m)` in `RESCUE_FLY_HOME`, and the reject gate is `velocityToHome < 0.2 * groundSpeed (1.5 m/s)` for 20 s (`RESCUE_FLYAWAY`). The estimator (`position_estimator.c`) is a per-axis Kalman filter fused each cycle from two measurements: GPS position (`GPS_distance2d(armLocation, gpsSol.llh)`) and GPS velocity (`gpsSol.velned`), with process prediction integrating velocity. Its `trustXY` is exposed but not consumed as a gating signal. See `proposal.md` — Why for motivation.

`FdmState` already carries independent fields (`lat/lon/alt`, `velocity_enu`, `linear_acceleration_xyz`, `pitch_deg`), so the decoupling needs no transport API change — only experiment scripts that author them inconsistently.

## Goals / Non-Goals

**Goals:**
- A decoupled "physical vs. spoofed" model that lets the FC's observed position disagree with the drone's narrative true position.
- Two attack scripts (Avenue 1 baseline, Avenue 2 velocity-bias decoupling) plus a metrics recorder.
- A reproducible run and a written results + RL/AI applicability note.

**Non-Goals:**
- No firmware modification, no transport-layer API change, no change to existing specs.
- No real-RF or hardware work; no learned controller (see Decision 7).

## Decisions

### Decision 1: Physical model lives in the experiment script, transport unchanged
The "physical" drone is a tiny point-mass integrator in the experiment script (position B, velocity, attitude) used only for narrative and metrics. The spoofed feed is the existing `FdmState` fields, authored independently. **Alternative:** extend `sitl_transport` with a dual-state type — rejected: it would bloat a shared module for one experiment, and the fields are already independently settable.

### Decision 2: Avenue 1 = rate-matched convergence on the true home
Reuse the proven `adaptive-home` mechanics (altitude gate + heading feed, then 7.5 m/s convergence on A). This is the control: it must land cleanly, confirming the harness and the descent path are correct before any decoupling.

### Decision 3: Avenue 2a = velocity-over-position bias
Hold `gpsSol.llh` (FDM lat/lon) at B while feeding `velocity_enu` toward A at a qualifying speed, with `pitch_deg`/accel kept consistent with the velocity. The Kalman integrates velocity toward A while the position measurement pulls toward B; the steady-state sits between them. The probe measures the achievable divergence and whether it crosses the 20 m descent ring. The knob is the ratio of fed velocity to position-hold error.

### Decision 4 (removed): jamming dead-reckoning was dropped
Avenue 2b (cut the GPS fix, then dead-reckon the estimate toward home) turned out to be untestable in this build: the virtual GPS (`gps_virtual.c`) always reports a 12-sat fix, so there is no no-fix path to stop the estimator's GPS corrections. The velocity-bias lever (Decision 3) is the only implementable estimator-decoupling lever, and its "frozen GPS at B" state is the mechanism itself, not a distinct jamming simulation. The requirement was removed from the spec and the script.

### Decision 5: Metrics are estimator-level, not just mission-level
Record per run: **divergence** = ‖estimate position − spoofed GPS position‖ (measured as `|GPS distance-to-home| − |estimate distance-to-home|` via `DEBUG_RTH` slot 6, since `trustXY` is not exposed by any debug/MSP path in this checkout); **flyaway margin** = `velocityToHome / 1.5` (m/s); **time-to-land**; **landing position error** vs B; **end state** (disarmed / FLYAWAY / GPSLOST). These capture both "how well it responds" and "how hard we pushed the estimator".

### Decision 6: Deterministic runs, documented inputs
Fix the physical trajectory, spoof sequence, and jam timing as constants; record them in the result file header. Note that the known `maxAltitudeCm` session nondeterminism (the running-max altitude captured from arm) still shifts gate timing, so reproducibility is "same trajectory, comparable metrics" rather than bit-identical timing — matching how the existing experiments treat the bimodal cases.

### Decision 7: No RL/AI now — deterministic model-based control; RL only when the plant becomes unknown/noisy
The gates are two scalar rate-ratio thresholds and the estimator is a known linear Kalman filter whose exact source (`position_estimator.c`) we have. Driving it is a state-estimation/optimal-control problem (closed-form or MPC), not a learning problem — RL would be learning a model we already possess. An RL/AI approach becomes genuinely interesting only when: (a) the plant is **unknown or non-stationary** (e.g. a real receiver's dynamics, an un-modeled autopilot, or a different firmware build we cannot read), (b) the observation is **noisy/partial** (real RF, multipath, latency, DOP variation), or (c) the reward is **sparse and hard to shape analytically** (e.g. "land undetected" across many interacting failsafes). This will be documented in the results note with a concrete threshold for revisiting (e.g. moving to hardware-in-the-loop with real SDRs).

## Risks / Trade-offs

- **[Velocity bias may be too small to cross 20 m]** → the probe sweeps the velocity/position ratio; if bounded below the descent ring, record it as the feasibility answer rather than a false "landed".
- **[`trustXY` is not gated]** → divergence may grow unbounded until a failsafe; the metrics capture where that boundary is, which is itself a finding.
- **[Session nondeterminism (maxAltitudeCm)]** → report distributions/timing bands, not single exact times, consistent with the existing altitude work.

## Migration Plan

Additive only: new `scripts/false_home_landing.py` (or similar), new result CSVs under `results/`, and a results/RL-AI note under `docs/`. No rollback beyond deleting the script and docs.

## Open Questions

None that change the specs or task breakdown — the velocity-bias magnitude was resolved empirically (≈1.9× velocity, landing threshold ≈65 m/s from B=150 m) and is documented in `docs/false-home-landing.md`.
