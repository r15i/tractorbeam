## 1. Figure

- [x] 1.1 Add `fig_attack_scenario()` to `make_figures.py` plotting `est_dist_home_m` vs time from `results/attack_scenario.csv`, with the phase transitions and the 20 m landing ring
- [x] 1.2 Run `just figures` and confirm `paper/figures/fig7_attack_scenario.png` is produced

## 2. Report content

- [x] 2.1 Add the tracking + integrated-scenario paragraph and the hijack-quality metrics table to `generate_report.py`
- [x] 2.2 Insert `fig7_attack_scenario.png` into the report (docx + LaTeX) alongside the new paragraph

## 3. Real-world documentation

- [x] 3.1 Write `docs/results/real-world-attack.md` covering the real-world attack chain and the explicit simplification routes
- [x] 3.2 Link it from `docs/README.md`

## 4. Regenerate and validate

- [x] 4.1 Run `just figures && just report` and confirm the report stays within ~9 pages
- [x] 4.2 Run `openspec validate report-rf-tracking-attack --strict` and resolve any issues
