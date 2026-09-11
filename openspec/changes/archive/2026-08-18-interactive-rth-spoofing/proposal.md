## Why

The existing Tractor Beam reproduction is fully scripted: every spoofed trajectory is hardcoded in advance and run non-interactively. That proves the safe-hijack vulnerability, but it does not let a human operator drive the hijack live — pick a position, start spoofing during return-to-home, and watch the drone's reported position deviate from where it physically is toward the chosen point. This change adds that interactive, human-in-the-loop demonstration as a first-class capability.

## What Changes

- Add a new interactive spoofing console that runs against the existing Betaflight SITL environment and transport layer (`scripts/sitl_transport.py`).
- During an active GPS Rescue (RTH), the operator picks a target position on a live map and the harness adaptively spoofs the reported GPS position toward it, so the drone's reported position visibly diverges from its fixed true (armed-at home) position.
- A live matplotlib map shows the true home position, the reported (spoofed) position, and the movable target marker, updating in real time.
- The spoofed trajectory is rate-matched to the firmware's own ground speed so it is not rejected by `RESCUE_FLYAWAY`, reusing the validated gate-clearing sequence (altitude ramp + forward-pitch/velocity heading feed) already proven by the scripted experiments.
- No changes to existing capabilities' requirements; this is a new capability layered on top of them.

## Capabilities

### New Capabilities
- `tests/interactive-rth-spoofing`: An interactive, live-map GPS spoofing console that lets an operator select a target position during Betaflight GPS Rescue and observes the reported position converging on it while the true position stays fixed.

### Modified Capabilities
<!-- none: existing specs are unchanged -->

## Impact

- New script under `scripts/` (e.g. `interactive_rth_spoof.py`) importing the existing `sitl_transport` module; no changes to the transport API.
- New runtime dependency: `matplotlib` (for the live map).
- Optional new `justfile` target to launch the interactive console against a running SITL instance.
- On archive, the delta merges into `openspec/specs/tests/interactive-rth-spoofing/spec.md`, alongside the other `tests/` spoofing capabilities.
