# RF Jam/Spoof Simulation + RL

A side simulation (kept separate from the SITL spoofing work) that models the
RF layer an attacker actually controls, and trains a Soft Actor-Critic agent
to learn *when to jam versus when to spoof*.

## Why RF matters

The SITL work feeds the GPS directly, ignoring the RF physics that decide
whether an attack even reaches the receiver. This module adds that layer:
free-space path loss, the receiver's lock-on-strongest behavior, and the
spoof-vs-jam power regimes.

## The RF model

- **Path loss** (Friis, GPS L1 = 1575.42 MHz): received power =
  `Tx − 20·log10(d) − 20·log10(f) + 27.55`.
- **Lock-on-strongest**: the receiver tracks the stronger source. With the
  satellite signal at −130 dBm, the regime is set by the attacker's received
  power:
  - `normal` — attacker below the satellites + 3 dB capture margin,
  - `spoofed` — attacker 3–30 dB above the satellites (capture window),
  - `jammed` — attacker > 30 dB above (AGC saturates → no fix).

## The RL formulation (discrete SAC / soft Q-learning)

- **Observation**: `[goal, distance/600]` — goal ∈ {hijack, disrupt}, plus the
  attacker-to-drone range.
- **Action**: transmit power, discretized into 64 bins over [−80, +30] dBm.
- **Reward**:
  - hijack goal: `+100` on hijack completion (`+10`/step of spoof progress),
    `−20` on failsafe (jammed during return), `−10` on landing at true home,
    plus a small power/detection cost ∝ power.
  - disrupt goal: `+30` on jamming, `−5` for spoofing (wrong tool).
- **Algorithm**: soft Q-learning (the discrete analog of SAC) — max-entropy
  objective, softmax policy, soft Bellman backup. Implemented in pure NumPy
  (no torch), since `stable-baselines3`/torch is a multi-GB install on this
  Python 3.14 environment.

## Result

| goal | distance | learned power | regime | outcome |
|---|---|---|---|---|
| hijack | 75 m | −29.4 dBm | spoofed | hijacked |
| hijack | 150 m | −20.6 dBm | spoofed | hijacked |
| hijack | 300 m | −31.1 dBm | spoofed | hijacked |
| hijack | 600 m | −31.1 dBm | spoofed | hijacked |
| disrupt | 75 m | +7.3 dBm | jammed | jammed |
| disrupt | 150 m | +21.3 dBm | jammed | jammed |
| disrupt | 300 m | +9.0 dBm | jammed | jammed |
| disrupt | 600 m | +24.8 dBm | jammed | jammed |

Average episode return (3 seeds): **random ~6–7**, **naive fixed-power ~82**,
**deterministic (analytic min power) ~82–85**, **learned ~83–87**. The learned
policy matches the deterministic baseline (it does not beat it) and vastly
beats random — confirming that with a known, deterministic plant the RL simply
rediscovers the analytically optimal jam/spoof policy.

## When is it better to jam?

The learned policy encodes the answer directly:

- **Spoof when you want control** (hijack goal): use just enough power to sit
  in the capture window — a coherent fake signal that steers the drone.
- **Jam when you want denial of service** (disrupt goal): use enough power to
  saturate the receiver — simple, reliable, no control.

Jamming is the right tool when the objective is disruption (or when a coherent
spoof is infeasible); spoofing is the right tool when the objective is precise
control. Both emerge as different power regimes of the *same* continuous power
action, which is exactly what the agent learned.
