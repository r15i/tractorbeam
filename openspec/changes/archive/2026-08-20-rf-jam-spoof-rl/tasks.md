## 1. Setup

- [x] 1.1 Implement a pure-NumPy discrete SAC (soft Q-learning) instead of `stable-baselines3` — torch requires a multi-GB CUDA install on Python 3.14, disproportionate to this 1-D control problem

## 2. RF environment

- [x] 2.1 Implement the free-space path-loss propagation model (with an optional log-normal fading term)
- [x] 2.2 Implement the receiver lock-on-strongest logic and the normal/spoofed/jammed regime classification from the capture margin and jamming threshold
- [x] 2.3 Implement the simplified drone response (normal → RTH, spoofed → follow fake, jammed → failsafe)

## 3. Gym environment

- [x] 3.1 Implement the Gym-style environment with the observation space, continuous power action, `reset`, and `step` over the RF simulation
- [x] 3.2 Implement the reward function that rewards a successful takeover and penalizes power, detection risk, and time

## 4. SAC training

- [x] 4.1 Train a discrete-SAC (soft Q-learning) agent on the environment
- [x] 4.2 Confirm the trained policy's average reward beats a random-policy baseline and a naive threshold policy (random 8.3, naive 82.2, learned 85.5)

## 5. Evaluation and documentation

- [x] 5.1 Verify the trained policy reaches both the spoofed and jammed regimes across evaluation scenarios (spoofed 83%, jammed 17%)
- [x] 5.2 Produce an evaluation report with the learned power profile, per-regime time fractions, and takeover success rate
- [x] 5.3 Document the chosen RL formulation (discrete SAC, obs/action/reward) and the learned jam-versus-spoof policy in `docs/`
- [x] 5.4 Add an optional `justfile` target to run the RF+RL simulation
- [x] 5.5 Run `openspec validate rf-jam-spoof-rl --strict` and resolve any issues
