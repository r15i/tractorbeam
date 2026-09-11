## Purpose
Provides an automated test suite capability to inject gradual GPS drift into Betaflight SITL and observe the EKF response to identify the "walk-off" threshold.

## ADDED Requirements

### Requirement: Gradual Drift Injection
The system SHALL provide a mechanism to inject fake GPS coordinates into the SITL with a configurable, incrementally increasing drift velocity relative to the initial Home position.

#### Scenario: Sub-threshold drift injection
- **WHEN** the drift rate is below the EKF variance threshold (e.g., 0.1 m/s)
- **THEN** the Betaflight SITL processes the GPS coordinates as valid and adjusts motor outputs to navigate towards the fake location without triggering a failsafe.

#### Scenario: Supra-threshold drift injection
- **WHEN** the drift rate exceeds the EKF variance threshold (e.g., 5.0 m/s)
- **THEN** the Betaflight SITL detects a sensor conflict between the GPS and IMU, increments the `nav_position_error`, and eventually rejects the GPS data.

### Requirement: Telemetry Logging
The system SHALL log the relevant Betaflight telemetry data (GPS coordinates, accelerometer data, nav position error, and motor outputs) during the experiment for offline analysis.

#### Scenario: Successful telemetry recording
- **WHEN** a test run completes
- **THEN** a log file is generated containing timestamped state data showing when the EKF accepted or rejected the spoofed trajectory.
