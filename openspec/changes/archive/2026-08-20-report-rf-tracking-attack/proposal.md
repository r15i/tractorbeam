## Why

The report currently stops at the RF power + RL layer and omits the project's newest work: the attacker's passive RF target tracking, the full jam→track→spoof→land scenario, and the paper-analog hijack quality metrics. Those results are implemented, tested, and spec'd, but a reader of `paper/Final_Report.pdf` would never know they exist. This change folds them into the report and documents — for the first time — how the attack would work in real life and which simplification routes we took.

## What Changes

- Add a short **Results** subsection to the report: a new figure for the full attack scenario, a paragraph on the RF tracking + integrated scenario, and the hijack-quality metrics table.
- Add a **documentation section** (`docs/`) explaining the attack as a plausible real-world operation (SDR + direction-finding array, jam the control link, track on the 5.8 GHz video feed, spoof GPS to land next to the attacker) and, explicitly, the **simplifications** the SITL/RF models make versus a field attack.
- No changes to simulation code, specs, or existing experiments.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
<!-- none -->

This is a documentation/reporting change only; `.openspec.yaml` declares `skip_specs: true` (no spec-level behavior change).

## Impact

- `make_figures.py` — one new figure for the attack scenario.
- `generate_report.py` — one new results paragraph + a quality-metrics table + the figure include.
- `docs/` — a new "real-world attack and simplifications" note.
- No changes to `scripts/`, specs, or the simulation pipeline.
