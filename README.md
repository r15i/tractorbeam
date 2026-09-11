# TractorBeam: GPS Spoofing on Betaflight

This repository contains the simulation harness, physics engine, and attack scripts for demonstrating rate-matched GPS spoofing (the "TractorBeam" attack) against the Betaflight flight controller.

Unlike ArduPilot, which relies on a strict Extended Kalman Filter (EKF), Betaflight's GPS Rescue mode evaluates drone recovery using simpler rate-of-change sanity checks. This project demonstrates how an attacker can bypass these checks by injecting fake sensor data that precisely matches the firmware's expected altitude and horizontal velocity.

## Requirements
- **Python 3.12**
- **uv** (Fast Python package manager)
- **just** (Command runner)
- **LaTeX** (for compiling the PDF report)
- **Graphviz** (for architecture diagrams)

## How to Reproduce
The entire experimental pipeline is completely fully automated. To run the simulations, generate the data, plot the figures, and compile the final report, simply run:

```bash
just all
```

This command will:
1. Compile the Betaflight SITL (Software-In-The-Loop) firmware.
2. Run the vertical and horizontal channel attack profiles.
3. Run the estimator decoupling and RF reinforcement learning experiments.
4. Compile the final PDF and DOCX reports in the `paper/` directory.

## Repository Structure
- `src/tractorbeam/` - The Python physics engine and UDP/TCP spoofing harness.
- `tools/` - Scripts for running experiments, rendering figures, and generating reports.
- `paper/` - Output directory for the final PDF and DOCX reports, including generated figures.
