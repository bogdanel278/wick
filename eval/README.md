# Wick eval harness

Posts labelled chart screenshots to the Wick backend (`POST /analyze`, see `../CONTRACT.md`), validates each response against `../contract/analysis.schema.json`, and scores it.

**What this measures:** whether Wick reads the *visible* chart correctly. It does not measure whether the analysis is useful for trading. See "Forward-outcome evaluation" below.

## Setup
    pip install -r requirements.txt --break-system-packages   # or in a venv

## Run
    python run_eval.py                       # defaults: charts/, labels.csv, http://localhost:8000, results/
    python run_eval.py --charts charts --labels labels.csv --api http://localhost:8000 --out results
    python run_eval.py --repeats 3           # run each chart 3 times, report agreement (accuracy uses run 1)
    python run_eval.py --no-hints --out results_nohints   # omit instrument/timeframe hints
    python compare.py results/results.json results_nohints/results.json   # paired McNemar test

Other flags: `--ohlcv DIR` (default `ohlcv/`), `--timeout`. Outputs `results/results.json` (meta, summary, per-image records) and `results/report.md`. Failures (HTTP errors, timeouts, bad JSON) are recorded per image, never abort the run, and count as wrong. The upload filename is always neutral (`chart.png`) so file names cannot leak labels.

## Labels
`labels.csv` columns: `filename,instrument,timeframe,expected_direction,notes`.

`expected_direction` is the **visible trend** as defined for `trend.direction` in the contract: the net close-to-close move across the visible window plus higher-high/higher-low (or lower-high/lower-low) structure; `sideways` when the net move is small relative to the typical bar range. It is **not a forecast** of what price did next. Allowed values: `up`, `down`, `sideways`, `not_a_chart` (negative examples; scored as correct when the response status is `not_a_chart`). There is no `unclear` label: if you cannot label a chart by the rule, it is a poor test chart. Decide your labelling rule up front and have a second person label a sample to check agreement.

Instrument and timeframe are sent as hints (may be blank; `--no-hints` drops them). Rows whose file is missing (including the `EXAMPLE_*` rows) are skipped with a warning.

**Real labelled charts, 50 to 100, with a mix of instruments, timeframes, platforms, themes and ambiguity, are what make this eval meaningful.** At n=24 a 95% interval on accuracy is roughly 30 points wide; at n=100 about 18.

## Metrics (all in `report.md`)
- Schema-valid rate; overall accuracy (all rows, including `not_a_chart`) and direction accuracy on chart rows, each with a 95% Wilson interval, overall and per expected label, plus a note on how wide the interval is at the given n.
- `not_a_chart` detection (negatives flagged) and charts wrongly flagged `not_a_chart`.
- Baselines on chart rows: always-up, majority class (from the labels), and a 20-bar SMA-slope baseline for charts that have `ohlcv/<stem>.csv` (columns `bar,open,high,low,close`; sideways if the SMA net change is under 2 mean bar ranges). A model that does not clearly beat these is not adding value.
- Confusion matrix (columns include `unclear`, `not_a_chart`, `none` = no trend or request failed).
- Reliability table (confidence bands 0-0.2 ... 0.8-1), Brier score against correctness, expected calibration error. Per the contract, `confidence` means image and pattern clarity, not the chance of being right, so calibration is only a sanity check.
- Banned-wording rate over every text field except `id`: buy/buying, sell/selling, take profit, entry point, guaranteed, will definitely (whole word, case-insensitive). `score.BANNED` **must stay in sync with the backend list and `CONTRACT.md`**; a test checks it against the contract.
- Repeat agreement (`--repeats N`): share of charts where all runs agree, and mean modal share.
- Response `meta` (model, prompt_version) is recorded in `results.json` and the report header.

## Comparing runs
`compare.py A/results.json B/results.json` pairs images by filename and runs an exact two-sided McNemar test on per-image correctness (binomial on the discordant pairs, no scipy). It prints both discordant counts and the p-value and warns when there are fewer than 10 discordant pairs, where the test has almost no power. Use it for prompt versions, models, or hints vs `--no-hints`.

## Forward-outcome evaluation (not built yet)
Matching the visible trend is necessary but is not the real test. The real test is whether the analysis holds up after the cut. Planned design:
1. For each chart keep real OHLCV data and the cut timestamp (the last visible bar), including bars after the cut.
2. Run the analysis on the screenshot; parse numeric levels, scenario triggers and invalidations (needs legible axes; skip `null`s).
3. Replay the post-cut bars at the chart's timeframe, using closes (not wicks), as the contract specifies, over a fixed horizon. Score: did a scenario trigger fire, did its invalidation fire first, did support/resistance levels hold (price respected the level within a tolerance) or break, and was the trigger/invalidation ordering internally consistent.
4. Compare with baselines (random scenario, SMA, always-neutral) using the same compare/Wilson tooling, on 100+ charts spanning different market regimes, since outcomes are heavily regime-dependent.

## Synthetic smoke test
    python make_synthetic.py        # charts_synthetic/, labels.synthetic.csv, ohlcv/*.csv (24 images)
    python run_eval.py --charts charts_synthetic --labels labels.synthetic.csv --out results_synthetic

20 candlestick charts (light and dark themes, some with a 20-bar MA overlay, some with a cropped axis, overlapping drift and noise so some are ambiguous) plus 4 non-chart negatives (bar chart, pie chart). Labels come from applying the contract rule mechanically to the generated series (net move of at least 3 mean bar ranges is up/down, otherwise sideways); no label or noise level appears in any image. **Synthetic charts are only a plumbing test, not a measure of real-world quality.** They are clean, generated by one process, and unlike real platform screenshots.

## Tests
    python -m pytest -q
