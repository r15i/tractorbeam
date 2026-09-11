# tests/false-home-landing Specification

## Purpose

Defines the estimator-decoupling landing attack: making a Betaflight GPS Rescue complete a landing at an attacker-chosen false home while its armed-at home stays locked, and measuring the estimator-level quality of the spoof.

## Requirements

### Requirement: Clean-landing baseline
The system SHALL demonstrate that an EKF-consistent, rate-matched spoofed trajectory converging on the true armed-at home completes the full rescue (descent, landing, disarm) without tripping `RESCUE_FLYAWAY`.

#### Scenario: Spoof converges on true home and lands
- **WHEN** the reported position closes on the true home at or above the firmware's ground speed
- **THEN** the rescue advances to descent and landing and the flight controller disarms, with no flyaway failure raised

### Requirement: Decoupled physical and spoofed state
The system SHALL model the drone's "physical" position separately from the spoofed GPS/IMU feed the flight controller observes, so the two MAY diverge, and SHALL record both throughout the run.

#### Scenario: Physical and spoofed positions are tracked independently
- **WHEN** a run is in progress with a spoofed feed that differs from the physical position
- **THEN** both the physical position and the spoofed (reported) position are recorded at each timestep, allowing the divergence to be computed

### Requirement: Velocity-over-position bias
The system SHALL characterize how far the position estimate diverges from the spoofed GPS position when the GPS position is held at a chosen point B while the fed velocity (with matching attitude) points toward the true home, and SHALL determine whether this bias can drive the estimate within the descent distance.

#### Scenario: Estimate diverges from GPS under velocity bias
- **WHEN** the GPS position is fixed at B and the fed velocity points toward the true home at a qualifying speed
- **THEN** the recorded position-estimate divergence from B is non-zero, and the system reports whether the estimate crosses the descent-distance threshold from the true home

### Requirement: Land-at-false-home outcome
The system SHALL determine whether the flight controller can be made to complete descent and landing while the physical position is at the attacker-chosen false home B rather than the locked true home A, and SHALL record the end state (disarmed, flyaway, or GPS-loss).

#### Scenario: Rescue lands while physically at the false home
- **WHEN** a decoupling feed drives the position estimate within the descent distance while the physical position remains at B
- **THEN** the system records whether the rescue reached landing/disarm and the corresponding end state

### Requirement: Estimator-attack metrics
The system SHALL record, per run, the estimate-vs-GPS divergence, the estimator trust value, the flyaway margin, the time-to-land, the landing position error relative to B, and the end state.

#### Scenario: Run produces estimator metrics
- **WHEN** a false-home-landing run completes
- **THEN** a result file is produced containing the divergence, trust, flyaway margin, time-to-land, landing error, and end state for that run

### Requirement: Reproducibility
The system SHALL make each run deterministic from documented inputs (spoof sequence, jam timing, and physical trajectory), so an identical re-run produces comparable results.

#### Scenario: Identical run is comparable
- **WHEN** the same run is executed twice with the same documented inputs
- **THEN** the recorded trajectories and metrics are reproducible within the documented sources of session-level nondeterminism
