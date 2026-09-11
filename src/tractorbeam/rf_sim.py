"""RF layer for the jam/spoof attack: free-space propagation and the receiver
regime model. Pure functions, no dependencies beyond stdlib + numpy.

Regimes (receiver tracks the strongest signal):
  normal   - attacker below the satellite signal + capture margin
  spoofed  - attacker within the capture window above the satellites
  jammed   - attacker far above the satellites (AGC saturation -> no fix)
"""

import math

GPS_L1_MHZ = 1575.42
SAT_POWER_DBM = -130.0  # typical GPS L1 C/A power at the receiver
CAPTURE_MARGIN_DB = 3.0  # attacker must exceed the satellites by this to capture
JAM_MARGIN_DB = 30.0  # attacker this far above -> receiver loses fix


def path_loss_db(distance_m, freq_mhz=GPS_L1_MHZ):
    """Free-space path loss in dB."""
    if distance_m <= 0.0:
        distance_m = 0.001
    return 20.0 * math.log10(distance_m) + 20.0 * math.log10(freq_mhz) - 27.55


def received_power_dbm(tx_power_dbm, distance_m, fading_db=0.0):
    """Power the receiver sees from the attacker."""
    return tx_power_dbm - path_loss_db(distance_m) + fading_db


def classify_regime(
    rx_power_dbm,
    sat_power_dbm=SAT_POWER_DBM,
    capture_db=CAPTURE_MARGIN_DB,
    jam_db=JAM_MARGIN_DB,
):
    """Classify the receiver state from the received attacker power."""
    if rx_power_dbm < sat_power_dbm + capture_db:
        return "normal"
    if rx_power_dbm < sat_power_dbm + jam_db:
        return "spoofed"
    return "jammed"
