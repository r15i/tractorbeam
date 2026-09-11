## 1. Directory Setup

- [x] 1.1 Create `src/tractorbeam`, `src/tractorbeam/__init__.py`, `experiments`, `tools`, and `scratch` directories.
- [x] 1.2 Move core scripts (`sitl_transport.py`, `sitl_common.py`, `rf_sim.py`, `hijack_quality.py`) to `src/tractorbeam/`.
- [x] 1.3 Move experimental scripts to `experiments/`.
- [x] 1.4 Move `generate_report.py` and `make_figures.py` to `tools/`.
- [x] 1.5 Move contents of `scripts/scratch/` to the root `scratch/` directory.
- [x] 1.6 Add `/scratch/` to `.gitignore`.

## 2. Code Updates & Packaging

- [x] 2.1 Initialize a standard `pyproject.toml` using `uv` standards to make `tractorbeam` an installable package and track dependencies.
- [x] 2.2 Update all python imports inside the moved scripts to reference `tractorbeam` (as an installed package) or absolute imports correctly.
- [x] 2.3 Run `ruff format` and `ruff check --fix` across `src/`, `experiments/`, and `tools/` to clean up the code.

## 3. Build & Test

- [x] 3.1 Update `justfile` targets to point to the new paths and rely on the `uv` environment.
- [x] 3.2 Run `just all` to verify the entire pipeline runs perfectly.
