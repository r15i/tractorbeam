# Bypassing the Extended Kalman Filter (EKF)

## What is the EKF?
In modern Flight Controllers (like Betaflight, INAV, and ArduPilot), the **Extended Kalman Filter (EKF)** is a complex mathematical algorithm used to estimate the drone's state (position, velocity, and orientation). 

Because individual sensors are noisy or prone to errors, the EKF fuses data from multiple sources:
1.  **GPS:** Provides absolute position (Lat/Lon) and velocity, but updates slowly (usually 5-10Hz) and can be inaccurate.
2.  **IMU (Accelerometers & Gyroscopes):** Provides rapid (1000Hz+), highly accurate data about short-term movement and tilt, but suffers from "drift" over time.
3.  **Barometer/Compass:** Provides altitude and heading.

## Why Simple GPS Spoofing Fails
If an attacker simply feeds fake GPS coordinates to a modern drone, the attack will likely fail. 
For example, if the spoofed GPS tells the drone it is suddenly moving North at 10 m/s, but the IMU (accelerometer) registers absolutely no physical acceleration, the EKF detects a massive **sensor variance (innovation error)**. 

When sensors violently disagree, the flight controller's failsafe mechanism triggers. It will usually reject the GPS data entirely and switch to a non-GPS emergency landing mode, preventing the "Tractor Beam" attack.

## The HITL Bypass Strategy
To successfully hijack the drone, our Hardware-In-The-Loop (HITL) engine must feed the EKF a cohesive narrative. 

When we want to spoof movement, we must simultaneously inject:
1.  **Fake GPS Data (via UART):** Drifting the coordinates smoothly toward the target vector.
2.  **Fake IMU Data (via MSP/USB):** Injecting brief acceleration spikes that perfectly match the simulated physical forces required to achieve the spoofed GPS velocity.

By ensuring the IMU's mathematical integration matches the GPS's derivative, the EKF remains "happy" and trusts the spoofed trajectory, allowing the flight controller to issue motor commands based on our fake reality.
