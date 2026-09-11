## Context

The Tractor Beam reproduction runs entirely in Betaflight SITL, driven by five experiment scripts over the transport layer in `scripts/sitl_transport.py` (UDP FDM/RC/PWM + MSP-over-TCP). Three of those scripts already have specs — `sitl_transport.py` → `sitl-environment`, `walkoff_experiment.py` → `tests/gps-walkoff`, `horizontal_gate_experiment.py` → `tests/horizontal-gps-spoofing` — but two do not:

- `scripts/sanity_check_experiment.py` exercises the **vertical channel**: `RESCUE_ATTAIN_ALT` in `gps_rescue_multirotor.c`, which compares the fed altitude change against the firmware's own climb target each 1 Hz tick and trips `RESCUE_STALLED` after 10 consecutive "not keeping pace" ticks (ratio ≤ 0.5). Profiles: `static` (0%), `slow` (8%), `partial` (30%), `adaptive` (110%).
- `scripts/heading_confidence_probe.py` exercises the **heading precondition**: a forward-pitch attitude plus a matching accelerometer tilt and velocity vector, needed to push `gpsHeadingConfidence` past the `canUseGPSHeading` threshold that gates `RESCUE_PITCH_FORWARD`/`RESCUE_ROTATE`.

Both are already implemented, wired into `justfile`'s `simulate` target, and described in `paper/Final_Report`. This change only adds the missing spec layer (see `proposal.md` — Why).

## Goals / Non-Goals

**Goals:**
- Give every experiment script a 1:1 spec capability, completing the safe-hijack traceability chain.
- Make the two new specs describe *observable* behavior (accept/reject classification, heading usability) rather than implementation internals.
- Keep the new specs consistent with the existing `tests/` specs in format and granularity.

**Non-Goals:**
- No code, script, or pipeline changes — the implementation is treated as the reference the specs describe.
- No change to the existing `sitl-environment`, `gps-walkoff`, or `horizontal-gps-spoofing` requirements (their behavior is unchanged).
- No new physical-layer RF modeling (that was already scoped out in the SITL pivot).

## Decisions

### Decision 1: Two new `tests/` capabilities, not folded into the horizontal spec
The altitude channel and the heading precondition are independently observable and independently testable (each has its own script, inputs, and success/failure signal), and the paper frames the attack per sensor channel. Folding them into `horizontal-gps-spoofing` would blur that per-channel framing and over-couple a precondition to the one experiment that uses it. **Alternative considered:** add them as requirements to `horizontal-gps-spoofing` — rejected because `heading_confidence_probe.py` is also used by future experiments and the altitude channel has its own reject semantics (`STALLED`, not `FLYAWAY`).

### Decision 2: Specs assert classification and windows, not exact trigger times
Repeated runs in `paper/Final_Report` show trigger timing is non-deterministic (e.g. `partial` lands on 5.1 s or 9.2 s; `adaptive` on 2.0 s or 13.3 s) while the *classification* (accept/reject) is stable for clearly-off-threshold profiles. The specs therefore require "rejected within the failing window" / "advances past the gate" and characterize the near-threshold profile as a distribution, mirroring the report's own treatment. **Alternative considered:** pin exact trigger times — rejected because it would make the spec false for one run in the bimodal cases.

### Decision 3: No `.openspec.yaml` `skip_specs` and no MODIFIED deltas
This change genuinely introduces two new capabilities, so it declares them as `ADDED Requirements` under new paths. No existing requirement's behavior changes, so there are no MODIFIED deltas.

## Risks / Trade-offs

- **[The specs describe behavior that is only verifiable by running SITL]** → The apply-phase tasks explicitly verify each new spec against its script via `just simulate` before archive.
- **[Non-deterministic timing could make a strict reader expect a fixed number]** → Mitigated by wording requirements around outcome classes and "within the failing window / timeout", and by the distribution requirement for the bimodal profile.
- **[Two scripts share the single MSP client slot and `debug_mode`]** → Already handled in the scripts and docs; no new risk introduced by spec-only changes, but apply verification must reuse the existing per-script launch sequence in `justfile` rather than invent a new one.

## Migration Plan

Not applicable: spec-only change. On archive, the two deltas merge into `openspec/specs/tests/altitude-gps-spoofing/spec.md` and `openspec/specs/tests/heading-confidence/spec.md`; no runtime rollback is needed.

## Open Questions

None.
