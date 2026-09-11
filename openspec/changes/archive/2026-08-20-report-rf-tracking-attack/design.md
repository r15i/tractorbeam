## Context

`generate_report.py` already produces the paper's Objectives / System Setup / Experiments / Results (SITL spoofing + false-home landing + RF power/RL) from live CSVs. The tracking + integrated scenario (`rf_tracking.py`, `attack_scenario.py`) and the quality metrics (`hijack_quality.py`) are implemented and spec'd but absent from the report. See `proposal.md` — Why.

## Goals / Non-Goals

**Goals:**
- Add one compact Results subsection (figure + paragraph + quality table) covering the tracking + full attack scenario.
- Add a `docs/` note: how the attack would run for real, and the simplifications we made.

**Non-Goals:**
- No changes to simulation code, specs, or the experiment pipeline.
- No new simulation; no re-running the SITL suite (the new figure is built from existing `results/`).

## Decisions

### Decision 1: One new figure — the attack-scenario timeline
Add `fig7_attack_scenario.png` to `make_figures.py`, plotting `est_dist_home_m` vs time from `results/attack_scenario.csv` with the phases (cruise / returning / spoofed / LANDING) and the 20 m landing ring marked. This is the single clearest visual of "jam → track → spoof → land next to the attacker".

### Decision 2: A compact Results subsection, not a full section
Append to the existing Results and Discussion: a short paragraph describing the integrated scenario (attacker at 150 m east of home; freeze GPS there; estimator drifts across the 20 m ring; lands next to the attacker) plus a small table of the hijack-quality metrics from `hijack_quality.py` (max divergence, min FLYAWAY margin, landing bearing + error). Keep it ~1 page so the report stays within limits.

### Decision 3: Document the real-world attack + simplifications honestly
A new `docs/results/real-world-attack.md` (linked from the index) covering:

- **Real-world attack**: a software-defined radio (HackRF/BladeRF) + a pseudo-Doppler direction-finding array; jam the 2.4 GHz control link to trigger RTH; track the drone on its 5.8 GHz video feed (bearing from phase/amplitude DF, range from RSSI); then spoof GPS (coherent, code-phase-aligned via `gps-sdr-sim`) so the drone lands next to the operator.
- **Simplification routes** (the explicit list of what we did not model): free-space path loss only (no multipath/fading); no antenna gains or cable loss; spoofing treated as a *power* regime rather than a *coherent signal* problem; a fixed −130 dBm satellite reference and fixed DOP; a first-order low-pass estimator model instead of the real Kalman; a simplified drone response (RTH/redirect/failsafe) instead of the full firmware; Gaussian-only measurement noise.

### Decision 4: Quality metrics = the paper's four measures
Report the `hijack_quality.py` output mapped to the paper: divergence (EKF-innovation analog), landing bearing + error (safe-hijacking-direction analog), FLYAWAY margin (leash analog), success/time (outcome).

## Risks / Trade-offs

- **[Length]** → keep the new subsection to one figure + one table + ~2 paragraphs; the report is currently 7 pages and should stay ≤ 9.
- **[Honesty about feasibility]** → the ~70 m/s spoof velocity and the ~150 m attack range are the honest limits; state them rather than overclaiming a field-ready exploit.

## Migration Plan

Additive only: one figure function, one report paragraph + table, one docs file. Regenerate `just figures && just report`. Rollback = revert those three edits.

## Open Questions

None that change the specs or task breakdown.
