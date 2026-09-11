## 1. Environment and telemetry

- [x] 1.1 Confirm SITL builds with the legacy controller (`make TARGET=SITL EXTRA_FLAGS="-DENABLE_RESCUE_PLAN=0"`) and the gate-clearing `sitl_safety.txt` config is intact
- [x] 1.2 Identify how to read the position estimate and `trustXY` from telemetry (a debug mode such as `POSITION_NAV`, or an MSP path) so divergence can be measured

## 2. Decoupled model and Avenue 1 baseline

- [x] 2.1 Implement a small physical point-mass model (position B, velocity, attitude) in the experiment script, authored independently of the spoofed `FdmState`
- [x] 2.2 Implement Avenue 1: a rate-matched spoofed trajectory converging on the true home, and confirm it completes descent/landing/disarm with no `RESCUE_FLYAWAY`

## 3. Avenue 2a: velocity-over-position bias

- [x] 3.1 Implement the probe that holds the spoofed GPS position at B while feeding velocity (and matching attitude/accel) toward the true home
- [x] 3.2 Sweep the velocity magnitude and record the estimate-vs-GPS divergence, including whether the estimate crosses the 20 m descent distance from home

## 4. Avenue 2b: jamming-enabled dead-reckoning

- [x] 4.1 Implement the probe that cuts the GPS fix (no-fix feed) during `RESCUE_FLY_HOME` and feeds velocity toward the true home
- [x] 4.2 Record whether `distanceToHome` freezes or drifts under GPS loss, and the resulting trend toward the descent threshold

## 5. Metrics and recording

- [x] 5.1 Implement a metrics recorder: divergence, `trustXY`, flyaway margin, time-to-land, landing position error vs B, and end state
- [x] 5.2 Emit a result CSV per run with the metrics and a header recording the documented inputs (physical trajectory, spoof sequence, jam timing)

## 6. Reproducible run and documentation

- [x] 6.1 Run the full set once with fixed inputs and document the results of that exact run
- [x] 6.2 Write the RL/AI applicability note: when a learned approach is warranted (unknown/noisy plant, real RF, sparse reward) and why the deterministic model-based approach suffices now
- [x] 6.3 Add an optional `justfile` target to run the false-home-landing experiment set
- [x] 6.4 Run `openspec validate false-home-landing --strict` and resolve any issues
