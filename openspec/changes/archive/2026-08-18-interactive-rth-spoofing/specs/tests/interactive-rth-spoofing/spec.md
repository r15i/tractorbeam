## Purpose

Lets a human operator interactively redirect a Betaflight GPS Rescue by selecting a spoof target position on a live map and observing the reported position diverge from the drone's fixed true position toward that target.

## ADDED Requirements

### Requirement: Interactive target selection during GPS Rescue
The system SHALL allow an operator to select a spoof target position while GPS Rescue is in its horizontal return-to-home phase, and SHALL begin spoofing the reported position toward that target once it is chosen.

#### Scenario: Target selected during horizontal flight
- **WHEN** the craft has reached the horizontal return-to-home phase and the operator selects a target position
- **THEN** spoofing toward the selected target begins and the reported position starts moving toward it

### Requirement: Live deviation visualization
The system SHALL present a live map showing the drone's fixed true position, its reported (spoofed) position, and the selected target, updating as the reported position moves.

#### Scenario: Reported position diverges from true position
- **WHEN** a target is selected away from the drone's true armed-at position
- **THEN** the map shows the reported position moving away from the true position toward the target while the true position remains fixed

### Requirement: Rate-matched adaptive spoofing toward target
The system SHALL move the reported position toward the selected target at a rate consistent with the firmware's own return-to-home ground speed, so the rescue logic does not reject the spoof as a flyaway while the target is being approached.

#### Scenario: Spoof toward an off-home target is accepted
- **WHEN** the reported position converges on an operator-chosen target at the qualifying rate
- **THEN** no flyaway failure is raised for the duration of the approach

### Requirement: Rescue logic follows the spoofed position
The system SHALL demonstrate that, while the target is being approached, the flight controller's rescue logic proceeds as if the drone were flying toward the selected target rather than its true home.

#### Scenario: Rescue advances toward the chosen position
- **WHEN** the reported position closes on a target that differs from the drone's true armed-at home
- **THEN** the rescue logic continues its return-to-home flight (no failure or disarm) driven by the spoofed position

### Requirement: Interactive run is recorded
The system SHALL log the interactive run's timeline (time, true position, reported position, target position, rescue phase, and failure state) so it can be compared with the scripted horizontal-channel results.

#### Scenario: Run produces a comparable artifact
- **WHEN** an interactive spoofing session completes
- **THEN** a CSV timeline is produced recording the positions, rescue phase, and failure state for the session
