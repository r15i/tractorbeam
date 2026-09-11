## Why

The current work answers *whether* a Betaflight GPS Rescue can be spoofed and landed at a false home, but it models the GPS feed directly and ignores the RF layer that a real attacker controls. This change adds a side simulation of that RF layer — free-space propagation, receiver lock-on-strongest, and the jam-vs-spoof threshold — so we can answer *when it is better to jam versus spoof*. RL's value is now correctly scoped: redirection speed is fixed by Betaflight's hardcoded return-to-home ground speed (750 cm/s), so the only thing an attacker can optimize is the RF spoofing/jamming *power* profile — which is exactly what a learned policy can tune.

## What Changes

- Add a standalone **RF simulation** (`rf-environment`) that models transmitter power, free-space path loss, the receiver's lock-on-strongest behavior, and the spoof-vs-jam power regimes, mapped to a simplified drone response (normal / spoofed / jammed → RTH / redirect / failsafe). This is additive and does not touch the existing SITL experiments.
- Add an **RL training harness** (`tests/rf-jam-spoof-rl`) that wraps the RF simulation as a Gym-style environment and trains an **SAC** agent to choose the jam/spoof power profile that maximizes hijack success while minimizing power and detection risk.
- Document the chosen RL formulation and why SAC is the right algorithm for this problem.
- Keep the existing SITL spoofing work unchanged (already committed).

## Capabilities

### New Capabilities
- `rf-environment`: The RF simulation layer — propagation, receiver lock, and the jam/spoof regime model that determines whether the receiver tracks the attacker, tracks the satellites, or loses fix.
- `tests/rf-jam-spoof-rl`: The RL training and evaluation harness — a Gym-style environment over the RF simulation with an SAC agent, a reward that trades takeover success against power and detection, and a documented jam-vs-spoof policy.

### Modified Capabilities
<!-- none: existing specs are unchanged; this is a separate side simulation -->

## Impact

- New standalone modules under `scripts/` (e.g. `rf_sim.py`, `rl_jam_spoof.py`) and possibly a `requirements` entry for a small RL library (`stable-baselines3` or a hand-rolled SAC).
- No changes to `sitl_transport`, the existing experiment scripts, or existing specs.
- On archive, the deltas merge into `openspec/specs/rf-environment/spec.md` and `openspec/specs/tests/rf-jam-spoof-rl/spec.md`.
