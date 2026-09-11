## Why

The current codebase has grown organically over the course of the project, with around 20 Python scripts (mix of core simulation logic, specific attack experiments, and report generation) stored in the root directory and `scripts/`. As the project enters its final stage, it is necessary to neatly organize these files to separate concerns (core vs experiments vs reporting) and improve code maintainability and navigability for final submission.

## What Changes

- Organize the project into a proper Python package layout.
- Move core simulator code (`sitl_transport.py`, `sitl_common.py`, `rf_sim.py`, `hijack_quality.py`) into a dedicated directory like `src/simulator/` or `src/tractorbeam/`.
- Move specific experimental scripts (`attack_scenario.py`, `false_home_landing.py`, `rf_tracking.py`, etc.) into an `experiments/` directory.
- Move report/figure generation scripts into a `tools/` or `report/` folder.
- Clean up any unused files in `scratch/`.
- Update imports across the codebase to reflect the new structure.
- Run a linter/formatter (like `ruff` or `black`) across the Python code to ensure clean formatting.
- Update `justfile` targets so that `just simulate`, `just false-home`, etc. run smoothly against the refactored paths.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None. (This is a pure structural refactor, no behavior changes).

## Impact

- All existing Python scripts will be moved.
- The `justfile` recipes will be updated.
- Imports inside the scripts will be adjusted.
