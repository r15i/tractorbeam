# tests/heading-confidence Specification

## Purpose

Defines the heading-confidence precondition the horizontal spoofing channel depends on: a synthetic forward-pitch, accelerometer-tilt, and velocity feed that drives Betaflight's GPS-heading confidence past its threshold so the rescue logic may enter the horizontal flight phases.

## Requirements

### Requirement: Matching pitch and velocity feed clears heading confidence
The system SHALL demonstrate that a consistent forward-pitch attitude with a matching accelerometer tilt and matching velocity vector drives the flight controller's GPS-heading confidence past its threshold, latching heading as usable.

#### Scenario: Confidence crosses threshold with matched feed
- **WHEN** a forward pitch (e.g. 15 degrees) is fed together with a matching accelerometer tilt and a matching forward velocity (e.g. 7.5 m/s)
- **THEN** the GPS-heading confidence exceeds the usability threshold and `canUseGPSHeading` becomes true within the rescue pitch-forward timeout (15 s)

### Requirement: Heading confidence is observable
The system SHALL expose the heading-confidence state (confidence value and usability flag) so the precondition can be measured rather than inferred.

#### Scenario: Confidence telemetry is readable
- **WHEN** the heading-confidence probe queries the flight controller's debug telemetry
- **THEN** the GPS-heading confidence value and the heading-usability flag are returned for the current fed attitude and velocity

### Requirement: Precondition timing is characterized
The system SHALL report the elapsed time for a given (pitch, speed) pair to clear the heading-confidence threshold, so downstream horizontal experiments can rely on validated parameters.

#### Scenario: Probe reports time to clear
- **WHEN** the probe is run with a specified pitch and forward speed
- **THEN** the elapsed time at which heading becomes usable is reported, along with the fed pitch and velocity used
