# Project Goal: Tractor Beam over Betaflight

## Overview
This project simulates GPS hijacking attacks on Flight Controllers (FC) using **Hardware In The Loop (HITL)** and **Software In The Loop (SITL)** simulation. By injecting fake GPS (via UART) and fake IMU/Sensor data (via USB/MSP), we can trick the FC into believing it is flying a mission while it sits safely on a desk without propellers, effectively creating a "Tractor Beam".

The goal is to analyze the behavior of Flight Controllers (like Betaflight and INAV) when subjected to spoofed navigation data and test mitigation strategies.
