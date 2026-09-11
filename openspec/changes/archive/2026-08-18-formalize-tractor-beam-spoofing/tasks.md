## 1. Build and environment

- [x] 1.1 Confirm `betaflight/` is the pinned checkout and `make TARGET=SITL EXTRA_FLAGS="-DENABLE_RESCUE_PLAN=0"` builds cleanly (or `just simulate` produces `betaflight/obj/main/betaflight_SITL.elf`)
- [x] 1.2 Confirm `sitl_safety.txt` (or the `justfile`-generated equivalent) enables `feature GPS`, `set gps_provider = VIRTUAL`, `set debug_mode = RTH`, `set runaway_takeoff_prevention = OFF`, and binds ARM + GPS RESCUE AUX channels

## 2. Verify altitude-gps-spoofing spec

- [x] 2.1 Confirm `scripts/sanity_check_experiment.py` accepts the four profiles in the spec (`static`, `slow`, `partial`, `adaptive`) and a `--tag` for repeat runs
- [x] 2.2 Run `static` and `slow` profiles and confirm each rejects with `RESCUE_STALLED` within the failing window (matches "Sub-rate altitude spoof is rejected")
- [x] 2.3 Run `adaptive` (110%) and confirm it advances past `RESCUE_ATTAIN_ALT` with no failure flag (matches "Rate-matched adaptive altitude spoof is accepted")
- [x] 2.4 Run `partial` (30%) multiple times via `--tag` and confirm distinct CSVs are produced and the accept/reject split is captured (matches "characterized as a distribution")
- [x] 2.5 Confirm each run writes a CSV with `t`, `armed`, `alt_fed_m`, `phase`, `failure` columns plus a terminal RESULT row

## 3. Verify heading-confidence spec

- [x] 3.1 Confirm `scripts/heading_confidence_probe.py` accepts `--pitch` and `--speed` and reads the confidence value + usability flag from debug telemetry
- [x] 3.2 Run `--pitch 15 --speed 7.5` and confirm `canUseGPSHeading` latches true within the 15 s `RESCUE_PITCH_FORWARD` timeout (matches "clears heading confidence")
- [x] 3.3 Confirm the probe reports the elapsed time-to-clear for the given pitch/speed pair (matches "timing is characterized")

## 4. Regression check on existing specs

- [x] 4.1 Run `just simulate` end-to-end and confirm the horizontal (`horizontal_gate_experiment.py`), walkoff (`walkoff_experiment.py`), and transport (`sitl_transport.py`) results still reproduce as their existing specs require
- [x] 4.2 Run `just figures && just report` and confirm the report regenerates without errors, with the new specs not affecting existing output

## 5. Validation

- [x] 5.1 Run `openspec validate formalize-tractor-beam-spoofing --strict` and resolve any delta/spec format issues
- [x] 5.2 Confirm the two new spec files exist at `openspec/changes/formalize-tractor-beam-spoofing/specs/tests/altitude-gps-spoofing/spec.md` and `specs/tests/heading-confidence/spec.md` and map 1:1 to their scripts
