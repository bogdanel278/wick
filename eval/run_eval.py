#!/usr/bin/env python3
"""Run the Wick eval: POST each labelled chart to /analyze, validate, score, report."""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

import requests
from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score as scoring  # noqa: E402

HERE = Path(__file__).resolve().parent
SCHEMA = HERE.parent / "contract" / "analysis.schema.json"
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def load_labels(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def analyze(api, img, row, timeout, hints=True):
    data = {k: row[k] for k in ("instrument", "timeframe") if row.get(k)} if hints else {}
    with open(img, "rb") as f:
        # Neutral upload name: the original filename must never leak the label to the backend.
        files = {"image": ("chart" + img.suffix.lower(), f, MIME.get(img.suffix.lower(), "application/octet-stream"))}
        return requests.post(api.rstrip("/") + "/analyze", files=files, data=data, timeout=timeout)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--charts", default=str(HERE / "charts"))
    ap.add_argument("--labels", default=str(HERE / "labels.csv"))
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--out", default=str(HERE / "results"))
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--ohlcv", default=str(HERE / "ohlcv"), help="folder of optional <stem>.csv OHLCV files for the SMA baseline")
    ap.add_argument("--repeats", type=int, default=1, help="run each chart N times and report agreement (accuracy uses run 1)")
    ap.add_argument("--no-hints", action="store_true", help="omit instrument and timeframe hints")
    a = ap.parse_args()

    validator = Draft202012Validator(json.loads(SCHEMA.read_text()))
    charts, out = Path(a.charts), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    records, skipped = [], []
    for row in load_labels(a.labels):
        fn, exp = row.get("filename", ""), row.get("expected_direction", "").lower()
        img = charts / fn
        if exp not in scoring.EXPECTED_VALUES:
            print(f"WARNING: skipping {fn!r}: bad expected_direction {exp!r}", file=sys.stderr)
            skipped.append(fn)
            continue
        if not img.is_file():
            print(f"WARNING: skipping {fn!r}: file not found in {charts}", file=sys.stderr)
            skipped.append(fn)
            continue
        rec = {"filename": fn, "expected": exp, "response": None, "schema_valid": False,
               "schema_errors": [], "error": None, "http_status": None, "latency_s": None}
        rec["sma_baseline"] = scoring.sma_baseline_for(a.ohlcv, fn)
        rec["repeat_labels"] = []
        t0 = time.time()
        for i in range(max(1, a.repeats)):
            label, err = "none", None
            try:
                r = analyze(a.api, img, row, a.timeout, hints=not a.no_hints)
                try:
                    body = r.json()
                except ValueError:
                    body = None
                if r.status_code == 200 and body is not None:
                    label = scoring.predicted_direction(body)
                    if i == 0:
                        rec["http_status"] = r.status_code
                        rec["response"] = body
                        rec["schema_errors"] = [f"{'/'.join(map(str, e.path))}: {e.message}" for e in validator.iter_errors(body)]
                        rec["schema_valid"] = not rec["schema_errors"]
                else:
                    err = f"HTTP {r.status_code}: {(r.text or '')[:200]}"
                    if i == 0:
                        rec["http_status"] = r.status_code
            except Exception as e:  # per-image failure must not abort run
                err = f"{type(e).__name__}: {e}"
            if i == 0:
                rec["error"] = err
            rec["repeat_labels"].append(label)
        rec["latency_s"] = round(time.time() - t0, 2)
        rec["correct"] = scoring.is_correct(rec)
        print(f"{fn}: expected={exp} " + (rec["error"] or f"pred={scoring.predicted_direction(rec['response'])} valid={rec['schema_valid']}"))
        records.append(rec)

    s = scoring.score(records)
    seen = s["meta_seen"]
    meta = {"api": a.api, "labels": a.labels, "skipped_rows": len(skipped),
            "model": ", ".join(sorted({str(m["model"]) for m in seen})) or None,
            "prompt_version": ", ".join(sorted({str(m["prompt_version"]) for m in seen})) or None,
            "hints": not a.no_hints, "repeats": max(1, a.repeats)}
    (out / "results.json").write_text(json.dumps({"meta": meta, "summary": s, "records": records}, indent=2))
    (out / "report.md").write_text(scoring.render_report(s, records, meta))
    print(f"\nWrote {out/'results.json'} and {out/'report.md'} ({len(records)} evaluated, {len(skipped)} skipped)")
    if not records:
        print("WARNING: no images evaluated.", file=sys.stderr)


if __name__ == "__main__":
    main()
