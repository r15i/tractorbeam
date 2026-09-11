## Purpose

Provides an automated test capability for Betaflight GPS Rescue's horizontal distance-to-home sanity check (`RESCUE_FLYAWAY`), determining whether a spoofed GPS trajectory is accepted (followed) or rejected (flagged), including the case where the reported arrival position differs from the drone's true armed-at home.

## ADDED Requirements

### Requirement: Reach the Horizontal Rescue Phase
The test harness SHALL bring the simulated flight controller to `RESCUE_FLY_HOME` (or later) before evaluating horizontal spoofing outcomes, since `RESCUE_FLYAWAY` is only evaluated in that phase and later.

#### Scenario: Clearing the altitude and heading gates
- **WHEN** GPS Rescue is triggered with an altitude feed that clears `RESCUE_ATTAIN_ALT` and a velocity feed consistent enough to validate GPS heading
- **THEN** the reported rescue phase advances to `RESCUE_ROTATE` and then `RESCUE_FLY_HOME` within the test's timeout

### Requirement: Frozen/No-Progress Spoof Is Rejected
The system SHALL demonstrate that a GPS feed reporting no reduction in distance-to-home during `RESCUE_FLY_HOME` results in a rejection.

#### Scenario: Distance never decreases
- **WHEN** the reported position is held constant (or moved away from home) throughout `RESCUE_FLY_HOME`
- **THEN** the rescue failure state becomes `RESCUE_FLYAWAY` within the check's failing-window timeout, and this is logged with the exact trigger time

### Requirement: Progress-Consistent Spoof Is Accepted
The system SHALL demonstrate that a GPS feed reporting home-ward progress at or above the rate Betaflight itself expects is followed without triggering `RESCUE_FLYAWAY`, regardless of whether the reported destination is the drone's true home.

#### Scenario: Adaptive convergence to true home
- **WHEN** the reported position closes on the true home position at a rate matching or exceeding the FC's configured rescue ground speed
- **THEN** no rescue failure flag is raised for the duration of the approach

#### Scenario: Adaptive convergence to a different (attacker-chosen) position
- **WHEN** the reported position closes, at the same qualifying rate, on a position other than the drone's true armed-at home
- **THEN** no rescue failure flag is raised, and the flight controller's rescue logic proceeds as if it had arrived home at that different position - demonstrating the "make it think it's somewhere else" hijack the test set out to check

### Requirement: Results Are Recorded and Visualized
The system SHALL log each run's timeline (time, reported and true positions, distance-to-home, rescue phase/failure, armed state) and produce a comparison view across all tested profiles, consistent with the existing altitude-channel result.

#### Scenario: Run produces a comparable artifact
- **WHEN** a horizontal spoofing profile test completes (accepted or rejected)
- **THEN** a CSV timeline and a summary suitable for side-by-side comparison with the altitude-channel results are produced
