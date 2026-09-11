## Context

A believable GPS spoof must stay consistent with the drone's real motion (see `docs/rf-simulation.md`), so an attacker must know the drone's actual position. In SITL that position is a harness variable; in the field it must be *measured*. The most practical passive measurement is RF direction-finding on the drone's FPV video feed — a strong, continuous signal on 5.8 GHz, distinct from GPS L1 (1.575 GHz) and control/telemetry (2.4 GHz), so it survives GPS jamming. This change models that tracking. See `proposal.md` — Why.

## Goals / Non-Goals

**Goals:**
- Model the drone's video/telemetry emission and the attacker's bearing + range estimation, producing a position estimate with an uncertainty region.
- Feed that estimate into a spoof-consistency constraint that flags divergence.

**Non-Goals:**
- No real SDR/array hardware, no multipath-fidelity channel, no radar/optical tracking.
- No changes to the existing `rf-environment` or `rf-jam-spoof-rl` capabilities.

## Decisions

### Decision 1: Track via the FPV video feed (the user's insight, confirmed)
The drone's 5.8 GHz video transmission is a strong, wideband, continuous signal on a band the GPS L1 jammer does not touch. This makes it an ideal passive tracking source, and it is what real "drone hunter" systems use. Modelled as a second RF source with its own EIRP (≈ +20 dBm, a typical 100 mW FPV VTX) and free-space path loss.

### Decision 2: Direction-finding = rotating directional antenna + RSSI peak-finding
Bearing is estimated by steering a directional antenna (gain ≈ 10 dBi) and locating the peak RSSI. Range is estimated by inverting the Friis path loss from the RSSI magnitude. This is the simplest, cheapest method and matches the user's idea. **Alternatives considered** (the "what technologies" answer):
- **Pseudo-Doppler DF array** (KrakenSDR/KerberosSDR) — 4–5 switched antennas, phase rotation → bearing at ~1–5°, the standard drone-hunting tool.
- **Amplitude monopulse / Adcock / Watson-Watt** — amplitude comparison between array elements.
- **TDoA** — multiple synchronized receivers, trilateration (needs 3+ stations).
- **SDR array + MUSIC / correlation interferometry** — angle-of-arrival via phase differences, highest accuracy.
We model RSSI+directional first because it is the most approachable; the bearing-error parameter can be lowered later to emulate a pseudo-Doppler array.

### Decision 3: Error model
- Bearing error: Gaussian, σ_θ ≈ 5° (RSSI+directional) — a parameter, lower for pseudo-Doppler.
- RSSI error: Gaussian, σ ≈ 2 dB.
- Range error propagates from RSSI noise via the Friis derivative: `Δd/d ≈ (ln 10 / 20) · ΔRSSI ≈ 0.115 · ΔRSSI`, i.e. 2 dB → ~23 % relative range error.
- The position uncertainty is therefore a cross-range error (`d · σ_θ`) plus a radial error (`d · 0.115·σ_RSSI`), i.e. it widens with range.

### Decision 4: Consistency constraint flags divergence
The tracked position (with its uncertainty) constrains the spoof: the spoofed trajectory must stay within `tracked_position ± tolerance`, where the tolerance is the drone's sensor-fusion tolerance (the innovation bound). The sim reports a `spoof-consistency violation` when the spoof leaves that region. This is the mechanism that makes the tracking *matter*: with poor tracking, the spoof can only be consistent for a short time.

### Decision 5: Standalone module, reusing the path-loss helper
`scripts/rf_tracking.py` imports `path_loss_db` from `rf_sim` and adds the emission, DF, RSSI, and consistency logic. No transport-layer or existing-experiment changes.

## Risks / Trade-offs

- **[RSSI-only range is crude]** (multipath, antenna-gain mismatch make real RSSI→range poor) → the error model deliberately penalizes range; this is honest and is exactly why bearing (via array DF) is the primary measurement in practice.
- **[Bearing error grows with noise]** → σ_θ is a tunable parameter; document it as the main accuracy knob.
- **[Tracking error constrains the spoof]** → this is the intended outcome, not a bug: the point is to show that a real attacker's spoof is bounded by tracking quality.

## Migration Plan

Additive only: a new `scripts/rf_tracking.py` (or a small `rf_tracking` module) and a short doc note. No rollback beyond deleting the module.

## Open Questions

None that change the specs or task breakdown — the σ_θ / σ_RSSI values are documented tunable parameters.
