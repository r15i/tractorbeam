# Strategic Pivot to SITL (Software-In-The-Loop)

## Decision
We have decided to pivot from a physical Hardware-In-The-Loop (HITL) approach (using a physical flight controller and FTDI adapters) to a 100% Software-In-The-Loop (SITL) simulated approach.

## Reasons for Pivot
1. **Reproducibility**: A software-only setup allows anyone (including the evaluator) to run the simulation without needing to purchase specific physical hardware.
2. **Speed of Development**: Eliminates flakiness related to USB/serial connections and hardware drivers, accelerating the development of the attack script.
3. **RF Signal Simulation in 3D Space**: Instead of just injecting hardcoded GPS coordinates, we can simulate the physics of RF signal propagation in 3D space. 
   - **Free-space path loss**: The GPS signal strength (L1 at 1575.42 MHz) will drop based on the distance squared from the satellite.
   - **Spoofing dynamics**: We can model the attacker's transmitter power and distance to the victim drone.
   - **Receiver behavior**: The simulated receiver will lock onto the strongest signal (legitimate vs. spoofed), providing a highly realistic physical layer simulation that strengthens the project's academic value.

## Next Steps
- Set up the Betaflight SITL environment.
- Adapt the existing `hitl_engine.py` and `fc_commander.py` scripts to interface with the SITL environment instead of a physical UART/USB connection.
- Implement the 3D RF signal strength physics logic.
