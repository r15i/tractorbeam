## Context

As established in `proposal.md`, we are testing Betaflight's EKF thresholds. Betaflight SITL receives its sensor and environment data (Flight Dynamics Model - FDM) from external simulators (like Gazebo or RealFlight) via UDP packets (typically on port 9003). To simulate a walk-off attack, we need to mimic this physics simulator and inject our own FDM data with drifting GPS coordinates.

## Goals / Non-Goals

**Goals:**
- Build a Python-based fake physics engine that sends FDM UDP packets to Betaflight SITL.
- Programmatically inject a configurable GPS drift vector into the FDM packets.
- Monitor and log the drone's motor outputs and arming state to detect failsafes.

**Non-Goals:**
- We are not modifying Betaflight source code.
- We are not simulating aerodynamics or wind (the drone is assumed to be physically hovering perfectly still according to the IMU data we send).

## Decisions

**Decision 1: UDP FDM Injection vs. MSP GPS Override**
- *Rationale*: Betaflight SITL expects sensor data to arrive via a specific C `struct` over UDP port 9003. By crafting these UDP packets in Python, we simulate the exact data flow of a real GPS module communicating with the flight controller in a SITL environment.
- *Alternatives Considered*: We considered using `MSP_SET_RAW_GPS` over TCP, but the SITL environment's internal physics loop often overrides MSP injections, making UDP the more reliable attack vector for this experiment.

**Decision 2: Telemetry Logging Mechanism**
- *Rationale*: We will use the Betaflight Blackbox (saved to `eeprom.bin` or a virtual file) OR monitor the MSP motor outputs (TCP 5761) to observe the drone's physical response. Monitoring MSP is faster for automated test assertions.

## Risks / Trade-offs

- **[Risk]** The FDM UDP packet structure is specific to Betaflight's C implementation and might be difficult to pack in Python. 
  **[Mitigation]** We will read `betaflight/src/main/target/SITL/sitl.h` or `sitl.c` to extract the exact byte-layout of the `fdm_packet` struct and use Python's `struct` module to pack the data.
