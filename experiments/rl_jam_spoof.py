"""Discrete SAC (soft Q-learning) agent over the RF jam/spoof environment.

Pure NumPy - no torch / stable-baselines3 (torch needs a multi-GB CUDA install
on Python 3.14, disproportionate to this 1-D control problem). Soft Q-learning
is the discrete analog of SAC: same max-entropy objective and softmax policy.

The agent learns, for a given goal (hijack vs. disrupt) and attacker-to-drone
distance, the transmit power that places the receiver in the desired regime:
  - hijack  goal -> spoof (medium power, capture window)
  - disrupt goal -> jam   (high power, no fix)
"""

import argparse
import csv
import os

import numpy as np

from tractorbeam.rf_sim import (
    received_power_dbm,
    classify_regime,
    path_loss_db,
    SAT_POWER_DBM,
    CAPTURE_MARGIN_DB,
    JAM_MARGIN_DB,
)

P_OFF_DBM = -80.0
P_MAX_DBM = 30.0
N_POWER = 64
DISTANCES = [75.0, 150.0, 300.0, 600.0]
HIJACK_STEPS = 5

LAMBDA_POWER = 0.02
LAMBDA_DETECT = 0.02

GOALS = [("hijack", 0), ("disrupt", 1)]
RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results"
)


def power_bin_to_dbm(i):
    return P_OFF_DBM + (P_MAX_DBM - P_OFF_DBM) * (i / (N_POWER - 1))


def state_index(goal_i, dist_i):
    return goal_i * len(DISTANCES) + dist_i


# Small power margin above the exact regime boundary, so the deterministic
# baseline lands safely inside the regime despite action-bin discretization.
BASELINE_MARGIN_DB = 2.0


def deterministic_policy(s):
    """Analytically optimal deterministic policy: the minimum power that
    achieves the goal's regime at the given distance (from inverting the
    free-space path loss). hijack -> minimum spoofing power, disrupt -> minimum
    jamming power."""
    goal_i = s // len(DISTANCES)
    dist_i = s % len(DISTANCES)
    pl = path_loss_db(DISTANCES[dist_i])
    if (
        goal_i == 0
    ):  # hijack: spoofed when rx >= SAT+CAPTURE -> tx >= pl + SAT + CAPTURE
        target_dbm = pl + (SAT_POWER_DBM + CAPTURE_MARGIN_DB) + BASELINE_MARGIN_DB
    else:  # disrupt: jammed when rx >= SAT+JAM -> tx >= pl + SAT + JAM
        target_dbm = pl + (SAT_POWER_DBM + JAM_MARGIN_DB) + BASELINE_MARGIN_DB
    bin_idx = (target_dbm - P_OFF_DBM) / (P_MAX_DBM - P_OFF_DBM) * (N_POWER - 1)
    return int(np.clip(round(bin_idx), 0, N_POWER - 1))


class RfAttackEnv:
    """One drone + attacker, one goal, one distance. Power action per step."""

    def __init__(self):
        self.goal_i = 0
        self.distance = 150.0
        self.hijack_progress = 0
        self.rth_progress = 0
        self.done_reason = None

    def reset(self, goal_i=0, distance=150.0):
        self.goal_i = goal_i
        self.distance = distance
        self.hijack_progress = 0
        self.rth_progress = 0
        self.done_reason = None
        return np.array([float(goal_i), distance / 600.0], dtype=np.float32)

    def step(self, power_dbm):
        rx = received_power_dbm(power_dbm, self.distance)
        regime = classify_regime(rx)
        norm_power = (power_dbm - P_OFF_DBM) / (P_MAX_DBM - P_OFF_DBM)
        reward = -(LAMBDA_POWER + LAMBDA_DETECT) * norm_power
        done = False

        if self.goal_i == 0:  # hijack: want spoof
            if regime == "spoofed":
                self.hijack_progress += 1
                if self.hijack_progress >= HIJACK_STEPS:
                    reward += 100.0
                    done = True
                    self.done_reason = "hijacked"
                else:
                    reward += 10.0
            elif regime == "jammed":
                reward += -20.0
                done = True
                self.done_reason = "failsafe"
            else:  # normal
                self.rth_progress += 1
                if self.rth_progress >= HIJACK_STEPS:
                    reward += -10.0
                    done = True
                    self.done_reason = "landed_home"
                else:
                    reward += -1.0
        else:  # disrupt: want jam
            if regime == "jammed":
                reward += 30.0
                done = True
                self.done_reason = "jammed"
            elif regime == "spoofed":
                reward += -5.0
            else:
                reward += -1.0

        return (
            self._obs(),
            reward,
            done,
            {"regime": regime, "done_reason": self.done_reason},
        )

    def _obs(self):
        return np.array([float(self.goal_i), self.distance / 600.0], dtype=np.float32)


class SoftQLearning:
    """Max-entropy Q-learning (discrete SAC)."""

    def __init__(self, n_states, n_actions, alpha=0.5, gamma=0.99, lr=0.5):
        self.Q = np.zeros((n_states, n_actions))
        self.alpha = alpha
        self.gamma = gamma
        self.lr = lr

    def soft_value(self, s):
        q = self.Q[s]
        m = q.max()
        return self.alpha * np.log(np.exp((q - m) / self.alpha).sum() + 1e-12) + m

    def probs(self, s):
        q = self.Q[s] - self.Q[s].max()
        e = np.exp(q / self.alpha)
        return e / (e.sum() + 1e-12)

    def act(self, s, greedy=False):
        if greedy:
            return int(np.argmax(self.Q[s]))
        return int(np.random.default_rng().choice(self.Q.shape[1], p=self.probs(s)))

    def update(self, s, a, r, s2, done):
        v2 = 0.0 if done else self.soft_value(s2)
        self.Q[s, a] += self.lr * (r + self.gamma * v2 - self.Q[s, a])


def train(env, agent, episodes, seed):
    rng = np.random.default_rng(seed)
    for _ in range(episodes):
        goal_i = int(rng.integers(0, 2))
        dist_i = int(rng.integers(0, len(DISTANCES)))
        s = state_index(goal_i, dist_i)
        env.reset(goal_i, DISTANCES[dist_i])
        for _ in range(40):
            a = agent.act(s)
            _, r, done, _ = env.step(power_bin_to_dbm(a))
            s2 = state_index(goal_i, dist_i)
            agent.update(s, a, r, s2, done)
            s = s2
            if done:
                break
    return agent


def rollout_return(env, policy_fn, seed, n_eps=400):
    """Average episode return for a policy function (power per state)."""
    rng = np.random.default_rng(seed)
    total = 0.0
    for _ in range(n_eps):
        goal_i = int(rng.integers(0, 2))
        dist_i = int(rng.integers(0, len(DISTANCES)))
        s = state_index(goal_i, dist_i)
        env.reset(goal_i, DISTANCES[dist_i])
        ep = 0.0
        for _ in range(40):
            a = policy_fn(s)
            _, r, done, _ = env.step(power_bin_to_dbm(a))
            ep += r
            if done:
                break
        total += ep
    return total / n_eps


def evaluate(env, agent):
    rows = []
    regime_counts = {"normal": 0, "spoofed": 0, "jammed": 0}
    for goal_name, goal_i in GOALS:
        for dist_i, d in enumerate(DISTANCES):
            s = state_index(goal_i, dist_i)
            a = agent.act(s, greedy=True)
            p = power_bin_to_dbm(a)
            det_p = power_bin_to_dbm(deterministic_policy(s))
            rx = received_power_dbm(p, d)
            regime = classify_regime(rx)
            env.reset(goal_i, d)
            done = False
            steps = 0
            while not done and steps < 40:
                aa = agent.act(s, greedy=True)
                _, _, done, info = env.step(power_bin_to_dbm(aa))
                regime_counts[info["regime"]] += 1
                steps += 1
            rows.append(
                {
                    "goal": goal_name,
                    "distance_m": d,
                    "power_dbm": round(p, 1),
                    "regime": regime,
                    "deterministic_power_dbm": round(det_p, 1),
                    "outcome": env.done_reason or "timeout",
                    "steps": steps,
                }
            )
    return rows, regime_counts


def main():
    ap = argparse.ArgumentParser(description="Train a discrete-SAC jam/spoof policy")
    ap.add_argument("--episodes", type=int, default=20000, help="training episodes")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    env = RfAttackEnv()
    n_states = 2 * len(DISTANCES)
    agent = SoftQLearning(n_states, N_POWER)

    train(env, agent, args.episodes, args.seed)

    # Baselines for comparison
    def random_policy(s):
        return int(np.random.default_rng().integers(0, N_POWER))

    def naive_policy(s):
        goal_i = s // len(DISTANCES)
        if goal_i == 0:  # hijack -> fixed medium power (spoof window)
            return int(
                np.argmin(
                    np.abs([power_bin_to_dbm(i) - (-35.0) for i in range(N_POWER)])
                )
            )
        return N_POWER - 1  # disrupt -> max power (jam)

    def learned_greedy(s):
        return agent.act(s, greedy=True)

    r_random = rollout_return(env, random_policy, args.seed)
    r_naive = rollout_return(env, naive_policy, args.seed)
    r_det = rollout_return(env, deterministic_policy, args.seed)
    r_learned = rollout_return(env, learned_greedy, args.seed + 1)
    print(
        f"avg episode return: random={r_random:.2f}  naive={r_naive:.2f}  "
        f"deterministic={r_det:.2f}  learned={r_learned:.2f}"
    )

    rows, regime_counts = evaluate(env, agent)
    total_regime = sum(regime_counts.values()) or 1
    print("learned policy per (goal, distance):")
    for r in rows:
        print(
            f"  {r['goal']:7s} d={r['distance_m']:4.0f}m -> {r['power_dbm']:6.1f} dBm "
            f"({r['regime']})  outcome={r['outcome']}"
        )
    print(
        "regime fractions:",
        {k: round(v / total_regime, 3) for k, v in regime_counts.items()},
    )

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out = os.path.join(RESULTS_DIR, "rf_jam_spoof_report.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
