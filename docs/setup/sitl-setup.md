# SITL Bring-Up

How to launch Betaflight SITL in a state that can be armed at a desk, with no
physical flight controller or serial hardware involved.

## Build

`betaflight/` is a plain (gitignored, not a git submodule) clone of
`https://github.com/betaflight/betaflight.git`, pinned at commit
`14283468fdc7df98f5b52fd649cf23c32587f36a` (2026-08-13) for reproducibility.
`just simulate` builds it automatically; to build by hand:

```bash
cd betaflight
make TARGET=SITL
```

Produces `obj/main/betaflight_SITL.elf`.

## Working directory

Always launch from `betaflight/` (the `Makefile` directory). The binary
creates/reads `eeprom.bin` (32768 bytes) in the current working directory -
running it from elsewhere gives you a fresh, unconfigured FC every time.

## Apply safety configuration and AUX modes (once)

The binary supports a `--config <file>` mode that loads a CLI script, saves
it to `eeprom.bin`, and exits - no need to type CLI commands interactively
every run.

`sitl_safety.txt`:

```bash
feature GPS
set gps_provider = VIRTUAL
set debug_mode = RTH
set runaway_takeoff_prevention = OFF
aux 0 0 0 1700 2100 0
aux 1 46 1 1700 2100 0
save
```

The repository uses `sitl_safety.txt` which enables the virtual GPS (required for SITL GPS spoofing), sets the debug mode to `RTH` (so our experiments can parse the rescue state), maps ARM and GPS_RESCUE to auxiliary channels, and disables Betaflight's runaway takeoff prevention (which goes crazy if we teleport the fake drone too fast).

If you need to change aux mappings later, Betaflight requires you to explicitly bind a mode to a channel range with the `aux` CLI command:
  `aux <index> <mode-permanentId> <aux-channel-index> <start> <end> <logic>`.
  The two lines above bind `ARM` (permanentId 0) to AUX1 (channel index 0,
  i.e. RC channel 5) and `GPS RESCUE` (permanentId 46, Betaflight's stand-in
  for INAV-style RTH) to AUX2, both over the 1700-2100 range - the same
  Aux1/Aux2 high-signal convention every `scripts/*.py` experiment uses.
  Without this, sending an "ARM" RC signal has no effect and arming will
  silently never happen, with zero arming-disable flags reported (looks like
  nothing is wrong, but nothing is bound to the switch either).

Apply it:

```bash
cd betaflight
./obj/main/betaflight_SITL.elf --config sitl_safety.txt
```

This writes the settings into `eeprom.bin` in the current directory. As long
as that same `eeprom.bin` is present, subsequent normal launches keep the
settings - confirmed by reading `runaway_takeoff_prevention` back over the
CLI after a fresh launch, and by successfully arming (see below).

## Boot grace period

Betaflight blocks arming for several seconds after boot (`BOOTGRACE` arming-disable
flag) and also requires the AUX arm switch to make a fresh low-to-high
transition after grace ends (`ARM_SWITCH` flag otherwise) - both real safety
features, not bugs. In practice: hold the arm channel low for **at least 10
seconds** after launching SITL, then raise it. Confirmed empirically: arming
attempted at ~2s post-launch failed with `BOOTGRACE`/`ARM_SWITCH` set; the
identical sequence at ~11s succeeded (`armed: True`, no disable flags).

## Launch

```bash
cd betaflight
./obj/main/betaflight_SITL.elf
```

Expected startup output:

```
[SITL] The SITL will output to IP 127.0.0.1:9002 (Gazebo) and 127.0.0.1:9001 (RealFlightBridge)
[system]Init...
[SITL] init PwmOut UDP link to gazebo 127.0.0.1:9002...0
[SITL] init PwmOut UDP link to RF9 127.0.0.1:9001...0
[SITL] start UDP server @9003...0
[SITL] start UDP server for RC input @9004...0
```

## Network endpoints

| Purpose                      | Transport | Port | Direction (relative to SITL) |
|-------------------------------|-----------|------|-------------------------------|
| FDM state injection (GPS/IMU) | UDP       | 9003 | in                             |
| RC channel input              | UDP       | 9004 | in                             |
| Motor PWM out (Gazebo)         | UDP       | 9002 | out                            |
| Motor PWM out (RealFlight)     | UDP       | 9001 | out                            |
| MSP (UART1)                    | TCP       | 5761 | in/out                         |

The UART-over-TCP ports are per-UART (`BASE_PORT` 5760 + UART index) and only
bind lazily when a client connects - UART1, used for MSP in this project, is
reachable at **5761**, not 5760, and prints `bind port 5761 for UART1` /
`New connection on UART1` on connect. Confirmed by connecting directly:

```bash
# Enter CLI mode and read a setting back, to confirm the saved config took effect
printf '#\nget runaway_takeoff_prevention\n' | nc 127.0.0.1 5761
```

## Motor readback and MSP quirks (why scripts/ is built this way)

Two non-obvious constraints shaped `scripts/sitl_transport.py`, both found by
testing against a live instance rather than reading source alone:

- **SITL serves only one live MSP TCP client at a time.** Opening a second
  TCP connection to port 5761 succeeds at the socket level, but every read on
  it returns EOF immediately. `sitl_transport.py` therefore opens the MSP
  socket lazily, on the first `send_msp()`/`read_msp()` call, and motor
  readback instead uses SITL's UDP `servo_packet_raw` broadcast on port 9001
  (`SitlTransport.get_motors()`) - the same raw 1000-2000 PWM values
  `MSP_MOTOR` would give, with no MSP connection needed at all.
- **This Betaflight version has no separate `MSP_ARMING_DISABLE_FLAGS`
  command.** The arming-disable bitmask is appended to the `MSP_STATUS`
  response itself, after a variable-length flight-mode-flags section - see
  `src/main/msp/msp.c`'s `MSP_STATUS`/`MSP_STATUS_EX` case, cross-checked
  against a captured raw response.

## Verification checklist

- [x] Binary starts and prints the UDP `@9003`/`@9004` lines with no errors.
- [x] `eeprom.bin` exists in `betaflight/` after applying `--config`.
- [x] Connecting to TCP 5761 and running `get runaway_takeoff_prevention` returns `OFF` after a fresh (non-`--config`) launch.
- [x] `scripts/*.py` experiment scripts connect over MSP with no connection conflicts and arming succeeds past the boot-grace window.
- [x] 30s baseline hover with no drift/RTH keeps the craft armed with zero arming-disable flags.
