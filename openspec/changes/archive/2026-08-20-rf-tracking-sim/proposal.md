## Why

A believable GPS spoof must stay consistent with the drone's real motion, so an attacker must know where the drone physically is — but in the field there is no "god variable" authoring that position like our SITL harness does. The most practical passive way to track a drone is RF direction-finding on its FPV video feed (a strong, continuous signal on a band distinct from GPS L1, so it survives GPS jamming). This change simulates that tracking and feeds the noisy position estimate into the spoof consistency constraint.

## What Changes

- Add a **drone emission model**: the drone's video/telemetry transmission (5.8 GHz FPV) as a second RF source whose received power follows free-space path loss and is unaffected by the GPS L1 jammer.
- Add an **attacker tracking model**: an antenna array / rotating directional antenna with an RSSI meter that estimates bearing (peak-finding) and range (path-loss inversion), each with modeled measurement error.
- Combine bearing + range into a **tracked position estimate with uncertainty**, and constrain the spoofed trajectory against it — reporting when the spoof diverges from the tracked position beyond the fusion tolerance.
- Keep it a standalone simulation alongside the existing `rf-environment` and `tests/rf-jam-spoof-rl` work; no changes to existing capabilities.

## Capabilities

### New Capabilities
- `rf-tracking`: The attacker's passive RF target-tracking model — a drone emission source plus direction-finding and RSSI-based range estimation that produces a noisy position estimate to constrain GPS spoofing.

### Modified Capabilities
<!-- none: existing specs are unchanged; this is a new side model -->

## Impact

- New module under `scripts/` (e.g. `rf_tracking.py`) importing the existing `rf_sim` path-loss helper; no change to the transport layer or existing experiments.
- On archive, the delta merges into `openspec/specs/rf-tracking/spec.md`.
