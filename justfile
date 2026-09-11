# Full reproduction: clean, run every experiment, then build the report.
# This is the complete pipeline every table and figure in the paper depends on.
all: clean simulate false-home rf-rl scenario report

# Compile only the Betaflight SITL firmware (GPS Rescue sanity-check controller).
build-sitl:
	#!/usr/bin/env bash
	set -e
	cd betaflight
	rm -rf obj
	make TARGET=SITL EXTRA_FLAGS="-DENABLE_RESCUE_PLAN=0"

# Clean simulation output and generated report artifacts
clean:
	rm -rf results
	# Only the generated PNGs - keep the .dot architecture-diagram sources
	# (tracked in git; make_figures.py re-renders them to PNG).
	rm -f paper/figures/*.png
	rm -f paper/Final_Report.docx paper/Final_Report.tex paper/Final_Report.pdf
	rm -f paper/Final_Report.aux paper/Final_Report.log
	rm -f betaflight/eeprom.bin
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Run all simulation experiments
simulate:
	#!/usr/bin/env bash
	set -e
	mkdir -p results
	cd betaflight
	# ENABLE_RESCUE_PLAN=0 forces the legacy gps_rescue_multirotor.c sanity-check
	# controller (RESCUE_ATTAIN_ALT/RESCUE_FLYAWAY) - this target's default build
	# (ENABLE_RESCUE_PLAN=1) ships a different, newer flight-plan autopilot that
	# none of these experiments target. `rm -rf obj` forces a full rebuild so a
	# stale object tree from a plain `make TARGET=SITL` can't linger.
	rm -rf obj
	make TARGET=SITL EXTRA_FLAGS="-DENABLE_RESCUE_PLAN=0"
	echo -e "feature GPS\nset gps_provider = VIRTUAL\nset debug_mode = RTH\nset runaway_takeoff_prevention = OFF\naux 0 0 0 1700 2100 0\naux 1 46 1 1700 2100 0\nsave" > sitl_safety.txt
	# The heading-confidence probe reads DEBUG_ATTITUDE slots (gpsHeadingConfidence
	# / canUseGPSHeading), so it needs debug_mode=ATTITUDE instead of RTH; every
	# other experiment uses the RTH config above.
	echo -e "feature GPS\nset gps_provider = VIRTUAL\nset debug_mode = ATTITUDE\nset runaway_takeoff_prevention = OFF\naux 0 0 0 1700 2100 0\naux 1 46 1 1700 2100 0\nsave" > sitl_safety_attitude.txt
	# run_test [<config>.txt] <script> [args...] - config defaults to sitl_safety.txt
	run_test() {
		local cfg="sitl_safety.txt"
		if [[ "${1:-}" == *.txt ]]; then cfg="$1"; shift; fi
		rm -f eeprom.bin
		./obj/main/betaflight_SITL.elf --config "$cfg" > /dev/null 2>&1
		./obj/main/betaflight_SITL.elf > /dev/null 2>&1 &
		PID=$!
		cd ..
		sleep 2
		PYTHONPATH=src uv run python "$@"
		kill -9 $PID 2>/dev/null || true
		wait $PID 2>/dev/null || true
		cd betaflight
	}

	run_test experiments/sanity_check_experiment.py --profile static
	run_test experiments/sanity_check_experiment.py --profile slow
	# adaptive is bimodal too (RESCUE_ATTAIN_ALT->PITCH_FORWARD fires the instant
	# fed altitude crosses maxAltitudeCm+initialClimbCm, and maxAltitudeCm - a
	# running max captured since arming - lands on very different equilibria
	# session to session, e.g. ~117m vs ~209m, a 2.0s vs 13.3s trigger swing).
	# A single run can silently draw the ~1-in-6 rare case, so it's repeated
	# like partial/adaptive-home rather than trusted as one-shot.
	run_test experiments/sanity_check_experiment.py --profile adaptive --tag run1
	run_test experiments/sanity_check_experiment.py --profile adaptive --tag run2
	run_test experiments/sanity_check_experiment.py --profile adaptive --tag run3
	run_test experiments/sanity_check_experiment.py --profile adaptive --tag run4
	run_test experiments/sanity_check_experiment.py --profile adaptive --tag run5
	run_test experiments/sanity_check_experiment.py --profile adaptive --tag run6
	run_test experiments/sanity_check_experiment.py --profile partial --tag run1
	run_test experiments/sanity_check_experiment.py --profile partial --tag run2
	run_test experiments/sanity_check_experiment.py --profile partial --tag run3
	run_test experiments/sanity_check_experiment.py --profile partial --tag run4
	run_test experiments/sanity_check_experiment.py --profile partial --tag run5
	run_test experiments/sanity_check_experiment.py --profile partial --tag run6
	run_test experiments/horizontal_gate_experiment.py --profile frozen
	run_test experiments/horizontal_gate_experiment.py --profile naive-jump
	# adaptive-fake-destination is the redirection attack and is bimodal per SITL
	# process (same ATTAIN_ALT nondeterminism as the false-home sweep), so repeat
	# it N=6 to characterise how often the spoofed approach is followed.
	run_test experiments/horizontal_gate_experiment.py --profile adaptive-fake-destination --tag run1
	run_test experiments/horizontal_gate_experiment.py --profile adaptive-fake-destination --tag run2
	run_test experiments/horizontal_gate_experiment.py --profile adaptive-fake-destination --tag run3
	run_test experiments/horizontal_gate_experiment.py --profile adaptive-fake-destination --tag run4
	run_test experiments/horizontal_gate_experiment.py --profile adaptive-fake-destination --tag run5
	run_test experiments/horizontal_gate_experiment.py --profile adaptive-fake-destination --tag run6
	run_test experiments/horizontal_gate_experiment.py --profile adaptive-home --tag run1
	run_test experiments/horizontal_gate_experiment.py --profile adaptive-home --tag run2
	run_test experiments/horizontal_gate_experiment.py --profile adaptive-home --tag run3
	run_test experiments/horizontal_gate_experiment.py --profile adaptive-home --tag run4
	# Walk-off drift (control vs. attack safe-hijack trajectory)
	run_test experiments/walkoff_experiment.py --mode control
	run_test experiments/walkoff_experiment.py --mode attack
	# Heading-confidence precondition probe (requires debug_mode=ATTITUDE; --immediate
	# isolates the heading mechanism by feeding pitch/velocity from t=0)
	run_test sitl_safety_attitude.txt experiments/heading_confidence_probe.py --pitch 15 --speed 7.5 --immediate

# Regenerates paper/figures/*.png straight from the SITL result CSVs
figures:
	PYTHONPATH=src uv run python tools/make_figures.py

# Fills Project Template.docx and emits/compiles the LaTeX version
report: figures
	PYTHONPATH=src uv run python tools/generate_report.py

# Skips figure regeneration; run `just figures` after changing plot data.
# Live preview: open the report and rebuild it on every save
watch:
	PYTHONPATH=src uv run python tools/watch_paper.py

# Launch the interactive live-map spoofing console against a fresh SITL instance.
# GUI mode: `just interactive` (click/drag the map to set the spoof target).
# Headless test: `just interactive --target 150,0 --headless`.
interactive:
	#!/usr/bin/env bash
	set -e
	cd betaflight
	if [ ! -f obj/main/betaflight_SITL.elf ]; then
		make TARGET=SITL EXTRA_FLAGS="-DENABLE_RESCUE_PLAN=0"
	fi
	echo -e "feature GPS\nset gps_provider = VIRTUAL\nset debug_mode = RTH\nset runaway_takeoff_prevention = OFF\naux 0 0 0 1700 2100 0\naux 1 46 1 1700 2100 0\nsave" > sitl_safety.txt
	rm -f eeprom.bin
	./obj/main/betaflight_SITL.elf --config sitl_safety.txt > /dev/null 2>&1
	./obj/main/betaflight_SITL.elf > /dev/null 2>&1 &
	PID=$!
	cd ..
	trap 'kill -9 $PID 2>/dev/null || true' EXIT
	sleep 2
	PYTHONPATH=src uv run python experiments/interactive_rth_spoof.py "$@"

# Run the false-home landing experiments (baseline + velocity-bias sweep)
false-home:
	#!/usr/bin/env bash
	set -e
	cd betaflight
	if [ ! -f obj/main/betaflight_SITL.elf ]; then
		make TARGET=SITL EXTRA_FLAGS="-DENABLE_RESCUE_PLAN=0"
	fi
	echo -e "feature GPS\nset gps_provider = VIRTUAL\nset debug_mode = RTH\nset runaway_takeoff_prevention = OFF\naux 0 0 0 1700 2100 0\naux 1 46 1 1700 2100 0\nsave" > sitl_safety.txt
	run_test() {
		rm -f eeprom.bin
		./obj/main/betaflight_SITL.elf --config sitl_safety.txt > /dev/null 2>&1
		./obj/main/betaflight_SITL.elf > /dev/null 2>&1 &
		PID=$!
		cd ..
		sleep 2
		PYTHONPATH=src uv run python "$@"
		kill -9 $PID 2>/dev/null || true
		wait $PID 2>/dev/null || true
		cd betaflight
	}
	# One control run (real GPS converging to home).
	run_test experiments/false_home_landing.py --mode baseline
	# The estimator-decoupling outcome is bimodal per SITL process (the
	# ATTAIN_ALT gate's returnAltitudeCm depends on a per-run maxAltitudeCm),
	# so each velocity is repeated N=6 times to characterise the distribution,
	# exactly as the sanity-check sweeps do. Tags: v<vel>_run<i>.
	for vel in 07:7.5 30:30 60:60 65:65 70:70; do
		lbl="${vel%%:*}"; v="${vel##*:}"
		for i in 1 2 3 4 5 6; do
			run_test experiments/false_home_landing.py --mode bias --bias-north 150 --vel "$v" --tag "v${lbl}_run${i}"
		done
	done

# Train and evaluate the discrete-SAC jam/spoof policy over the RF simulation
rf-rl:
	PYTHONPATH=src uv run python experiments/rl_jam_spoof.py --episodes 20000

# Attacker target-tracking demo + the full integrated jam->track->spoof->land scenario
scenario:
	PYTHONPATH=src uv run python experiments/rf_tracking.py
	PYTHONPATH=src uv run python experiments/attack_scenario.py
