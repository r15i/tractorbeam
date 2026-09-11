"""Isolated test of Betaflight GPS Rescue's RESCUE_ATTAIN_ALT anomaly check
(gps_rescue_multirotor.c: performSanityChecks()), reframed around the actual
research question: does the firmware ACCEPT a spoofed sensor reading (follow
it, no rejection) or REJECT it (trip a failure flag / disarm) depending on
whether the fake reading keeps pace with what the firmware itself expects?

The check being tested (case RESCUE_ATTAIN_ALT in performSanityChecks()):
    measuredAltitudeChange = getAltitudeCm() - prevAltitudeCm   (per 1Hz tick)
    targetAltitudeChange   = targetAltitudeCm - prevTargetAltitudeCm
    error = measuredAltitudeChange / targetAltitudeChange   (when target moved)
    secondsFailing += error > 0.5 ? -1 : 1
    secondsFailing >= 10  ->  RESCUE_STALLED

This is a *progress-rate* check, not a plausibility/glitch check (Betaflight
has no raw-GPS glitch detector at all - confirmed by grep across src/main/io/
gps*.c). It only cares whether the fed altitude is climbing at >=50% of the
rate Betaflight's own autopilot is internally commanding - not whether that
climb is physically believable. Three synthetic profiles let us classify
accept-vs-reject as a function of that one rate ratio:

  --profile static    fed altitude never changes            (ratio ~= 0)
  --profile partial   fed altitude climbs at 30% of the FC's own ascend rate
  --profile adaptive  fed altitude climbs at 100%+ of the FC's own ascend rate

Isolated on purpose: no horizontal fly-out, no separate GPS spoof - one
variable (vertical rate) at a time, avoiding the cross-talk that caused an
unexplained early disarm in an earlier combined attempt.

Usage (SITL must already be running with sitl_safety.txt applied):
    python3 sanity_check_experiment.py --profile static
    python3 sanity_check_experiment.py --profile partial
    python3 sanity_check_experiment.py --profile adaptive
"""

import argparse
import csv
import threading
import time

from tractorbeam.sitl_transport import SitlTransport, FdmState, results_csv_path
from tractorbeam.sitl_common import (
    METERS_PER_DEG_LAT,
    parse_rth_debug,
    parse_status_armed,
)

BOOT_GRACE_S = 10.0
ASCEND_RATE_MS = 7.5  # gps_rescue_ascend_rate default (750 cm/s)
TEST_DURATION_S = 30.0
POLL_HZ = 1.0
# GPS_RESCUE_ACCEPT_RADIUS is 20cm - RESCUE_INITIALIZE treats "already inside
# that radius" as "arrived, shut down now" (rescueDisarmNow()), regardless of
# the altitude test we're actually trying to isolate. A small, fixed offset
# (held constant - not part of what's under test) avoids that short-circuit.
OFFSET_METERS_NORTH = 50.0

PROFILE_RATE_FRACTION = {
    "static": 0.0,
    "slow": 0.08,
    "partial": 0.3,
    "adaptive": 1.1,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=list(PROFILE_RATE_FRACTION), required=True)
    parser.add_argument(
        "--tag",
        default="",
        help="suffix for the output CSV, so repeat runs "
        "(for distribution sampling) don't overwrite each other",
    )
    args = parser.parse_args()
    rate_fraction = PROFILE_RATE_FRACTION[args.profile]
    climb_rate = ASCEND_RATE_MS * rate_fraction

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

    print(f"[{args.profile}] waiting {BOOT_GRACE_S:.0f}s boot grace...")
    time.sleep(BOOT_GRACE_S)

    channels[4] = 2000  # ARM
    time.sleep(1.0)

    d_lat = OFFSET_METERS_NORTH / METERS_PER_DEG_LAT
    state.lat += d_lat  # fixed, held constant - not part of what's under test
    time.sleep(1.0)

    channels[5] = (
        2000  # AUX2 high -> GPS Rescue (triggers RESCUE_INITIALIZE -> ATTAIN_ALT)
    )
    alt_start = state.alt
    t0 = time.time()
    print(
        f"[{args.profile}] rescue triggered, feeding altitude at "
        f"{climb_rate:.2f} m/s ({rate_fraction * 100:.0f}% of FC's {ASCEND_RATE_MS} m/s ascend rate)"
    )

    rows = []
    outcome = "TIMEOUT_HEALTHY"
    trigger_t = None
    while True:
        elapsed = time.time() - t0
        state.alt = alt_start + climb_rate * elapsed

        if elapsed > TEST_DURATION_S:
            break

        time.sleep(1.0 / POLL_HZ)

        transport.send_msp(101)
        _, status_data = transport.read_msp()
        transport.send_msp(254)
        _, debug_data = transport.read_msp()

        armed = parse_status_armed(status_data)
        phase, failure = parse_rth_debug(debug_data)

        row = {
            "t": round(elapsed, 1),
            "armed": armed,
            "alt_fed_m": round(state.alt, 2),
            "phase": phase,
            "failure": failure,
        }
        rows.append(row)
        print(
            f"[{args.profile}] t={row['t']:5.1f}s armed={armed} alt={row['alt_fed_m']:6.2f}m "
            f"phase={phase} failure={failure}"
        )

        if armed is False:
            outcome, trigger_t = "REJECTED_DISARMED", row["t"]
            break
        if failure not in (None, "HEALTHY"):
            outcome, trigger_t = f"REJECTED_{failure}", row["t"]
            break
        if phase not in (None, "IDLE", "ATTAIN_ALT"):
            outcome, trigger_t = f"ACCEPTED_ADVANCED_TO_{phase}", row["t"]
            break

    print(
        f"[{args.profile}] RESULT: {outcome}"
        + (f" at t={trigger_t}s" if trigger_t else " (ran full test window)")
    )

    suffix = f"_{args.tag}" if args.tag else ""
    out_path = results_csv_path(f"altitude_gate_{args.profile}{suffix}.csv")
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["t", "armed", "alt_fed_m", "phase", "failure"]
        )
        writer.writeheader()
        writer.writerows(rows)
        writer.writerow(
            {
                "t": "RESULT",
                "armed": "",
                "alt_fed_m": "",
                "phase": outcome,
                "failure": trigger_t,
            }
        )
    print(f"[{args.profile}] wrote {len(rows)} rows to {out_path}")

    running = False
    time.sleep(0.3)
    transport.close()


if __name__ == "__main__":
    main()
