"""False-home landing experiments: estimator decoupling.

Tests whether a Betaflight GPS Rescue can be made to complete a landing while
the spoofed GPS is frozen at an attacker-chosen point B (the "false home"),
even though the armed-at home A is locked. The landing gate is
`distanceToHome < 20 m` where `distanceToHome` is the *position estimator's*
norm (DEBUG_RTH slot 6), not the raw GPS distance.

Modes:
  --mode baseline   Avenue 1: rate-matched convergence on the true home A.
                    Control run - must land (DESCENT -> LANDING -> disarm).
  --mode bias       Avenue 2: converge GPS to B, then FREEZE the GPS at B and
                    feed velocity toward home A. Measures whether the estimate
                    drifts below 20 m (land) while the GPS stays at B.

Note: the jamming dead-reckoning avenue was removed - true no-fix jamming is
not reachable with the virtual GPS in this build (gps_virtual.c always reports
a 12-sat fix), so the velocity-bias mode above is the only estimator-decoupling
lever that is testable. See docs/false-home-landing.md for the failure analysis.

Telemetry used:
  - DEBUG_RTH slot 6 = distanceToHomeCm (the estimator's position norm)
  - DEBUG_RTH slot 2/3 = rescue phase / failure
  - trustXY is NOT exposed by any debug/MSP path in this checkout (only
    trustZ is, via DEBUG_ALTITUDE slot 0), so the estimate-vs-GPS divergence
    is reported as |GPS distance| - |estimate distance| instead.

Reuses scripts/sitl_transport.py unchanged; no firmware changes.
"""

import argparse
import csv
import threading
import time

from tractorbeam.sitl_transport import SitlTransport, FdmState, results_csv_path
from tractorbeam.sitl_common import (
    METERS_PER_DEG_LAT,
    meters_to_latlon_delta,
    latlon_dist_m,
    parse_rth_debug_full,
    parse_status_armed,
)

BOOT_GRACE_S = 10.0
FLY_OUT_METERS_NORTH = 500.0
ALT_ASCEND_RATE_MS = 7.5
ALT_CLEAR_MARGIN_S = 18.0
HEADING_PITCH_DEG = 15.0
HEADING_SPEED_MS = 7.5
HEADING_CLEAR_MARGIN_S = 10.0
RESCUE_GROUND_SPEED_MS = 7.5
DESCENT_DISTANCE_M = 20.0  # gpsRescueConfig()->descentDistanceM default
FLYAWAY_MIN_SPEED_MS = 1.5  # 0.2 * groundSpeedCmS(750)
MAX_TEST_S = 140.0


def north_m_of(lat, home_lat):
    return (lat - home_lat) * METERS_PER_DEG_LAT


def latlon_at(north_m, home_lat, home_lon):
    d_lat, d_lon = meters_to_latlon_delta(north_m, 0.0, home_lat)
    return home_lat + d_lat, home_lon + d_lon


class PhysicalDrone:
    """Narrative 'true' position. Independent of the spoofed FdmState feed."""

    def __init__(self, home_lat, home_lon):
        self.home_lat = home_lat
        self.home_lon = home_lon
        self.north_m = 0.0  # relative to home

    def fly_out(self, north_m):
        self.north_m = north_m

    def latlon(self):
        return latlon_at(self.north_m, self.home_lat, self.home_lon)


def main():
    ap = argparse.ArgumentParser(description="False-home landing experiments")
    ap.add_argument("--mode", choices=["baseline", "bias"], required=True)
    ap.add_argument(
        "--bias-north",
        type=float,
        default=150.0,
        help="false home B distance north of true home (m)",
    )
    ap.add_argument(
        "--vel",
        type=float,
        default=7.5,
        help="velocity toward home while GPS is frozen at B (m/s)",
    )
    ap.add_argument(
        "--ramp-s",
        type=float,
        default=10.0,
        help="seconds to ramp the spoofed velocity up to --vel (gentle transition)",
    )
    ap.add_argument("--tag", default="", help="output CSV suffix")
    args = ap.parse_args()

    transport = SitlTransport()
    state = FdmState()
    home_lat, home_lon = state.lat, state.lon
    physical = PhysicalDrone(home_lat, home_lon)
    channels = [1500, 1500, 1000, 1500, 1000, 1000, 1000, 1000]

    lock = threading.Lock()
    shared = {
        "running": True,
        "in_flight_home": False,
        "converging": False,  # phase A: GPS moving toward B (bias) or home (baseline)
        "freezing": False,  # phase B: GPS frozen at B, velocity toward home
        "freeze_north": args.bias_north,
        "freeze_t": 0.0,
        "velocity": [0.0, 0.0, 0.0],  # ENU, authored per phase
        "phase": "IDLE",
        "failure": "HEALTHY",
        "armed": False,
        "rows": [],
    }
    t_start = time.time()

    flyout_lat, flyout_lon = latlon_at(FLY_OUT_METERS_NORTH, home_lat, home_lon)

    def fdm_loop():
        last = time.time()
        while shared["running"]:
            now = time.time()
            dt = now - last
            last = now
            with lock:
                if shared["converging"]:
                    # phase A: move GPS toward the target at 7.5 m/s
                    target_north = (
                        shared["freeze_north"] if args.mode == "bias" else 0.0
                    )
                    t_lat, t_lon = latlon_at(target_north, home_lat, home_lon)
                    dist = latlon_dist_m(state.lat, state.lon, t_lat, t_lon)
                    if dist > 0.5:
                        frac = min(1.0, RESCUE_GROUND_SPEED_MS * dt / dist)
                        state.lat += (t_lat - state.lat) * frac
                        state.lon += (t_lon - state.lon) * frac
                    else:
                        # arrived at B (bias) or home (baseline)
                        shared["converging"] = False
                        if args.mode == "bias":
                            shared["freezing"] = True
                            shared["freeze_t"] = now
                            shared["velocity"] = [
                                0.0,
                                -RESCUE_GROUND_SPEED_MS,
                                0.0,
                            ]  # start gentle
                elif shared["freezing"]:
                    # phase B: GPS stays frozen at B; velocity ramps gently from
                    # the converge speed up to --vel over --ramp-s (no hard step).
                    ramp = min(1.0, (now - shared["freeze_t"]) / args.ramp_s)
                    vel_mag = (
                        RESCUE_GROUND_SPEED_MS
                        + (args.vel - RESCUE_GROUND_SPEED_MS) * ramp
                    )
                    state.velocity_enu = [0.0, -vel_mag, 0.0]
                transport.send_fdm(state, dt=0.01)
            time.sleep(0.01)

    def rc_loop():
        while shared["running"]:
            with lock:
                ch = list(channels)
            transport.send_rc(ch)
            time.sleep(0.02)

    def setup_loop():
        time.sleep(BOOT_GRACE_S)
        with lock:
            channels[4] = 2000  # ARM
        time.sleep(1.0)
        with lock:
            state.lat, state.lon = flyout_lat, flyout_lon
            physical.fly_out(FLY_OUT_METERS_NORTH)
        time.sleep(1.0)
        with lock:
            channels[5] = 2000  # GPS Rescue
            state.pitch_deg = HEADING_PITCH_DEG
            state.set_velocity_towards(bearing_deg=0.0, speed_ms=HEADING_SPEED_MS)
            shared["velocity"] = [0.0, HEADING_SPEED_MS, 0.0]
        t_gate = time.time()
        gate_window = max(ALT_CLEAR_MARGIN_S, HEADING_CLEAR_MARGIN_S)
        while time.time() - t_gate < gate_window and shared["running"]:
            with lock:
                state.alt = 100.0 + ALT_ASCEND_RATE_MS * (time.time() - t_gate)
            time.sleep(0.05)
        with lock:
            shared["in_flight_home"] = True
            # from here, converge toward the target (baseline: home; bias: B)
            state.set_velocity_towards(
                bearing_deg=180.0, speed_ms=RESCUE_GROUND_SPEED_MS
            )
            shared["velocity"] = [0.0, -RESCUE_GROUND_SPEED_MS, 0.0]
            shared["converging"] = True

    def telemetry_loop():
        prev_dist_cm = None
        while shared["running"]:
            transport.send_msp(101)
            _, status = transport.read_msp()
            transport.send_msp(254)
            _, debug = transport.read_msp()
            armed = parse_status_armed(status)
            phase, failure, dist_cm = parse_rth_debug_full(debug)
            with lock:
                shared["armed"] = armed
                if phase:
                    shared["phase"] = phase
                if failure:
                    shared["failure"] = failure
                spoofed_north = north_m_of(state.lat, home_lat)
                phys_north = physical.north_m
                est_dist_m = (dist_cm / 100.0) if dist_cm is not None else None
                # flyaway margin: how fast the estimate is closing on home
                flyaway_margin = None
                if est_dist_m is not None and prev_dist_cm is not None:
                    closing = (prev_dist_cm - dist_cm) / 100.0  # m per sample (~0.5s)
                    flyaway_margin = round(closing / FLYAWAY_MIN_SPEED_MS, 3)
                if dist_cm is not None:
                    prev_dist_cm = dist_cm
                gps_dist_m = abs(spoofed_north)  # distance from home (north axis)
                divergence_m = (
                    round(gps_dist_m - est_dist_m, 1)
                    if est_dist_m is not None
                    else None
                )
                shared["rows"].append(
                    {
                        "t": round(time.time() - t_start, 1),
                        "physical_north_m": round(phys_north, 1),
                        "spoofed_gps_north_m": round(spoofed_north, 1),
                        "estimate_dist_home_m": round(est_dist_m, 1)
                        if est_dist_m is not None
                        else "",
                        "gps_dist_home_m": round(gps_dist_m, 1),
                        "divergence_m": divergence_m
                        if divergence_m is not None
                        else "",
                        "flyaway_margin": flyaway_margin
                        if flyaway_margin is not None
                        else "",
                        "phase": shared["phase"],
                        "failure": shared["failure"],
                        "armed": armed,
                    }
                )
            time.sleep(0.5)

    threading.Thread(target=fdm_loop, daemon=True).start()
    threading.Thread(target=rc_loop, daemon=True).start()
    threading.Thread(target=setup_loop, daemon=True).start()
    threading.Thread(target=telemetry_loop, daemon=True).start()

    print(f"[{args.mode}] waiting for completion (max {MAX_TEST_S:.0f}s)...")
    deadline = time.time() + MAX_TEST_S + BOOT_GRACE_S
    while time.time() < deadline and shared["running"]:
        with lock:
            phase, failure, armed = shared["phase"], shared["failure"], shared["armed"]
        if armed is False and phase not in (
            "IDLE",
            "INITIALIZE",
            "ATTAIN_ALT",
            "PITCH_FORWARD",
        ):
            print(f"[{args.mode}] disarmed -> ending (phase={phase} failure={failure})")
            break
        if failure not in (None, "HEALTHY"):
            print(f"[{args.mode}] failure={failure} -> ending (phase={phase})")
            break
        if phase in ("LANDING", "DO_NOTHING"):
            print(f"[{args.mode}] reached {phase} -> ending")
            break
        time.sleep(0.5)

    shared["running"] = False
    time.sleep(0.3)
    transport.close()

    rows = shared["rows"]
    out = results_csv_path(
        f"false_home_{args.mode}{('_' + args.tag) if args.tag else ''}.csv"
    )
    if rows:
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"[{args.mode}] wrote {len(rows)} rows to {out}")
        # summary (only count estimate distance while actually flying home)
        landed = any(r["phase"] in ("DESCENT", "LANDING") for r in rows)
        fly_rows = [
            r
            for r in rows
            if r["phase"] == "FLY_HOME" and r["estimate_dist_home_m"] != ""
        ]
        min_est = min((r["estimate_dist_home_m"] for r in fly_rows), default=None)
        max_div = max(
            (r["divergence_m"] for r in fly_rows if r["divergence_m"] != ""),
            default=None,
        )
        print(
            f"[{args.mode}] SUMMARY landed={landed} min_estimate_dist_home={min_est}m "
            f"max_divergence={max_div}m final_phase={rows[-1]['phase']} final_failure={rows[-1]['failure']}"
        )
    else:
        print(f"[{args.mode}] no rows recorded")


if __name__ == "__main__":
    main()
