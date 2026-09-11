"""Attacker target-tracking simulation.

The attacker passively locates the drone by direction-finding on its FPV video
feed (5.8 GHz), producing a *noisy* position estimate. That estimate is the
input to the spoof-consistency constraint: a believable GPS spoof must stay
within the tracked position +/- the drone's sensor-fusion tolerance, so poor
tracking bounds how long an attack can stay consistent.

The video feed is modelled as a distinct RF source that is unaffected by the
GPS L1 jammer (different band), which is exactly why it is the tracking signal
of choice in the field.
"""

import argparse
import math
import random

from tractorbeam.rf_sim import path_loss_db

VIDEO_FREQ_MHZ = 5800.0
VIDEO_EIRP_DBM = 20.0  # typical 100 mW FPV VTX
SIGMA_THETA_DEG = 5.0  # bearing error, RSSI + directional antenna
SIGMA_RSSI_DB = 2.0  # RSSI measurement noise
FUSION_TOLERANCE_M = 15.0  # the drone's sensor-fusion tolerance (spoof bound)

# Friis derivative: relative range error per dB of RSSI error.
# dRSSI = -20*log10(d) + const  ->  dd/d = (ln10/20) * dRSSI ~= 0.115 * dRSSI.
RANGE_ERROR_PER_DB = math.log(10.0) / 20.0  # ~0.1151


def video_rssi_dbm(distance_m, eirp_dbm=VIDEO_EIRP_DBM, freq_mhz=VIDEO_FREQ_MHZ):
    """Received video-feed power at the attacker (free-space path loss)."""
    return eirp_dbm - path_loss_db(distance_m, freq_mhz)


def estimate_range(rssi_dbm, eirp_dbm=VIDEO_EIRP_DBM, freq_mhz=VIDEO_FREQ_MHZ):
    """Invert the path loss to recover range from RSSI."""
    pl = eirp_dbm - rssi_dbm
    return 10.0 ** ((pl - 20.0 * math.log10(freq_mhz) + 27.55) / 20.0)


class AttackerTracker:
    """Attacker at the origin, locating a drone by DF + RSSI on the video feed."""

    def __init__(
        self, sigma_theta_deg=SIGMA_THETA_DEG, sigma_rssi_db=SIGMA_RSSI_DB, seed=0
    ):
        self.sigma_theta = math.radians(sigma_theta_deg)
        self.sigma_rssi = sigma_rssi_db
        self.rng = random.Random(seed)

    def measure(self, drone_x, drone_y):
        """Return a noisy estimate of the drone's position plus its uncertainty."""
        true_range = math.hypot(drone_x, drone_y)
        true_bearing = math.atan2(drone_x, drone_y)  # 0 = north, CCW
        est_bearing = true_bearing + self.rng.gauss(0.0, self.sigma_theta)
        rssi = video_rssi_dbm(true_range) + self.rng.gauss(0.0, self.sigma_rssi)
        est_range = estimate_range(rssi)
        return {
            "true_range": true_range,
            "est_range": est_range,
            "true_bearing_deg": math.degrees(true_bearing),
            "est_bearing_deg": math.degrees(est_bearing),
            "est_x": est_range * math.sin(est_bearing),
            "est_y": est_range * math.cos(est_bearing),
            "cross_range_err_m": true_range * self.sigma_theta,  # angular
            "radial_err_m": true_range * RANGE_ERROR_PER_DB * self.sigma_rssi,  # RSSI
        }

    def consistent(
        self, spoofed_x, spoofed_y, tracked_x, tracked_y, tol=FUSION_TOLERANCE_M
    ):
        """True while the spoof stays within `tol` of the tracked position."""
        return math.hypot(spoofed_x - tracked_x, spoofed_y - tracked_y) <= tol


def _demo():
    print("=" * 70)
    print("1) Emission is a function of range only (independent of the GPS jammer)")
    print("=" * 70)
    for d in (50, 150, 300, 600):
        print(
            f"  drone at {d:4.0f} m -> video RSSI = {video_rssi_dbm(d):6.1f} dBm "
            f"(5.8 GHz feed; GPS L1 jammer irrelevant)"
        )

    print()
    print("=" * 70)
    print("2) Bearing + range estimation, and how uncertainty grows with range")
    print("=" * 70)
    tr = AttackerTracker(seed=1)
    print(f"  {'true':>8} {'est':>8} {'cross':>8} {'radial':>8}")
    for d in (50, 150, 300, 600):
        m = tr.measure(0.0, d)  # drone due north
        err = math.hypot(m["est_x"], m["est_y"] - d)
        print(
            f"  {d:7.0f}m {m['est_range']:7.0f}m "
            f"{m['cross_range_err_m']:7.1f}m {m['radial_err_m']:7.1f}m "
            f"(pos err {err:.0f}m)"
        )

    print()
    print("=" * 70)
    print("3) Spoof consistency: tracking error must stay under the fusion")
    print("   tolerance (~15 m), or the spoof is detected")
    print("=" * 70)
    print()
    print("   max range for a *consistent* spoof, by tracker quality:")
    for name, sd_deg, sr_db in [
        ("RSSI + directional antenna", 5.0, 2.0),
        ("pseudo-Doppler array", 2.0, 0.5),
        ("SDR array (MUSIC)", 1.0, 0.2),
    ]:
        k = math.hypot(math.radians(sd_deg), RANGE_ERROR_PER_DB * sr_db)
        max_range = FUSION_TOLERANCE_M / k
        print(
            f"     - {name:26s} (sigma_theta={sd_deg:.0f} deg, "
            f"sigma_rssi={sr_db:.1f} dB) -> ~{max_range:4.0f} m"
        )
    print()
    print("   -> with a simple RSSI rig the attacker must be within ~60 m;")
    print("      a pseudo-Doppler array extends that to ~200+ m. Tracking")
    print("      quality is what bounds the spoof, not the jammer power.")


def main():
    ap = argparse.ArgumentParser(description="RF target-tracking demo")
    ap.add_argument("--seed", type=int, default=0)
    ap.parse_args()
    _demo()


if __name__ == "__main__":
    main()
