## Context

The SITL spoofing work already answers *whether* a Betaflight GPS Rescue can be decoupled and landed at a false home, but it feeds the GPS directly and has no notion of RF. A real attacker steers the drone through a transmitter whose power determines whether the receiver tracks the satellites, tracks the attacker, or loses fix. See `proposal.md` — Why. Redirection speed is fixed by Betaflight's hardcoded `groundSpeedCmS = 750`, so the only knob an attacker optimizes is RF power — which is where RL applies.

## Goals / Non-Goals

**Goals:**
- A standalone RF simulation (propagation + receiver lock + jam/spoof regimes) with a simplified drone response.
- An SAC agent that learns the power profile for "when to jam vs. when to spoof".
- A documented answer on the best RL formulation for this problem.

**Non-Goals:**
- No wiring into the existing SITL transport or experiment scripts.
- No real-RF hardware; no firmware changes.
- No attempt to beat the hardcoded RTH speed (it is fixed).

## Decisions

### Decision 1: Standalone side simulation, decoupled from SITL
The RF sim is a self-contained module with a simplified drone state machine (normal → RTH, spoofed → follow fake, jammed → failsafe), not a modification of `sitl_transport` or the SITL experiments. **Alternative:** integrate the RF layer to gate the virtual GPS in SITL — rejected: it couples a fast RF/RL loop to a ~100 s-per-episode SITL, which is far too slow to train SAC.

### Decision 2: Friis free-space model + lock-on-strongest + regime thresholds
Received power = `P_tx − 20·log10(d) − path constants`, optionally with log-normal fading. The receiver tracks the stronger source; two thresholds split the outcome: a **capture margin** (attacker just above satellites → spoof lock) and a **jamming threshold** (attacker far above → AGC saturates, no fix). This gives the three regimes the spec requires.

### Decision 3: SAC is the right RL algorithm (this is the "best approach" answer)
- **Action is continuous power** — SAC handles continuous actions natively, and the jam/spoof decision emerges from the power-vs-threshold physics rather than a hardcoded mode.
- **Off-policy + entropy bonus** — the RF sim is cheap to run, and the entropy term encourages exploring the spoof↔jam boundary, which is the interesting region.
- **Robust to the stochastic channel** — the max-entropy objective degrades gracefully when fading/noise is added.

Alternatives rejected: **PPO** (on-policy, needs more environment steps and doesn't exploit the cheap simulator as well); **DQN** (discrete only — would force a lossy power discretization); **TD3** (deterministic policy, more brittle against a noisy RF channel and the spoof/jam threshold discontinuity). If a *discrete* jam/spoof/off action is ever preferred, switch to PPO-discrete or SAC-discrete; the continuous-power formulation is the natural first cut.

### Decision 4: Gym-style environment contract
`obs = [range, received_power, receiver_regime, current_tx_power, drone_phase]`, `action = [tx_power]` (continuous, dBm), `reward = +success − λ_power·power − λ_detect·detection_risk − λ_time`, with `done` on episode end (takeover completes / failsafe). The regime is included in the observation so the agent can learn *when* to cross each threshold.

### Decision 5: Hand-rolled discrete SAC (soft Q-learning) in NumPy
`stable-baselines3` was not used because it pulls in `torch`, which on Python 3.14 resolves to a multi-GB CUDA-toolkit install disproportionate to this 1-D control problem. Instead the change implements **soft Q-learning** (the discrete analog of SAC — same max-entropy objective and softmax policy) in pure NumPy over a 64-bin discretized power action. This is faithful to SAC's core and needs no heavy dependency; `stable-baselines3.SAC` remains the drop-in upgrade if continuous actions or a larger state space are ever needed.

## Risks / Trade-offs

- **[Friis-only is too clean]** → add optional log-normal fading to make the channel stochastic and give SAC a real robustness problem.
- **[SAC hyperparameters are finicky]** → train against a random-policy baseline and a simple threshold policy; report the return gap, not absolute reward.
- **[Simplified drone response may mislead the jam-vs-spoof answer]** → keep the response model explicit and document it as an approximation; the regime classification (the core question) is model-independent.

## Migration Plan

Additive only: new `scripts/rf_sim.py` and `scripts/rl_jam_spoof.py` (or a small `rf/` package), plus a `stable-baselines3` dependency. No rollback beyond deleting the new modules. Existing SITL work is untouched and already committed.

## Open Questions

None that change the specs or task breakdown — the capture-margin and jamming-threshold values are tunable parameters (documented constants), not decisions that affect the approach.
