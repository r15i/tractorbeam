"""Shared helpers for the SITL experiment scripts.

Consolidates the geo conversions, rescue phase/failure name tables, and the
MSP debug/status parsers that were previously copy-pasted across the experiment
scripts. Import from here instead of re-defining them locally.
"""

import math
import struct

METERS_PER_DEG_LAT = 111320.0

RESCUE_PHASE_NAMES = [
    "IDLE",
    "INITIALIZE",
    "ATTAIN_ALT",
    "PITCH_FORWARD",
    "ROTATE",
    "FLY_HOME",
    "DESCENT",
    "LANDING",
    "EMERG_DESCENT",
    "DO_NOTHING",
]
RESCUE_FAILURE_NAMES = [
    "HEALTHY",
    "FLYAWAY",
    "GPSLOST",
    "LOWSATS",
    "CRASHFLIP_DETECTED",
    "STALLED",
    "TOO_CLOSE",
    "NO_HOME_POINT",
    "NO_ALTITUDE",
    "NO_HEADING",
]


def meters_to_latlon_delta(d_north_m, d_east_m, at_lat_deg):
    d_lat = d_north_m / METERS_PER_DEG_LAT
    d_lon = d_east_m / (METERS_PER_DEG_LAT * math.cos(math.radians(at_lat_deg)))
    return d_lat, d_lon


def latlon_dist_m(lat1, lon1, lat2, lon2):
    d_north = (lat2 - lat1) * METERS_PER_DEG_LAT
    d_east = (lon2 - lon1) * METERS_PER_DEG_LAT * math.cos(math.radians(lat1))
    return math.hypot(d_north, d_east)


def latlon_to_enu(lat, lon, home_lat, home_lon):
    north = (lat - home_lat) * METERS_PER_DEG_LAT
    east = (lon - home_lon) * METERS_PER_DEG_LAT * math.cos(math.radians(home_lat))
    return east, north


def enu_to_latlon(east_m, north_m, home_lat, home_lon):
    d_lat, d_lon = meters_to_latlon_delta(north_m, east_m, home_lat)
    return home_lat + d_lat, home_lon + d_lon


def parse_rth_debug(data):
    """Returns (phase, failure) from the first 4 DEBUG_RTH slots."""
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


def parse_rth_debug_full(data):
    """Returns (phase, failure, distanceToHomeCm) from the 8 DEBUG_RTH slots.

    distanceToHomeCm is stored in a signed int16 slot, so distances above ~327 m
    wrap negative; unwrap once (the experiments never exceed ~655 m).
    """
    if not data or len(data) < 16:
        return None, None, None
    debug = struct.unpack_from("<8h", data, 0)
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
    dist_cm = debug[6]
    if dist_cm < 0:
        dist_cm += 65536
    return phase, failure, dist_cm


def parse_status_armed(data):
    if not data or len(data) < 11:
        return None
    flags32 = struct.unpack_from("<HHHIB", data, 0)[3]
    return (flags32 & 1) == 1
