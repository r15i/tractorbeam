## Purpose

Models how an attacker passively tracks a drone's actual position — via direction-finding and RSSI on the drone's video/telemetry transmission — so the spoofed GPS can be kept consistent with the drone's real motion.

## ADDED Requirements

### Requirement: Drone emission model
The system SHALL model the drone's video/telemetry transmission as an RF source with a distinct frequency band and transmit power, whose received power follows free-space path loss and is unaffected by GPS L1 jamming.

#### Scenario: Emission survives GPS jamming
- **WHEN** the GPS L1 band is jammed
- **THEN** the received power of the drone's video/telemetry emission is unchanged, because it occupies a different frequency band

### Requirement: Bearing estimation
The system SHALL estimate the bearing to the drone from a direction-finding antenna by locating the peak received signal, with a modeled angular error.

#### Scenario: Bearing has bounded error
- **WHEN** the attacker's antenna is steered toward the drone
- **THEN** the reported bearing is within a modeled angular error of the true bearing

### Requirement: Range estimation
The system SHALL estimate the range to the drone from the received signal strength by inverting the path-loss law, with a modeled error.

#### Scenario: Range has bounded error
- **WHEN** the attacker measures the received signal strength of the drone's emission
- **THEN** the reported range is within a modeled error of the true range

### Requirement: Position estimate
The system SHALL combine the bearing and range estimates into an estimated position of the drone, with an associated uncertainty that grows with range and measurement error.

#### Scenario: Position has an uncertainty region
- **WHEN** bearing and range are estimated
- **THEN** the resulting position estimate carries an uncertainty region that widens with range and with the bearing and RSSI errors

### Requirement: Spoof consistency constraint
The system SHALL constrain the spoofed GPS trajectory against the tracked position estimate and SHALL report when the spoof diverges from the tracked position beyond the fusion tolerance.

#### Scenario: Divergence is flagged
- **WHEN** the spoofed position moves away from the tracked position by more than the configured tolerance
- **THEN** the system reports the divergence as a spoof-consistency violation
