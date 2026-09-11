## 1. Setup

- [x] 1.1 Add `matplotlib` to the project's Python environment (`.venv`), or confirm it is already installed
- [x] 1.2 Confirm `just simulate` still builds and launches SITL with the gate-clearing `sitl_safety.txt` config intact

## 2. Console scaffold and gate clearing

- [x] 2.1 Create `scripts/interactive_rth_spoof.py` importing `SitlTransport` and `FdmState` from `sitl_transport`
- [x] 2.2 Implement background FDM-send, RC-send, and MSP-telemetry-poll threads writing into a lock-guarded shared state
- [x] 2.3 Reuse the altitude-ramp + forward-pitch/velocity sequence from `horizontal_gate_experiment.py` to reach and hold `RESCUE_FLY_HOME` before enabling target selection

## 3. Live map and target selection

- [x] 3.1 Render the map in North/East meters anchored at true home, with markers for the true (fixed) position, reported position, and target
- [x] 3.2 Add a click (and drag) handler that moves the target marker and begins spoofing toward the selected position
- [x] 3.3 Drive map refresh from a non-blocking `FuncAnimation` timer reading the shared state under the lock

## 4. Adaptive spoofing toward the target

- [x] 4.1 Move the reported position toward the current target at the firmware's ground speed (7.5 m/s), using the same fractional interpolation as `adaptive-fake-destination`
- [x] 4.2 Keep the fed velocity on the fixed North heading (matching the fixed yaw) and the forward-pitch attitude consistent while spoofing - position and velocity are decoupled (position drives `RESCUE_FLYAWAY`, velocity drives heading confidence)

## 5. Telemetry and recording

- [x] 5.1 Reflect the live rescue phase and failure state on the map/console from MSP telemetry
- [x] 5.2 Record a CSV timeline (time, true position, reported position, target position, phase, failure) via `results_csv_path`

## 6. Wiring and verification

- [x] 6.1 Add an optional `justfile` target (e.g. `just interactive`) that launches the console against a running SITL instance
- [x] 6.2 Verify: launch SITL, run the console against an off-home target during RTH, and confirm the reported position diverges from the true position toward the target with no flyaway during the approach (headless `--target` run; GUI click interaction is manual)
- [x] 6.3 Run `openspec validate interactive-rth-spoofing --strict` and resolve any issues
