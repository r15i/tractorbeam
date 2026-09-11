## Why

We need to identify the exact thresholds at which Betaflight's Extended Kalman Filter (EKF) detects a variance between GPS coordinates and IMU acceleration. Specifically, we are looking for the "blind spot" where a slow, gradual GPS drift goes unnoticed by the EKF. This is necessary to validate our hypothesis about "walk-off" GPS spoofing attacks causing misdirection during a Return-To-Home (RTH) task.

## What Changes

- Set up a test suite architecture in a new `sim_tests/` directory.
- Develop a Python orchestrator to interact with Betaflight SITL (via MSP or websockets) to inject GPS drift during an RTH sequence.
- Automate the gradual ramping of the fake GPS velocity error (e.g., from 0.1 m/s up to 2.0 m/s) across multiple runs.
- Log telemetry data (specifically `nav_position_error` and motor outputs) to determine the exact threshold where the FC corrects its physical heading vs. when it rejects the GPS entirely.

## Capabilities

### New Capabilities
- `tests/gps-walkoff`: An automated test capability for injecting gradual GPS drift into Betaflight SITL and monitoring the EKF's response during RTH.

### Modified Capabilities

## Impact

- Introduces a new testing directory (`sim_tests/`) and potentially Python dependencies for MSP interaction.
- Does not modify any core Betaflight firmware code; this is purely a black-box test harness against the compiled SITL executable.
