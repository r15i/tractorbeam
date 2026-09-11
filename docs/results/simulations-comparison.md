# Simulation Comparison: SITL vs. RF+RL

Two side-by-side simulations of the same attack, at two different layers. This
document confronts their results.

## 1. SITL estimator-decoupling (`false-home-landing`)

Deterministic, hardware-free SITL. Freeze the spoofed GPS at a false home B and
feed velocity toward the true home; the position estimator (a Kalman filter)
gets dragged off the GPS.

| scenario | outcome | max estimate↔GPS divergence | min estimate dist-to-home |
|---|---|---|---|
| baseline (7.5 m/s → home) | LANDED | — | 22.1 m |
| bias 7.5 m/s, B=150 m | FLYAWAY | 15.7 m | 134.7 m |
| bias 30 m/s | FLYAWAY | 62.8 m | 87.7 m |
| bias 60 m/s | FLYAWAY | 125.4 m | 25.1 m |
| bias 65 m/s | LANDED | 125.1 m | 25.3 m |
| bias 70 m/s | LANDED | 129.7 m | 20.8 m |
| bias 70 m/s (ramp, gentle) | LANDED | 128.1 m | 22.4 m |
| bias 70 m/s, B=100 m | LANDED | 78.5 m | 22.0 m |
| bias 70 m/s, B=200 m | FLYAWAY | 146.1 m | 54.3 m |

**Rule:** `bias ≈ 2.1 s × velocity`; landing threshold `v > (B − 20 m) / 2.1 s`.

## 2. RF power control + RL (`rf-jam-spoof-rl`)

Standalone RF layer (Friis path loss + lock-on-strongest) with a discrete-SAC
agent deciding transmit power, compared against deterministic baselines.

Average episode return (3 seeds):

| random | naive (fixed power) | deterministic (analytic min) | learned (RL) |
|---|---|---|---|
| ~6–7 | 82.2–85.5 | 82.2–85.5 | 82.7–87.4 |

The learned policy chooses the correct regime everywhere — **spoof (medium
power) for hijack, jam (high power) for disrupt** — but its powers sit 10–20 dB
*above* the deterministic minimum, because the power/detection penalty in the
reward is negligible (≈0.04 vs a +100 success reward).

## Confrontation

1. **The deterministic model already gives the exact answer in both layers.**
   The SITL bias rule (`≈2.1 s × velocity`) and the RF analytic minimum power
   are both closed-form. RL is *not* needed to find the policy — it only
   confirms it.
2. **RL rediscovers, it does not beat, the deterministic optimum.** The learned
   return (82.7–87.4) is statistically indistinguishable from the deterministic
   baseline (82.2–85.5). This is the empirical confirmation of the earlier
   assessment: with a known, deterministic plant, model-based control suffices.
3. **The two simulations answer complementary questions.** The SITL work asks
   *can we land at a false home* (position decoupling); the RF work asks *when
   is it better to jam vs spoof* (power). They meet at the boundary: the SITL
   result says the hard part is the estimator's GPS trust, not the RF; the RF
   result says the attacker's only real knob is power.
4. **Reward shaping matters.** The RL learns the *regime* but not *minimal
   power*, because the reward's power term is too weak. If power efficiency
   mattered, the `LAMBDA_POWER`/`LAMBDA_DETECT` weights would need raising — a
   concrete, actionable observation, not an RL failure.
