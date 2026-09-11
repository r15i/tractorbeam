"""Full integrated attack scenario: jam -> track -> spoof -> land next to the attacker.

2-D geometry (north, east in metres): home at the origin, the attacker (false
home) 150 m east of home. The drone's reported GPS position converges to the
attacker, is frozen there, and velocity toward home drives the estimator across
the 20 m landing ring — so the drone lands next to the attacker instead of home.

Reports the quality measures mapped from the Tractor Beam paper (see
scripts/hijack_quality.py): divergence (innovation analog), landing bearing +
error (safe-hijacking-direction analog), FLYAWAY margin (leash analog), and
success / time-to-land.
"""

import csv
import math
import os

from tractorbeam.hijack_quality import quality_metrics
from rf_tracking import AttackerTracker

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")

HOME = (0.0, 0.0)  # north, east
ATTACKER = (0.0, 150.0)  # false home: 150 m east of home
DRONE_START = (500.0, 0.0)  # 500 m north, RTH path passes near home

CRUISE_V_MS = 7.5
SPOOF_VEL_MS = 70.0
ESTIMATOR_TAU_S = 2.1
LANDING_DIST_M = 20.0

T_JAM_S = 5.0
T_SPOOF_S = 10.0
DT = 0.5
T_MAX = 40.0


def lerp(a, b, t):
    return a + (b - a) * t


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    tracker = AttackerTracker(seed=3)

    # GPS position: converges from the flyout to the false home, then freezes
    gps = list(DRONE_START)
    est_dist_home = math.hypot(*DRONE_START)  # estimate, anchored to home
    prev_est_dist = est_dist_home

    rows = []
    samples = []
    landed = False
    spoof_started = False
    t = 0.0
    converge_dist = math.hypot(
        ATTACKER[0] - DRONE_START[0], ATTACKER[1] - DRONE_START[1]
    )
    while t <= T_MAX:
        if t < T_JAM_S:
            phase = "cruising"
        elif t < T_SPOOF_S:
            phase = "returning"
        else:
            phase = "spoofed"

        # GPS motion: cruise at the start, converge toward the false home
        # during RTH, then freeze at the false home once spoofing starts
        if t < T_JAM_S:
            gps = list(DRONE_START)
        elif t < T_SPOOF_S:
            frac = (
                min(1.0, (CRUISE_V_MS * (t - T_JAM_S)) / converge_dist)
                if converge_dist > 0
                else 1.0
            )
            gps[0] = lerp(DRONE_START[0], ATTACKER[0], frac)
            gps[1] = lerp(DRONE_START[1], ATTACKER[1], frac)
        else:
            gps = list(ATTACKER)  # frozen at the false home

        # attacker tracks the drone via the video feed (noisy)
        m = tracker.measure(gps[1], gps[0])  # east=x, north=y
        tracked = (m["est_y"], m["est_x"])

        # estimator drifts toward home while GPS is frozen at the false home
        if t >= T_SPOOF_S:
            if not spoof_started:
                # the estimate snaps to the frozen GPS, then decouples
                est_dist_home = math.hypot(*gps)
                prev_est_dist = est_dist_home
                spoof_started = True
            gps_dist = math.hypot(*gps)
            bias = max(0.0, gps_dist - ESTIMATOR_TAU_S * SPOOF_VEL_MS)
            est_dist_home += (bias - est_dist_home) * (DT / ESTIMATOR_TAU_S)
        else:
            est_dist_home = math.hypot(*gps)

        velocity_to_home = (prev_est_dist - est_dist_home) / DT
        prev_est_dist = est_dist_home

        # estimate position (along the home direction, for the divergence)
        est_dir = 0.0 if est_dist_home < 1e-6 else 1.0
        est_xy = (
            gps[0] * (est_dist_home / (math.hypot(*gps) or 1e-9)),
            gps[1] * (est_dist_home / (math.hypot(*gps) or 1e-9)),
        )

        # only the spoofed phase is where the FLYAWAY check (and thus the
        # margin / divergence quality) actually applies
        if t >= T_SPOOF_S:
            samples.append(
                {
                    "estimate_xy": est_xy,
                    "gps_xy": tuple(gps),
                    "velocity_to_home_ms": velocity_to_home,
                }
            )

        if est_dist_home < LANDING_DIST_M:
            landed = True
            rows.append(
                {
                    "t": round(t, 1),
                    "phase": "LANDING",
                    "gps_north_m": round(gps[0], 1),
                    "gps_east_m": round(gps[1], 1),
                    "tracked_north_m": round(tracked[0], 1),
                    "est_dist_home_m": round(est_dist_home, 1),
                }
            )
            break

        rows.append(
            {
                "t": round(t, 1),
                "phase": phase,
                "gps_north_m": round(gps[0], 1),
                "gps_east_m": round(gps[1], 1),
                "tracked_north_m": round(tracked[0], 1),
                "est_dist_home_m": round(est_dist_home, 1),
            }
        )
        t += DT

    q = quality_metrics(samples, HOME, ATTACKER)
    print(f"[scenario] landed={landed} time_to_land={round(t, 1)} s")
    print(f"[scenario] home={HOME} attacker(false home)={ATTACKER}")
    print(
        f"[scenario] hijack direction = {q['intended_bearing_deg']} deg "
        f"(bearing from home to false home)"
    )
    print(
        f"[scenario] landing bearing = {q['landing_bearing_deg']} deg, "
        f"bearing error = {q['bearing_error_deg']} deg, "
        f"landing error = {q['landing_error_m']} m"
    )
    print(f"[scenario] max divergence (innovation analog) = {q['max_divergence_m']} m")
    print(
        f"[scenario] min FLYAWAY margin (leash analog) = {q['min_flyaway_margin']} "
        f"(>1 = safe)"
    )
    print(
        f"[scenario] -> landed {q['landing_error_m']} m from the attacker, "
        f"{math.hypot(*ATTACKER):.0f} m from home"
    )

    out = os.path.join(RESULTS_DIR, "attack_scenario.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[scenario] wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
