# Blood Culture Early Alert Agent

Blood-culture time-to-positivity (TTP), Gram-stain, bottle-pattern, and contamination heuristic utilities for research, education, workflow prototyping, and software testing.

> **Important:** the contamination score is a transparent heuristic, not a calibrated clinical probability or a validated clinical decision-support model. Clinical actions should follow local microbiology, antimicrobial-stewardship, infectious-diseases, and infection-control procedures.

## What it does

The repository provides a dependency-free Python analysis module and CLI plus a static browser interface. The core workflow:

- categorizes TTP using explicit cut points;
- recognizes common Gram-stain descriptions and abbreviations such as GNB/GNR and GPC patterns;
- combines organism class, TTP, and bottle positivity into an interpretable contamination score;
- flags review priorities without prescribing a drug regimen;
- provides selective follow-up-culture prompts;
- processes CSV files in batch mode;
- exports browser results as JSON.

The Python implementation in `blood_culture_sentinel.py` is the authoritative analysis path. The installable package CLI delegates to the same implementation so command-line behavior is consistent.

## Browser application

The static application is in `docs/` and is designed for GitHub Pages. It uses plain HTML, CSS, and JavaScript with no external assets or API calls.

Data entered into the page are processed locally in the browser. The only value stored in browser storage is the selected light/dark theme.

## CLI usage

Install locally:

```bash
python -m pip install -e .
```

Run a complete analysis:

```bash
blood-culture-early-alert-agent analyze \
  --organism staphylococcus_aureus \
  --ttp 8.5 \
  --gram-stain gram_positive_cocci_clusters \
  --positive-bottles 2 \
  --total-bottles 2
```

Other commands:

```bash
blood-culture-early-alert-agent ttp --hours 18
blood-culture-early-alert-agent contamination --organism staphylococcus_epidermidis --ttp 38
blood-culture-early-alert-agent gram-stain --result GNB
blood-culture-early-alert-agent batch -i sample.csv -o results.csv
```

The optional API server is available with:

```bash
python -m pip install -e ".[server]"
blood-culture-early-alert-agent serve
```

It exposes `GET /health`, `POST /api/analyze`, and the compatibility alias `POST /api/audit`.

## Batch input

`sample.csv` demonstrates accepted column names. TTP must be explicitly present and parseable; the batch workflow no longer silently substitutes a default value when TTP is missing or malformed.

Computed fields include:

- `computed_urgency_escalation`
- `time_to_positivity_category`
- `empiric_antibiotic_advisory`
- `likely_pathogens`
- `critical_panic_call_window_minutes`

Urgency labels are workflow prompts, not treatment orders.

## Development and verification

Python 3.10–3.12 are tested in GitHub Actions.

```bash
python -m pip install -e . pytest ruff build
python -m pytest -p no:zarr
ruff check blood_culture_sentinel.py cli.py \
  blood_culture_early_alert_agent/cli.py \
  blood_culture_early_alert_agent/__init__.py
python -m build
python -m pip check
node --check docs/app.js
```

The project has no third-party runtime dependency for the core CLI. FastAPI, Pydantic, and Uvicorn are optional and used only by the server extra.

## Evidence and limitations

TTP varies by organism, inoculum, blood-culture platform, bottle formulation, collection timing, and antimicrobial exposure. Contemporary blood-culture data show substantial organism-specific variation in time to positivity, so the fixed TTP bands in this repository should be treated as software heuristics rather than universal diagnostic thresholds.

Follow-up blood cultures in Gram-negative bloodstream infection are also context dependent; published systematic reviews report heterogeneous observational evidence and identify higher-risk subgroups for persistent bacteremia. The implementation therefore avoids a universal repeat-culture rule for all Gram-negative isolates.

Selected references:

- Ransom EM, Alipour Z, Wallace MA, Burnham C-A. *J Clin Microbiol.* 2021;59:e02459-20. doi:10.1128/JCM.02459-20.
- Gatti M, et al. *Clin Microbiol Infect.* 2023;29:1150-1158. doi:10.1016/j.cmi.2023.02.024.
- Shinohara J, et al. *Open Forum Infect Dis.* 2022;9:ofac568. doi:10.1093/ofid/ofac568.

## Browser compatibility

The Pages interface targets current versions of Chrome, Edge, Firefox, and Safari. On desktop it uses a compact two-panel layout intended to fit within one viewport where screen size permits; on narrow screens it stacks panels vertically.

## License

MIT. See `LICENSE`.
