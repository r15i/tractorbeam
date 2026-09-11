"""Quality measures of the hijack, mapped from the Tractor Beam paper.

The paper measured:
  EKF innovation variance   -> our estimate-vs-GPS divergence
  safe-hijacking direction  -> landing bearing (home -> false home)
  leash length              -> FLYAWAY margin (velocityToHome / 1.5 m/s)
  success / fail            -> landed + time-to-land

Positions are (north, east) in metres. Divergence is the positional analog of
the paper's velocity-innovation statistic (Betaflight's estimator trust value
`trustXY` is not exposed by any debug/MSP path, so divergence is the proxy).
"""

import math

FLYAWAY_FLOOR_MS = 1.5  # 0.2 * groundSpeedCmS(750)


def divergence_m(estimate_xy, gps_xy):
    """Distance between the estimator's position and the spoofed GPS position."""
    return math.hypot(estimate_xy[0] - gps_xy[0], estimate_xy[1] - gps_xy[1])


def bearing_deg(from_xy, to_xy):
    """Bearing (0 = north, 90 = east) from one point to another."""
    dn = to_xy[0] - from_xy[0]
    de = to_xy[1] - from_xy[1]
    return math.degrees(math.atan2(de, dn)) % 360.0


def flyaway_margin(velocity_to_home_ms):
    """Headroom above the flyaway floor; >1 means closing fast enough."""
    return velocity_to_home_ms / FLYAWAY_FLOOR_MS


def quality_metrics(samples, home, false_home):
    """Compute the paper-analog quality metrics from a run's samples.

    samples: list of dicts with 'estimate_xy', 'gps_xy', 'velocity_to_home_ms'.
    """
    max_div = max(
        (divergence_m(s["estimate_xy"], s["gps_xy"]) for s in samples), default=0.0
    )
    margins = [flyaway_margin(s["velocity_to_home_ms"]) for s in samples]
    min_margin = min(margins) if margins else float("inf")
    intended_bearing = bearing_deg(home, false_home)
    landing_xy = samples[-1]["gps_xy"] if samples else false_home
    landing_bearing = bearing_deg(home, landing_xy)
    bearing_err = abs((landing_bearing - intended_bearing + 180.0) % 360.0 - 180.0)
    landing_error = math.hypot(
        landing_xy[0] - false_home[0], landing_xy[1] - false_home[1]
    )
    return {
        "max_divergence_m": round(max_div, 1),
        "min_flyaway_margin": round(min_margin, 2),
        "intended_bearing_deg": round(intended_bearing, 1),
        "landing_bearing_deg": round(landing_bearing, 1),
        "bearing_error_deg": round(bearing_err, 1),
        "landing_error_m": round(landing_error, 1),
    }
