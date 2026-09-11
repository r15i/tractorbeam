## Context

See `proposal.md` - Why for motivation. Relevant current state:

- Betaflight SITL is already built at `softwareversion/betaflight/obj/main/betaflight_SITL.elf`.
- `src/platform/SIMULATOR/sitl.c` defines the simulator's network interface: `PORT_STATE 9003` (UDP, in - FDM state from the "physics" side), `PORT_RC 9004` (UDP, in - RC channels), `PORT_PWM 9002`/`PORT_PWM_RAW 9001` (UDP, out - motor PWM; `PORT_PWM_RAW` carries raw 1000-2000 PWM values and is what this change reads motors from - see Decision 2).
- `src/main/drivers/serial_tcp.c` defines `BASE_PORT 5760` - SITL exposes each configured UART as a TCP port starting at 5760 (confirmed by launching the binary: UART1, used for MSP, binds at `5761`), so the existing MSP wire protocol (`$M<`/`$M>` framing) used by `hardwareversion/*.py` is reachable unchanged, just over a TCP socket instead of `pyserial`.
- The archived `tests/gps-walkoff` change already validated the UDP FDM-injection approach over MSP-override for this same reason (SITL's internal physics loop can override raw MSP GPS injection; the FDM channel does not have that problem).
- `docs/Architecture.md` documents the safety CLI settings and the operator workflow (arm -> WASD teleport -> trigger RTH -> observe) that this environment must preserve. Applying that settings list against this checkout showed three of the four (`nav_disarm_on_ground`, `msp_override_channels`, `nav_extra_arming_safety`) are INAV-only and don't exist in vanilla Betaflight; only `runaway_takeoff_prevention` is real here. A fresh config also has no AUX-to-mode binding at all, so arming (and Betaflight's GPS Rescue, its stand-in for INAV's full RTH) needed explicit `aux` CLI mappings added - see `docs/SITL_Setup.md`.

## Goals / Non-Goals

**Goals:**
- One documented command sequence to bring up SITL in a state that can be armed and driven exactly like the physical rig.
- A single small transport module shared by `hitl_engine.py`, `fc_commander.py`, and `fc_monitor.py`, so future experiments (like `tests/gps-walkoff`) build on one connection implementation instead of each reinventing UDP/TCP framing.
- Zero new third-party dependencies (stdlib `socket`/`struct` only), consistent with the archived design's approach.

**Non-Goals:**
- Not implementing the actual drift/spoofing attack logic - that is `tests/gps-walkoff` and future experiments, layered on top of this environment.
- Not simulating aerodynamics/wind (drone treated as stationary/hovering, same assumption as the archived design).
- Not touching the `hardwareversion/` scripts or Betaflight firmware source.
- Not building Gazebo/RealFlight integration - this project acts as the "physics" side itself (a minimal stand-in), same role the archived `mock_physics.py` played.

## Decisions

**Decision 1: One shared transport module vs. per-script socket code**
- *Rationale*: `hitl_engine.py` (GPS/IMU injection), `fc_commander.py` (RC), and `fc_monitor.py` (telemetry) all need the same two connections (TCP MSP, UDP FDM/RC). A single `sitl_transport.py` module owning connection setup, MSP framing, and FDM/RC packet packing avoids duplicating wire-format code across three scripts and gives later experiments (e.g. drift injection) one place to extend.
- *Alternatives considered*: Keep the archived experiment's approach of a standalone one-off script per experiment. Rejected because this environment is meant to be the reusable foundation multiple future experiments sit on, not a single-purpose test harness.

**Decision 2: TCP MSP for status/GPS/attitude, UDP `PORT_PWM_RAW` for motor readback - not MSP for everything**
- *Rationale*: SITL exposes the exact MSP protocol the physical scripts use, just on a TCP socket, which is what `fc_monitor.py` uses for status/GPS/attitude. But testing revealed **SITL only serves one live MSP TCP client at a time** - a second connection is accepted at the socket level, but every read on it returns EOF immediately (confirmed by opening two connections directly and observing the second's `recv()` return `b''`). Since `hitl_engine.py`'s closed loop also needs motor state, giving it its own MSP connection would silently break `fc_monitor.py`'s. Instead, `hitl_engine.py` (and `SitlTransport.get_motors()`) reads motor state from SITL's UDP `servo_packet_raw` broadcast on `PORT_PWM_RAW` (9001) - the same raw 1000-2000 values `MSP_MOTOR` would return, pushed automatically every time SITL processes an FDM packet, with no MSP connection at all. `SitlTransport`'s MSP socket is also made lazy (opened only on first `send_msp`/`read_msp` call) so a script that never touches MSP never contends for the single slot in the first place - in practice only `fc_monitor.py` ever opens it.
- *Alternatives considered*: Keep motor readback on MSP and serialize access across scripts (e.g. a local proxy multiplexing one MSP connection to multiple clients). Rejected as unnecessary machinery given SITL already broadcasts the same data over UDP for exactly this purpose (it's how the Gazebo/RealFlight bridges consume motor output).
- *Also found*: this Betaflight checkout has no separate `MSP_ARMING_DISABLE_FLAGS` command - the arming-disable bitmask is appended to the `MSP_STATUS` response itself (see `src/main/msp/msp.c`'s shared `MSP_STATUS`/`MSP_STATUS_EX` case), after a variable-length flight-mode-flags section. `fc_monitor.py`'s `parse_status()` decodes this directly instead of issuing a second (non-existent) command; verified by capturing and hand-decoding a raw response.

**Decision 3: New `softwareversion/sitl_tools/` directory rather than modifying `hardwareversion/` in place**
- *Rationale*: `AGEnts.md` already documents `hardwareversion/` as physical-HITL and `softwareversion/` as "SITL components and software-only approaches." Keeping SITL variants separate avoids a `--target` branch inside every script and keeps the physical rig scripts (still potentially useful later) untouched.
- *Alternatives considered*: A single script with a hardware/SITL flag. Rejected for now as unnecessary abstraction over two small, rarely-changing entry points; the shared logic that's actually worth sharing (transport/framing) lives in `sitl_transport.py`, not in the CLI scripts themselves.

**Decision 4: Reuse the archived design's FDM struct-packing approach**
- *Rationale*: The archived `2026-08-12-gps-walkoff-experiment` design already worked out that FDM state must be sent via `struct.pack` matching the C `fdm_t` layout in `sitl.c`/`sitl.h`, and that MSP GPS override alone gets fought by SITL's internal physics loop. This change adopts that same mechanism as the baseline (steady-state / no drift) case, so the walkoff experiment's drift logic can later plug into the same transport without rework.

## Risks / Trade-offs

- **[Risk]** The `fdm_t` struct layout is internal to the Betaflight C source and could shift between versions. **[Mitigation]** Read the exact layout from `src/platform/SIMULATOR/sitl.c`/`sitl.h` at implementation time (not guessed), and pin to the currently-checked-out submodule commit.
- **[Risk]** TCP MSP framing assumes SITL's per-UART TCP behavior matches physical serial closely enough for the existing checksum/read logic in `fc_monitor.py`/`fc_commander.py` to work unmodified. **[Mitigation]** The environment verification smoke test (see spec) exercises exactly this path before any experiment logic is layered on.
- **[Trade-off]** Centralizing transport logic in one module adds a layer of indirection compared to each script owning its own socket. Accepted because three call sites already need the identical framing, and the archived experiment's design anticipated more experiments building on this same connection.
- **[Risk]** Betaflight's boot-grace period and arm-switch-edge requirement (`BOOTGRACE`/`ARM_SWITCH` arming-disable flags) mean arming attempted too soon after launch silently does nothing, with no error - easy to mistake for a broken transport. **[Mitigation]** Documented in `docs/SITL_Setup.md` (wait >=10s post-launch before raising the arm channel) and exercised by the environment verification tasks.
