## 1. SITL Bring-Up

- [x] 1.1 Verify/rebuild `betaflight_SITL.elf` and confirm it launches, printing the expected `[SITL]` UDP/TCP init lines for `PORT_STATE` (9003), `PORT_RC` (9004), and the MSP TCP server (5760+).
- [x] 1.2 Determine and document how to apply the safety CLI settings to the SITL instance's saved config and confirm they persist across restarts. Found: only `runaway_takeoff_prevention = OFF` is a real Betaflight setting (the other three from `docs/Architecture.md` are INAV-only and rejected as invalid names); also needed explicit `aux` mode bindings (ARM on AUX1, GPS Rescue on AUX2) since a fresh config has no switch behavior at all. See `docs/SITL_Setup.md`.
- [x] 1.3 Write up the bring-up procedure (launch command, working directory, config location) in `docs/Architecture.md` or a new `docs/SITL_Setup.md`.

## 2. Simulator Transport Layer

- [x] 2.1 Read the exact `fdm_t`/state-packet and RC-packet struct layouts from `src/platform/SIMULATOR/sitl.c`/`sitl.h` in the checked-out submodule.
- [x] 2.2 Implement `softwareversion/sitl_tools/sitl_transport.py` with: a UDP FDM-state sender (steady-state/hover baseline + GPS/IMU override matching the layout from 2.1), a UDP RC sender (port 9004), a UDP motor-PWM reader (port 9001, `get_motors()` - added after discovering the MSP TCP port only serves one client at a time, see design.md Decision 2), and a lazily-connected TCP MSP client (port 5761, reusing the existing `$M<`/`$M>` framing/checksum logic from `hardwareversion/fc_monitor.py`, hardened to treat a closed/superseded connection as EOF rather than spinning).
- [x] 2.3 Add a minimal manual check (e.g. a `__main__` block or small script) that connects to a running SITL instance and confirms all three sockets connect and a baseline FDM packet is accepted.

## 3. Adapt HITL Tooling

- [x] 3.1 Create `softwareversion/sitl_tools/hitl_engine.py` from `hardwareversion/hitl_engine.py`, replacing the `pyserial` GPS/IMU/MSP calls with `sitl_transport.py`, keeping the WASD teleport and closed-loop IMU-injection behavior unchanged. Motor readback uses `SitlTransport.get_motors()` (UDP), not MSP - see 2.2.
- [x] 3.2 Create `softwareversion/sitl_tools/fc_commander.py` from `hardwareversion/fc_commander.py`, sending RC channels through `sitl_transport.py` instead of a serial MSP write.
- [x] 3.3 Create `softwareversion/sitl_tools/fc_monitor.py` from `hardwareversion/fc_monitor.py`, reading MSP telemetry (status, GPS, motors, attitude, arming flags) through `sitl_transport.py`'s TCP MSP client. `parse_status()` decodes arming-disable flags from the MSP_STATUS payload directly (this Betaflight version has no separate MSP_ARMING_DISABLE_FLAGS command); flag names corrected to match `src/main/fc/runtime_config.c`'s `armingDisableFlagNames[]`.

## 4. Environment Verification

- [x] 4.1 Run the full loop against SITL: launch SITL, start `fc_monitor.py`, start `hitl_engine.py`, start `fc_commander.py`, arm, WASD-teleport the GPS, trigger RTH, and confirm motor/attitude response is visible in the monitor - matching the workflow in `docs/Architecture.md`. Verified: all three run concurrently with no connection conflicts; arming succeeded past boot-grace (`armed: True`, zero disable flags); GPS teleport (+500m) reflected correctly in `MSP_RAW_GPS`; triggering GPS Rescue (Betaflight's RTH stand-in) changed all 4 motor outputs uniformly (1000 -> 1055), i.e. the FC responded to the spoofed position as expected.
- [x] 4.2 Run a baseline hover smoke test: arm with no drift/teleport for at least 30 seconds and confirm no failsafe/arming-disable flags appear and telemetry stays stable. **PASS** - 30/30 seconds armed, zero arming-disable flags at every 1s sample, GPS position unchanged throughout.
- [x] 4.3 Record the smoke-test result (pass/fail, any flags seen) so it's clear this environment is the known-good starting point before `tests/gps-walkoff` or other drift experiments are run on top of it. Recorded above (4.2) and in `docs/SITL_Setup.md`'s verification checklist.
