"""Builds the figures used in the project report (paper/Final_Report.*) directly
from the SITL experiment results in results/, so the
report always reflects the actual collected data rather than transcribed numbers.

Figure style deliberately mirrors the reference paper's own plots (Tractor Beam,
Figs. 5/9/13/14): monochrome, thin full-frame axes, no background grid, markers
(not color) distinguishing categories, open circles for individual data points.

Run with the project's .venv: .venv/bin/python3 make_figures.py
"""

import csv
import glob
import os
import subprocess
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
FIG_DIR = os.path.join(PROJECT_ROOT, "paper", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

# --- visual style ---------------------------------------------------------------
# Okabe-Ito qualitative palette: colourblind-safe and print-legible. Used as the
# default line cycle and for the semantic accept/reject/mixed colours below.
OKABE_ITO = [
    "#0072B2",  # blue
    "#E69F00",  # orange
    "#009E73",  # green
    "#D55E00",  # vermillion
    "#CC79A7",  # purple
    "#56B4E9",  # sky blue
    "#F0E442",  # yellow
    "#000000",  # black
]

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.size": 10,
        "axes.edgecolor": "#333333",
        "axes.linewidth": 0.9,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": "#D9D9D9",
        "grid.linewidth": 0.6,
        "axes.prop_cycle": plt.cycler(color=OKABE_ITO),
        "axes.spines.top": True,
        "axes.spines.right": True,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "legend.frameon": True,
        "legend.edgecolor": "#333333",
        "legend.fancybox": False,
    }
)

BLACK = "#000000"
GREY = "#6B7280"
DASH = (0, (5, 3))

# Semantic colours: green = spoof accepted (attack succeeds), red = rejected
# (fail-safe fires), amber = bimodal/near-threshold. Marker shape ALSO encodes
# the category, so the figures still read correctly in greyscale.
ACCEPT = "#009E73"
REJECT = "#D55E00"
MIXED = "#E69F00"
STYLES = {
    "reject": dict(color=REJECT, marker="s", markersize=4, markerfacecolor="white"),
    "accept": dict(color=ACCEPT, marker="o", markersize=4, markerfacecolor=ACCEPT),
    "mixed": dict(color=MIXED, marker="^", markersize=5, markerfacecolor="white"),
}


def read_csv_rows(path):
    with open(path) as f:
        rows = list(csv.reader(f))
    header, data, result_row = rows[0], rows[1:-1], rows[-1]
    return header, data, result_row


def path_for(name):
    return os.path.join(RESULTS_DIR, name)


# --- Figure 1: altitude channel -------------------------------------------------
def fig_altitude():
    """adaptive's plotted line is one of six repeated runs (run1, the majority
    ~5/6 outcome) - like partial, it is bimodal (see Figure 3), so this single
    line is representative, not exhaustive."""
    profiles = [
        ("altitude_gate_static.csv", "static (0%)", "reject", "-"),
        ("altitude_gate_slow.csv", "slow (8%)", "reject", "--"),
        ("altitude_gate_adaptive_run1.csv", "adaptive (110%)", "accept", "-"),
    ]
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    for fname, label, outcome, ls in profiles:
        _, data, result_row = read_csv_rows(path_for(fname))
        t = [float(r[0]) for r in data]
        alt = [float(r[2]) for r in data]
        style = STYLES[outcome]
        ax.plot(t, alt, linestyle=ls, linewidth=1.1, markevery=3, label=label, **style)
        ax.scatter(
            [t[-1]],
            [alt[-1]],
            s=40,
            facecolor=style["markerfacecolor"],
            edgecolor="black",
            linewidth=0.9,
            zorder=5,
        )

    ax.axhline(110, color=GREY, linestyle=DASH, linewidth=1)
    ax.text(
        0.3, 113, "return-altitude target ($\\approx$110 m)", fontsize=8, color=GREY
    )
    ax.text(
        0.97,
        0.75,
        "adaptive: 1 of 6 repeated runs\n(bimodal, see Figure 3)",
        fontsize=7.5,
        color=GREY,
        ha="right",
        va="top",
        transform=ax.transAxes,
    )
    ax.set_xlabel("time since rescue trigger [s]")
    ax.set_ylabel("fed altitude [m]")
    ax.set_title("Altitude channel (RESCUE_ATTAIN_ALT)", fontsize=10)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig1_altitude.png"), dpi=200)
    plt.close(fig)


# --- Figure 2: horizontal channel ------------------------------------------------
def _best_run(pattern, fallback):
    """Pick the repeat run with the most rows (the one that flew longest);
    fall back to a single untagged file if no repeats exist."""
    files = sorted(glob.glob(os.path.join(RESULTS_DIR, pattern)))
    if not files:
        return fallback
    return os.path.basename(max(files, key=lambda f: sum(1 for _ in open(f))))


def fig_horizontal():
    # adaptive-fake-destination is bimodal; show a run that actually flew the
    # spoofed approach so the redirect is visible rather than a stalled point.
    fake_dest = _best_run("horizontal_gate_adaptive-fake-destination_run*.csv",
                          "horizontal_gate_adaptive-fake-destination.csv")
    profiles = [
        ("horizontal_gate_frozen.csv", "frozen", "reject", "-"),
        ("horizontal_gate_naive-jump.csv", "naive jump", "accept", "--"),
        ("horizontal_gate_adaptive-home_run1.csv", "adaptive → home", "accept", "-"),
        (fake_dest, "adaptive → fake dest.", "mixed", "-."),
    ]
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    for fname, label, outcome, ls in profiles:
        _, data, result_row = read_csv_rows(path_for(fname))
        t = [float(r[0]) for r in data]
        dist_home = [float(r[6]) for r in data]
        style = STYLES[outcome]
        ax.plot(
            t, dist_home, linestyle=ls, linewidth=1.1, markevery=6, label=label, **style
        )
        ax.scatter(
            [t[-1]],
            [dist_home[-1]],
            s=40,
            facecolor=style["markerfacecolor"],
            edgecolor="black",
            linewidth=0.9,
            zorder=5,
        )

    ax.axhline(20, color=GREY, linestyle=DASH, linewidth=1)
    ax.text(2, 34, "descentDistanceCm ($\\approx$20 m)", fontsize=8, color=GREY)
    ax.set_xlabel("time since rescue trigger [s]")
    ax.set_ylabel("distance to TRUE home [m]")
    ax.set_title("Horizontal channel (RESCUE_FLYAWAY)", fontsize=10)
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig2_horizontal.png"), dpi=200)
    plt.close(fig)


# --- Figure 3: distribution study ------------------------------------------------
def fig_distribution():
    """Deliberately NOT a box plot (unlike the paper's Figs. 5/13, which box-plot
    a genuinely continuous angular-error spread over ~10 runs). Our repeated runs
    land on exactly one of two fixed values every time (see results/DISTRIBUTION.md)
    - a box plot would misrepresent that as continuous spread it is not. A strip
    plot of the raw per-run values is the honest equivalent here."""
    partial_files = sorted(glob.glob(path_for("altitude_gate_partial_run*.csv")))
    adaptive_files = sorted(glob.glob(path_for("altitude_gate_adaptive_run*.csv")))
    adhome_files = sorted(glob.glob(path_for("horizontal_gate_adaptive-home_run*.csv")))

    partial_outcomes = []
    for fname in partial_files:
        _, _, result_row = read_csv_rows(fname)
        partial_outcomes.append(result_row[3])
    n_reject = sum(1 for o in partial_outcomes if o.startswith("REJECTED"))
    n_accept = len(partial_outcomes) - n_reject

    adaptive_times = []
    for fname in adaptive_files:
        _, _, result_row = read_csv_rows(fname)
        adaptive_times.append(float(result_row[4]))

    adhome_times = []
    for fname in adhome_files:
        _, _, result_row = read_csv_rows(fname)
        adhome_times.append(float(result_row[3]))

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(11.4, 3.8))

    ax1.bar(
        ["rejected\n(STALLED)", "accepted"],
        [n_reject, n_accept],
        color=[REJECT, ACCEPT],
        edgecolor="#333333",
        linewidth=1.1,
        width=0.55,
    )
    for i, v in enumerate([n_reject, n_accept]):
        ax1.text(i, v + 0.1, str(v), ha="center", fontsize=9)
    ax1.set_ylim(0, len(partial_outcomes) + 1)
    ax1.set_ylabel("run count")
    ax1.set_title(
        f"altitude 'partial' (30%)\noutcome, n={len(partial_outcomes)} runs", fontsize=9
    )

    n_a = len(adaptive_times)
    xs_a = [1 + 0.12 * (i - (n_a - 1) / 2) for i in range(n_a)]
    ax2.scatter(
        xs_a,
        adaptive_times,
        s=55,
        facecolor="#0072B2",
        edgecolor="#333333",
        linewidth=1.1,
        zorder=5,
    )
    for val in sorted(set(adaptive_times)):
        ax2.axhline(val, color=GREY, linestyle=DASH, linewidth=0.9)
        ax2.text(
            1.08,
            val,
            f"{val}s",
            fontsize=8,
            color=GREY,
            va="center",
            bbox=dict(facecolor="white", edgecolor="none", pad=1),
        )
    ax2.set_xlim(0.7, 1.6)
    ax2.set_xticks([1])
    ax2.set_xticklabels([f"adaptive (110%)\n(n={n_a} runs)"])
    ax2.set_ylabel("trigger time [s]")
    ax2.set_title("altitude 'adaptive'\ntrigger time, per run", fontsize=9)

    n = len(adhome_times)
    xs = [1 + 0.12 * (i - (n - 1) / 2) for i in range(n)]
    ax3.scatter(
        xs,
        adhome_times,
        s=55,
        facecolor="#0072B2",
        edgecolor="#333333",
        linewidth=1.1,
        zorder=5,
    )
    for val in (69.8, 76.6):
        ax3.axhline(val, color=GREY, linestyle=DASH, linewidth=0.9)
        ax3.text(
            1.08,
            val,
            f"{val}s",
            fontsize=8,
            color=GREY,
            va="center",
            bbox=dict(facecolor="white", edgecolor="none", pad=1),
        )
    ax3.set_xlim(0.7, 1.6)
    ax3.set_xticks([1])
    ax3.set_xticklabels([f"adaptive-home\n(n={len(adhome_times)} runs)"])
    ax3.set_ylabel("time to DESCENT [s]")
    ax3.set_title("horizontal 'adaptive-home'\ntrigger time, per run", fontsize=9)

    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig3_distribution.png"), dpi=200)
    plt.close(fig)


# --- Figure 4: false-home landing (estimator decoupling) ----------------------
def fig_false_home():
    """Distribution of estimator decoupling over N=6 repeat runs per velocity
    (B = 150 m). Each run that reaches the fly-home leg is one point (max
    estimate-vs-GPS divergence); green = it landed at the false home, red = it
    flew home but tripped FLYAWAY first. Runs that stalled in ATTAIN_ALT never
    reach fly-home and are counted separately. Landing needs the estimate to
    cross the 20 m ring, i.e. divergence > B - 20 = 130 m. The dashed guide is
    the first-order-lag prediction, divergence ~ 2.1 s x velocity."""
    cases = [
        (7.5, "false_home_bias_v07_run*.csv"),
        (30.0, "false_home_bias_v30_run*.csv"),
        (60.0, "false_home_bias_v60_run*.csv"),
        (65.0, "false_home_bias_v65_run*.csv"),
        (70.0, "false_home_bias_v70_run*.csv"),
    ]
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    land_v, land_d, fly_v, fly_d = [], [], [], []
    stuck = {}  # velocity -> count of runs that never reached fly-home
    for v, pattern in cases:
        files = sorted(glob.glob(os.path.join(RESULTS_DIR, pattern)))
        stuck[v] = 0
        for i, f in enumerate(files):
            data = list(csv.reader(open(f)))[1:]
            phases = {r[7] for r in data if len(r) > 7}
            if not (phases & {"FLY_HOME", "DESCENT", "LANDING"}):
                stuck[v] += 1
                continue
            maxdiv = max(
                (float(r[5]) for r in data if len(r) > 7 and r[7] == "FLY_HOME" and r[5] != ""),
                default=0.0,
            )
            landed = bool(phases & {"DESCENT", "LANDING"})
            jitter = v + 1.2 * (i - len(files) / 2)
            (land_v if landed else fly_v).append(jitter)
            (land_d if landed else fly_d).append(maxdiv)
    # first-order-lag guide: divergence ~ 2.1 * v (saturating at B = 150)
    vv = [0, 30, 60, 71]
    ax.plot(vv, [min(2.1 * x, 150) for x in vv], color="#0072B2",
            linestyle=DASH, linewidth=1.2, label="2.1 s × v (lag model)", zorder=1)
    ax.scatter(fly_v, fly_d, s=55, facecolor=REJECT, edgecolor="#333333",
               linewidth=0.8, label="flew home, FLYAWAY", zorder=5)
    ax.scatter(land_v, land_d, s=70, marker="*", facecolor=ACCEPT,
               edgecolor="#333333", linewidth=0.8, label="landed at false home", zorder=6)
    ax.axhline(130, color=GREY, linestyle=(0, (1, 1)), linewidth=1)
    ax.text(37, 133, "divergence needed to land (B − 20 = 130 m)",
            fontsize=8, color=GREY)
    # annotate how many runs stalled in ATTAIN_ALT per velocity (stagger the
    # y-offset so the closely-spaced 60/65/70 labels do not overlap)
    for k, (v, pattern) in enumerate(cases):
        if stuck[v]:
            ax.text(v, -13 if k % 2 == 0 else -20,
                    f"{stuck[v]}/6 stalled", fontsize=6.5, color=REJECT,
                    ha="center", va="top")
    ax.set_xlabel("spoofed velocity toward home [m/s]")
    ax.set_ylabel("max estimate↔GPS divergence [m]")
    ax.set_title("Estimator decoupling distribution (B = 150 m, N=6/velocity)", fontsize=10)
    ax.set_ylim(-28, 160)
    ax.legend(loc="upper left", fontsize=7.5)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig4_false_home.png"), dpi=200)
    plt.close(fig)


# --- Figure 5: RF regime bands ---------------------------------------------------
def fig_rf_regimes():
    """Received attacker power vs range for several transmit powers, with the
    three receiver regimes shaded: normal / spoofed / jammed."""
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
    from tractorbeam.rf_sim import (
        received_power_dbm,
        SAT_POWER_DBM,
        CAPTURE_MARGIN_DB,
        JAM_MARGIN_DB,
    )

    dist = [10 * (1.35**i) for i in range(18)]  # 10 m .. ~ 2500 m, log-ish
    tx_powers = [-50, -35, -20, -5]
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    ax.axhspan(
        SAT_POWER_DBM + CAPTURE_MARGIN_DB,
        SAT_POWER_DBM + JAM_MARGIN_DB,
        color="#009E73",
        alpha=0.15,
        zorder=0,
    )
    ax.axhspan(SAT_POWER_DBM + JAM_MARGIN_DB, -60, color="#D55E00", alpha=0.15, zorder=0)
    ax.text(15, -108, "spoofed", fontsize=8, color="#00664c", fontweight="bold")
    ax.text(15, -72, "jammed", fontsize=8, color="#8f3d00", fontweight="bold")
    ax.text(15, -150, "normal", fontsize=8, color="#333333", fontweight="bold")
    for tx in tx_powers:
        rx = [received_power_dbm(tx, d) for d in dist]
        ax.plot(dist, rx, linewidth=1.2, label=f"Tx = {tx} dBm")
    ax.set_xscale("log")
    ax.set_xlabel("attacker-to-drone range [m]")
    ax.set_ylabel("received power at receiver [dBm]")
    ax.set_title("RF jam/spoof regimes (GPS L1, satellites at −130 dBm)", fontsize=10)
    ax.set_ylim(-180, -60)
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig5_rf_regimes.png"), dpi=200)
    plt.close(fig)


# --- Figure 6: learned vs deterministic RF policy ---------------------------------
def fig_rf_policy():
    """Learned (RL) vs deterministic (analytic min) transmit power per
    (goal, distance), from results/rf_jam_spoof_report.csv."""
    rows = list(csv.reader(open(path_for("rf_jam_spoof_report.csv"))))
    data = rows[1:]
    labels = [f"{r[0][:3]}\n{r[1]}m" for r in data]
    learned = [float(r[2]) for r in data]
    det = [float(r[4]) for r in data]
    x = range(len(data))
    w = 0.38
    fig, ax = plt.subplots(figsize=(6.6, 3.8))
    ax.bar(
        [i - w / 2 for i in x],
        learned,
        w,
        color="#0072B2",
        edgecolor="#333333",
        linewidth=1.0,
        label="learned (RL)",
    )
    ax.bar(
        [i + w / 2 for i in x],
        det,
        w,
        color="#E69F00",
        edgecolor="#333333",
        linewidth=1.0,
        label="deterministic (analytic min)",
    )
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=7.5)
    ax.axhline(0, color=GREY, linewidth=0.7)
    ax.set_ylabel("transmit power [dBm]")
    ax.set_title("Learned vs deterministic jam/spoof power", fontsize=10)
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig6_rf_policy.png"), dpi=200)
    plt.close(fig)


def fig_attack_scenario():
    """Full integrated attack: estimator distance-to-home vs time, with the
    jam -> track -> spoof -> land phase transitions and the 20 m landing ring."""
    _, data, _ = read_csv_rows(path_for("attack_scenario.csv"))
    t = [float(r[0]) for r in data]
    est = [float(r[5]) for r in data]
    phase = [r[1] for r in data]
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    # draw the estimate as one line, then annotate phase transitions
    ax.plot(t, est, color="#0072B2", linewidth=1.6, zorder=2)
    # phase boundaries (jam at ~5 s, spoof at ~10 s)
    for ti, label in ((5.0, "jam → RTH"), (10.0, "spoof")):
        if min(t) <= ti <= max(t):
            ax.axvline(ti, color=GREY, linestyle=DASH, linewidth=1, zorder=1)
            ax.text(
                ti + 0.3,
                max(est) * 0.85,
                label,
                fontsize=8,
                color=GREY,
                rotation=90,
                va="top",
            )
    # landing point
    for i in range(len(t)):
        if phase[i] == "LANDING":
            ax.scatter(
                [t[i]],
                [est[i]],
                s=70,
                facecolor="#D55E00",
                edgecolor="#333333",
                linewidth=0.9,
                zorder=5,
            )
            ax.text(
                t[i] - 0.3, est[i] + max(est) * 0.06, "LANDING", fontsize=8, ha="right"
            )
            break
    ax.axhline(20, color=GREY, linestyle=DASH, linewidth=1)
    ax.text(min(t) + 0.3, 24, "landing ring (20 m)", fontsize=8, color=GREY)
    ax.set_xlabel("time [s]")
    ax.set_ylabel("estimate distance-to-home [m]")
    ax.set_title("Integrated attack: jam → track → spoof → land", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig7_attack_scenario.png"), dpi=200)
    plt.close(fig)


def render_dot_diagrams():
    """Render the static architecture diagrams from their Graphviz .dot sources
    (tracked in git) to PNG, so `just clean` + regenerate reproduces them rather
    than relying on hand-made PNGs that a clean would delete."""
    dots = sorted(glob.glob(os.path.join(FIG_DIR, "*.dot")))
    if not dots:
        return
    for dot in dots:
        png = dot[:-4] + ".png"
        try:
            subprocess.run(
                ["dot", "-Tpng", "-Gdpi=150", dot, "-o", png],
                check=True, capture_output=True, text=True,
            )
        except FileNotFoundError:
            print("  WARNING: graphviz 'dot' not found; architecture diagrams "
                  "not regenerated. Install graphviz.", file=sys.stderr)
            return
        except subprocess.CalledProcessError as e:
            print(f"  WARNING: dot failed on {dot}: {e.stderr}", file=sys.stderr)
    print(f"Rendered {len(dots)} architecture diagram(s) from .dot sources")


if __name__ == "__main__":
    render_dot_diagrams()
    fig_altitude()
    fig_horizontal()
    fig_distribution()
    fig_false_home()
    fig_rf_regimes()
    fig_rf_policy()
    fig_attack_scenario()

def merge_sanity_figures():
    """Merge fig1 and fig2 side-by-side for a combined layout."""
    try:
        from PIL import Image
        img1 = Image.open(os.path.join(FIG_DIR, "fig1_altitude.png"))
        img2 = Image.open(os.path.join(FIG_DIR, "fig2_horizontal.png"))
        target_height = max(img1.height, img2.height)
        img1 = img1.resize((int(img1.width * target_height / img1.height), target_height), Image.Resampling.LANCZOS)
        img2 = img2.resize((int(img2.width * target_height / img2.height), target_height), Image.Resampling.LANCZOS)
        total_width = img1.width + img2.width
        new_img = Image.new('RGB', (total_width, target_height), (255, 255, 255))
        new_img.paste(img1, (0, 0))
        new_img.paste(img2, (img1.width, 0))
        new_img.save(os.path.join(FIG_DIR, "fig1_2_combined.png"))
    except ImportError:
        pass

if __name__ == "__main__":
    render_dot_diagrams()
    fig_altitude()
    fig_horizontal()
    fig_distribution()
    fig_false_home()
    fig_rf_regimes()
    fig_rf_policy()
    fig_attack_scenario()
    merge_sanity_figures()
    print(f"Figures written to {FIG_DIR}")
