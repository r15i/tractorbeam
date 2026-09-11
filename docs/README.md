# Documentation

> **Note:** This documentation is designed as an [Obsidian](https://obsidian.md/) vault. Opening the `docs/` directory in Obsidian will enable wiki-links, graph views, and the best reading experience.


## Index

### Project (goals, history, security analysis)

| Doc | What |
|---|---|
| [`project/goal.md`](project/goal.md) | The project's objective and scope |
| [`project/pivot-to-sitl.md`](project/pivot-to-sitl.md) | Why we moved from hardware-in-the-loop to software-only |
| [`project/architecture.md`](project/architecture.md) | Original HITL design (historical) |
| [`project/strategy.md`](project/strategy.md) | Early grading/execution plan (historical) |
| [`project/kalman-bypass.md`](project/kalman-bypass.md) | Why naive GPS spoofing fails — the EKF consistency problem |
| [`project/mitigation.md`](project/mitigation.md) | Countermeasures to GPS hijacking |
| [`project/references.md`](project/references.md) | External links and local resources |

### Setup

| Doc | What |
|---|---|
| [`setup/sitl-setup.md`](setup/sitl-setup.md) | Betaflight SITL bring-up, config, and network endpoints |

### Results & analysis

| Doc | What |
|---|---|
| [`results/simulation-scenarios.md`](results/simulation-scenarios.md) | The four simulation layers and how they connect |
| [`results/false-home-landing.md`](results/false-home-landing.md) | Estimator-decoupling landing results + RL/quality discussion |
| [`results/rf-jam-spoof-rl.md`](results/rf-jam-spoof-rl.md) | RF power layer + discrete-SAC policy |
| [`results/rf-simulation.md`](results/rf-simulation.md) | The RF data model and the attacker's tracking requirement |
| [`results/simulations-comparison.md`](results/simulations-comparison.md) | SITL vs RF+RL, deterministic vs learned |
| [`results/real-world-attack.md`](results/real-world-attack.md) | The attack in the field and our simplification routes |

### Code

| Doc | What |
|---|---|
| [`code/reference.md`](code/reference.md) | Module-by-module code reference |

### Resources

- [`resources/`](resources/) — the reference paper PDFs and research notes.
