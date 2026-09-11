"""Probe (task 2.2/2.3, test-horizontal-gps-spoofing change): how long does it
take Betaflight's GPS-heading confidence (gpsHeadingConfidence, imu.c) to
cross the 1.5 threshold for a given (pitch_deg, speed_ms) pair, and does it
clear before RESCUE_PITCH_FORWARD's 15s give-up timer?

Reads DEBUG_ATTITUDE slot 1 (gpsHeadingConfidence*100) and slot 4
(canUseGPSHeading inverted: 0=usable, 1=not yet) - requires
`set debug_mode = ATTITUDE` on the SITL instance (see
/tmp/sitl_safety_attitude_debug.txt), NOT debug_mode=RTH, since DEBUG_SET()
only writes to the shared debug[] array for whichever debug_mode is active.
Rescue-phase visibility isn't needed here: the altitude-clearing timing is
already known from sanity_check_experiment.py's "adaptive" profile.

Usage (SITL running with the ATTITUDE debug config applied):
    python3 heading_confidence_probe.py --pitch 15 --speed 7.5
"""

import argparse
import struct
import threading
import time

from tractorbeam.sitl_transport import SitlTransport, FdmState

BOOT_GRACE_S = 10.0
ALT_ASCEND_RATE_MS = 7.5  # confirmed "adaptive" profile from sanity_check_experiment.py
OFFSET_METERS_NORTH = 50.0
METERS_PER_DEG_LAT = 111320.0
PROBE_DURATION_S = (
    25.0  # > RESCUE_PITCH_FORWARD's 15s giveup, so we see it either clear or time out
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pitch", type=float, required=True, help="nose-forward pitch, degrees"
    )
    parser.add_argument(
        "--speed", type=float, required=True, help="forward (North) speed, m/s"
    )
    parser.add_argument(
        "--immediate",
        action="store_true",
        help="skip the altitude-clearing wait; feed pitch/velocity from t=0 "
        "(isolates the heading-confidence mechanism on its own)",
    )
    args = parser.parse_args()
    delay = 0.0 if args.immediate else 15.0

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

    print(f"waiting {BOOT_GRACE_S:.0f}s boot grace...")
    time.sleep(BOOT_GRACE_S)

    channels[4] = 2000  # ARM
    time.sleep(1.0)

    d_lat = OFFSET_METERS_NORTH / METERS_PER_DEG_LAT
    state.lat += (
        d_lat  # clear GPS_RESCUE_ACCEPT_RADIUS, same as sanity_check_experiment.py
    )
    time.sleep(1.0)

    channels[5] = 2000  # AUX2 high -> GPS Rescue
    t_trigger = time.time()
    seen_heading_init = False
    print(
        f"rescue triggered; clearing ATTAIN_ALT at {ALT_ASCEND_RATE_MS} m/s, "
        f"then holding pitch={args.pitch} deg, forward speed={args.speed} m/s"
    )

    while True:
        elapsed = time.time() - t_trigger
        if elapsed > delay:
            state.pitch_deg = args.pitch
            state.set_velocity_towards(
                bearing_deg=0.0, speed_ms=args.speed
            )  # North, matches heading=0
        else:
            state.alt = 100.0 + ALT_ASCEND_RATE_MS * elapsed

        if elapsed > delay + PROBE_DURATION_S:
            print("probe window elapsed, stopping")
            break

        time.sleep(0.1)

        if int(elapsed * 10) % 5 == 0:  # 2Hz
            transport.send_msp(254)
            _, data = transport.read_msp()
            if data and len(data) >= 16:  # DEBUG16_VALUE_COUNT=8 slots, 2 bytes each
                debug = struct.unpack_from("<8h", data, 0)
                confidence = debug[1] / 100.0
                course_err = (
                    debug[3] / 100.0
                )  # imuCourseError, normalized 0 (aligned) - 1 (>=90deg off)
                # debug[4] is 0 in two distinct states: uninitialized (BSS-zero,
                # before updateGpsHeadingUsable() has ever run) and genuinely
                # "canUseGPSHeading" latched. Only trust 0 as "usable" after we
                # have seen the intermediate 1 ("not yet usable") that
                # updateGpsHeadingUsable() writes while confidence is < 1.5.
                if debug[4] == 1:
                    seen_heading_init = True
                usable = (debug[4] == 0) and seen_heading_init
                print(
                    f"t={elapsed:6.1f}s pitch={state.pitch_deg:5.1f} "
                    f"vel_enu={[round(v, 2) for v in state.velocity_enu]} "
                    f"gpsHeadingConfidence={confidence:.2f} courseErr={course_err:.2f} usable={usable}"
                )
                if usable:
                    # gpsHeadingConfidence resets to 0 the instant canUseGPSHeading
                    # latches true (imu.c: "re-evaluate from scratch on arming") -
                    # usable is the authoritative signal, not catching confidence
                    # >=1.5 in a sample (easy to miss between poll ticks).
                    print(
                        f"CLEARED at t={elapsed:.1f}s (pitch={args.pitch}, speed={args.speed})"
                    )
                    break

    running = False
    time.sleep(0.3)
    transport.close()


if __name__ == "__main__":
    main()
