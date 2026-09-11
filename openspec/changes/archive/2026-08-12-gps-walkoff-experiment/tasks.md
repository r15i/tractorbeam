## 1. Setup

- [ ] 1.1 Create the `sim_tests` directory structure and `requirements.txt` for Python dependencies.
- [ ] 1.2 Investigate Betaflight source code (`src/main/target/SITL/`) to determine the exact C struct format for the incoming UDP FDM packets.

## 2. Core Simulator Mock

- [ ] 2.1 Write `sim_tests/mock_physics.py` to open a UDP socket sending data to `127.0.0.1:9003`.
- [ ] 2.2 Implement the Python `struct` packing logic to transmit a baseline "hovering" physical state (static GPS, flat IMU).

## 3. Drift Injection & Telemetry

- [ ] 3.1 Create `sim_tests/walkoff_test.py` as the main orchestrator script.
- [ ] 3.2 Add a function to programmatically increment a drift vector to the injected GPS coordinates over time.
- [ ] 3.3 Implement an MSP listener via TCP (port 5761) to monitor the drone's motor outputs and `nav_position_error`.

## 4. Automation and Logging

- [ ] 4.1 Write a loop that executes multiple test runs, starting with a drift of 0.1 m/s and ramping up to 5.0 m/s.
- [ ] 4.2 Log the telemetry data to a CSV file to pinpoint the exact threshold where the FC rejects the GPS (failsafe) vs. when it accepts the misdirection.
