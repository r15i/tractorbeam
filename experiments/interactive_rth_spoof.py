"""Interactive Tractor Beam spoofing console.

Drives Betaflight SITL through a GPS Rescue (RTH) and lets a human operator
pick a spoof target on a live matplotlib map. The reported (spoofed) position
converges on the chosen target at the firmware's own ground speed while the
"true" armed-at home stays fixed, demonstrating the safe-hijack deviation live.

GUI path (default): click or drag on the map to set the target; close the
window to finish and write the CSV.

Headless path (--target east,north): set the target programmatically and run a
fixed duration - used for automated verification without a display.

Endpoints/config: same as the other experiment scripts (see docs/setup/sitl-setup.md).
Reuses scripts/sitl_transport.py unchanged.
"""

import argparse
import csv
import threading
import time

from tractorbeam.sitl_transport import SitlTransport, FdmState, results_csv_path
from tractorbeam.sitl_common import (
    meters_to_latlon_delta,
    latlon_dist_m,
    latlon_to_enu,
    enu_to_latlon,
    parse_rth_debug,
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
HEADLESS_RUN_S = 40.0


def _step_toward_target(state, target_enu, home_lat, home_lon, step_m):
    """Move the reported position toward (east_m, north_m) by at most step_m."""
    t_lat, t_lon = enu_to_latlon(target_enu[0], target_enu[1], home_lat, home_lon)
    dist = latlon_dist_m(state.lat, state.lon, t_lat, t_lon)
    if dist <= 1e-3:
        return
    frac = min(1.0, step_m / dist)
    state.lat += (t_lat - state.lat) * frac
    state.lon += (t_lon - state.lon) * frac


def _write_csv(rows):
    if not rows:
        print("No telemetry rows recorded.")
        return
    out = results_csv_path("interactive_rth_spoof.csv")
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {out}")


def _run_headless(shared, duration):
    print("headless mode: waiting for FLY_HOME (gate clearing)...")
    while shared["running"] and not shared["in_flight_home"]:
        time.sleep(0.2)
    if not shared["running"]:
        return
    print(f"FLY_HOME reached; spoofing toward {shared['target']} for {duration:.0f}s")
    deadline = time.time() + duration
    while shared["running"] and time.time() < deadline:
        time.sleep(0.5)
    print("headless run complete")


def _run_gui(shared, lock, state, home_lat, home_lon):
    import matplotlib

    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_title("Interactive Tractor Beam spoofing - click/drag to set target")
    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    ax.set_aspect("equal")
    ax.axhline(0, color="0.8", lw=0.5)
    ax.axvline(0, color="0.8", lw=0.5)

    (home_marker,) = ax.plot([0], [0], "s", color="green", ms=10, label="true home")
    (reported_marker,) = ax.plot(
        [], [], "o", color="red", ms=8, label="reported (spoofed)"
    )
    (target_marker,) = ax.plot([], [], "x", color="blue", ms=12, mew=3, label="target")
    (trail_line,) = ax.plot([], [], "-", color="red", lw=1, alpha=0.6)
    status_text = ax.text(0.02, 0.98, "", transform=ax.transAxes, va="top", fontsize=9)

    ax.set_xlim(-400, 400)
    ax.set_ylim(-100, 700)
    ax.legend(loc="lower right")

    trail_x, trail_y = [], []

    def on_click(event):
        if event.inaxes is not ax or event.xdata is None or event.ydata is None:
            return
        with lock:
            shared["target"] = (float(event.xdata), float(event.ydata))

    def on_drag(event):
        if (
            event.button == 1
            and event.inaxes is ax
            and event.xdata is not None
            and event.ydata is not None
        ):
            with lock:
                shared["target"] = (float(event.xdata), float(event.ydata))

    fig.canvas.mpl_connect("button_press_event", on_click)
    fig.canvas.mpl_connect("motion_notify_event", on_drag)

    def update(_frame):
        with lock:
            e, n = latlon_to_enu(state.lat, state.lon, home_lat, home_lon)
            tgt = shared["target"]
            phase = shared["phase"]
            failure = shared["failure"]
            armed = shared["armed"]
        reported_marker.set_data([e], [n])
        trail_x.append(e)
        trail_y.append(n)
        if len(trail_x) > 400:
            trail_x.pop(0)
            trail_y.pop(0)
        trail_line.set_data(trail_x, trail_y)
        if tgt is not None:
            target_marker.set_data([tgt[0]], [tgt[1]])
        status_text.set_text(f"phase={phase} failure={failure} armed={armed}")
        return reported_marker, target_marker, trail_line, status_text

    FuncAnimation(fig, update, interval=200, blit=False, cache_frame_data=False)
    print(
        "Opening map - click or drag to set the spoof target; close the window to finish."
    )
    plt.show()


def main():
    parser = argparse.ArgumentParser(
        description="Interactive GPS spoofing during Betaflight GPS Rescue (RTH)."
    )
    parser.add_argument(
        "--target", help="headless spoof target as 'east,north' meters relative to home"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="run without the GUI (for automated tests)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=HEADLESS_RUN_S,
        help="headless spoof duration in seconds after FLY_HOME",
    )
    args = parser.parse_args()

    headless = args.headless or args.target is not None
    target_enu = None
    if args.target:
        try:
            e_str, n_str = args.target.split(",")
            target_enu = (float(e_str), float(n_str))
        except ValueError:
            parser.error("--target must be 'east,north' e.g. '150,0'")

    transport = SitlTransport()
    state = FdmState()
    home_lat, home_lon = state.lat, state.lon
    channels = [1500, 1500, 1000, 1500, 1000, 1000, 1000, 1000]

    lock = threading.Lock()
    shared = {
        "running": True,
        "in_flight_home": False,
        "target": target_enu,
        "phase": "IDLE",
        "failure": "HEALTHY",
        "armed": False,
        "rows": [],
    }
    t_start = time.time()

    d_lat, d_lon = meters_to_latlon_delta(FLY_OUT_METERS_NORTH, 0.0, home_lat)
    flyout_lat, flyout_lon = home_lat + d_lat, home_lon + d_lon

    def fdm_loop():
        last = time.time()
        while shared["running"]:
            now = time.time()
            dt = now - last
            last = now
            with lock:
                if shared["in_flight_home"] and shared["target"] is not None:
                    _step_toward_target(
                        state,
                        shared["target"],
                        home_lat,
                        home_lon,
                        RESCUE_GROUND_SPEED_MS * dt,
                    )
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
        time.sleep(1.0)
        with lock:
            channels[5] = 2000  # AUX2 high -> GPS Rescue
            state.pitch_deg = HEADING_PITCH_DEG
            state.set_velocity_towards(bearing_deg=0.0, speed_ms=HEADING_SPEED_MS)
        t_gate = time.time()
        gate_window = max(ALT_CLEAR_MARGIN_S, HEADING_CLEAR_MARGIN_S)
        while time.time() - t_gate < gate_window and shared["running"]:
            with lock:
                state.alt = 100.0 + ALT_ASCEND_RATE_MS * (time.time() - t_gate)
            time.sleep(0.05)
        with lock:
            shared["in_flight_home"] = True

    def telemetry_loop():
        while shared["running"]:
            transport.send_msp(101)
            _, status = transport.read_msp()
            transport.send_msp(254)
            _, debug = transport.read_msp()
            armed = parse_status_armed(status)
            phase, failure = parse_rth_debug(debug)
            with lock:
                shared["armed"] = armed
                if phase:
                    shared["phase"] = phase
                if failure:
                    shared["failure"] = failure
                e, n = latlon_to_enu(state.lat, state.lon, home_lat, home_lon)
                tgt = shared["target"]
                shared["rows"].append(
                    {
                        "t": round(time.time() - t_start, 1),
                        "true_east_m": 0.0,
                        "true_north_m": 0.0,
                        "reported_east_m": round(e, 1),
                        "reported_north_m": round(n, 1),
                        "target_east_m": round(tgt[0], 1) if tgt else "",
                        "target_north_m": round(tgt[1], 1) if tgt else "",
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

    if headless:
        _run_headless(shared, args.duration)
    else:
        _run_gui(shared, lock, state, home_lat, home_lon)

    shared["running"] = False
    time.sleep(0.3)
    transport.close()
    _write_csv(shared["rows"])


if __name__ == "__main__":
    main()
