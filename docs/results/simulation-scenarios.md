# Simulation Scenarios

The project models the same attack at four successive layers. Each answers one
question, and together they show the full path from "can the radio win" to
"can the drone be made to land".

```
┌────────────────────────────────────────────────────────────────────┐
│ Scenario 1 — GPS spoofing (SITL)        can the firmware be fooled? │
│   altitude + horizontal sanity checks   (the Tractor Beam question) │
└───────────────┬────────────────────────────────────────────────────┘
                │ the landing gate is the Kalman position estimate
                ▼
┌────────────────────────────────────────────────────────────────────┐
│ Scenario 2 — False-home landing (SITL)  can it be made to LAND?    │
│   decouple the position estimator from GPS                         │
└───────────────┬────────────────────────────────────────────────────┘
                │ a believable spoof must match the drone's real motion
                ▼
┌────────────────────────────────────────────────────────────────────┐
│ Scenario 3 — RF jam/spoof (power)       can the radio win, at what  │
│   path loss + lock-on-strongest + RL    power, jam vs spoof?        │
└───────────────┬────────────────────────────────────────────────────┘
                │ winning the receiver needs knowing where the drone is
                ▼
┌────────────────────────────────────────────────────────────────────┐
│ Scenario 4 — Attacker tracking (RF)     how does the attacker know  │
│   DF + RSSI on the 5.8 GHz video feed   the drone's actual position?│
└────────────────────────────────────────────────────────────────────┘
```

## Scenario 1 — GPS spoofing (SITL, `scripts/sanity_check_experiment.py`, `horizontal_gate_experiment.py`)

**Question:** does Betaflight's GPS Rescue accept a spoofed trajectory, or
reject it via its sanity checks?

**Result:** both the altitude gate (`RESCUE_ATTAIN_ALT` → `STALLED`) and the
horizontal gate (`RESCUE_FLYAWAY`) are evadable by a rate-matched adaptive
spoof. The vulnerability generalizes from the paper's proprietary drones to
low-cost Betaflight — but the redirect is bounded, not permanent.

## Scenario 2 — False-home landing (SITL, `scripts/false_home_landing.py`)

**Question:** can the drone be made to *land* at an attacker-chosen false home
while the armed-at home is locked?

**Result:** yes, by decoupling the position estimator from the GPS (freeze GPS
at B, feed velocity toward home). The estimator is a first-order low-pass with
a ~2.1 s time constant, so landing needs `v > (B − 20)/2.1 ≈ 65 m/s` — an
implausibly high velocity, proving the estimator's GPS trust is the boundary.

## Scenario 3 — RF jam/spoof (power, `scripts/rf_sim.py` + `rl_jam_spoof.py`)

**Question:** at what transmit power does the attacker's signal capture the
receiver (spoof) vs. saturate it (jam), and can an RL agent learn that?

**Result:** the learned policy spoofs (medium power) for hijack and jams (high
power) for disruption. RL matches but does not beat the analytic-minimum
deterministic policy — with a known plant the closed-form answer is enough.

## Scenario 4 — Attacker tracking (RF, `scripts/rf_tracking.py`)

**Question:** the spoof from Scenario 2 must stay consistent with the drone's
real motion — so how does the attacker know where the drone actually is?

**Approach:** passive direction-finding + RSSI on the drone's **5.8 GHz FPV
video feed** (unaffected by the GPS L1 jammer). Bearing from peak-finding a
directional antenna, range from inverting the path loss.

**Result:** the tracking error (cross-range `d·σ_θ` + radial `d·0.115·σ_RSSI`)
sets the max range at which a spoof can stay within the drone's ~15 m fusion
tolerance:

| tracker | σ_θ | σ_RSSI | consistent-spoof range |
|---|---|---|---|
| RSSI + directional antenna | 5° | 2.0 dB | ~60 m |
| pseudo-Doppler array | 2° | 0.5 dB | ~220 m |
| SDR array (MUSIC) | 1° | 0.2 dB | ~520 m |

**Conclusion:** tracking quality — not jammer power — is what bounds a real
spoof. A cheap RSSI rig only works up close; a pseudo-Doppler array buys real
standoff.
