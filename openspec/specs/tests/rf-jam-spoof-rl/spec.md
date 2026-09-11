# tests/rf-jam-spoof-rl Specification

## Purpose

Trains and evaluates a Soft Actor-Critic agent over the RF simulation so it learns a jam-versus-spoof power policy that maximizes takeover success while minimizing power and detection risk.

## Requirements

### Requirement: Gym-style environment
The system SHALL expose the RF simulation as a reinforcement-learning environment with an observation space, a continuous power action, a step function, and a reset function.

#### Scenario: Environment steps through episodes
- **WHEN** the agent takes a power action each step
- **THEN** the environment advances the simulation and returns the next observation, a reward, and a done flag

### Requirement: SAC training
The system SHALL train a Soft Actor-Critic agent on the environment to produce a policy over continuous transmit power.

#### Scenario: Training improves episode return
- **WHEN** the agent is trained for a configured number of timesteps
- **THEN** the average episode reward increases relative to a random-policy baseline

### Requirement: Jam-versus-spoof decision emerges from power
The system SHALL allow the learned policy to select powers that place the receiver in either the spoofed or jammed regime, so "when to jam" is a learned outcome rather than a hardcoded mode.

#### Scenario: Policy reaches both regimes
- **WHEN** the trained policy is evaluated across a range of scenarios
- **THEN** the recorded episode traces show the agent choosing powers in both the spoofing and jamming regimes as the situation demands

### Requirement: Reward trades success against cost
The system SHALL score the agent with a reward that rewards a successful takeover and penalizes excessive power and detection risk.

#### Scenario: Low-power success is preferred
- **WHEN** two episodes achieve the same takeover outcome at different power levels
- **THEN** the lower-power episode receives a higher reward

### Requirement: Policy evaluation and reporting
The system SHALL record the trained policy's behavior and report the jam-versus-spoof power profile and its success rate.

#### Scenario: Run produces a report
- **WHEN** training and evaluation complete
- **THEN** a report is produced with the learned power profile, the fraction of time spent in each regime, and the takeover success rate
