"""Scoring functions for the Wick eval. Pure functions, no network."""
import csv
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

DIRECTIONS = ["up", "down", "sideways"]
EXPECTED_VALUES = DIRECTIONS + ["not_a_chart"]
# none = no usable trend / request failed
PRED_COLUMNS = ["up", "down", "sideways", "unclear", "not_a_chart", "none"]

# Banned wording. MUST stay in sync with the backend's list and CONTRACT.md ("Banned wording").
BANNED = ["buy", "buying", "sell", "selling", "take profit", "entry point", "guaranteed", "will definitely"]
_BANNED_RE = re.compile(
    r"\b(" + "|".join(r"\s+".join(re.escape(w) for w in b.split()) for b in BANNED) + r")\b", re.I)
_SKIP_KEYS = {"id"}

BANDS = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0)]
SMA_WINDOW = 20
SMA_FLAT_RANGES = 2.0  # SMA net change below this many mean bar ranges => "sideways"


# ---------- prediction helpers ----------
def predicted_direction(resp):
    """Return up/down/sideways/unclear, 'not_a_chart', or 'none' if no usable trend."""
    if not isinstance(resp, dict):
        return "none"
    if resp.get("status") == "not_a_chart":
        return "not_a_chart"
    if resp.get("status") != "ok":
        return "none"
    trend = resp.get("trend")
    if not isinstance(trend, dict):
        return "none"
    d = trend.get("direction")
    return d if d in ("up", "down", "sideways", "unclear") else "none"


def is_correct(rec):
    resp = rec.get("response")
    pred = predicted_direction(resp) if resp is not None else "none"
    return pred == rec["expected"]


def iter_strings(obj, key=None):
    if isinstance(obj, str):
        if key not in _SKIP_KEYS:
            yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from iter_strings(v, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from iter_strings(v, key)


def banned_hits(resp):
    """List of banned words/phrases (lowercased, single-spaced) found in any text field."""
    hits = []
    for s in iter_strings(resp):
        hits += [" ".join(m.group(1).lower().split()) for m in _BANNED_RE.finditer(s)]
    return hits


# ---------- statistics ----------
def wilson(k, n, z=1.96):
    """Wilson score interval (lo, hi) for k successes out of n; (None, None) if n == 0."""
    if n <= 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def _acc(k, n):
    lo, hi = wilson(k, n)
    return {"n": n, "correct": k, "accuracy": k / n if n else None, "ci_low": lo, "ci_high": hi}


def mcnemar_exact(b, c):
    """Exact two-sided McNemar p-value from discordant counts b, c (binomial(b+c, 0.5))."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def sma_direction(highs, lows, closes, window=SMA_WINDOW, flat=SMA_FLAT_RANGES):
    """20-bar SMA slope baseline: up/down/sideways, or None if too few bars."""
    n = len(closes)
    if n < window + 1:
        return None
    sma = [sum(closes[i - window + 1:i + 1]) / window for i in range(window - 1, n)]
    net = sma[-1] - sma[0]
    mean_range = sum(h - l for h, l in zip(highs, lows)) / n
    if abs(net) < flat * mean_range:
        return "sideways"
    return "up" if net > 0 else "down"


def load_ohlcv(path):
    """CSV with header bar,open,high,low,close -> (highs, lows, closes)."""
    hs, ls, cs = [], [], []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            hs.append(float(row["high"]))
            ls.append(float(row["low"]))
            cs.append(float(row["close"]))
    return hs, ls, cs


def sma_baseline_for(ohlcv_dir, filename):
    p = Path(ohlcv_dir) / (Path(filename).stem + ".csv")
    if not p.is_file():
        return None
    try:
        return sma_direction(*load_ohlcv(p))
    except (ValueError, KeyError, OSError):
        return None


def calibration(records):
    """Reliability table, Brier score and ECE of confidence vs correctness (records with numeric confidence)."""
    pts = []
    for r in records:
        resp = r.get("response")
        if isinstance(resp, dict) and isinstance(resp.get("confidence"), (int, float)):
            pts.append((float(resp["confidence"]), 1 if is_correct(r) else 0))
    N = len(pts)
    bands = []
    ece = 0.0
    for i, (lo, hi) in enumerate(BANDS):
        last = i == len(BANDS) - 1
        sel = [(c, o) for c, o in pts if lo <= c < hi or (last and c == hi)]
        if sel:
            mc = sum(c for c, _ in sel) / len(sel)
            ac = sum(o for _, o in sel) / len(sel)
            ece += len(sel) / N * abs(ac - mc)
        else:
            mc = ac = None
        bands.append({"band": f"{lo:.1f}-{hi:.1f}", "n": len(sel), "mean_confidence": mc, "accuracy": ac})
    return {
        "n": N,
        "bands": bands,
        "brier": sum((c - o) ** 2 for c, o in pts) / N if N else None,
        "ece": ece if N else None,
    }


def agreement(records):
    """Repeat agreement: share of charts with all runs identical, and mean modal share."""
    multi = [r["repeat_labels"] for r in records if len(r.get("repeat_labels") or []) > 1]
    if not multi:
        return None
    unanimous = sum(1 for ls in multi if len(set(ls)) == 1)
    modal = sum(Counter(ls).most_common(1)[0][1] / len(ls) for ls in multi)
    return {"charts": len(multi), "runs_per_chart": len(multi[0]),
            "unanimous_rate": unanimous / len(multi), "mean_modal_share": modal / len(multi)}


# ---------- main scoring ----------
def score(records):
    """records: dicts with expected, response (dict|None), schema_valid, error; optional repeat_labels, sma_baseline."""
    n = len(records)
    answered = [r for r in records if r.get("response") is not None]
    valid = [r for r in answered if r.get("schema_valid")]
    per = defaultdict(lambda: [0, 0])
    matrix = {e: {c: 0 for c in PRED_COLUMNS} for e in EXPECTED_VALUES}
    correct_total = 0
    for r in records:
        exp = r["expected"]
        pred = predicted_direction(r.get("response")) if r.get("response") is not None else "none"
        ok = pred == exp
        per[exp][0] += 1
        per[exp][1] += ok
        correct_total += ok
        if exp in matrix:
            matrix[exp][pred] += 1

    chart_rows = [r for r in records if r["expected"] in DIRECTIONS]
    chart_correct = sum(is_correct(r) for r in chart_rows)
    nac_rows = [r for r in records if r["expected"] == "not_a_chart"]
    nac_ok = sum(is_correct(r) for r in nac_rows)
    false_nac = sum(1 for r in chart_rows
                    if r.get("response") is not None and predicted_direction(r["response"]) == "not_a_chart")

    exp_counts = Counter(r["expected"] for r in chart_rows)
    majority = sorted(exp_counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if exp_counts else None
    baselines = {
        "scope": "rows with expected up/down/sideways (not_a_chart rows excluded)",
        "always_up": _acc(exp_counts.get("up", 0), len(chart_rows)),
        "majority_class": dict(_acc(exp_counts.get(majority, 0), len(chart_rows)), predicts=majority),
    }
    sma_rows = [r for r in chart_rows if r.get("sma_baseline")]
    baselines["sma20_slope"] = _acc(sum(r["sma_baseline"] == r["expected"] for r in sma_rows), len(sma_rows)) \
        if sma_rows else None
    if baselines["sma20_slope"]:
        baselines["sma20_slope"]["model_accuracy_same_rows"] = sum(is_correct(r) for r in sma_rows) / len(sma_rows)

    metas = sorted({(r["response"]["meta"].get("model"), r["response"]["meta"].get("prompt_version"))
                    for r in answered if isinstance(r["response"].get("meta"), dict)}, key=str)
    banned_resp = sum(1 for r in answered if banned_hits(r["response"]))
    banned_counter = Counter(h for r in answered for h in banned_hits(r["response"]))
    return {
        "total_images": n,
        "responses_received": len(answered),
        "request_failures": n - len(answered),
        "schema_valid_count": len(valid),
        "schema_valid_rate": len(valid) / n if n else None,
        "overall_accuracy": _acc(correct_total, n),
        "direction_accuracy": correct_total / n if n else None,  # all rows; failures count as wrong
        "direction_accuracy_chart_rows": _acc(chart_correct, len(chart_rows)),
        "not_a_chart_detection": dict(_acc(nac_ok, len(nac_rows)), false_not_a_chart_on_charts=false_nac),
        "accuracy_by_expected": {k: _acc(v[1], v[0]) for k, v in sorted(per.items())},
        "confusion_matrix": {"rows_expected": EXPECTED_VALUES, "columns_predicted": PRED_COLUMNS, "counts": matrix},
        "baselines": baselines,
        "calibration": calibration(records),
        "agreement": agreement(records),
        "meta_seen": [{"model": m, "prompt_version": p} for m, p in metas],
        "banned_wording_rate": banned_resp / len(answered) if answered else None,
        "banned_wording_responses": banned_resp,
        "banned_wording_counts": dict(banned_counter),
    }


# ---------- report ----------
def _pct(x):
    return "n/a" if x is None else f"{x*100:.1f}%"


def _num(x):
    return "n/a" if x is None else f"{x:.3f}"


def _ci(d):
    if not d or d.get("accuracy") is None:
        return "n/a"
    return f"{_pct(d['accuracy'])} [{_pct(d['ci_low'])}, {_pct(d['ci_high'])}] ({d['correct']}/{d['n']})"


def ci_note(d):
    if not d or not d["n"]:
        return "No rows, no interval."
    w = (d["ci_high"] - d["ci_low"]) * 100
    return (f"At n={d['n']} the 95% Wilson interval on accuracy is {w:.0f} percentage points wide "
            f"({_pct(d['ci_low'])} to {_pct(d['ci_high'])}). Per-class intervals are wider because n is smaller. "
            f"Differences smaller than this are not distinguishable from noise.")


def render_report(s, records, meta=None):
    L = ["# Wick eval report", ""]
    for k, v in (meta or {}).items():
        L.append(f"- {k}: {v}")
    ms = s.get("meta_seen") or []
    L.append("- response meta seen (model / prompt_version): " +
             ("; ".join(f"{m['model']} / {m['prompt_version']}" for m in ms) if ms else "none"))
    cr, nd = s["direction_accuracy_chart_rows"], s["not_a_chart_detection"]
    L += ["", "## Summary", "",
          f"- Images evaluated: {s['total_images']} (responses: {s['responses_received']}, request failures: {s['request_failures']})",
          f"- Schema-valid rate: {_pct(s['schema_valid_rate'])} ({s['schema_valid_count']}/{s['total_images']})",
          f"- Overall accuracy, all rows (failures count as wrong): {_ci(s['overall_accuracy'])}",
          f"- Direction accuracy, chart rows only: {_ci(cr)}",
          f"- not_a_chart detection (negatives flagged correctly): {_ci(nd)}; charts wrongly flagged not_a_chart: {nd['false_not_a_chart_on_charts']}",
          f"- Banned wording rate: {_pct(s['banned_wording_rate'])} ({s['banned_wording_responses']} responses) {s['banned_wording_counts'] or ''}",
          "", f"**Interval width:** {ci_note(s['overall_accuracy'])}",
          "", "## Baselines (direction, chart rows)", "",
          f"- Model: {_ci(cr)}",
          f"- Always predict up: {_ci(s['baselines']['always_up'])}",
          f"- Majority class ({s['baselines']['majority_class'].get('predicts')}): {_ci(s['baselines']['majority_class'])}"]
    sma = s["baselines"]["sma20_slope"]
    L.append("- 20-bar SMA slope: " + (f"{_ci(sma)}; model on the same rows {_pct(sma['model_accuracy_same_rows'])}"
                                      if sma else "n/a (no OHLCV csv found for any chart)"))
    L += ["", "A model that does not clearly beat these baselines (taking the intervals into account) is not adding value on this set.",
          "", "## Accuracy by expected label", "", "| expected | n | correct | accuracy [95% Wilson] |", "|---|---|---|---|"]
    for k, v in s["accuracy_by_expected"].items():
        L.append(f"| {k} | {v['n']} | {v['correct']} | {_ci(v).split(' (')[0]} |")
    cm = s["confusion_matrix"]
    L += ["", "## Confusion matrix (rows expected, columns predicted)", "",
          "| expected \\ predicted | " + " | ".join(cm["columns_predicted"]) + " |",
          "|---|" + "---|" * len(cm["columns_predicted"])]
    for e in cm["rows_expected"]:
        L.append(f"| {e} | " + " | ".join(str(cm['counts'][e][c]) for c in cm["columns_predicted"]) + " |")
    L += ["", "`none` = missing trend or request failed.", ""]
    cal = s["calibration"]
    L += ["## Confidence reliability", "",
          f"Responses with confidence: {cal['n']}. Brier score vs correctness: {_num(cal['brier'])}. Expected calibration error: {_num(cal['ece'])}.", "",
          "| band | n | mean confidence | accuracy |", "|---|---|---|---|"]
    for b in cal["bands"]:
        L.append(f"| {b['band']} | {b['n']} | {_num(b['mean_confidence'])} | {_pct(b['accuracy'])} |")
    L += ["", "Per the contract, `confidence` means image and pattern clarity, not the chance of being right about direction, "
              "so calibration here is only a sanity check (clean charts should score higher than cluttered ones).", ""]
    ag = s.get("agreement")
    if ag:
        L += ["## Repeat agreement", "",
              f"{ag['charts']} charts x {ag['runs_per_chart']} runs: all runs agree on {_pct(ag['unanimous_rate'])} of charts; "
              f"mean modal share {_pct(ag['mean_modal_share'])}. Accuracy above uses the first run only.", ""]
    L += ["## Per image", "", "| file | expected | predicted | confidence | schema | notes |", "|---|---|---|---|---|---|"]
    for r in records:
        resp = r.get("response")
        pred = predicted_direction(resp) if resp is not None else "none"
        conf = resp.get("confidence") if isinstance(resp, dict) else None
        note = r.get("error") or ""
        if r.get("schema_errors"):
            note += " schema: " + "; ".join(r["schema_errors"][:2])
        if len(set(r.get("repeat_labels") or [])) > 1:
            note += " repeats: " + ",".join(r["repeat_labels"])
        L.append(f"| {r.get('filename','?')} | {r['expected']} | {pred} | {_num(conf)} | {'ok' if r.get('schema_valid') else 'FAIL'} | {note.replace('|','/')} |")
    return "\n".join(L) + "\n"
