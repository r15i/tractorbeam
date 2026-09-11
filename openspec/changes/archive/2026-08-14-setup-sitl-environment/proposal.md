## Why

The project has decided to run purely on Betaflight SITL instead of physical hardware (`docs/Strategic_Pivot_to_SITL.md`), and the SITL binary is already built (`softwareversion/betaflight/obj/main/betaflight_SITL.elf`). However, `hitl_engine.py`, `fc_commander.py`, and `fc_monitor.py` still hard-code physical serial ports (`/dev/ttyUSB0`, `/dev/ttyACM1`) and there is no documented, repeatable procedure for bringing the SITL binary up and wiring the HITL tooling to it. Without this, no spoofing experiment (including the archived `tests/gps-walkoff` work) can actually be run end-to-end.

## What Changes

- Document and script the SITL bring-up procedure: build/launch the SITL binary, apply the safety CLI settings from `docs/Architecture.md` (`runaway_takeoff_prevention = OFF`, `nav_disarm_on_ground = OFF`, `msp_override_channels = ON`, `nav_extra_arming_safety = OFF`) so it can be armed on a desk with no propellers.
- Introduce a shared simulator-transport layer (stdlib `socket`, no new dependencies) that talks to SITL over:
  - TCP for MSP (SITL exposes its UARTs over TCP starting at `BASE_PORT 5760`, per `src/main/drivers/serial_tcp.c`), replacing raw `pyserial` connections.
  - UDP for FDM state injection (port 9003, `PORT_STATE`) and RC input (port 9004, `PORT_RC`), per `src/platform/SIMULATOR/sitl.c`.
- Adapt `hitl_engine.py`, `fc_commander.py`, and `fc_monitor.py` (as new SITL-targeted variants under `softwareversion/sitl_tools/`) to use this transport layer instead of physical serial, preserving existing behavior (WASD GPS teleport, arm/disarm/RTH triggers, live telemetry display). The existing `hardwareversion/` scripts are left untouched.
- Add an environment smoke test / verification step confirming SITL launches, the transport connects, the FC arms, and baseline hover telemetry stays stable (no failsafe) before any drift/spoofing logic (e.g. `tests/gps-walkoff`) is layered on top.

## Capabilities

### New Capabilities
- `sitl-environment`: Bringing up the Betaflight SITL binary and connecting HITL tooling (GPS/IMU injection, RC commander, telemetry monitor) to it over TCP MSP + UDP FDM instead of physical serial hardware.

### Modified Capabilities

(none — `tests/gps-walkoff` depends on this environment but its own requirements are unchanged)

## Impact

- Adds `softwareversion/sitl_tools/` (SITL-targeted `hitl_engine.py`, `fc_commander.py`, `fc_monitor.py` plus the shared transport module).
- No new third-party dependencies — TCP/UDP transport uses Python's standard `socket`/`struct` modules, matching the pattern already used by the archived `gps-walkoff` design.
- Does not modify Betaflight/INAV firmware source or the existing `hardwareversion/` physical-hardware scripts.
