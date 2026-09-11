# False-Home Landing: Estimator-Decoupling Results

Extends the Tractor Beam reproduction from *redirecting* a Betaflight GPS
Rescue to *completing a landing* at an attacker-chosen false home, even though
the armed-at home is locked. Landing is gated by the **position estimator**
(`distanceToHome = |positionEstimatorGetEstimate().position| < 20 m`), not by
the raw GPS — so the attack is to decouple the estimator from the spoofed GPS.

## Kalman filter: estimator vs. detector

A common misconception is that Betaflight has no Kalman filter here. The
reverse is true — and the distinction explains everything:

- **Estimator** — `position_estimator.c` is a real per-axis Kalman filter
  (`kfEast` / `kfNorth` / `kfUp`) fusing GPS position, GPS velocity, and baro.
  This is the state the rescue reads, and the thing this attack decouples.
- **Detector** — the legacy GPS Rescue (`gps_rescue_multirotor.c`) does *not*
  use the Kalman filter's innovation or variance (`trustXY`) as a rejection
  gate; it uses two crude rate-ratio checks (`RESCUE_ATTAIN_ALT`,
  `RESCUE_FLYAWAY`).

So: Betaflight *has* a Kalman estimator, but its rescue controller does *not*
use that estimator's statistical trust as a spoof detector.

**Why landing is hard:** the landing gate `distanceToHome < 20 m` is measured
against the Kalman estimate anchored to the locked home A. To land at a false
home B you must drag that estimate ~130 m off the frozen GPS — and the Kalman
resists because it trusts GPS position (≈2.1 s time constant), which is why it
takes ≈70 m/s. The hardness is the estimator's GPS trust, not the rescue logic.

## Method

Deterministic, hardware-free SITL runs (`scripts/false_home_landing.py`) with
fixed inputs: home A locked at arm; fly out 500 m north; trigger GPS Rescue;
clear the altitude and heading gates; reach `FLY_HOME`. Then:

- **baseline** (Avenue 1): spoofed GPS converges on the true home at 7.5 m/s.
- **bias** (Avenue 2): spoofed GPS converges to B (north of home), then the
  GPS is **frozen at B** while velocity toward home is fed at `--vel`.

## Results

| Mode | Spoofed velocity | B (false home) | Max estimate↔GPS divergence | Min estimate dist-to-home (FLY_HOME) | Outcome |
|---|---|---|---|---|---|
| baseline | 7.5 m/s → home | — | — | 22.1 m | **LANDED** |
| bias | 7.5 m/s | 150 m | 15.7 m | 134.7 m | FLYAWAY |
| bias | 30 m/s | 150 m | 62.8 m | 87.7 m | FLYAWAY |
| bias | 60 m/s | 150 m | 125.4 m | 25.1 m | FLYAWAY |
| bias | 65 m/s | 150 m | 125.1 m | 25.3 m | **LANDED** |
| bias | 70 m/s | 150 m | 129.7 m | 20.8 m | **LANDED** |
| bias | 70 m/s | 150 m (repeat) | 129.6 m | 20.9 m | **LANDED** |
| bias | 70 m/s | 100 m | 78.5 m | 22.0 m | **LANDED** |
| bias | 70 m/s | 200 m | 146.1 m | 54.3 m | FLYAWAY |

The landing result is reproducible (two identical 70 m/s / B=150 m runs both
landed).

## Findings

1. **The estimator is a first-order low-pass with ~2.1 s time constant.**
   Across the whole sweep the steady-state bias is `bias ≈ 2.1 s × velocity`:
   7.5→15.7, 30→62.8, 60→125.4, 70→146.1 (ratios all ≈2.09). So a constant
   velocity feed `v` pulls the estimate `~2.1 v` meters off the frozen GPS.
2. **Landing threshold.** To trigger descent the estimate must cross 20 m, so
   the required velocity is `v > (B − 20 m) / 2.1 s`:
   B=100 → ~38 m/s, B=150 → ~62 m/s, B=200 → ~86 m/s. Every run matches this
   rule (60 m/s at B=150 fails, 65 m/s lands, 70 m/s lands at B=100 and fails
   at B=200).
3. **Landing at a false home is achievable** but only with an implausibly high
   spoofed velocity (≈65–70 m/s, ~230–250 km/h). This is the estimator's GPS
   trust (fixed DOP=10 in the virtual GPS) acting as the real boundary.

## Gentle transition

The spoofed velocity now ramps from the converge speed (7.5 m/s) up to `--vel`
over `--ramp-s` (default 10 s) rather than stepping, so the feed has no hard
velocity discontinuity. Verified: `vel=70, B=150, ramp=10s` still lands
(`LANDING`, divergence ≈128 m, `HEALTHY`).

## Differences vs. the Tractor Beam paper

| | Tractor Beam (paper) | This project |
|---|---|---|
| Targets | ArduPilot / DJI / Parrot / 3DR Solo | Betaflight (open-source) |
| Detector | ArduCopter `ekf_check()` — EKF innovation-variance test (variance > 0.8 for ~1 s) | Rate-ratio checks (measured ÷ target, 10–20 × 1 Hz ticks); no EKF innovation gate |
| Estimator | EKF fusing GPS+IMU; its variance *is* the detector | Kalman estimator; its `trustXY` is not wired into the rescue |
| Path model | Moving intermediate target point (ITP) + "leash length" | Flies straight at one recorded home point; no ITP/leash |
| Outcome | Redirects the drone (safe-hijack) | Extended to actually land at a false home via estimator decoupling |

## Why the non-landing cases fail

When the velocity is below threshold, the estimate does **not** keep drifting:
it settles at its steady-state bias point (e.g. 25.1 m at 60 m/s / B=150),
where the Kalman's velocity integration balances the GPS position correction.
At that point `velocityToHome → 0`, which is below the `0.2 × 7.5 = 1.5 m/s`
flyaway floor, so `RESCUE_FLYAWAY` trips after the 20 s window. This is the
same stall-and-reject failure the earlier `adaptive-fake-destination` profile
showed — it is a property of the *bounded bias*, not a trajectory error.

## Removed: jamming dead-reckoning (Avenue 2b)

The second lever — cut the GPS fix and dead-reckon the estimate toward home —
was **removed** because it is not testable in this build: the virtual GPS
(`gps_virtual.c`) always reports a 12-sat fix, so there is no no-fix state to
stop the estimator's GPS corrections. The frozen-GPS velocity bias above is
the only implementable estimator-decoupling lever, and its "frozen GPS" state
is the mechanism itself rather than a separate jamming simulation. Testing
true no-fix jamming would require a firmware or GPS-provider change.

## RL / AI applicability

**Why a learned approach is not warranted now.** Both gates are scalar
rate-ratio thresholds, and the estimator is a known, fixed linear Kalman
filter whose exact source (`position_estimator.c`) we possess — and we now
know it behaves as a first-order low-pass with a measured ~2.1 s time constant.
Driving it is a *state-estimation / optimal-control* problem with a closed-form
plant, so a model-based controller (or even the open-loop velocity schedule
above) is sufficient and more interpretable than RL.

**When an RL/AI approach would become interesting:**

- **Unknown or non-stationary plant** — a real GNSS receiver's tracking
  dynamics, a proprietary/closed autopilot, or a firmware build we can't read.
- **Noisy or partial observations** — real RF (multipath, latency, DOP
  variation, jitter), where state and reward become stochastic.
- **Sparse, hard-to-shape reward** — "land undetected" across many interacting
  failsafes (flyaway, stall, low-sats, GPS-lost), where a hand-written
  objective is brittle and a learned policy can trade off the failure modes.

The concrete threshold for revisiting: **hardware-in-the-loop with a real SDR
GNSS spoofer**, which introduces all three at once. Until then the
deterministic model-based approach is both sufficient and more interpretable.

## RL / SAC environment (proposed)

A Soft Actor-Critic agent would wrap the SITL transport as a Gym-style
environment:

- **obs**: `[distanceToHome, velocityToHome, phase, gps_distance, fed_velocity]`
- **action**: `[spoofed velocity]` (continuous)
- **reward**: `+1` land (estimate < 20 m → descent), `−1` flyaway / stall /
  gps-lost, plus small shaping for closing distance while staying above the
  1.5 m/s flyaway floor.

**Where SAC earns its keep — and where it does not.** In this deterministic,
known plant, "when to push the velocity" already has a closed-form answer (the
~2.1 s bias rule), so SAC would only rediscover the same ramp. It becomes
genuinely useful when the *defender* is unknown or adaptive: a real GNSS
receiver's dynamics, a firmware build that actually gates on EKF innovation
(the paper's real detector), or real-RF noise/latency. In those cases "when to
push and when not to" is no longer derivable, and a learned policy trading off
*landing* vs *not tripping an unknown detector* is the right tool.

**Recommendation:** keep the deterministic controller for SITL; build the SAC
environment as a separate change aimed at the unknown-defender / real-RF case,
ideally with an injected EKF-innovation gate so the agent has something
non-obvious to learn.
