# Architecture & Hardware

> **Superseded**: describes the original physical-hardware HITL design
> (`hitl_engine.py`, `fc_commander.py`, `fc_monitor.py`, FTDI/USB wiring).
> The project pivoted to a 100% software SITL approach - see
> `docs/project/pivot-to-sitl.md` and `docs/setup/sitl-setup.md` for the current,
> software-only setup. Kept for historical context only.

## Architecture
1.  **GPS Spoofer (FTDI):** Sends NMEA streams ($GPGGA, $GPRMC) to the FC's GPS UART port.
2.  **HITL Engine (USB):** 
    -   Reads **Motor Outputs** from the FC via MSP.
    -   Injects **Fake IMU/ACC** data to satisfy the EKF and prevent "Runaway Takeoff" disarms.
    -   Allows manual "Teleportation" of the GPS signal using WASD.
3.  **RC Commander (USB):** Simulates a radio transmitter to Arm, Disarm, and trigger RTH.

## Hardware Setup
- **FTDI Adapter:** TX -> FC RX (GPS), GND -> FC GND. Port: `/dev/ttyUSB0` (57600 baud).
- **FC USB:** Connected to PC. Port: `/dev/ttyACM1` (MSP 115200 baud).

## Safety Configuration (Betaflight/INAV CLI)
To prevent the FC from disarming on the desk, run these commands:
```bash
set runaway_takeoff_prevention = OFF
save
```

## Tools
- `hitl_engine.py`: The main simulation core. Handles IMU injection and WASD GPS control.
- `fc_commander.py`: RC transmitter simulator (Arm/Disarm/RTH).
- `fc_monitor.py`: Real-time telemetry (Attitude, GPS, Motors, Arming Flags).

## Experimental Workflow
1.  Start `hitl_engine.py`.
2.  Start `fc_monitor.py`.
3.  Start `fc_commander.py`.
4.  **Home Point:** Arm the FC. It records the current spoofed GPS as Home.
5.  **Teleport:** Use WASD in the `hitl_engine` to move the "Drone" 500m away.
6.  **Attack:** Trigger RTH in `fc_commander`.
7.  **Observation:** Watch the FC try to fly back. The `hitl_engine` will automatically tilt the virtual IMU and move the GPS in response to the FC's motor outputs.
