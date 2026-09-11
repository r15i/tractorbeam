## 1. Emission and propagation

- [x] 1.1 Implement the drone video/telemetry emission model (5.8 GHz, configurable EIRP) using the shared `path_loss_db` helper
- [x] 1.2 Confirm the emission's received power is independent of the GPS L1 jammer band

## 2. Direction-finding and ranging

- [x] 2.1 Implement bearing estimation via a rotating directional antenna with RSSI peak-finding and a Gaussian angular error (σ_θ)
- [x] 2.2 Implement range estimation by inverting the path loss from RSSI, with a Gaussian RSSI error propagated to range

## 3. Position estimate and uncertainty

- [x] 3.1 Combine bearing + range into an estimated position with a cross-range and radial uncertainty region
- [x] 3.2 Verify the uncertainty region widens with range and with the bearing/RSSI errors

## 4. Spoof consistency constraint

- [x] 4.1 Implement the consistency check that flags when the spoofed position diverges from the tracked position beyond the fusion tolerance
- [x] 4.2 Demonstrate the constraint: with noisy tracking the spoof stays consistent only briefly

## 5. Integration and documentation

- [x] 5.1 Wire the tracking estimate into the existing RF/RL environment so it constrains the spoofed trajectory
- [x] 5.2 Document the tracking technologies, the chosen model, and the error parameters in `docs/`
- [x] 5.3 Run `openspec validate rf-tracking-sim --strict` and resolve any issues
