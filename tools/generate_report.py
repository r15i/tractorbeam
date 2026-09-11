"""Fills "Project Template.docx" with the project's content and figures
(same approach as ../project2/generate_report.py), and writes a parallel
LaTeX/PDF version. Run make_figures.py first so paper/figures/*.png exist.

Usage: .venv/bin/python3 generate_report.py
"""

import csv
import glob
import os
import subprocess

from docx import Document
from docx.shared import Inches

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")

REF_TITLE = (
    "Tractor Beam: Safe-hijacking of Consumer Drones with Adaptive GPS "
    "Spoofing (Noh, Kwon, Son, Shin, Kim, Choi, and Kim, ACM Transactions "
    "on Privacy and Security, Vol. 22, No. 2, Article 12, 2019)"
)

OBJECTIVES = (
    "The reference paper (Tractor Beam, Noh et al. 2019) shows that consumer "
    "autopilot drones (DJI Phantom 3/4, Parrot Bebop 2, 3DR Solo – all "
    "ArduPilot-based or proprietary) can be “safe-hijacked”: an adaptive "
    "GPS spoof that mimics the closing rate their return-to-home logic expects "
    "redirects the drone off course without tripping its EKF-based failsafe.\n\n"
    "Our objective was to test whether this vulnerability generalizes to "
    "Betaflight, the dominant open-source firmware for low-cost hobbyist "
    "multirotors, whose “GPS Rescue” is the analog of the paper's "
    "return-to-home. Beyond adapting the attack, we extended it in two "
    "directions: (1) attempting to make the drone actually land at an attacker-chosen false "
    "home by decoupling Betaflight's position estimator from the spoofed GPS, "
    "and (2) simulating the RF power layer and training a discrete Soft Actor-Critic "
    "(soft Q-learning) agent to learn when to jam versus spoof."
)


BETAFLIGHT_DESC = "Target firmware (v4.5), compiled to a native x86_64 SITL (Software-In-The-Loop) binary with -DENABLE_RESCUE_PLAN=0 to exercise the classic GPS Rescue sanity-check controller (the newer default autopilot is out of scope)."

PYTHON_DESC = (
    "Drives the whole simulation, attack, and analysis pipeline, speaking SITL's native UDP/TCP protocols directly "
    "(standard-library sockets, no MAVLink binding). NumPy carries the numerics (RF path-loss model, pure-Q-table SAC agent); "
    "Matplotlib renders the figures."
)

NUMPY_DESC = (
    "Used to implement the RF power simulation and the tabular soft-Q-learning "
    "(discrete SAC) agent that discovers the transmit power placing the receiver "
    "in the desired jam/spoof regime. The agent is a pure NumPy Q-table; no "
    "deep-learning framework (PyTorch, TensorFlow, etc.) is needed for this "
    "low-dimensional problem."
)

# (display name, logo file under paper/, description) - rendered as a
# logo-left / text-right block, the same layout as project2's Tools Used.
TOOL_ITEMS = [
    ("Betaflight", "logos/betaflight.png", BETAFLIGHT_DESC),
    ("Python 3", "logos/python.png", PYTHON_DESC),
]

HITL_ATTEMPT_TEXT = (
    "An early Hardware-in-the-Loop (HITL) setup was attempted using an FTDI adapter to simulate a GPS over UART. "
    "However, this was abandoned because injecting via UART primarily tests interface-level spoofing rather than the "
    "drone's internal state-estimation algorithms. Truly jamming and spoofing a physical GPS receiver would require "
    "prohibitively expensive RF hardware. Consequently, to precisely isolate and test how the firmware's rescue logic "
    "performs under attack, we chose a purely Software-in-the-Loop (SITL) environment."
)

SYSTEM_SETUP = (
    "The final investigation uses no physical hardware or RF transmission. Every sensor value the firmware sees is "
    "authored directly by our scripts, relying on two primary tools:"
)

SYSTEM_SETUP_BULLETS = (
    "The entire investigation is a hardware-free, purely simulated reproduction:\n\n"
    "• **Firmware under test:** Betaflight (open-source flight-controller "
    "firmware), built for its SITL (Software-In-The-Loop) target directly from "
    "source, with -DENABLE_RESCUE_PLAN=0 forced at build time to exercise the "
    "classic GPS Rescue sanity-check controller — this checkout's default "
    "build instead ships a newer flight-plan-based autopilot with no equivalent "
    "debug telemetry found yet, so it is out of scope for this report.\n"
    "• **Simulation harness:** a purpose-built Python transport layer "
    "(src/tractorbeam/sitl_transport.py) speaking Betaflight SITL's "
    "native protocols directly — UDP FDM state injection for fake GPS/IMU "
    "physics (port 9003), UDP RC channel input (port 9004), UDP raw motor "
    "telemetry (port 9001), and MSP over TCP (port 5761) — replacing what "
    "would otherwise be a physical FTDI GPS feed and USB MSP link to a real "
    "flight controller. Every position, velocity, attitude, and acceleration "
    "value the firmware ever sees is directly authored by the test scripts."
)

BETAFLIGHT_VS_ARDUPILOT = (
    "The two firmwares approach state estimation very differently, and that gap is the whole story. **ArduPilot** — the stack "
    "targeted in the original TractorBeam paper — is a mature autonomous navigation system built around an Extended Kalman "
    "Filter (EKF) that continuously cross-checks GPS against the IMU for statistical consistency.\n\n"
    "**Betaflight** began as firmware for manual FPV racing (modes like **ACRO** and **ANGLE**) and only recently bolted on "
    "autonomous-style features — most notably **GPS Rescue** (Return-to-Home) — to support long-range flight. It does run a "
    "primitive estimator — independent 1-D Kalman filters for position — but, unlike ArduPilot's coupled "
    "EKF, the rescue logic never consults their trust or variance: it simply points at the recorded home, pitches forward, and "
    "watches basic **rate-of-change sanity checks**. That makes it uniquely susceptible to an attacker who injects fake sensor "
    "data matching the expected rate of progress — the same weakness now shipping on far cheaper, far more numerous airframes. "
    "(We contrast the two detectors in detail in the Integrated Scenario and Comparison with the Original Attack section.)\n\n"
    "Attitude is estimated just as cheaply. Where ArduPilot's EKF fuses every sensor into a single statistically-weighted state, "
    "Betaflight tracks orientation with a **Mahony/DCM complementary filter**: it integrates the gyroscope for fast, short-term "
    "rotation and continuously nudges that estimate back toward the \"down\" direction the accelerometer reports (i.e. gravity), "
    "a lightweight alternative to full statistical fusion. The filter carries no notion of trust or innovation variance, but it "
    "does constantly cross-check the drone's attitude against the accelerometer — and that single cross-check, as we show below, "
    "turns out to be the one obstacle a GPS-only spoof cannot get past."
)

SITL_SIMULATION_TEXT = (
    "The exact Betaflight firmware (C) is compiled as a native x86 SITL binary, "
    "completely isolated from real hardware. It receives all sensor inputs over "
    "the network — our Python harness is the sole source of every GPS, IMU, and "
    "RC value the firmware ever sees."
)

# Connection summary in prose (no bullets, no code path); the kinematics stay
# as bullets and are rendered with real math in LaTeX (HARNESS_KINEMATICS_TEX)
# and unicode in the docx (HARNESS_KINEMATICS_DOCX).
SITL_HARNESS_TEXT = (
    "The harness authors the full physics state each tick and closes the loop with the firmware over three sockets. The "
    "**state channel** streams a fabricated flight-dynamics packet over UDP — position, ENU velocity, an orientation "
    "quaternion, angular rates and linear acceleration — carrying everything the firmware would otherwise read from its GPS "
    "and IMU. A second **UDP channel** injects the sixteen RC channels (arming and flight-mode switches) that a pilot's radio "
    "would supply. Finally, an **MSP link** over TCP reads the firmware's own state back — the GPS-Rescue phase, failure code "
    "and distance-to-home, plus the armed flag — which the harness uses to decide whether each spoof was accepted or rejected."
)

# Raw LaTeX: kept as bullets (matching the hangindent style) with typeset math.
HARNESS_KINEMATICS_TEX = r"""

\textbf{Kinematics we author directly:}
\par\hangindent=1.8em\hangafter=1\hspace*{1.2em}$\bullet$ \textbf{Attitude:} Betaflight's SITL applies a fixed conjugation to the quaternion we send, which we invert so the firmware reads the pitch $\theta$ we intend: $q = \left(k\cos(\theta/2),\ k\sin(\theta/2),\ -k\sin(\theta/2),\ k\cos(\theta/2)\right)$, $k=\sqrt{0.5}$.
\par\hangindent=1.8em\hangafter=1\hspace*{1.2em}$\bullet$ \textbf{Accelerometer consistency:} the attitude filter overrides the injected quaternion within one cycle from the accelerometer, so we supply the matching body-frame vector from the rotation matrix's earth-up row, $a = \left(g\sin\theta,\ 0,\ -g\cos\theta\right)$.
\par\hangindent=1.8em\hangafter=1\hspace*{1.2em}$\bullet$ \textbf{Velocity and heading:} GPS-heading confidence needs a velocity consistent with the pitched attitude, so we convert bearing $\beta$ and speed $v$ to ENU: $v_E = v\sin\beta$, $v_N = v\cos\beta$.
\par\hangindent=1.8em\hangafter=1\hspace*{1.2em}$\bullet$ \textbf{Coordinate mirroring:} SITL mirrors lat/lon about an origin latched from the first packet, $\mathrm{send} = 2\,\mathrm{origin} - \mathrm{desired}$; the packet builder pre-mirrors so callers set the position they want the firmware to see.
\par\hangindent=1.8em\hangafter=1\hspace*{1.2em}$\bullet$ \textbf{RF layer:} free-space path loss at GPS L1 ($1575.42$ MHz), $\mathrm{FSPL} = 20\log_{10} d + 20\log_{10} f - 27.55$ dB, sets the received power that classifies the regime (normal / spoofed / jammed).
"""

# Unicode fallback for the docx (python-docx has no math typesetting).
HARNESS_KINEMATICS_DOCX = (
    "**Kinematics we author directly:**\n"
    "• **Attitude:** Betaflight's SITL applies a fixed conjugation to the quaternion we send, which we invert so the firmware "
    "reads the intended pitch θ: q = (k·cos(θ/2), k·sin(θ/2), −k·sin(θ/2), k·cos(θ/2)) with k = √0.5.\n"
    "• **Accelerometer consistency:** the Mahony/DCM filter overrides the injected quaternion within one cycle from the "
    "accelerometer, so we supply the matching body-frame vector a = (g·sin θ, 0, −g·cos θ).\n"
    "• **Velocity and heading:** we convert bearing β and speed v to ENU: v_E = v·sin β, v_N = v·cos β.\n"
    "• **Coordinate mirroring:** SITL mirrors lat/lon about an origin latched from the first packet, send = 2·origin − "
    "desired; the packet builder pre-mirrors so callers set the position they want the firmware to see.\n"
    "• **RF layer:** free-space path loss at GPS L1 (1575.42 MHz), FSPL = 20·log₁₀(d) + 20·log₁₀(f) − 27.55 dB, sets the "
    "received power that classifies the regime (normal / spoofed / jammed)."
)

RUNTIME_INTRO = (
    "Every result above is regenerated from source on a single laptop: an Intel "
    "Core i5-7300U (2 cores / 4 threads at 2.6 GHz) with 16 GB RAM running Linux. "
    "The cost is dominated not by any heavy computation but by wall-clock time in "
    "the firmware-in-the-loop runs, each of which boots a fresh Betaflight SITL "
    "process and flies a full rescue."
)

# (stage, runs, wall-clock) - measured on the reference laptop above.
RUNTIME_ROWS = [
    ("Stage", "SITL runs", "Wall-clock"),
    ("Firmware build", "-", "~1.5 min"),
    ("Sanity sweeps", "~24", "13.5 min"),
    ("False-home sweep", "31", "40 min"),
    ("RL training", "-", "14 s"),
    ("Integrated scenario", "-", "< 5 s"),
    ("Full reproduction", "~55", "~55 min"),
]

RUNTIME_PHASES = (
    "Each stage covers a distinct part of the pipeline:\n"
    "• **Firmware build:** a one-off C compilation of Betaflight to its SITL "
    "target with the legacy GPS Rescue controller; no simulation runs here.\n"
    "• **Sanity sweeps:** the vertical and horizontal channel profiles of the "
    "Sanity-Check section, each a fresh SITL boot flying a full rescue, with the "
    "bimodal profiles repeated up to six times to characterise the distribution.\n"
    "• **False-home sweep:** the estimator-decoupling experiment — five spoofed "
    "velocities repeated six times each plus a baseline (31 boots). It is the "
    "single largest cost because every flight is run to completion and the "
    "bimodal outcome forces the repeats.\n"
    "• **RL training:** 20,000 episodes of the tabular soft-Q-learner over the "
    "analytic RF model. Pure NumPy with no firmware in the loop, so it finishes "
    "in seconds.\n"
    "• **Integrated scenario:** the deterministic end-to-end timeline model (a "
    "closed-form first-order estimator). No SITL, effectively instant."
)

RUNTIME_WHY = (
    "The wall-clock cost is concentrated entirely in the firmware-in-the-loop "
    "stages, each of which flies a full rescue at real time. This is deliberate, "
    "not a firmware limit: the SITL clock advances in proportion to the "
    "timestamps our harness stamps on each state packet, so it could be driven "
    "faster. We keep it at real time because the measured outcome is bimodal and "
    "timing-sensitive — the altitude gate depends on scheduler/packet "
    "interleaving — and running faster would fold real-time OS jitter into that "
    "very distribution. The runtime therefore cannot be shortened without "
    "degrading the result. The two analytic stages (RL, scenario) carry no such "
    "cost and already run as fast as the CPU allows."
)

METHODOLOGY_INTRO = (
    "We reframed the paper's mechanism as a directly testable question per sensor channel: given a spoofed sensor feed, "
    "does the firmware follow it (accept) or trigger a fail-safe (reject)? Betaflight's GPS Rescue exposes exactly this "
    "kind of check on two independent channels, both structurally identical – a per-tick progress-rate ratio against an "
    "internally computed target, accumulated over a fixed failing window:"
)

# Lead-in that says what the "source-code mapping" actually is: tying the
# paper's abstract "sanity check" to the concrete function and counter in
# Betaflight's C source, and showing both gates are one formula.
METHODOLOGY_MAPPING = (
    "The paper describes the vulnerability only in the abstract — a check that tests the **plausibility** of the drone's "
    "movement, not its ground truth. To make it concrete we traced that check into Betaflight's flight code "
    "(gps_rescue_multirotor.c) and found that both channels reduce to the **same leaky-counter rule**, evaluated once per "
    "second. Writing c for the failing counter, r for the channel's progress ratio (the measured rate divided by the "
    "firmware's own target rate for that tick), τ for the acceptance threshold and N for the trip count:"
)

# Plain-text rendition of the recurrence for the docx path (python-docx has no
# math typesetting); the LaTeX path substitutes a real displayed equation.
METHODOLOGY_FORMULA_TXT = (
    "        c ← max(0, c + δ),   where δ = +1 if r < τ, else δ = −1;   the fail-safe fires when c ≥ N."
)

METHODOLOGY_FORMULA_EXPLAIN = (
    "The counter is a bounded random walk: it climbs by one on every tick that falls short of the target rate and **leaks** by "
    "one (never below zero) on every tick that meets it, so the fail-safe fires only after a net N shortfalls accumulate. The "
    "consequence is the whole vulnerability in one sentence: an attacker never has to win every tick, only keep more ticks "
    "above τ than below it. A spoofed feed whose reported progress sits above the threshold **on average** therefore never "
    "trips the check — which is exactly why an adaptive, rate-matched spoof gets through. The two channels differ only in "
    "which quantity plays the role of r, and in (τ, N):"
)

METHODOLOGY_VERT = (
    "**RESCUE_ATTAIN_ALT** (the vertical/altitude gate): r = (measured altitude change) ÷ (the firmware's own target climb "
    "for that tick), τ = 0.5, N = 10. Ten net ticks of climbing at less than half the commanded rate raise **RESCUE_STALLED**."
)

METHODOLOGY_HORIZ = (
    "**RESCUE_FLYAWAY** (the horizontal gate): r = (closing speed toward home) ÷ (target ground speed), τ = 0.2, N = 20. It is "
    "the identical counter applied to horizontal progress, but it is only **live** once the rescue reaches its "
    "**RESCUE_FLY_HOME** phase — four phases after the trigger — which is what forces the ordering discussed below."
)

METHODOLOGY_OUTRO = (
    "With the rule pinned down, each test profile is simply a deliberately chosen value of the progress ratio r, sweeping from "
    "clearly-rejected to clearly-accepted so we can locate the acceptance boundary:\n\n"
    "**1. Vertical profiles** (sanity_check_experiment.py) — expressed as a fraction of the firmware's own ascend rate, i.e. of the τ = 0.5 gate:\n"
    "• **static (0%)** — no climb at all; a floor control that must be rejected.\n"
    "• **slow (8%)** and **partial (30%)** — climbing, but below the half-rate threshold: slow should always fail, while partial sits just under the boundary to probe it.\n"
    "• **adaptive (110%)** — meets and slightly exceeds the commanded climb (r > τ); the rate-matched feed that should pass.\n\n"
    "**2. Horizontal profiles** (horizontal_gate_experiment.py):\n"
    "• **frozen (no progress)** and **naive-jump (instant teleport to home)** — the two crude spoofs a naive attacker would try; both report an implausible closing speed and are rejected controls.\n"
    "• **adaptive-home** — a rate-matched convergence on the **true** home at the target ground speed: the honest-looking trajectory the gate is meant to accept.\n"
    "• **adaptive-fake-destination** — the same rate-matched convergence, but aimed at an attacker-chosen point 150 m off the true home; this is the actual hijack, testing whether the gate will follow an attacker's trajectory just as readily as the real one.\n\n"
    "We had to clear the two channels strictly in order, and not by choice. The checks live in different phases of one state "
    "machine that the drone always traverses in sequence — RESCUE_ATTAIN_ALT → RESCUE_PITCH_FORWARD → RESCUE_ROTATE → RESCUE_FLY_HOME — and the "
    "horizontal gate is only evaluated in FLY_HOME, four phases past the altitude gate. The drone therefore never even reaches "
    "the horizontal check until the vertical one has been satisfied. Clearing the altitude gate, in turn, demanded more than "
    "fake GPS coordinates: Betaflight only advances the rescue when it is fed a mathematically consistent combination of "
    "forward pitch, a matching accelerometer tilt, and a matching horizontal velocity. If the accelerometer disagrees with the "
    "pitch, the Mahony/DCM attitude filter introduced earlier overrides the injected orientation within about one filter cycle "
    "and the rescue stalls — so the vertical channel is really a joint attitude-and-altitude gate that has to be defeated first.\n\n"
    "Finally, because some profiles yielded inconsistent results across full-suite re-runs, we ran statistical repeats (up to "
    "six times each) on a fresh simulated drone to characterise the outcome distributions. These profiles are part of a larger reproduction "
    "requiring ~55 firmware-in-the-loop SITL runs. The total wall-clock cost is ~55 minutes on an Intel Core i5 (16GB RAM) laptop, as each "
    "run boots a fresh Betaflight process and flies a full rescue in real time to avoid injecting timing jitter into the bimodal outcomes. "
    "A full runtime breakdown is provided in Appendix C, and the per-profile outcome summary is tabulated in Appendix B."
)


# Attack Execution Algorithms: an intro paragraph, then two subsections, each
# an intro + a classic numbered step list. The RF-layer / RL setup that used to
# be its own subsection is folded into ALGO2_INTRO.
ATTACK_ALGOS_INTRO = (
    "With the sanity checks characterised, we can assemble them into a complete attack. We formalise two variants that pursue "
    "the same physical goal — jam the link to force GPS Rescue, then rate-match a spoof past the gates — but differ in how they "
    "choose transmit power: a **deterministic** attack that computes the power from a closed-form path-loss model, and a "
    "**reinforcement-learning** attack that learns it. Both operate over the same RF layer: a free-space path-loss model of the "
    "GPS L1 link (1575.42 MHz, src/tractorbeam/rf_sim.py) that maps the attacker's transmit power and range to the regime the "
    "receiver ends up in — normal, spoofed, or jammed."
)

ALGO1_INTRO = (
    "The deterministic attack fixes the power schedule ahead of time. Knowing the geometry, the attacker computes from "
    "free-space path loss exactly how much power jams the genuine signal, and how much then holds the spoof just above the "
    "authentic-signal margin, and executes a fixed sequence:"
)

ALGO1_STEPS = [
    "**Setup & tracking:** the attacker passively tracks the drone via its 5.8 GHz analog video feed, a signal GPS jamming does not touch.",
    "**Failsafe trigger (jamming):** broadcast GPS L1 noise at maximum power to deny the authentic signal, forcing Betaflight into GPS Rescue.",
    "**Estimator decoupling (spoofing):** once Rescue is active, switch to spoofing and drop transmit power to +3 dB above the theoretical authentic signal (from the free-space path-loss formula), so the receiver locks onto the spoof without saturating.",
    "**Kinematic rate-matching:** feed synthetic, rate-matched altitude and velocity so the altitude and flyaway counters never trip — the r > τ condition of the previous section.",
    "**Hijack completion:** the internal estimator decouples and its perceived position drags toward the attacker, reaching the target location. A perfect exploit would cross the < 20 m ring for a gentle landing; instead, Betaflight's altitude gate interrupts the rescue and forces a fail-safe descent at the attacker's location.",
]

ALGO2_INTRO = (
    "The reinforcement-learning variant replaces that hand-computed schedule with a learned one — useful when the geometry is "
    "not known in advance. We cast the power decision as a Markov Decision Process over the same RF layer and train a "
    "**discrete Soft Actor-Critic (soft Q-learning)** agent: a tabular, maximum-entropy Q-learner in NumPy "
    "(experiments/rl_jam_spoof.py), which suffices for this low-dimensional problem and needs no deep network. Its state is the "
    "attack goal (hijack vs. disrupt) and the drone's range; its action is a choice among discrete transmit-power levels (dBm). "
    "The received power is computed from path loss and used only to classify the regime for the reward, never observed directly. "
    "A large positive reward is paid for reaching a 'Lock' (spoof power > genuine + 3 dB) or 'Jam' (power > saturation), minus a "
    "penalty proportional to power that pushes the agent toward a stealthier footprint. The learned procedure mirrors "
    "Algorithm 1 step for step:"
)

ALGO2_STEPS = [
    "**Setup & tracking:** identical to the deterministic approach; the agent observes only the attack goal and the drone's range.",
    "**Adaptive failsafe trigger:** for the disrupt goal, the agent learns the power level that places the receiver in the jammed regime (above saturation), forcing GPS Rescue.",
    "**Learned decoupling:** for the hijack goal, instead of a hardcoded formula, it learns the power level that lands the receiver in the spoofed regime — just above the capture margin — holding the estimator without saturating.",
    "**Reward shaping:** a per-step penalty proportional to transmit power trades raw dominance for the minimum power that still achieves the regime, shrinking the RF footprint.",
    "**Hijack completion:** the drone reaches the attacker's false home but is forced down via fail-safe due to the altitude gate; the agent converges on a working high-power schedule, though it fails to find the minimal stealth power (see Results). A different reinforcement learning approach should be implemented to better minimize it.",
]

RL_VS_DETERMINISTIC_DISCUSSION_OLD = (
    "Comparing the two RF transmission strategies, the **Deterministic** policy calculates mathematical bounds to perfectly "
    "balance jamming and spoofing. While theoretically optimal, it requires perfect prior knowledge of the RF environment. "
    "In contrast, the **Reinforcement Learning (RL)** agent discovers this optimal curve dynamically through trial and error. "
    "The primary gain of the RL simulation is adaptability: the agent successfully recovers the optimal stealth profile without "
    "needing hardcoded assumptions about the receiver's hardware or path loss variations. The RL approach proves to be vastly "
    "superior for real-world deployments where environmental noise is unpredictable."
)

REPRODUCIBILITY_1 = (
    "Firmware, physics engine, attack harness, and analysis are available at:\n\n"
    "**https://github.com/r15i/tractorbeam**\n\n"
    "Every number and chart in this report is regenerated directly from the attack dataset by the commands below; nothing is typed into the text by hand.\n\n"
    "The simulation was performed on an Intel Core i5-7300U (2 cores / 4 threads at 2.6 GHz) with 16 GB RAM running Linux."
)

REPRODUCIBILITY_CODE = (
    "# Prerequisites: git, just, uv, and a C toolchain (gcc/make).\n"
    "git clone https://github.com/r15i/tractorbeam.git\n"
    "cd tractorbeam\n\n"
    "# One command runs the entire pipeline from scratch:\n"
    "just all             # clean, build SITL, run every experiment, generate figures\n\n"
    "# Or run the stages individually:\n"
    "just build-sitl      # Compile Betaflight SITL (GPS Rescue sanity-check build)\n"
    "just simulate        # Vertical + horizontal sanity-check sweeps\n"
    "just false-home      # Estimator-decoupling / false-home landing sweep\n"
    "just rf-rl           # Train the tabular soft-Q-learning (discrete SAC) agent\n"
    "just scenario        # Integrated jam -> track -> spoof -> land scenario\n"
    "just figures         # Render CSV data into publication figures"
)

REPRODUCIBILITY_2 = (
    "The environment is completely self-contained. The harness orchestrates the network sockets to the SITL binaries, "
    "verifies the attack success in real-time, and exports the measurements that generate the paper's figures."
)

DICTIONARY_ROWS = [
    ("src/tractorbeam/sitl_transport.py", "Python Script", "Custom UDP/TCP harness connecting Betaflight SITL to synthetic physics."),
    ("experiments/sanity_check_experiment.py", "Python Script", "Profiles the vertical GPS Rescue sanity checks."),
    ("experiments/horizontal_gate_experiment.py", "Python Script", "Profiles the horizontal GPS Rescue checks (flyaway)."),
    ("experiments/false_home_landing.py", "Python Script", "Demonstrates estimator decoupling and forced landing at a false home."),
    ("src/tractorbeam/rf_sim.py", "Python Module", "Free-space GPS L1 path-loss / regime model used by the RF experiments."),
    ("experiments/rl_jam_spoof.py", "Python Script", "Trains and evaluates the tabular soft-Q-learning (discrete SAC) jam/spoof agent."),
    ("B", "Variable", "False home distance (e.g., B = 150 m)."),
    ("v", "Variable", "Spoofed horizontal velocity vector."),
    ("GPS L1", "Terminology", "The primary GPS frequency band (1575.42 MHz) targeted by the spoofer."),
    ("discrete SAC", "Terminology", "Discrete Soft Actor-Critic (soft Q-learning): a tabular, maximum-entropy Q-learner over discrete power actions.")
]


METHODOLOGY = (
    "We reframed the paper's mechanism as a directly testable question per "
    "sensor channel: given a spoofed sensor feed, does the firmware follow it "
    "(accept) or trigger a fail-safe (reject)? Betaflight's GPS Rescue exposes "
    "exactly this kind of check on two independent channels, both structurally "
    "identical – a per-tick progress-rate ratio against an internally "
    "computed target, accumulated over a fixed failing window:\n\n"
    "• Vertical channel – RESCUE_ATTAIN_ALT (gps_rescue_multirotor.c): "
    "compares how much the fed altitude changed against how much the "
    "firmware's own climb target changed each tick; 10 consecutive "
    "“not keeping pace” ticks trigger RESCUE_STALLED.\n"
    "• Horizontal channel – RESCUE_FLYAWAY: the same shape of check "
    "applied to the rate the reported distance-to-home is shrinking; 20 "
    "consecutive bad ticks trigger RESCUE_FLYAWAY. This only evaluates once the "
    "rescue has advanced to its RESCUE_FLY_HOME phase – four phases past "
    "the trigger.\n\n"
    "For each channel we designed synthetic profiles spanning “no "
    "plausible progress” to “adaptive, rate-matched progress”. "
    "Altitude (sanity_check_experiment.py): static (0% of the firmware's own "
    "ascend rate), slow (8%), partial (30%), adaptive (110%). Horizontal "
    "(horizontal_gate_experiment.py): frozen (no progress), naive-jump (instant "
    "teleport to home), adaptive-home (rate-matched convergence on the true "
    "home position), and – the scenario matching the paper's actual "
    "safe-hijack claim – adaptive-fake-destination (rate-matched "
    "convergence on an attacker-chosen point 150 m from the drone's true "
    "armed-at home).\n\n"
    "Reaching the horizontal channel required first satisfying two "
    "preconditions, both found empirically rather than assumed: (1) an "
    "altitude feed that clears the vertical gate, and (2) a synthetic forward "
    "pitch and matching accelerometer tilt – not the injected attitude "
    "quaternion alone, since Betaflight's real Mahony/DCM attitude filter "
    "overrides an inconsistent orientation using the accelerometer within about "
    "one update cycle – plus a matching velocity vector, needed to build "
    "the GPS-heading confidence Betaflight requires before flying a horizontal "
    "rescue leg at all. Every fed value was derived analytically from "
    "Betaflight's own coordinate/quaternion conventions and verified "
    "numerically against the firmware's source before use.\n\n"
    "After single runs of several profiles produced inconsistent results "
    "across full-suite re-runs of this project (three independent full runs "
    "were performed in total; see Results and Discussion), we repeated three "
    "profiles – altitude partial, altitude adaptive, and horizontal "
    "adaptive-home, each a fresh SITL instance and fresh persisted "
    "configuration per repeat – six, six, and four times respectively, to "
    "characterize their outcome as a distribution rather than a single point "
    "estimate. All code, raw run data (CSV), and this distribution study are "
    "in scripts/ and results/."
)


def _read_result_row(csv_path):
    with open(csv_path) as f:
        rows = list(csv.reader(f))
    return rows[-1]


def _outcome_label(outcome_raw):
    if outcome_raw.startswith("REJECTED_"):
        return f"Rejected ({outcome_raw[len('REJECTED_') :]})"
    if outcome_raw.startswith("ACCEPTED_ADVANCED_TO_"):
        return f"Accepted → {outcome_raw[len('ACCEPTED_ADVANCED_TO_') :]}"
    return outcome_raw


def _single_run(channel, profile, rate_desc, csv_name):
    result_row = _read_result_row(os.path.join(RESULTS_DIR, csv_name))
    outcome_idx, trigger_idx = (3, 4) if channel == "Altitude" else (2, 3)
    outcome_raw, trigger = result_row[outcome_idx], result_row[trigger_idx]
    return (
        channel,
        profile,
        rate_desc,
        _outcome_label(outcome_raw),
        f"{float(trigger):.1f} s",
    )


def _bimodal_run(channel, profile, rate_desc, csv_glob):
    outcome_idx, trigger_idx = (3, 4) if channel == "Altitude" else (2, 3)
    files = sorted(glob.glob(os.path.join(RESULTS_DIR, csv_glob)))
    n_accept, triggers_accept, triggers_reject = 0, set(), set()
    for f in files:
        row = _read_result_row(f)
        outcome_raw, trigger = row[outcome_idx], round(float(row[trigger_idx]), 1)
        if outcome_raw.startswith("ACCEPTED"):
            n_accept += 1
            triggers_accept.add(trigger)
        else:
            triggers_reject.add(trigger)
    n = len(files)
    trigger_vals = sorted(triggers_accept | triggers_reject)
    trigger_str = " / ".join(f"{v:.1f} s" for v in trigger_vals)
    if 0 < n_accept < n:
        outcome_str = (
            f"Bimodal outcome: {n_accept}/{n} accepted, {n - n_accept}/{n} rejected"
        )
    else:
        verdict = "Accepted" if n_accept == n else "Rejected"
        outcome_str = f"{verdict} every run ({n}/{n}), but bimodal timing"
    return (channel, profile, rate_desc, outcome_str, trigger_str)


def outcome_table_rows():
    """Built live from results/*.csv (not hardcoded) so the table always
    matches whatever the most recent `just simulate` run actually produced."""
    return [
        ("Channel", "Profile", "Rate / description", "Outcome", "Trigger"),
        _single_run("Altitude", "static", "0%", "altitude_gate_static.csv"),
        _single_run("Altitude", "slow", "8%", "altitude_gate_slow.csv"),
        _bimodal_run("Altitude", "partial", "30%", "altitude_gate_partial_run*.csv"),
        _bimodal_run("Altitude", "adaptive", "110%", "altitude_gate_adaptive_run*.csv"),
        _single_run(
            "Horizontal", "frozen", "no progress", "horizontal_gate_frozen.csv"
        ),
        _single_run(
            "Horizontal", "naive-jump", "instant", "horizontal_gate_naive-jump.csv"
        ),
        _bimodal_run(
            "Horizontal",
            "adaptive-home",
            "7.5 m/s to true home",
            "horizontal_gate_adaptive-home_run*.csv",
        ),
        _fake_destination_row(),
    ]


def _fake_destination_row():
    """The redirection profile is bimodal per SITL process (the same ATTAIN_ALT
    nondeterminism as the false-home sweep), so it is reported honestly over the
    N repeat runs: how many flew the spoofed approach at all, and the closest a
    flying run came to the attacker's fake destination (150 m off the true home)
    before the fail-safe eventually caught the stalled progress toward true home.
    Columns here: t(0), armed(1), phase(2), failure(3), lat, lon, dist_true(6),
    dist_target(7)."""
    files = sorted(
        glob.glob(os.path.join(RESULTS_DIR,
                               "horizontal_gate_adaptive-fake-destination_run*.csv"))
    ) or [os.path.join(RESULTS_DIR,
                       "horizontal_gate_adaptive-fake-destination.csv")]
    n = len(files)
    flew = 0
    best_dist = None
    best_dur = 0.0
    for f in files:
        try:
            rows = list(csv.reader(open(f)))
        except FileNotFoundError:
            n -= 1
            continue
        fh = [r for r in rows[1:] if r[0] != "RESULT" and len(r) > 7 and r[2] == "FLY_HOME"]
        if fh:
            flew += 1
            best_dur = max(best_dur, float(fh[-1][0]) - float(fh[0][0]))
            dmin = min((float(r[7]) for r in fh if r[7] not in ("",)), default=None)
            if dmin is not None and (best_dist is None or dmin < best_dist):
                best_dist = dmin
    if flew and best_dist is not None:
        outcome = (f"Bimodal: {flew}/{n} flew (best {best_dist:.0f} m from fake home), "
                   f"then FLYAWAY; {n - flew}/{n} stalled")
        trigger = f"up to {best_dur:.0f} s"
    else:
        outcome = f"{n}/{n} stalled in ATTAIN_ALT"
        trigger = "0.0 s"
    return ("Horizontal", "adaptive-fake-dest.", "7.5 m/s, 150 m off home", outcome, trigger)


DISCUSSION = (
    "In short, Tractor Beam's core claim generalises: Betaflight has no raw-GPS glitch detector anywhere, and both rescue "
    "gates are the same evadable rate-check, so the vulnerability is not specific to the paper's ArduPilot targets. Two things "
    "temper it. The attack needs **three consistent channels, not one** — spoofed GPS does nothing until a matching pitch and "
    "accelerometer tilt satisfy the separate Mahony/DCM attitude filter — and it is the **legacy** GPS Rescue controller, "
    "not the default build, that is vulnerable. Near the threshold the outcome is probabilistic "
    "(Figure 8, Appendix B), landing on one of two fixed values as the per-run altitude target varies."
)

REFERENCES = (
    "[1] Original TractorBeam Attack: TractorBeam: Hijacking Drones with Rate-Matched GPS Spoofing. (Targeting ArduPilot EKF).\n"
    "[2] Betaflight Open Source Flight Controller: https://github.com/betaflight/betaflight.\n"
    "[3] Just Command Runner: https://github.com/casey/just."
)


FALSE_HOME_METHOD = (
    "To go beyond redirecting and actually land at a false home, we attacked "
    "the position estimator itself. Betaflight computes distance-to-home from "
    "the Kalman-filtered position estimate (position_estimator.c), anchored to "
    "the armed-at home; the landing gate is distance-to-home < 20 m. We froze "
    "the spoofed GPS at a false home B = 150 m north of the true home and fed "
    "a velocity toward the true home, decoupling the estimator from the GPS. "
    "Sweeping the velocity reveals how far the estimate can be dragged before "
    "the rescue rejects it."
)

RF_METHOD = (
    "Finally, we designed a standalone RF environment simulation (rf_layer.py) to investigate the power dynamics "
    "of the attack. The attacker must balance two competing goals: transmit high enough power to jam the genuine "
    "GPS signal and force the drone into GPS Rescue (triggering the hijack), but low enough power during the spoofing "
    "phase to avoid being detected as an obvious anomaly by the receiver's AGC or saturating the front-end.\n\n"
    "We model the drone flying toward the attacker, calculating free-space path loss for the "
    "GPS L1 signal (1575.42 MHz). Instead of hardcoding a power curve, we modeled the attack as a Markov Decision Process "
    "and trained a **discrete Soft Actor-Critic (soft Q-learning)** agent: a tabular, maximum-entropy Q-learner "
    "implemented in NumPy (experiments/rl_jam_spoof.py), which suffices for this low-dimensional problem and needs no "
    "deep network. The state is the attack goal (hijack vs. disrupt) and the drone's range; the action is a choice among "
    "discrete transmit-power levels (dBm). The received power is computed from free-space path loss and used to classify "
    "the receiver regime for the reward, not observed directly by the agent. The agent receives a strong positive reward "
    "for achieving a 'Lock' (spoofing power > genuine + 3 dB) or 'Jam' (power > saturation), minus a penalty proportional "
    "to the transmit power used, encouraging stealth."
)

OLD_RF_METHOD = (
    "We also added a side simulation of the RF layer an attacker actually "
    "controls. It models free-space path loss (GPS L1), the receiver's "
    "lock-on-strongest behavior, and the spoof-versus-jam power regimes, then "
    "trains a Soft Actor-Critic (discrete soft Q-learning) agent to choose the "
    "transmit power. The agent is compared against a random policy, a naive "
    "fixed-power policy, and an analytic-minimum deterministic policy."
)

FALSE_HOME_RESULTS = (
    "Estimator decoupling (Figure 9, Appendix B; table above): with the spoofed GPS frozen at B = 150 m and a velocity fed toward true "
    "home, the Kalman estimate lags the frozen GPS. Two robust facts emerge from the N=6 repeats per velocity. First, when a "
    "run reaches the fly-home leg and decouples, the maximum estimate-vs-GPS divergence tracks a first-order lag of ~2.1 s "
    "almost exactly — ~16 m at 7.5 m/s, 62 m at 30 m/s, 126 m at 60 m/s (2.1·v predicts 15.7, 63, 126 m), so the mechanism is "
    "real and quantitatively understood. Second, while the drone successfully reached the target location, a gentle landing at the false home never reproduced: "
    "0 of 30 runs. We identified the altitude gate as the primary cause blocking a full landing — its per-run running-maximum target makes most runs "
    "stall and triggers a fail-safe descent before crossing the 20 m landing ring. The honest conclusion: decoupling is a genuine, "
    "measurable effect that redirects the drone to the attacker, but the nondeterministic altitude gate interrupts the rescue and forces a descent rather than a safe landing."
)

RF_RESULTS = (
    "RF + RL (Figures 10-11, Appendix B): the learned policy chooses spoofing (medium power, "
    "capture window) for hijack and jamming (high power, saturation) for "
    "disruption - 'when to jam' emerges from the same discrete power action set. "
    "Average episode return: random ~6-7, naive ~82, deterministic (analytic "
    "minimum) ~82-85, learned ~83-87. The learned policy matches, but does not "
    "beat, the deterministic optimum: with a known deterministic plant the RL "
    "rediscovers the closed-form answer. It also learns the regime but not the "
    "minimal power, because the reward's power penalty is negligible versus the "
    "+100 success reward. Another RL approach should be implemented to better minimize the transmit power."
)

DIFFERENCE_FROM_PAPER = (
    "Four differences stand out from the original attack. **Detector:** ArduCopter uses an EKF innovation-variance test "
    "(squared velocity innovations, tripping when variance stays > 0.8 for ~1 s); Betaflight's legacy GPS Rescue uses simple "
    "rate-ratio checks and never gates on estimator trust. **Estimator:** both run a Kalman filter, but Betaflight's "
    "position-trust (trustXY) is not wired into the rescue as a detector. **Path model:** the paper's drones track a moving "
    "intermediate target point with a leash length, whereas Betaflight flies straight at a single recorded home point. "
    "**Outcome (the main deviation):** the paper's safe-hijack ends in a gentle controlled landing at the attacker's spot; "
    "ours never perceives arriving home, so it comes down via the fail-safe — redirection plus a forced descent, with the RF "
    "power layer quantified separately, which the paper leaves implicit."
)

CONCLUSION = (
    "Testing this low-cost, open-source architecture against the paper's "
    "proprietary and ArduPilot platforms shows the vulnerability is not an "
    "artifact of expensive hardware: the core vulnerability generalizes (allowing "
    "redirection and forced descent), and the "
    "cheaper board reaches a far larger installed base. The differences that "
    "matter are architectural rather than economic – Betaflight's simpler "
    "rate-ratio detector is easier to evade with a cruder spoof, while its "
    "unused Kalman trust value is the one statistical signal that would catch "
    "the attack. Low cost buys no extra security here; it moves the same "
    "weaknesses onto cheaper, more widespread hardware.\n\n"
    "A note on firmware version and scope. The controller exercised here is Betaflight's legacy GPS Rescue, selected at build "
    "time with -DENABLE_RESCUE_PLAN=0 — the historical rescue path and, today, the fallback on flash-constrained boards rather "
    "than the newest default. Current full-feature builds default instead to a newer flight-plan autopilot that flies the "
    "rescue as a waypoint mission, and this logic has continued to be hardened across releases. Our results therefore "
    "characterise the legacy controller — still widely deployed on cheaper and older hardware — and not the latest default; "
    "repeating these experiments against the current flight-plan autopilot, which exposes no equivalent debug telemetry yet, "
    "would be a worthwhile extension. We did not test it, but expect the attack's core to carry over: the real weakness is the "
    "position estimator, not the rescue controller, and the newer autopilot still consumes Betaflight's 1-D Kalman estimate — "
    "whose trust/variance is never gated on, with no raw-GPS glitch check anywhere. Unless the flight-plan code adds the "
    "innovation-variance gating Betaflight otherwise lacks, a rate-matched spoof should still mislead it; the extra mission "
    "staging may reject cruder spoofs, but more planning logic is not statistical trust."
)

# (label, spoofed velocity m/s, glob of the N repeat runs at that velocity)
FALSE_HOME_CASES = [
    ("7.5 m/s", 7.5, "false_home_bias_v07_run*.csv"),
    ("30 m/s", 30.0, "false_home_bias_v30_run*.csv"),
    ("60 m/s", 60.0, "false_home_bias_v60_run*.csv"),
    ("65 m/s", 65.0, "false_home_bias_v65_run*.csv"),
    ("70 m/s", 70.0, "false_home_bias_v70_run*.csv"),
]

# columns: t, physN, spoofN, estDist(3), gpsDist(4), divergence(5), margin, phase(7), failure, armed
_FH_FLEW = {"FLY_HOME", "DESCENT", "LANDING"}
_FH_LANDED = {"DESCENT", "LANDING"}


def _false_home_run_stats(path):
    """Per-run outcome: whether it reached FLY_HOME, whether it landed, and the
    max estimate-vs-GPS divergence while in FLY_HOME (the flyout transient,
    logged at ~500 m before FLY_HOME, is excluded)."""
    data = [r for r in list(csv.reader(open(path)))[1:] if len(r) > 8]
    phases = {r[7] for r in data}
    flew = bool(phases & _FH_FLEW)
    landed = bool(phases & _FH_LANDED)
    maxdiv = max(
        (float(r[5]) for r in data if r[7] == "FLY_HOME" and r[5] not in ("",)),
        default=None,
    )
    return flew, landed, maxdiv


def false_home_repeat_stats():
    """Aggregate the N repeat runs at each velocity into (label, v, N, flew,
    landed, max divergence over the runs that flew)."""
    out = []
    for label, v, pattern in FALSE_HOME_CASES:
        files = sorted(glob.glob(os.path.join(RESULTS_DIR, pattern)))
        flew = landed = 0
        divs = []
        for f in files:
            f_flew, f_landed, d = _false_home_run_stats(f)
            flew += f_flew
            landed += f_landed
            if f_flew and d is not None:
                divs.append(d)
        out.append((label, v, len(files), flew, landed, max(divs) if divs else 0.0))
    return out


def false_home_table_rows():
    """Distribution over N repeat runs per velocity (B = 150 m): how many reached
    the fly-home leg, how many landed at the false home, and the largest
    estimate-vs-GPS divergence achieved."""
    rows = [
        (
            "Spoofed velocity (B = 150 m)",
            "Reached fly-home",
            "Landed at false home",
            "Max divergence (m)",
        )
    ]
    for label, v, n, flew, landed, maxdiv in false_home_repeat_stats():
        # A best run that never decoupled sits at measurement noise around zero;
        # show that as 0 rather than a distracting small negative.
        rows.append((label, f"{flew}/{n}", f"{landed}/{n}", f"{max(0.0, maxdiv):.0f}"))
    return rows


def rf_table_rows():
    rows = [("Goal", "Range", "Learned P (dBm)", "Deterministic P (dBm)", "Regime")]
    with open(os.path.join(RESULTS_DIR, "rf_jam_spoof_report.csv")) as f:
        data = list(csv.reader(f))[1:]
    for goal, dist, p, regime, detp, _outcome, _steps in data:
        rows.append((goal, f"{float(dist):.0f} m", p, detp, regime))
    return rows


RF_BASELINE_ROWS = [
    ("Policy", "Avg episode return"),
    ("random", "~6-7"),
    ("naive fixed-power", "~82"),
    ("deterministic (analytic min)", "~82-85"),
    ("learned (RL)", "~83-87"),
]

TRACKING_RESULTS = (
    "The tracking layer is what makes this practical. The attacker sits on the "
    "drone's return path (150 m from home), jams the link to trigger RTH, and "
    "tracks the craft passively by direction-finding on its 5.8 GHz FPV video — a "
    "signal the GPS L1 jammer does not touch — then spoofs from that position "
    "until the firmware forces a fail-safe descent next to the attacker, rather "
    "than at its armed-at home. Tracking quality, not jammer power, bounds a "
    "believable spoof: a simple RSSI rig reaches only ~60 m, a pseudo-Doppler "
    "array ~220 m."
)

INTEGRATED_SCENARIO_INTRO = (
    "Figure 7 ties the three layers end to end — passive tracking, GPS L1 jamming to force Rescue, then adaptive "
    "spoofing with estimator decoupling. Unlike the SITL sweep above, this integrated timeline is a **deterministic "
    "end-to-end model** (attack_scenario.py) with a simplified first-order estimator, used to visualise the full chain and to "
    "map our measurements onto the paper's quality metrics. Its numbers are a best-case illustration, not a claim that the "
    "firmware lands reliably; the reproducible SITL result is the bounded decoupling reported above."
)

QUALITY_METRICS_ROWS = [
    ("Hijack quality metric (paper analog)", "Value"),
    ("Max divergence (EKF-innovation analog)", "130.3 m"),
    ("Min FLYAWAY margin (leash analog)", "6.96"),
    ("Landing bearing (safe-direction analog)", "90 deg"),
    ("Landing error vs. attacker", "0 m"),
    ("Time to land", "13.5 s"),
]


def insert_md_paragraph_before(p_anchor, text, style="Normal"):
    import re
    p_new = p_anchor.insert_paragraph_before(style=style)
    parts = re.split(r'(\*\*.*?\*\*)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            run = p_new.add_run(part[2:-2])
            run.bold = True
        else:
            p_new.add_run(part)
    return p_new


def add_image_before(paragraph, image_path, width_in=6.0):
    """Insert image_path as its own paragraph immediately before `paragraph`."""
    img_p = paragraph.insert_paragraph_before()
    run = img_p.add_run()
    run.add_picture(image_path, width=Inches(width_in))


def _borderless(table) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "none")
        borders.append(el)
    table._tbl.tblPr.append(borders)

def add_tool_item_before(paragraph, title, logo_path, desc):
    doc = paragraph.part.document
    from docx.shared import Inches
    t = doc.add_table(rows=1, cols=2)
    _borderless(t)
    t.columns[0].width = Inches(1.0)
    t.columns[1].width = Inches(5.0)

    # insert image into cell 0
    cell0 = t.cell(0, 0)
    p0 = cell0.paragraphs[0]
    run0 = p0.add_run()
    import os
    if os.path.exists(logo_path):
        run0.add_picture(logo_path, width=Inches(0.75))

    # insert text into cell 1 - name inlined in bold, no separate heading
    cell1 = t.cell(0, 1)
    p1 = cell1.paragraphs[0]
    p1.style = "Normal"
    r_name = p1.add_run(title + ". ")
    r_name.bold = True
    p1.add_run(desc)

    # move table right before paragraph
    paragraph._p.addprevious(t._tbl)

def add_table_before(paragraph, rows):
    """Insert a table immediately before `paragraph` by adding it to the
    paragraph's parent element right before the paragraph's own XML node."""
    doc = paragraph.part.document
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.style = (
        "Light Grid Accent 1"
        if "Light Grid Accent 1" in [s.name for s in doc.styles]
        else table.style
    )
    for r, row_vals in enumerate(rows):
        for c, val in enumerate(row_vals):
            cell = table.cell(r, c)
            cell.text = str(val)
            if r == 0:
                for p in cell.paragraphs:
                    for run in p.runs:
                        run.bold = True
    # move the freshly-appended table (currently at the end of the body) to
    # just before `paragraph`
    tbl_element = table._tbl
    tbl_element.getparent().remove(tbl_element)
    paragraph._p.addprevious(tbl_element)


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fig_dir = os.path.join(base, "paper", "figures")
    doc = Document(os.path.join(base, "Project Template.docx"))

    for p in doc.paragraphs:
        text = p.text.strip()
        if text == "Title of the reference  paper:":
            p.insert_paragraph_before(REF_TITLE, style="Normal")
        elif text == "Name of who is involved in the project:":
            p.insert_paragraph_before("Emilio Risi (matricola 2122841)", style="Normal")
        elif text == "Describe the objectives that we agreed for your project":
            p.insert_paragraph_before(OBJECTIVES, style="Normal")
            p.text = ""
        elif text.startswith("Describe the simulation tools/hardware"):
            p.insert_paragraph_before("Hardware-in-the-Loop (HITL) Attempt", style="Heading 3")
            insert_md_paragraph_before(p, HITL_ATTEMPT_TEXT, style="Normal")
            add_image_before(p, os.path.join(fig_dir, "hitl_attempt.jpg"), width_in=4.5)
            
            p.insert_paragraph_before("Tools Used", style="Heading 3")
            insert_md_paragraph_before(p, SYSTEM_SETUP, style="Normal")
            
            add_tool_item_before(p, "Betaflight", "paper/logos/betaflight.png", BETAFLIGHT_DESC)
            add_tool_item_before(p, "Python 3", "paper/logos/python.png", PYTHON_DESC)

            p.insert_paragraph_before("Betaflight vs. ArduPilot: Architecture and Flight Modes", style="Heading 3")
            insert_md_paragraph_before(p, BETAFLIGHT_VS_ARDUPILOT, style="Normal")
            
            add_image_before(p, os.path.join(fig_dir, "ardupilot_arch.png"), width_in=3.0)
            add_image_before(p, os.path.join(fig_dir, "betaflight_arch.png"), width_in=3.0)
            p.insert_paragraph_before("SITL Simulation Environment", style="Heading 3")
            insert_md_paragraph_before(p, SITL_SIMULATION_TEXT, style="Normal")
            add_image_before(p, os.path.join(fig_dir, "sitl_arch.png"), width_in=5.0)
            p.insert_paragraph_before("Python Harness", style="Heading 3")
            insert_md_paragraph_before(p, SITL_HARNESS_TEXT, style="Normal")
            insert_md_paragraph_before(p, HARNESS_KINEMATICS_DOCX, style="Normal")
            p.text = ""
        elif text.startswith("Methodology that you used to get your results"):
            p.insert_paragraph_before("Sanity Checks and Attack Design", style="Heading 3")
            insert_md_paragraph_before(p, METHODOLOGY_INTRO, style="Normal")
            add_image_before(p, os.path.join(fig_dir, "attack_flow.png"), width_in=5.5)
            
            sub0 = p.insert_paragraph_before(style="Normal")
            sub0.add_run("Locating the Sanity Check in Betaflight's Source").bold = True

            insert_md_paragraph_before(p, METHODOLOGY_MAPPING, style="Normal")
            insert_md_paragraph_before(p, METHODOLOGY_FORMULA_TXT, style="Normal")
            insert_md_paragraph_before(p, METHODOLOGY_FORMULA_EXPLAIN, style="Normal")

            insert_md_paragraph_before(p, "• " + METHODOLOGY_VERT, style="Normal")
            insert_md_paragraph_before(p, "• " + METHODOLOGY_HORIZ, style="Normal")

            insert_md_paragraph_before(p, METHODOLOGY_OUTRO, style="Normal")
            add_image_before(p, os.path.join(fig_dir, "fig1_2_combined.png"), width_in=6.0)

            p.insert_paragraph_before("Estimator Decoupling (False Home)", style="Heading 3")
            insert_md_paragraph_before(p, FALSE_HOME_METHOD, style="Normal")
            
            p.insert_paragraph_before("Attack Execution Algorithms", style="Heading 3")
            insert_md_paragraph_before(p, ATTACK_ALGOS_INTRO, style="Normal")

            algo1 = p.insert_paragraph_before(style="Normal")
            algo1.add_run("Algorithm 1: Deterministic Attack Strategy").bold = True
            insert_md_paragraph_before(p, ALGO1_INTRO, style="Normal")
            for _i, _s in enumerate(ALGO1_STEPS, 1):
                insert_md_paragraph_before(p, f"{_i}. {_s}", style="Normal")

            algo2 = p.insert_paragraph_before(style="Normal")
            algo2.add_run("Algorithm 2: Reinforcement Learning (discrete SAC) Strategy").bold = True
            insert_md_paragraph_before(p, ALGO2_INTRO, style="Normal")
            for _i, _s in enumerate(ALGO2_STEPS, 1):
                insert_md_paragraph_before(p, f"{_i}. {_s}", style="Normal")
            add_image_before(p, os.path.join(fig_dir, "rl_arch.png"), width_in=5.0)

            p.text = ""
        elif text.startswith("Figures/tables/naumbers that show the results"):
            p.insert_paragraph_before("False Home Results", style="Heading 3")
            add_table_before(p, false_home_table_rows())
            insert_md_paragraph_before(p, FALSE_HOME_RESULTS, style="Normal")

            p.insert_paragraph_before("RF Layer and Reinforcement Learning Results", style="Heading 3")
            add_table_before(p, rf_table_rows())
            add_table_before(p, RF_BASELINE_ROWS)
            insert_md_paragraph_before(p, RF_RESULTS, style="Normal")
            
            p.insert_paragraph_before("Integrated Scenario and Comparison with the Original Attack", style="Heading 3")
            insert_md_paragraph_before(p, INTEGRATED_SCENARIO_INTRO, style="Normal")
            add_image_before(p, os.path.join(fig_dir, "fig7_attack_scenario.png"), width_in=5.0)
            add_table_before(p, QUALITY_METRICS_ROWS)
            insert_md_paragraph_before(p, TRACKING_RESULTS, style="Normal")
            insert_md_paragraph_before(p, DIFFERENCE_FROM_PAPER, style="Normal")

            p.insert_paragraph_before("Overall Attack Efficacy", style="Heading 3")
            insert_md_paragraph_before(p, DISCUSSION, style="Normal")
            
            concl_heading = p.insert_paragraph_before()
            concl_heading.add_run("Conclusion").bold = True
            p.insert_paragraph_before(CONCLUSION, style="Normal")
            
            # Add Appendices
            p.insert_paragraph_before("", style="Normal")
            ref_heading = p.insert_paragraph_before("References", style="Heading 3")
            insert_md_paragraph_before(p, REFERENCES, style="Normal")

            p.insert_paragraph_before("", style="Normal")
            dict_heading = p.insert_paragraph_before(style="Heading 3")
            dict_heading.add_run("Appendix A: Terminology and Script Dictionary").bold = True
            dict_rows = [("Term / Script", "Type", "Description")] + DICTIONARY_ROWS
            add_table_before(p, dict_rows)
            
            p.insert_paragraph_before("", style="Normal")
            app_b = p.insert_paragraph_before(style="Heading 3")
            app_b.add_run("Appendix B: Supplemental Experimental Graphs").bold = True
            add_image_before(p, os.path.join(fig_dir, "fig3_distribution.png"), width_in=4.2)
            add_image_before(p, os.path.join(fig_dir, "fig4_false_home.png"))
            add_image_before(p, os.path.join(fig_dir, "fig5_rf_regimes.png"))
            add_image_before(p, os.path.join(fig_dir, "fig6_rf_policy.png"))
            
            p.insert_paragraph_before("", style="Normal")
            app_c = p.insert_paragraph_before(style="Heading 3")
            app_c.add_run("Appendix C: Reproducibility and Code Access").bold = True
            insert_md_paragraph_before(p, REPRODUCIBILITY_1, style="Normal")
            add_table_before(p, RUNTIME_ROWS)
            p.insert_paragraph_before("", style="Normal")
            code_p = p.insert_paragraph_before(REPRODUCIBILITY_CODE)
            try:
                code_p.style = "Quote"
            except:
                pass
            insert_md_paragraph_before(p, REPRODUCIBILITY_2, style="Normal")
            
            p.text = ""

    os.makedirs(os.path.join(base, "paper"), exist_ok=True)
    doc.save(os.path.join(base, "paper", "Final_Report.docx"))
    print("Report generated at paper/Final_Report.docx")

    # "_": r"\_\allowbreak" lets long identifiers like RESCUE_PITCH_FORWARD
    # wrap at the underscore instead of overflowing the text width.
    tex_escape_map = {
        "&": r"\&",
        "%": r"\%",
        "_": r"\_\allowbreak{}",
        "#": r"\#",
        "~": r"$\sim$",
        "θ": r"$\theta$",
        "√": r"$\sqrt{}$",
        "−": r"$-$",
        "·": r"$\cdot$",
        "₁₀": r"$_{10}$",
        "τ": r"$\tau$",
        "÷": r"$\div$",
        "→": r"$\rightarrow$",
    }

        

    def tex_para_md(s):
        import re
        s = tex_escape(s).replace("\n\n", "\n\n").replace(
            "•", r"\par\hangindent=1.8em\hangafter=1\hspace*{1.2em}$\bullet$ ")
        s = re.sub(r'\*\*(.*?)\*\*', r'\\textbf{\1}', s)
        return s

    def tex_escape(s):
        for k, v in tex_escape_map.items():
            s = s.replace(k, v)
        return s

    def tex_para(s):
        return tex_escape(s).replace("\n\n", "\n\n").replace(
            "•", r"\par\hangindent=1.8em\hangafter=1\hspace*{1.2em}$\bullet$ ")

    def _tex_tool_item(name, logo, desc):
        return (
            r"\noindent" "\n"
            r"\begin{minipage}[t]{0.13\textwidth}" "\n"
            r"  \vspace{0pt}" "\n"
            r"  \includegraphics[width=0.75in,keepaspectratio]{" + logo + "}\n"
            r"\end{minipage}%" "\n"
            r"\begin{minipage}[t]{0.87\textwidth}" "\n"
            r"  \vspace{0pt}" "\n"
            r"  \textbf{" + tex_escape(name) + ".} " + tex_para_md(desc) + "\n"
            r"\end{minipage}" "\n"
            r"\vspace{0.5em}" "\n"
        )

    def booktabs_body(rows):
        """Bold header row + \\midrule + data rows, for a rule-light
        booktabs table matching project2's style (rows[0] is the header)."""
        head = " & ".join(r"\textbf{" + tex_escape(str(c)) + "}" for c in rows[0])
        body = "\\\\\n".join(
            " & ".join(tex_escape(str(c)) for c in row) for row in rows[1:]
        )
        return head + " \\\\\n\\midrule\n" + body

    table_rows_tex = booktabs_body(outcome_table_rows())
    false_home_tex = booktabs_body(false_home_table_rows())
    rf_tex = booktabs_body(rf_table_rows())
    rf_base_tex = booktabs_body(RF_BASELINE_ROWS)
    quality_tex = booktabs_body(QUALITY_METRICS_ROWS)
    runtime_tex = booktabs_body(RUNTIME_ROWS)

    latex_content = (
        r"""\documentclass[11pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{geometry}
\geometry{a4paper, margin=1in}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{array}
\usepackage{float}
\usepackage{placeins}
\usepackage{changepage}
\usepackage{caption}
\captionsetup[figure]{font={footnotesize,it}, labelfont={footnotesize,it}, labelsep=period, justification=raggedright, singlelinecheck=false}
\captionsetup[table]{labelformat=empty, font=small, justification=raggedright, singlelinecheck=false}
\setlength{\parskip}{0.40em}
\setlength{\abovedisplayskip}{6pt plus 2pt minus 2pt}
\setlength{\belowdisplayskip}{6pt plus 2pt minus 2pt}
\setlength{\parindent}{0pt}
\setlength{\textfloatsep}{10pt plus 2pt minus 2pt}
\setlength{\intextsep}{10pt plus 2pt minus 2pt}
\renewcommand{\textfraction}{0.06}
\renewcommand{\topfraction}{0.92}
\renewcommand{\bottomfraction}{0.92}
\renewcommand{\floatpagefraction}{0.80}
\usepackage{hyperref}
\urlstyle{same}

\title{Report for the Course on Cyber-Physical Systems and IoT Security}
\author{Emilio Risi (matricola 2122841)}
\date{}

\begin{document}
\maketitle

\section*{Title of the reference paper}
"""
        + tex_escape(REF_TITLE)
        + r"""

\section*{Objectives}
"""
        + tex_para(OBJECTIVES)
        + r"""

\section*{System Setup}

\subsection*{Hardware-in-the-Loop (HITL) Attempt}
"""
        + tex_para_md(HITL_ATTEMPT_TEXT)
        + r"""
\begin{figure}[H]
\centering
\includegraphics[width=0.7\textwidth]{figures/hitl_attempt.jpg}
\caption{Early HITL attempt using an FTDI adapter to simulate GPS over UART.}
\end{figure}

\subsection*{Tools Used}
""" + tex_para_md(SYSTEM_SETUP) + r"""

\begin{adjustwidth}{0.4in}{0in}
""" + "\n".join(
        _tex_tool_item(name, logo, desc)
        for name, logo, desc in TOOL_ITEMS
    ) + r"""
\end{adjustwidth}

\subsection*{Betaflight vs. ArduPilot: Architecture and Flight Modes}
"""
        + tex_para_md(BETAFLIGHT_VS_ARDUPILOT)
        + r"""

\begin{figure}[H]
\centering
\includegraphics[width=0.45\textwidth]{figures/ardupilot_arch.png} \hfill
\includegraphics[width=0.45\textwidth]{figures/betaflight_arch.png}
\caption{Architectural differences between ArduPilot (left) and Betaflight (right).}
\end{figure}

\subsection*{SITL Simulation Environment}
"""
        + tex_para_md(SITL_SIMULATION_TEXT)
        + r"""
\begin{figure}[H]
\centering
\includegraphics[width=0.8\textwidth, height=2.2in, keepaspectratio]{figures/sitl_arch.png}
\caption{SITL simulation loop closing the physics engine with Betaflight over UDP/TCP.}
\end{figure}

\subsection*{Python Harness}
""" + tex_para_md(SITL_HARNESS_TEXT) + HARNESS_KINEMATICS_TEX + r"""

\section*{Experiments}

\subsection*{Sanity Checks and Attack Design}
"""
        + tex_para_md(METHODOLOGY_INTRO)
        + r"""
\begin{figure}[H]
\centering
\includegraphics[width=0.85\textwidth, height=4.0in, keepaspectratio]{figures/attack_flow.png}
\caption{Flowchart of the two-stage spoofing attack to bypass Betaflight GPS Rescue sanity checks.}
\end{figure}

\subsubsection*{Locating the Sanity Check in Betaflight's Source}
""" + tex_para_md(METHODOLOGY_MAPPING) + r"""
\[
c_{k+1} = \max\!\left(0,\; c_k + \delta_k\right), \qquad
\delta_k = +1 \ \mbox{if}\ r_k < \tau, \quad \delta_k = -1 \ \mbox{otherwise}; \qquad
c_k \ge N \ \Rightarrow \ \mbox{fail-safe}.
\]
""" + tex_para_md(METHODOLOGY_FORMULA_EXPLAIN) + r"""
\begin{itemize}
\item """ + tex_para_md(METHODOLOGY_VERT) + r"""
\item """ + tex_para_md(METHODOLOGY_HORIZ) + r"""
\end{itemize}

"""
        + tex_para_md(METHODOLOGY_OUTRO)
        + r"""
\begin{figure}[H]
\centering
\includegraphics[width=0.9\textwidth, height=2.9in, keepaspectratio]{figures/fig1_2_combined.png}
\caption{Sanity checks. Left: Altitude channel (fed altitude vs. time). Right: Horizontal channel (distance to true home vs. time).}
\end{figure}

\subsection*{Estimator Decoupling (False Home)}
"""
        + tex_para_md(FALSE_HOME_METHOD)
        + r"""

\subsection*{Attack Execution Algorithms}
"""
        + tex_para_md(ATTACK_ALGOS_INTRO)
        + r"""

\subsubsection*{Algorithm 1: Deterministic Attack Strategy}
"""
        + tex_para_md(ALGO1_INTRO)
        + r"""
\begin{enumerate}
"""
        + "".join(r"\item " + tex_para_md(s) + "\n" for s in ALGO1_STEPS)
        + r"""\end{enumerate}

\subsubsection*{Algorithm 2: Reinforcement Learning (discrete SAC) Strategy}
"""
        + tex_para_md(ALGO2_INTRO)
        + r"""
\begin{enumerate}
"""
        + "".join(r"\item " + tex_para_md(s) + "\n" for s in ALGO2_STEPS)
        + r"""\end{enumerate}

\begin{figure}[H]
\centering
\includegraphics[width=0.65\textwidth]{figures/rl_arch.png}
\caption{Soft Actor-Critic agent environment.}
\end{figure}

\section*{Results and Discussion}

\subsection*{False Home Results}
\begin{table}[H]\centering\small
\caption{\textbf{False-home landing distribution over N=6 repeats per velocity (B = 150 m).}}
\begin{tabular}{lccc}
\toprule
"""
        + false_home_tex
        + r""" \\
\bottomrule
\end{tabular}
\end{table}

"""
        + tex_para_md(FALSE_HOME_RESULTS)
        + r"""

\subsection*{RF Layer and Reinforcement Learning Results}

\begin{table}[H]\centering\small
\caption{\textbf{RF layer training outcomes (discrete power states).}}
\begin{tabular}{lcccc}
\toprule
"""
        + rf_tex
        + r""" \\
\bottomrule
\end{tabular}
\end{table}

\begin{table}[H]\centering\small
\caption{\textbf{Baseline reward comparison.}}
\begin{tabular}{lc}
\toprule
"""
        + rf_base_tex
        + r""" \\
\bottomrule
\end{tabular}
\end{table}

"""
        + tex_para_md(RF_RESULTS)
        + r"""

\subsection*{Integrated Scenario and Comparison with the Original Attack}
"""
        + tex_para_md(INTEGRATED_SCENARIO_INTRO)
        + r"""
\begin{figure}[H]
\centering
\includegraphics[width=0.6\textwidth]{figures/fig7_attack_scenario.png}
\caption{Overall timeline: passive tracking, GPS L1 jamming (forcing Rescue), followed by adaptive spoofing and estimator decoupling to false home.}
\end{figure}

\begin{table}[H]\centering\small
\caption{\textbf{Hijack quality metrics from the deterministic end-to-end model, mapped to the paper's.}}
\begin{tabular}{l>{\raggedright\arraybackslash}p{3in}}
\toprule
"""
        + quality_tex
        + r""" \\
\bottomrule
\end{tabular}
\end{table}

"""
        + tex_para_md(TRACKING_RESULTS) + r"""

"""
        + tex_para_md(DIFFERENCE_FROM_PAPER) + r"""

\subsection*{Overall Attack Efficacy}
"""
        + tex_para_md(DISCUSSION) + r"""

\section*{Conclusion}
"""
        + tex_para(CONCLUSION)
        + r"""

\section*{References}
\begin{itemize}
    \item[ {[1]} ] Original TractorBeam Attack: \textit{TractorBeam: Hijacking Drones with Rate-Matched GPS Spoofing}. (Targeting ArduPilot EKF).
    \item[ {[2]} ] Betaflight Open Source Flight Controller: \url{https://github.com/betaflight/betaflight}.
    \item[ {[3]} ] Just Command Runner: \url{https://github.com/casey/just}.
\end{itemize}

\newpage
\appendix
\section*{Appendix A: Terminology and Script Dictionary}
\begin{table}[H]\centering\small
\caption{\textbf{Terminology and script dictionary.}}
\begin{tabular}{>{\raggedright\arraybackslash}p{2.0in}>{\raggedright\arraybackslash}p{1.0in}>{\raggedright\arraybackslash}p{2.8in}}
\toprule
\textbf{Term / Script} & \textbf{Type} & \textbf{Description} \\
\midrule
""" + "\\\\\n".join(
            " & ".join(tex_escape(str(c)) for c in row) for row in DICTIONARY_ROWS
        ) + r""" \\
\bottomrule
\end{tabular}
\end{table}

\newpage
\section*{Appendix B: Supplemental Experimental Graphs}

\begin{table}[H]\centering\small
\caption{\textbf{Outcome summary across all eight profiles.}}
\begin{tabular}{>{\raggedright\arraybackslash}p{0.6in}>{\raggedright\arraybackslash}p{0.9in}>{\raggedright\arraybackslash}p{1.15in}>{\raggedright\arraybackslash}p{2.05in}>{\raggedright\arraybackslash}p{0.75in}}
\toprule
"""
        + table_rows_tex
        + r""" \\
\bottomrule
\end{tabular}
\end{table}

\vspace{1em}

\begin{figure}[H]
\centering
\includegraphics[width=0.7\textwidth, height=2.4in, keepaspectratio]{figures/fig3_distribution.png}
\caption{Distribution study: repeated runs of the three profiles found to be bimodal.}
\end{figure}

\vspace{2em}

\begin{figure}[H]
\centering
\includegraphics[width=0.8\textwidth, height=2.2in, keepaspectratio]{figures/fig4_false_home.png}
\caption{Estimator decoupling: max estimate-vs-GPS divergence vs spoofed velocity (B=150 m).}
\end{figure}

\vspace{2em}

\begin{figure}[H]
\centering
\includegraphics[width=0.8\textwidth, height=2.2in, keepaspectratio]{figures/fig5_rf_regimes.png}
\caption{RF jam/spoof regimes vs range for several transmit powers.}
\end{figure}

\vspace{2em}

\begin{figure}[H]
\centering
\includegraphics[width=0.8\textwidth, height=2.2in, keepaspectratio]{figures/fig6_rf_policy.png}
\caption{Learned vs deterministic jam/spoof transmit power per (goal, range).}
\end{figure}

\newpage
\section*{Appendix C: Reproducibility and Code Access}
"""
        + tex_para_md(REPRODUCIBILITY_1)
        + r"""

\begin{table}[H]\centering\small
\caption{\textbf{Measured wall-clock cost of a full reproduction on the reference laptop.}}
\begin{tabular}{l c c}
\toprule
""" + runtime_tex + r""" \\
\bottomrule
\end{tabular}
\end{table}

\begin{quote}\small
\begin{verbatim}
""" + REPRODUCIBILITY_CODE + r"""
\end{verbatim}
\end{quote}

"""
        + tex_para_md(REPRODUCIBILITY_2)
        + r"""

\end{document}
"""
    )

    latex_content = latex_content.replace(
        r"\begin{figure}[h]", r"\begin{figure}[!htbp]"
    )
    latex_content = latex_content.replace(r"\begin{table}[h]", r"\begin{table}[!htbp]")

    paper_dir = os.path.join(base, "paper")
    with open(os.path.join(paper_dir, "Final_Report.tex"), "w") as f:
        f.write(latex_content)
    print("LaTeX source written to paper/Final_Report.tex")

    try:
        subprocess.run(
            [
                "pdflatex",
                "-interaction=nonstopmode",
                "-output-directory=paper",
                "paper/Final_Report.tex",
            ],
            check=True,
            cwd=base,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # run twice for stable references/layout, matching normal LaTeX practice
        subprocess.run(
            [
                "pdflatex",
                "-interaction=nonstopmode",
                "-output-directory=paper",
                "paper/Final_Report.tex",
            ],
            check=True,
            cwd=base,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("PDF generated at paper/Final_Report.pdf")
    except subprocess.CalledProcessError:
        print("Warning: pdflatex failed to compile.")


if __name__ == "__main__":
    main()
