# The Attack in Real Life, and Our Simplifications

This documents how the jam → track → spoof → land attack would run in the field,
and — explicitly — the simplification routes we took so the SITL/RF models stay
tractable. Being honest about the gap between the simulation and a real exploit
is the point: the model demonstrates a *firmware* weakness, not a field-ready
weapon.

## The real-world attack chain

1. **Position the operator.** Place yourself on (or near) the drone's expected
   return-to-home path, ~150 m from the armed-at home.
2. **Jam the control link** (2.4 GHz) to force a failsafe → the drone triggers
   RTH. A few hundred mW of broadband noise is enough at close range.
3. **Track the drone** passively on its **5.8 GHz FPV video feed** — a signal the
   GPS L1 jammer does not touch. Bearing comes from a pseudo-Doppler direction-
   finding array (KrakenSDR-style); range from RSSI via path-loss inversion.
4. **Spoof GPS** with an SDR (HackRF/BladeRF) running `gps-sdr-sim`: emit a
   coherent, code-phase-aligned replica a few dB above the authentic signal, and
   steer the reported position to your location while feeding velocity toward
   home.
5. **Land next to the operator.** The drone's estimator is decoupled from the GPS
   and crosses the landing ring, so it lands at your position instead of home.

## Simplification routes we took

| Real world | Our model |
|---|---|
| Multipath, fading, polarization | Free-space path loss only |
| Antenna gains + cable loss (EIRP) | Flat transmit power → received power |
| Coherent, code-aligned spoof (signal generation) | Spoofing as a *power* regime (3–30 dB above −130 dBm) |
| Variable satellite levels, DOP, receiver AGC/tracking loops | Fixed −130 dBm satellites, fixed DOP, three discrete regimes |
| Full per-axis Kalman estimator | First-order low-pass with a measured ~2.1 s time constant |
| Full flight-controller firmware + airframe physics | Simplified drone response (RTH / redirect / failsafe) |
| Non-Gaussian, non-stationary measurement noise | Gaussian σ_θ and σ_RSSI only |

## What this means for the results

The headline numbers are therefore *upper bounds on plausibility*, not field
numbers. The ~70 m/s spoof velocity needed to land at 150 m off-home, and the
~60 m tracking standoff of a cheap RSSI rig, are honest consequences of the
simplifications — they tell you *where* the real attack is hard (estimator GPS
trust, tracking accuracy, coherent signal generation), not that it is easy.
