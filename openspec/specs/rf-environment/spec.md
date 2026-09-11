# rf-environment Specification

## Purpose

Models the RF layer an attacker actually controls — free-space propagation, the receiver's lock-on-strongest behavior, and the spoof-versus-jam power regimes — so the effect of transmitter power on a GPS receiver can be simulated without touching the existing SITL feed.

## Requirements

### Requirement: Propagation model
The system SHALL compute the power a GPS receiver receives from an attacker transmitter as a function of transmitter power and range, using free-space path loss.

#### Scenario: Received power falls with distance
- **WHEN** transmitter power is held constant and the receiver range increases
- **THEN** the computed received power decreases according to the path-loss law

### Requirement: Receiver lock-on-strongest
The system SHALL determine which signal the receiver tracks (the attacker's or the legitimate satellites') by comparing their received powers, with the receiver locking onto the stronger source.

#### Scenario: Attacker overtakes the satellites
- **WHEN** the attacker's received power exceeds the legitimate signal by a configurable capture margin
- **THEN** the simulated receiver tracks the attacker's signal

### Requirement: Jam-versus-spoof regime
The system SHALL classify the receiver into one of three regimes — normal, spoofed, or jammed — based on the attacker power relative to the legitimate signal.

#### Scenario: Regimes are separated by power
- **WHEN** attacker power is below the spoofing threshold
- **THEN** the receiver is classified normal
- **WHEN** attacker power is within the spoofing window above the capture margin
- **THEN** the receiver is classified spoofed
- **WHEN** attacker power exceeds the jamming threshold
- **THEN** the receiver is classified jammed (no fix)

### Requirement: Drone response mapping
The system SHALL map the receiver regime to a simplified drone response so the trade-off between jamming and spoofing is observable.

#### Scenario: Response follows regime
- **WHEN** the receiver is normal
- **THEN** the drone proceeds on a normal return-to-home
- **WHEN** the receiver is spoofed
- **THEN** the drone follows the attacker's fake position
- **WHEN** the receiver is jammed
- **THEN** the drone enters a GPS-loss failsafe
