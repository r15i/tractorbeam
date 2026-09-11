## Why

The paper's core question — does Betaflight's GPS Rescue *follow* a spoofed sensor reading or *reject* it, depending on whether the fake data mimics expected progress — has only been answered for the vertical (altitude) channel so far (`docs/` "Spoofing the Altitude Gate" result). The horizontal channel is the one that actually matches the user's stated goal: *given a return-to-home position, make the firmware think it's at another position entirely*. That check (`RESCUE_FLYAWAY`, comparing reported distance-to-home closing rate against the FC's own expectation) has never been exercised in testing, because every prior run stalled in the earlier `RESCUE_ATTAIN_ALT` phase before the craft ever reached `RESCUE_FLY_HOME`. The altitude experiment now tells us exactly what climb rate clears that earlier gate, unblocking this test.

## What Changes

- Add a horizontal-spoofing test harness (`softwareversion/sitl_tools/`) that first clears `RESCUE_ATTAIN_ALT` using the already-confirmed adaptive climb rate, then takes over the horizontal GPS feed once the craft reaches `RESCUE_ROTATE`/`RESCUE_FLY_HOME`.
- Test the same three-way accept/reject framing used for altitude, applied to distance-to-home:
  - **Frozen** — reported position never approaches home (no progress) → expect `RESCUE_FLYAWAY` after the ~20s failing window.
  - **Naive jump** — GPS reports having already arrived at home the instant rescue starts flying → expect accepted (the check is progress-based, not plausibility-based, per the altitude finding).
  - **Adaptive-to-fake-destination** — GPS closes in on an attacker-chosen point (not true home) at the FC's own expected closing rate → this is the actual "made it think it's somewhere else" hijack case; expect accepted, with the craft ending the rescue believing it arrived at a location it never reached.
- Produce a results artifact (CSV + visualization, matching the altitude report's format) so the two channels can be compared side by side in the paper.

## Capabilities

### New Capabilities
- `tests/horizontal-gps-spoofing`: Testing whether Betaflight GPS Rescue's horizontal distance-to-home sanity check (`RESCUE_FLYAWAY`) accepts or rejects a spoofed GPS trajectory, including the case where the reported arrival point differs from the drone's true armed-at home position.

### Modified Capabilities

(none — this is additive test tooling; no existing capability's requirements change)

## Impact

- Adds new script(s) under `softwareversion/sitl_tools/` (e.g. `horizontal_gate_experiment.py`), reusing `sitl_transport.py` and the SITL config (aux mappings, `debug_mode=RTH`) already established by the `setup-sitl-environment` change.
- No changes to `hitl_engine.py`, `fc_commander.py`, `fc_monitor.py`, or the existing altitude-gate experiment script.
- Depends on the already-confirmed altitude-clearing rate from the prior experiment (documented in design.md) to reliably reach `RESCUE_FLY_HOME` — this is new, load-bearing knowledge this change relies on rather than re-derives.
