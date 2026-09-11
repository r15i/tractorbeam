## Why

The existing spoofing work can *redirect* a Betaflight GPS Rescue but cannot *complete* the hijack: because the rescue's landing gate is `distanceToHome < 20 m` measured against the armed-at origin (locked at arming), a spoofed trajectory that converges on an attacker-chosen point B is rejected by `RESCUE_FLYAWAY` instead of landing. This change attacks the position estimator itself so the flight controller lands at a false home B while its true home A stays locked — and documents the result with a reproducible run plus a note on when an RL/AI approach would actually be warranted.

## What Changes

- Add a decoupled model: a "physical" drone state (narrative true position at B) authored separately from the spoofed GPS/IMU feed the flight controller sees, so the two can disagree on purpose.
- Implement **Avenue 1** (baseline): an EKF-consistent, rate-matched spoofed trajectory that converges on the true home A and lands cleanly, establishing the control outcome.
- Implement **Avenue 2** (the attack): decouple the position estimate from the GPS so the estimator reaches "near home" (triggering descent/landing) while the GPS and motors still point at B — via velocity-over-position bias.
- Record estimator-attack metrics (estimate-vs-GPS divergence, `trustXY`, FLYAWAY margin, time-to-land, landing position error, end state) and document results from a single deterministic, reproducible run.
- Add an RL/AI applicability note documenting when a learned approach would be justified (unknown/noisy plant, real RF) and why the deterministic, model-based approach is sufficient for now.

## Capabilities

### New Capabilities
- `tests/false-home-landing`: The estimator-decoupling landing attack — landing a Betaflight GPS Rescue at an attacker-chosen false home despite the armed-at home being locked, covering the clean-landing baseline, the velocity-bias decoupling lever, and the estimator-attack metrics.

### Modified Capabilities
<!-- none: existing specs (sitl-environment, gps-walkoff, horizontal-gps-spoofing, altitude-gps-spoofing, heading-confidence) are unchanged; this builds on them -->

## Impact

- New experiment scripts under `scripts/` (e.g. `false_home_landing.py`) that author a physical-vs-spoofed decoupled feed against the existing `sitl_transport` layer (no transport API change).
- New result CSV(s) under `results/` recording the estimator-attack metrics; a short results write-up (likely `docs/` or the change's `design.md` addendum) plus the RL/AI applicability note.
- On archive, the delta merges into `openspec/specs/tests/false-home-landing/spec.md`.
