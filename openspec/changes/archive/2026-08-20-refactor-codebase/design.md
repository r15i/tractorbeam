## Context

See proposal.md for the motivation behind this refactor. The codebase contains around 20 Python files at the project root and in `scripts/`.

## Goals / Non-Goals

**Goals:**
- Define a canonical directory structure for this codebase.
- Ensure all Python files are correctly placed according to their role.
- Update all Python imports and the `justfile` targets so that everything runs correctly post-refactor.

**Non-Goals:**
- We are not changing the behavior or logic of any script.
- We are not touching the `.tex` paper files or the actual content of the documentation (other than path references if needed).

## Decisions

**Target Directory Structure:**
- `src/tractorbeam/`: Core simulator library modules.
  - `sitl_common.py`
  - `sitl_transport.py`
  - `rf_sim.py`
  - `hijack_quality.py`
- `experiments/`: Specific attack scripts and analysis probes.
  - `attack_scenario.py`
  - `false_home_landing.py`
  - `heading_confidence_probe.py`
  - `horizontal_gate_experiment.py`
  - `interactive_rth_spoof.py`
  - `rf_tracking.py`
  - `rl_jam_spoof.py`
  - `sanity_check_experiment.py`
  - `walkoff_experiment.py`
- `tools/`: Report and figure generation.
  - `generate_report.py`
  - `make_figures.py`
- `scratch/`: Keep leftover scratch scripts here, but add this directory to `.gitignore` to prevent repository clutter.

*Rationale*: A standard Python `src/` layout prevents import path confusion, and isolating `experiments/` from `tools/` clarifies the boundaries between data generation and reporting.

**Packaging and Dependencies:**
- We will adopt `uv` standards for Python packaging. A standard `pyproject.toml` will be added to make `tractorbeam` an installable package and formally track dependencies.

**Code Quality:**
- `ruff` will be run across the entire codebase to automatically format and lint the Python code.

**Import Management:**
- `src/` will need an `__init__.py` to act as a package.
- The `justfile` will be updated to execute scripts within the `uv` environment, taking advantage of the installed `tractorbeam` package.

## Risks / Trade-offs

- [Risk] Breaking the `justfile` pipeline. → Mitigation: We will test all `just` targets after moving files to ensure the paths and imports are correct.
- [Risk] Broken Python imports. → Mitigation: We will run `ruff check` or simply execute the scripts to catch `ModuleNotFoundError`.
