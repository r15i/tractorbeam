# sitl-environment Specification

## Purpose

Provides a fully software, hardware-free environment for the Tractor Beam
reproduction: bringing up Betaflight SITL with safe arming configuration and
connecting the GPS/IMU spoofing and telemetry tooling to it over TCP/UDP
instead of physical serial ports. The project's original design used
equivalent tooling against physical hardware (HITL); that approach was
abandoned in favor of this SITL-only one (see `docs/Strategic_Pivot_to_SITL.md`).

## Requirements

### Requirement: SITL Bring-Up
The system SHALL provide a documented, repeatable procedure to launch the Betaflight SITL binary with arming-safety CLI settings applied, so it can be armed at a desk with no propellers attached.

#### Scenario: Launching SITL exposes the expected endpoints
- **WHEN** the SITL binary is started
- **THEN** it opens a UDP listener for FDM state on port 9003, a UDP listener for RC input on port 9004, and a TCP MSP server starting at port 5760, with no physical UART/USB hardware involved

#### Scenario: Safety configuration prevents desk-arming failsafes
- **WHEN** `runaway_takeoff_prevention` is disabled and saved on the SITL instance
- **THEN** arming the flight controller over MSP while stationary does not trigger a runaway-takeoff or on-ground disarm

### Requirement: Simulator Transport Layer
The system SHALL provide a transport layer that connects to a running SITL instance over TCP (MSP) and UDP (FDM state / RC input), exposing the same operations the physical HITL tooling relies on: sending fake GPS/IMU state, reading motor outputs and telemetry, and sending RC channel updates.

#### Scenario: Connecting without physical hardware
- **WHEN** the transport layer is pointed at a running local SITL instance
- **THEN** it establishes MSP (TCP) and FDM/RC (UDP) connections successfully without requiring an FTDI adapter or FC USB connection

#### Scenario: Injected state is reflected in telemetry
- **WHEN** fake GPS coordinates and IMU acceleration are sent through the transport layer
- **THEN** querying MSP telemetry (RAW_GPS, ATTITUDE) on the same SITL instance reflects the injected values

### Requirement: Environment Verification
The system SHALL provide a way to verify, before any spoofing/drift experiment is run, that the environment is correctly wired end-to-end.

#### Scenario: Baseline hover smoke test
- **WHEN** SITL is launched, the transport layer connects, and the FC is armed with baseline (non-drifting) injected GPS/IMU state
- **THEN** the FC remains armed with no failsafe flags active and stable telemetry for at least 30 seconds, establishing a known-good starting point for later experiments
