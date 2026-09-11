## Why

The Tractor Beam adaptive GPS spoofing (safe-hijack) reproduction is already implemented and validated against Betaflight SITL — the experiment scripts, raw results, and `paper/Final_Report` all exist. However, the OpenSpec layer is incomplete: two of the five experiment scripts that carry the attack have no corresponding spec, so the full safe-hijack cannot yet be traced requirement-by-requirement, and the reproduction is not a formally spec'd capability set. This change closes that gap so the paper's claims are backed by a complete, reviewable spec surface rather than only by code and a report.

## What Changes

- Add a spec for the **vertical channel** of the spoofing attack (`RESCUE_ATTAIN_ALT` → `RESCUE_STALLED`), currently exercised only by `scripts/sanity_check_experiment.py` (profiles `static`, `slow`, `partial`, `adaptive`).
- Add a spec for the **heading-confidence precondition** (forward pitch + matching accelerometer tilt + matching velocity, clearing `canUseGPSHeading`), currently exercised only by `scripts/heading_confidence_probe.py`.
- Consolidate these with the three existing specs (`sitl-environment`, `tests/gps-walkoff`, `tests/horizontal-gps-spoofing`) so every experiment script in the pipeline maps to exactly one capability.
- No production behavior changes: the scripts and pipeline are already implemented. This change is a formalization/consolidation of spec coverage (with verification tasks in the apply phase).

## Capabilities

### New Capabilities
- `tests/altitude-gps-spoofing`: The vertical channel of the spoofing attack — whether Betaflight's GPS Rescue `RESCUE_ATTAIN_ALT` sanity check accepts or rejects (`RESCUE_STALLED`) a spoofed altitude feed as a function of its rate ratio against the firmware's own climb target.
- `tests/heading-confidence`: The precondition required to reach the horizontal rescue phases — the synthetic forward-pitch / accelerometer / velocity feed that builds `gpsHeadingConfidence` past the `canUseGPSHeading` threshold.

### Modified Capabilities
<!-- none: existing specs already cover the horizontal channel and safe-hijack scenario -->

## Impact

- Specs only (no code, no API, no dependency changes). Adds two delta specs under `openspec/changes/formalize-tractor-beam-spoofing/specs/tests/`.
- On archive, they merge into `openspec/specs/tests/altitude-gps-spoofing/spec.md` and `openspec/specs/tests/heading-confidence/spec.md`, sitting alongside the existing `tests/` capabilities.
- Apply-phase work is verification/consolidation: confirm `scripts/sanity_check_experiment.py` and `scripts/heading_confidence_probe.py` match the new specs and that `just simulate` reproduces the report's altitude/heading results end-to-end.
