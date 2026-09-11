## 1. Correlated Signal Support

- [x] 1.1 In `softwareversion/sitl_tools/sitl_transport.py`, extend `FdmState` (or add a variant) to accept a target pitch angle and derive the raw `imu_orientation_quat` for it analytically, extending the existing `LEVEL_ORIENTATION_QUAT` derivation (same `ENABLE_GAZEBO_BRIDGE` conjugation, parameterized by pitch instead of hardcoded to level).
- [x] 1.2 Add a `velocity_enu` setter/helper that derives East/North components from a desired ground course (bearing) and speed, consistent with how `sitl.c` feeds `setVirtualGPS()`.
- [x] 1.3 (found while probing) Pitch quaternion alone doesn't stick - `imuUpdateAttitude()` always runs the real Mahony filter from gyro+accelerometer and overrides it. Added `pitch_tilted_accel()`, derived and numerically verified against `imu.c`'s actual `rMat.m[NWU_U]` formula, and wired it into `FdmState.pack()` alongside the quaternion. Confirmed via direct `MSP_ATTITUDE` readback: pitch now converges and holds within ~1s (previously stuck at 0 indefinitely). See design.md Decision 1 addendum.

## 2. Characterize Heading-Confidence Timing (probe, before full profiles)

- [x] 2.1 Add MSP_DEBUG handling to read `DEBUG_ATTITUDE` slot 1 (`gpsHeadingConfidence * 100`) and slot 4 (`canUseGPSHeading` inverted flag). Correction while implementing: `DEBUG_SET()` only writes to the shared `debug[]` array for the currently-active `debug_mode`, so `DEBUG_ATTITUDE` and `DEBUG_RTH` can't be read simultaneously - the probe uses its own `debug_mode=ATTITUDE` config (`/tmp/sitl_safety_attitude_debug.txt`); the main experiment (group 3) keeps `debug_mode=RTH` and relies on parameters already validated here. Also caught: `MSP_DEBUG` returns all 8 `debug[]` slots (`DEBUG16_VALUE_COUNT=8`), not 4 - fixed the unpack format before it silently misread slot 4.
- [x] 2.2 Isolated probe script (`heading_confidence_probe.py`): arm, trigger rescue, clear `ATTAIN_ALT` with the already-confirmed adaptive climb rate, then feed a candidate pitch angle + matching velocity and log `gpsHeadingConfidence` over time until it crosses 1.5 or `RESCUE_PITCH_FORWARD`'s 15s timeout elapses.
- [x] 2.3 Validated: `pitch=15deg, speed=7.5 m/s` (the FC's own configured rescue ground speed) clears `usable=True` at t~3.6s - comfortable margin under the 15s `RESCUE_PITCH_FORWARD` timeout. No need for a larger angle. (Fixed a probe bug while confirming: `gpsHeadingConfidence` resets to 0 the instant it latches, per imu.c's "re-evaluate from scratch" comment, so the probe now breaks on `usable=True` rather than trying to catch a `>=1.5` sample that can fall between poll ticks.)

## 3. Horizontal Spoofing Profiles

- [x] 3.1 Create `softwareversion/sitl_tools/horizontal_gate_experiment.py` (parallel structure to `sanity_check_experiment.py`): arm, fly out, trigger rescue, clear `ATTAIN_ALT` and heading confidence using the parameters found in step 2, then hand control of the horizontal GPS feed to the profile under test. Correction found while running: clearing altitude and heading *sequentially* let `RESCUE_PITCH_FORWARD`'s own 15s giveup counter (which starts unconditionally once `ATTAIN_ALT` clears) run out before the pitch/velocity feed even started, landing in `RESCUE_EMERG_DESCENT` every time. Fixed by feeding both gates concurrently from t=0.
- [x] 3.2 Implement `--profile frozen`: reported position stops changing once `RESCUE_FLY_HOME` is reached (or moves away from home); expect `RESCUE_FLYAWAY` within the ~20s failing-window.
- [x] 3.3 Implement `--profile naive-jump`: reported position jumps to true home the instant `RESCUE_FLY_HOME` begins; expect accepted - confirmed by reading source: lands inside `descentDistanceCm` immediately, transitioning to `RESCUE_DESCENT` before `FLYAWAY`'s failing counter could ever accumulate.
- [x] 3.4 Implement `--profile adaptive-home`: reported position closes on true home at >= the FC's configured rescue ground speed; expect accepted, as a control matching the altitude channel's "adaptive" result.
- [x] 3.5 Implement `--profile adaptive-fake-destination`: reported position closes, at the same qualifying rate, on an attacker-chosen point offset from true home; expect accepted - this is the case the user asked for ("make it think it is actually another position").
- [x] 3.6 Each profile logs a CSV timeline (time, reported position, distance-to-true-home, distance-to-fake-target where applicable, rescue phase/failure, armed state), matching the altitude experiment's log shape.

## 4. Results and Comparison

- [x] 4.1 Run all four horizontal profiles against a freshly-launched SITL instance each (matching the altitude experiment's isolation discipline), and record outcome + trigger time for each. Results:
  - `frozen`: REJECTED (`FLYAWAY`) at t=27.1s (~20.3s after entering `FLY_HOME`)
  - `naive-jump`: ACCEPTED, advanced to `DESCENT` at t=15.6s, `FLYAWAY` never fired
  - `adaptive-home`: ACCEPTED, smooth 63s convergence, `DESCENT` at t=69.8s
  - `adaptive-fake-destination`: reached the fake target undetected (0 flags for the full ~63s approach), but `FLYAWAY` fired ~15s *after* arrival, once stopped there - distance-to-*true*-home never dropped below `descentDistanceCm`, so the "no further progress" check eventually caught it. Genuinely more informative than a clean accept: the check has a real (if delayed) self-correction once the craft stops making progress toward the actual armed-at home.
- [x] 4.2 Extend or companion the existing "Spoofing the Altitude Gate" artifact with the horizontal-channel results, so both channels are visible side by side for the paper.
- [x] 4.3 Write up the comparison in prose: does the horizontal channel's accept/reject boundary behave the same way as altitude's (progress-based, not plausibility-based; a "cross the gap before the failing-window closes" threshold), and does `adaptive-fake-destination` succeed in making the rescue logic act as if it arrived somewhere it never physically reached.
