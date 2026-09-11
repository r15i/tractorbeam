# Code Reference

Module-by-module reference for `scripts/` (plus the report generators at the
repo root). Run everything via the `justfile` targets listed in the root
`README.md`.

## SITL layer (firmware simulation)

### `sitl_transport.py` — transport to Betaflight SITL
Speaks Betaflight SITL's native protocols over UDP/TCP instead of physical
serial. No firmware changes.

- `FdmState` — mutable fake-physics state (`lat/lon/alt`, `velocity_enu`,
  `linear_acceleration_xyz`, `pitch_deg`). `pack()` serializes the `fdm_packet`
  with the lat/lon origin-mirroring and the `ENABLE_GAZEBO_BRIDGE` quaternion
  conjugation handled internally.
- `SitlTransport` — owns the sockets (FDM 9003, RC 9004, PWM-raw 9001, MSP 5761),
  with `send_fdm`, `send_rc`, `get_motors`, `send_msp`, `read_msp`.
- `results_csv_path(name)` — path helper into `results/`.
- Helpers: `LEVEL_ORIENTATION_QUAT`, `pitched_orientation_quat()`,
  `pitch_tilted_accel()`.

### `sitl_common.py` — shared SITL helpers (single source of truth)
The geo conversions and MSP parsers shared by the experiment scripts
(previously copy-pasted):

- `meters_to_latlon_delta`, `latlon_dist_m`, `latlon_to_enu`, `enu_to_latlon`.
- `RESCUE_PHASE_NAMES`, `RESCUE_FAILURE_NAMES`.
- `parse_rth_debug(data)` → `(phase, failure)` from DEBUG_RTH slots 2/3.
- `parse_rth_debug_full(data)` → `(phase, failure, distanceToHomeCm)` (with the
  int16 wrap fix).
- `parse_status_armed(data)` → `bool`.

### `sanity_check_experiment.py` — vertical channel
Tests `RESCUE_ATTAIN_ALT` (altitude rate-ratio check). Profiles `static`,
`slow`, `partial`, `adaptive` (0/8/30/110 % of the firmware's ascend rate).
`--tag` supports repeat runs for the bimodal distribution study.

### `horizontal_gate_experiment.py` — horizontal channel
Tests `RESCUE_FLYAWAY` (distance-to-home rate check). Profiles `frozen`,
`naive-jump`, `adaptive-home`, `adaptive-fake-destination`. Reaches `FLY_HOME`
by clearing the altitude and GPS-heading gates concurrently.

### `walkoff_experiment.py` — control vs. attack safe-hijack
`--mode control|attack`: the same rate-matched trajectory ending at true home
vs. an attacker-chosen point 150 m east. (Earlier, less-refined safe-hijack;
superseded by `horizontal_gate_experiment.py`.)

### `heading_confidence_probe.py` — GPS-heading precondition
Measures how long `gpsHeadingConfidence` takes to cross the `canUseGPSHeading`
threshold for a given `--pitch`/`--speed`. Needs `debug_mode=ATTITUDE`.

### `false_home_landing.py` — estimator decoupling (the novel landing attack)
Freezes the spoofed GPS at a false home B and feeds velocity toward home,
decoupling the position estimator to trigger descent/landing. Modes
`--mode baseline|bias`; `--bias-north`, `--vel`, `--ramp-s`, `--headless`.
Key finding: `bias ≈ 2.1 s × velocity`, landing threshold `v > (B−20)/2.1`.

### `interactive_rth_spoof.py` — live-map spoofing console
Matplotlib map: click/drag to set a spoof target during RTH. `--target` +
`--headless` for automated runs.

## RF layer (attacker radio)

### `rf_sim.py` — path loss + receiver regimes
- `path_loss_db(distance_m, freq_mhz)` — Friis free-space path loss.
- `received_power_dbm(tx, distance)`.
- `classify_regime(rx)` → `normal`/`spoofed`/`jammed` (thresholds vs. the
  −130 dBm satellite reference, capture margin +3 dB, jam margin +30 dB).

### `rl_jam_spoof.py` — discrete SAC (soft Q-learning) policy
- `RfAttackEnv` — Gym-style env: obs `[goal, distance]`, continuous power
  action discretized into 64 bins, reward trades takeover success vs power.
- `SoftQLearning` — max-entropy Q-learning (discrete analog of SAC).
- `train`, `rollout_return`, `evaluate`, plus baselines (random, naive
  fixed-power, `deterministic_policy` analytic-minimum).

### `rf_tracking.py` — attacker target tracking
- `video_rssi_dbm`, `estimate_range` — 5.8 GHz video-feed emission + inversion.
- `AttackerTracker` — DF + RSSI: noisy bearing (σ_θ) and range (σ_RSSI)
  estimates, with cross-range/radial uncertainty.
- `consistent()` — spoof-consistency check against a fusion tolerance.

### `hijack_quality.py` — paper-analog quality metrics
- `divergence_m`, `bearing_deg`, `flyaway_margin`.
- `quality_metrics(samples, home, false_home)` → max divergence, min flyaway
  margin, intended/landing bearing + error, landing error (maps the paper's
  EKF-innovation / direction / leash / success metrics).

### `attack_scenario.py` — full integrated jam → track → spoof → land
2-D geometry (home at origin, false home 150 m east). Cruise → jam (RTH) →
track (video feed) → freeze GPS at the attacker + velocity toward home →
estimator drifts → landing. Reports `hijack_quality.quality_metrics`.

## Report generation (repo root)

### `make_figures.py`
Builds `paper/figures/*.png` from `results/*.csv` (fig1–3 SITL, fig4
false-home, fig5 RF regimes, fig6 RF policy).

### `generate_report.py`
Fills `Project Template.docx` and emits `paper/Final_Report.tex` + PDF. The
text sections (objectives, methodology, discussion, conclusion) and the
live-from-CSV tables are defined here.
