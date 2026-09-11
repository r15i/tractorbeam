## Context

The spoofing pipeline already reaches and holds Betaflight's `RESCUE_FLY_HOME` phase using a validated sequence: an altitude ramp at the firmware's own ascend rate (clears `RESCUE_ATTAIN_ALT`) plus a forward-pitch attitude with matching accelerometer tilt and velocity (clears GPS-heading confidence), all authored through `scripts/sitl_transport.py`. The scripted `horizontal_gate_experiment.py` then moves the reported lat/lon toward a fixed target at the firmware's ground speed. This change wraps that same mechanism in a live, operator-driven console (see `proposal.md` — Why).

## Goals / Non-Goals

**Goals:**
- An interactive map where the operator picks a target during RTH and the reported position converges on it live.
- Reuse `sitl_transport.py` unchanged; add a new `scripts/interactive_rth_spoof.py` that composes the existing pieces.
- A clear visual of the deviation: fixed true position vs. moving reported position vs. target.

**Non-Goals:**
- No physical RF layer, no new firmware build, no change to the transport API or existing specs.
- No change to how the rescue logic itself behaves — the console only authors the fake feed.

## Decisions

### Decision 1: New standalone script, transport unchanged
`interactive_rth_spoof.py` imports `SitlTransport`/`FdmState` and the lat/lon↔meter helpers. **Alternative considered:** extend `horizontal_gate_experiment.py` with an interactive flag — rejected because its structure is a fixed-profile loop, not an event-driven GUI.

### Decision 2: matplotlib on the main thread; I/O on background threads
matplotlib's event loop must own the main thread, so the FDM-send, RC-send, and MSP-telemetry-polling loops run on daemon threads writing into a shared, lock-guarded state object. The map refreshes from a `FuncAnimation` timer (non-blocking) rather than blocking `plt.show()`-with-busy-loop. **Alternative considered:** `matplotlib` `blocking show` with `mpl_connect` callbacks doing the socket work inline — rejected because socket reads block the GUI.

### Decision 3: 2D North/East meter plane anchored at true home
The map is plotted in meters (East = x, North = y) relative to the armed-at home point, converted to lat/lon with the existing `meters_to_latlon_delta` helpers. This keeps the interactive geometry trivial while matching how the scripted experiments express offsets.

### Decision 4: Click-to-set target starts spoofing
The first map click (and any subsequent click, or a drag) moves the target marker and (re)points the spoof at it; spoofing converges toward the current target at the firmware's ground speed. **Alternative considered:** a separate "arm spoofing" key — rejected as an extra control with no added value for the demonstration.

### Decision 5: Rate-matched convergence, reusing the proven rate
The reported position moves toward the target at `RESCUE_GROUND_SPEED_MS` (7.5 m/s) using the same fractional interpolation as `horizontal_gate_experiment.py`'s `adaptive-fake-destination`, so the approach stays inside the `RESCUE_FLYAWAY` acceptance window.

### Decision 6: Hold the gate-clearing feed; keep velocity on the fixed heading
The proven pitch/velocity feed (pitch 15°, velocity North at ~7.5 m/s) is held unchanged once the gates clear; the spoof only moves the reported `lat`/`lon` toward the target. Betaflight derives GPS ground course/speed from the fed `velocity_enu` (`gps_virtual.c` / `sitl.c`), and the IMU heading (yaw) stays fixed North because the injected quaternion is pitch-only, so keeping velocity North preserves heading confidence. The reported position and the velocity are intentionally decoupled: position drives the `RESCUE_FLYAWAY` distance-to-home check, while velocity drives the heading-confidence check. This is exactly how `adaptive-fake-destination` already succeeded (position moved east while velocity stayed north).

## Risks / Trade-offs

- **[GUI thread-safety] shared `FdmState`/target mutated from callbacks and read from the poll thread** → a single `threading.Lock` guards every read/write; telemetry is sampled at a low rate (≈2 Hz) so lock contention is negligible.
- **[SITL serves one live MSP client]** → only the console's poll thread opens the MSP socket; motor readback stays on the UDP PWM-raw path (already handled by `sitl_transport`).
- **[Heading confidence for arbitrary bearings]** the heading probe validated a north course only → mitigation: keep the fed velocity fixed North (matching the fixed yaw), so the GPS course-over-ground stays aligned with the heading no matter which direction the spoofed position moves; position and velocity are decoupled. If an off-axis demo still loses heading, re-run `heading_confidence_probe.py` for the needed bearing before finalizing the demo.
- **[Spoof window is bounded]** once the reported position arrives at the target and stalls, `RESCUE_FLYAWAY` can trip (same as the paper's finding) → the console keeps showing live phase/failure so the operator can keep nudging the target to sustain the hijack.

## Migration Plan

Additive only: a new `scripts/interactive_rth_spoof.py`, an optional `justfile` target (`just interactive`), and a `matplotlib` entry in the project's Python environment. Rollback is deleting the script and target; no data or API migration.

## Open Questions

None that affect the specs or task breakdown.
