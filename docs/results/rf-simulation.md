# RF Simulation and the Attacker's Data Model

This documents what the RF/RL simulation models, *why* each piece of data is
needed, what it is used for, and — the key practical question — how an attacker
keeps the spoofed GPS *consistent* with the drone's real motion.

## What we simulate, and why

The SITL spoofing experiments (`false_home_landing.py`) assume the GPS feed is
*already* under attacker control: they just author fake `lat/lon/velocity`.
That is a necessary simplification, but it skips the question that actually
decides whether an attack works in the field: **can the attacker's radio even
win the drone's receiver, and at what power?**

The RF simulation (`scripts/rf_sim.py` + `rl_jam_spoof.py`) answers that:

- **Free-space path loss** (Friis, GPS L1 = 1575.42 MHz): `PL = 20·log₁₀(d) + 36.4 dB`.
- **Lock-on-strongest**: the receiver tracks whichever signal is stronger —
  the attacker's or the satellites (real on-ground level ≈ −130 dBm).
- **Three regimes** from the received attacker power:
  - `normal` — attacker below the satellites + 3 dB capture margin (no effect),
  - `spoofed` — attacker 3–30 dB above the satellites (receiver captured),
  - `jammed` — attacker > 30 dB above (AGC saturates → no fix).

This is deliberately a first-order model: it does **not** model antenna gain,
cable loss, multipath/fading, the receiver's tracking loops, or the
**coherence/alignment** a real spoof requires (emitting a valid, code-phase-
aligned GPS replica). It captures *when power is sufficient*, not *whether a
working spoof was generated*.

## The data, and their purpose

| Data | Why we need it | Purpose |
|---|---|---|
| Transmit power + range → received power | to know whether the receiver locks onto the attacker or the satellites | jam-vs-spoof decision |
| Receiver regime (normal/spoofed/jammed) | the effect on the drone (RTH / redirect / failsafe) | attack outcome |
| **The drone's actual position + velocity** | to author a spoof that is *consistent* with real motion | the consistency constraint (below) |
| The estimator's position / divergence | to verify the decoupling attack and measure its quality | attack-quality metric |

## The key requirement: knowing the aircraft's *actual* position

The user's intuition is exactly right, and it is the central difficulty of a
*real* (non-simulated) attack: **you cannot spoof GPS believably unless you
track where the drone physically is.**

Why: a flight controller does not trust raw GPS. It fuses GPS with the IMU
(accelerometer/gyro) — Mahony/DCM for attitude, a Kalman filter for position.
If the spoofed GPS says "moving north at 10 m/s" while the accelerometer
reports no such acceleration, the fusion sees an **innovation error** and
rejects the GPS (or triggers a failsafe). This is the exact finding in
`docs/project/kalman-bypass.md` and in the paper's own EKF detector
(`ekf_check()`).

So the spoofed GPS *and* the drone's real dynamics must agree — which means
the attacker needs a model of the target's true position, velocity, and
attitude.

**How this is handled in our project vs. in the field:**

- **In our SITL** — the harness is "god": it authors every value the firmware
  ever sees (position, velocity, acceleration, attitude). So "the actual
  position" is simply a variable the script sets, and consistency is
  guaranteed *by construction*: we compute matching velocity/accel from the
  fake trajectory. No separate tracking problem exists.
- **In the paper / a real attack** — the attacker **tracks the drone**
  independently (telemetry if unencrypted, radar, optical tracking, ADS-B,
  or the drone's own downlink) to know its true position, then crafts the
  spoofed trajectory *relative to that true position*: the paper's "adaptive"
  spoof mimics the closing rate the drone's RTH logic expects, which requires
  knowing both the drone's position and the home-point geometry (its
  "leash length").
- **In our false-home landing** — we deliberately **broke** the consistency:
  GPS frozen at B while velocity points home. This worked *only because*
  Betaflight's legacy GPS-Rescue controller does **not** gate on the Kalman
  filter's trust/innovation (unlike the paper's EKF). So on Betaflight the
  attack is possible *without* perfect IMU/GPS consistency — but at the cost
  of needing an implausible ~70 m/s velocity bias, because the estimator still
  resists.

## What a real attacker would need

- **To jam** (denial of service): a noise source on 1575.42 MHz + amplifier +
  antenna. Power budget: `EIRP = P_tx + G_ant − losses`; to raise the noise at
  the drone ~30 dB above the floor needs roughly +20 dBm (100 mW) EIRP within a
  few hundred metres.
- **To spoof** (control): an SDR (HackRF/BladeRF/USRP) + `gps-sdr-sim`, emitting
  a coherent, code-phase-aligned replica a few dB above the authentic signal —
  and the target's real position/velocity to keep the spoof consistent with the
  drone's IMU.
- **Constraints:** line-of-sight, receiver sensitivity, and keeping the spoof
  locked while the drone's tracking loops fight it.
- **Legal/ethical:** jamming and spoofing GNSS is illegal in most jurisdictions
  and dangerous near aviation — this project demonstrates the *firmware*
  weakness; it is not a build guide for a field weapon.
