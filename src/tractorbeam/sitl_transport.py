"""Shared transport layer for talking to Betaflight SITL over the network
instead of physical serial hardware (FTDI/USB).

Endpoints (from betaflight/src/platform/SIMULATOR/{sitl.c,target/SITL/target.h}
and src/main/drivers/serial_tcp.c), also documented in docs/setup/sitl-setup.md:
  - UDP 9003 (PORT_STATE):    fdm_packet in       - fake GPS/IMU "physics" state
  - UDP 9004 (PORT_RC):       rc_packet  in        - RC channels
  - UDP 9001 (PORT_PWM_RAW):  servo_packet_raw out - raw motor PWM (1000-2000),
                              SITL's "RealFlight bridge" feed, emitted every
                              time it processes an FDM packet
  - TCP 5761 (BASE_PORT+1 = UART1): MSP, same $M< / $M> framing the project's
                              earlier physical-hardware HITL tooling used over
                              pyserial (since removed - this project is now
                              software-only, see docs/project/architecture.md)

SITL only serves ONE live MSP TCP client at a time - a second connection is
accepted at the socket level but every read on it returns EOF (confirmed by
opening two connections and observing the second's recv() return b''
immediately). Motor readback therefore goes over the UDP PWM-raw broadcast
instead of MSP_MOTOR, so a closed-loop motor-state consumer never has to
compete with a concurrent MSP telemetry reader for the single MSP slot.
"""

import math
import os
import socket
import struct

SIM_IP = "127.0.0.1"
FDM_PORT = 9003
RC_PORT = 9004
PWM_RAW_PORT = 9001
MSP_PORT = 5761

# Where experiment scripts write their result CSVs - `make clean` (Makefile,
# this directory) empties this instead of leaving runs scattered in /tmp.
RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "results",
)


def results_csv_path(filename):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    return os.path.join(RESULTS_DIR, filename)


GRAVITY = 9.80665  # m/s/s, matches ACC_SCALE's reference in sitl.c

# fdm_packet (target.h): all little-endian doubles -
#   timestamp, angular_velocity_rpy[3], linear_acceleration_xyz[3],
#   orientation_quat[4] (w,x,y,z), velocity_xyz[3] (ENU), position_xyz[3]
#   (lon, lat, alt - USE_VIRTUAL_GPS mode), pressure
FDM_STRUCT = struct.Struct("<18d")

RC_MAX_CHANNELS = 16  # SIMULATOR_MAX_RC_CHANNELS in target.h
# rc_packet (target.h): timestamp (double) + channels[16] (uint16)
RC_STRUCT = struct.Struct("<d16H")

# servo_packet_raw (target.h): uint16 motorCount, then float pwm_output_raw[16]
# (4-byte aligned, so 2 bytes padding after the uint16) -> 4 + 16*4 = 68 bytes.
# Confirmed by listening on 9001: 68-byte packets, motorCount=4, values 1000.0
# at idle (same 1000-2000 range as MSP_MOTOR).
PWM_RAW_STRUCT = struct.Struct("<H2x16f")

# This build (`make TARGET=SITL`, no config.h override) uses target.h's default
# ENABLE_GAZEBO_BRIDGE=1 - confirmed by reading src/config/configs/BTFL/*/config.h,
# none of which apply to the plain SITL target. Two consequences for senders:
#
# 1. sitl.c's updateState() reconstructs attitude from a conjugated quaternion
#    (see the ENABLE_GAZEBO_BRIDGE branch there). Solving attQ(pktQ) = identity
#    for pktQ gives this constant - send it to make Betaflight see a level
#    attitude with zero angular rate:
LEVEL_ORIENTATION_QUAT = (math.sqrt(0.5), 0.0, 0.0, math.sqrt(0.5))  # (w, x, y, z)


def pitched_orientation_quat(pitch_deg):
    """Raw quat to send for a pure pitch (nose up/down, yaw=roll=0) attitude
    of pitch_deg degrees. Solves the same ENABLE_GAZEBO_BRIDGE conjugation as
    LEVEL_ORIENTATION_QUAT (that's this function at pitch_deg=0), composed
    with the standard roll=0/yaw=0 Euler->quaternion reduction:
        target attQ (w,x,y,z) = (cos(h), 0, sin(h), 0), h = radians(pitch_deg)/2

    On its own this is NOT enough to make Betaflight's own attitude.values.pitch
    read this angle: imuUpdateAttitude() always runs the real Mahony filter
    (imuMahonyAHRSupdate(), imu.c) from gyro+accelerometer, every scheduler
    tick - it does not trust an injected quaternion. Confirmed directly: with
    only this quaternion sent (accelerometer left level), MSP_ATTITUDE still
    read pitch=0. pitch_tilted_accel() below derives the matching accelerometer
    reading the same filter actually uses; FdmState applies both together.

    Positive pitch_deg represents "pitched forward to fly toward the target" -
    matches how imuCalcGroundspeedGain()'s pitchSuppression term (zero at
    level, needed for GPS-heading confidence) reads attitude.values.pitch.
    """
    half = math.radians(pitch_deg) / 2.0
    c, s = math.cos(half), math.sin(half)
    k = math.sqrt(0.5)
    return (c * k, s * k, -s * k, c * k)


def pitch_tilted_accel(pitch_deg):
    """linear_acceleration_xyz for a stationary body pitched pitch_deg forward
    (matching pitched_orientation_quat's convention) - what a real
    accelerometer reads there (just gravity, no linear acceleration).

    Derived from, and numerically verified against, this exact codebase's own
    Mahony correction term (imuMahonyAHRSupdate(), imu.c): it drives the
    attitude estimate's error from the cross product between the measured
    (accelerometer) vector and rMat.m[NWU_U] - "earth-up expressed in the
    body frame" - so the accelerometer we feed must equal that row for the
    filter to converge to pitch_deg. For attQ = (cos(h),0,sin(h),0):
        rMat.m[NWU_U] = (-sin(2h), 0, cos(2h)) = (-sin(theta), 0, cos(theta))
    (verified against the literal rMat.m[NWU_U][X/Y/Z] formula in imu.c, not
    just generic rotation math - see design.md Decision 1 addendum). Translated
    through sitl.c's negate-before-send convention (matching the existing
    level-case baseline of linear_acceleration_xyz = [0, 0, -GRAVITY]):
    """
    theta = math.radians(pitch_deg)
    return [GRAVITY * math.sin(theta), 0.0, -GRAVITY * math.cos(theta)]


# 2. updateState() latches the *first* packet's lat/lon as its internal origin
#    and mirrors every later packet around it: correctedLatLon = 2*origin - raw.
#    FdmState pre-mirrors so callers can just set .lat/.lon to the position they
#    want Betaflight to see. This only holds if this transport sends the first
#    FDM packet SITL receives since it was launched - restart SITL, don't just
#    reconnect, when starting a fresh experiment (see docs/setup/sitl-setup.md).


class FdmState:
    """Mutable fake-physics state sent to SITL's FDM UDP input.

    Starts as a stationary, level hover at (lat, lon, alt). Callers mutate
    .lat/.lon/.alt/.velocity_enu directly for GPS spoofing; angular_velocity_rpy
    and linear_acceleration_xyz are exposed for future IMU-injection experiments
    but default to "stationary, level" (gravity on the vertical axis only).
    """

    def __init__(self, lat=37.7749, lon=-122.4194, alt=100.0):
        self._origin_lat = lat
        self._origin_lon = lon
        self.lat = lat
        self.lon = lon
        self.alt = alt
        self.velocity_enu = [0.0, 0.0, 0.0]  # East, North, Up (m/s)
        self.angular_velocity_rpy = [0.0, 0.0, 0.0]  # rad/s
        # NED-ish body accel as sitl.c expects it (it negates + scales this
        # directly into the accelerometer): -Z holds the "1G, level" baseline.
        self.linear_acceleration_xyz = [0.0, 0.0, -GRAVITY]
        self.pressure = 101325.0  # only used when ENABLE_GAZEBO_BRIDGE is 0
        self.timestamp = 0.0
        # Degrees, nose-forward positive - see pitched_orientation_quat().
        # Needed (alongside a matching velocity_enu, set_velocity_towards())
        # to build Betaflight's GPS-heading confidence; level (0) is fine for
        # anything that doesn't need RESCUE_ROTATE/FLY_HOME. Nonzero pitch_deg
        # makes pack() override linear_acceleration_xyz with pitch_tilted_accel()
        # - callers doing their own closed-loop accel injection never set
        # this, so their direct linear_acceleration_xyz writes are untouched.
        self.pitch_deg = 0.0

    def set_velocity_towards(self, bearing_deg, speed_ms):
        """Set velocity_enu for a given compass bearing (0=North, 90=East)
        and speed. Keep bearing near 0 (North) when also using pitch_deg !=0
        - imuCalcCourseErr() wants the GPS course-over-ground to roughly match
        the fixed heading pitched_orientation_quat() implies (yaw=0, i.e.
        facing North), or heading confidence won't build regardless of speed."""
        rad = math.radians(bearing_deg)
        self.velocity_enu[0] = speed_ms * math.sin(rad)  # East
        self.velocity_enu[1] = speed_ms * math.cos(rad)  # North

    def pack(self, dt=0.01):
        """Advance time by dt and return the packed fdm_packet bytes."""
        self.timestamp += dt
        send_lat = 2.0 * self._origin_lat - self.lat
        send_lon = 2.0 * self._origin_lon - self.lon
        if self.pitch_deg:
            qw, qx, qy, qz = pitched_orientation_quat(self.pitch_deg)
            accel = pitch_tilted_accel(self.pitch_deg)
        else:
            qw, qx, qy, qz = LEVEL_ORIENTATION_QUAT
            accel = self.linear_acceleration_xyz
        return FDM_STRUCT.pack(
            self.timestamp,
            *self.angular_velocity_rpy,
            *accel,
            qw,
            qx,
            qy,
            qz,
            *self.velocity_enu,
            send_lon,
            send_lat,
            self.alt,
            self.pressure,
        )


class SitlTransport:
    """Owns the sockets an experiment script needs to drive Betaflight SITL.

    The MSP TCP connection is opened lazily, on the first send_msp()/read_msp()
    call, same as the PWM-raw socket - a script that never touches MSP never
    occupies SITL's single MSP client slot. See module docstring for why that
    slot is scarce.
    """

    def __init__(
        self,
        ip=SIM_IP,
        fdm_port=FDM_PORT,
        rc_port=RC_PORT,
        pwm_raw_port=PWM_RAW_PORT,
        msp_port=MSP_PORT,
    ):
        self._fdm_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._fdm_addr = (ip, fdm_port)

        self._rc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._rc_addr = (ip, rc_port)

        self._msp_sock = None
        self._msp_ip = ip
        self._msp_port = msp_port

        self._pwm_sock = None
        self._pwm_ip = ip
        self._pwm_port = pwm_raw_port

    def _ensure_msp(self):
        if self._msp_sock is None:
            self._msp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._msp_sock.settimeout(2.0)
            self._msp_sock.connect((self._msp_ip, self._msp_port))

    def send_fdm(self, fdm_state, dt=0.01):
        """Send one fdm_packet built from an FdmState."""
        self._fdm_sock.sendto(fdm_state.pack(dt=dt), self._fdm_addr)

    def send_rc(self, channels, timestamp=0.0):
        """Send RC channels (list of uint16, AETR1234... order) via the native
        UDP RC input. Padded/truncated to RC_MAX_CHANNELS; missing channels
        are filled with 1500 (neutral)."""
        padded = list(channels)[:RC_MAX_CHANNELS]
        padded += [1500] * (RC_MAX_CHANNELS - len(padded))
        self._rc_sock.sendto(RC_STRUCT.pack(timestamp, *padded), self._rc_addr)

    def get_motors(self, timeout=0.5):
        """Read the most recent raw motor PWM values (1000-2000) from SITL's
        UDP PWM-raw broadcast (port 9001). Only meaningful once this transport
        (or something else) is actively sending FDM packets - SITL only emits
        a PWM update when it processes one. Binds lazily so a transport that
        never calls this doesn't hold the port."""
        if self._pwm_sock is None:
            self._pwm_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._pwm_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._pwm_sock.bind((self._pwm_ip, self._pwm_port))
        self._pwm_sock.settimeout(timeout)
        try:
            data, _ = self._pwm_sock.recvfrom(200)
        except socket.timeout:
            return None
        motor_count = PWM_RAW_STRUCT.unpack(data)[0]
        motors = PWM_RAW_STRUCT.unpack(data)[1:]
        return tuple(int(m) for m in motors[:motor_count])

    # --- MSP over TCP: standard $M< / $M> framing, just over a socket instead
    # of pyserial.Serial. Only one process should hold this connection at a
    # time - see module docstring. ---

    def send_msp(self, code, payload=b""):
        self._ensure_msp()
        size = len(payload)
        checksum = size ^ code
        for b in payload:
            checksum ^= b
        msg = b"$M<" + bytes([size, code]) + bytes(payload) + bytes([checksum])
        self._msp_sock.sendall(msg)

    def _recv_exact(self, n):
        """Read exactly n bytes, or return None on timeout/EOF (peer closed -
        e.g. this connection got superseded by another MSP client)."""
        buf = b""
        while len(buf) < n:
            chunk = self._msp_sock.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def read_msp(self, timeout=0.5):
        """Read and decode one MSP response. Returns (code, data) or (None, None)."""
        self._ensure_msp()
        self._msp_sock.settimeout(timeout)
        try:
            while True:
                b = self._recv_exact(1)
                if b is None:
                    return None, None
                if b != b"$":
                    continue
                b = self._recv_exact(1)
                if b != b"M":
                    if b is None:
                        return None, None
                    continue
                direction = self._recv_exact(1)
                if direction is None:
                    return None, None
                if direction == b">":
                    break
                if direction == b"!":
                    return None, None

            header = self._recv_exact(2)
            if header is None:
                return None, None
            size, code = header[0], header[1]
            data = self._recv_exact(size)
            if data is None:
                return None, None
            checksum = size ^ code
            for b in data:
                checksum ^= b
            rx_checksum = self._recv_exact(1)
            if rx_checksum is None:
                return None, None
            if checksum == rx_checksum[0]:
                return code, data
            return None, None
        except socket.timeout:
            return None, None

    def close(self):
        self._fdm_sock.close()
        self._rc_sock.close()
        if self._msp_sock is not None:
            self._msp_sock.close()
        if self._pwm_sock is not None:
            self._pwm_sock.close()


def _smoke_check():
    """Manual connectivity check against an already-running SITL instance:
    connect all three sockets, send a few baseline FDM/RC packets, and read
    MSP_STATUS (101) back. Run with `python3 sitl_transport.py` while SITL is
    running - see docs/setup/sitl-setup.md for how to launch it."""
    import time

    print(
        f"Connecting to SITL at {SIM_IP} (FDM :{FDM_PORT}, RC :{RC_PORT}, MSP :{MSP_PORT})..."
    )
    t = SitlTransport()
    print("Connected.")

    state = FdmState()
    for _ in range(10):
        t.send_fdm(state, dt=0.01)
        t.send_rc([1500, 1500, 1000, 1500, 1000, 1000, 1000, 1000])
        time.sleep(0.01)
    print("Sent 10 baseline FDM/RC packets.")

    MSP_STATUS = 101
    t.send_msp(MSP_STATUS)
    code, data = t.read_msp()
    if code == MSP_STATUS and data:
        print(f"MSP_STATUS OK: code={code} bytes={len(data)}")
    else:
        print(f"MSP_STATUS FAILED: code={code} data={data}")

    t.close()


if __name__ == "__main__":
    _smoke_check()
