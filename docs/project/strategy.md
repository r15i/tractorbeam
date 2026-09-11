# Project Strategy & Grading Guide

> **Superseded**: this early plan assumed the physical-hardware HITL route
> (`hardwareversion/`, `hitl_engine.py`, `fc_commander.py`, `fc_monitor.py`).
> The project pivoted to a 100% software SITL approach - see
> `docs/project/pivot-to-sitl.md` - and those scripts/directories no longer
> exist. Kept for historical context only.

To achieve the best grade in the shortest amount of time, you need a focused execution plan that balances a working demonstration with deep academic analysis. 

## 1. The Fastest Way to Solve the Project
The core of the project is demonstrating the **"Tractor Beam" (GPS Spoofing + HITL)**. Since the Python scripts for HITL are already started in `hardwareversion/`, focus your efforts there rather than building SITL from scratch.

**Step-by-step Fast Track:**
1. **Hardware Validation:** Connect the Flight Controller (FC) and FTDI adapter. Ensure you can successfully send NMEA sentences via `hitl_engine.py` and see the GPS coordinate change in Betaflight/INAV Configurator.
2. **Disable Safety Checks:** Ensure the CLI commands to disable runaway takeoff and arming checks are applied (as documented in `docs/project/architecture.md`). This is critical for desk testing.
3. **IMU Injection:** The hardest part of spoofing modern FCs is the Extended Kalman Filter (EKF). If the GPS says the drone is moving but the IMU says it's perfectly still, the FC will trigger a failsafe. Your `hitl_engine.py` must send fake, matching accelerometer/gyro data via MSP when you "teleport" the GPS.
4. **Trigger the Attack:** 
   - Arm the FC so it locks a "Home" position.
   - Use the `hitl_engine.py` to spoof the GPS, tricking the drone into thinking it has been blown 500m away.
   - Trigger Return To Home (RTH).
   - Observe the motor outputs via `fc_monitor.py` responding to the fake GPS coordinates as it tries to fly back.

## 2. How to Get the Best Grade Possible

To elevate this from a basic coding project to a top-tier academic submission, focus on the following deliverables:

### A. Create a Compelling Video Demonstration
Graders love visual proof. Record a video showing:
- Your terminal running the spoofing scripts.
- The Betaflight/INAV Configurator screen showing the drone's 3D model tilting and the GPS map location moving.
- A clear narrative explaining *why* the motors are ramping up (the FC is trying to correct the spoofed error).

### B. Deep Dive into the EKF (Extended Kalman Filter)
Don't just show that it works; explain *why* it's hard to achieve. Dedicate a section in your final report to how modern drones fuse GPS, Barometer, and IMU data. Explain how your script successfully tricks the EKF by matching the spoofed GPS movement with synthetic IMU bumps.

### C. Propose Mitigation Strategies
A top-tier engineering project doesn't just exploit a vulnerability; it proposes a fix. Include a section discussing:
- **Sensor Cross-Checking:** How could the FC detect spoofing by comparing GPS speed against IMU integration?
- **GPS Signal Authentication:** Discussing encrypted GPS (e.g., Galileo OSNMA).
- **Failsafe Behaviors:** Suggesting that the FC should switch to a "dumb" angle-mode descent if GPS and IMU data diverge wildly, rather than flying away.

### D. Keep the Repo and Code Clean
- Ensure all Python scripts (`fc_commander.py`, `hitl_engine.py`, etc.) are heavily commented.
- Maintain this Obsidian vault. A well-organized `docs/` folder shows professionalism and a structured thought process.
