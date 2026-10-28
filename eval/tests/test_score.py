import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pytest
import score as S


def resp(direction="up", conf=0.6, status="ok", summary="Higher highs.", extra="", meta=("m1", "p1")):
    return {"id": "x", "status": status, "confidence": conf, "caveats": [extra] if extra else [],
            "trend": None if status != "ok" else {"direction": direction, "strength": "weak", "summary": summary},
            "levels": [], "patterns": [], "scenarios": [], "disclaimer": "Educational.",
            "meta": {"model": meta[0], "prompt_version": meta[1]}}


def rec(exp, r, valid=True, **kw):
    return dict({"expected": exp, "response": r, "schema_valid": valid, "error": None if r else "boom"}, **kw)


FIX = [
    rec("up", resp("up", 0.8)),
    rec("up", resp("down", 0.7)),
    rec("down", resp("down", 0.6)),
    rec("down", resp("unclear", 0.3), valid=False),
    rec("sideways", resp(status="not_a_chart", conf=0.1)),
    rec("sideways", None, valid=False),
    rec("not_a_chart", resp(status="not_a_chart", conf=0.9)),
    rec("not_a_chart", resp("up", 0.5)),
]


def test_predicted_direction():
    assert S.predicted_direction(resp("up")) == "up"
    assert S.predicted_direction(resp(status="not_a_chart")) == "not_a_chart"
    assert S.predicted_direction(None) == "none"


def test_score_overall_and_per_class():
    s = S.score(FIX)
    assert s["total_images"] == 8 and s["request_failures"] == 1
    assert s["schema_valid_rate"] == pytest.approx(6 / 8)
    assert s["overall_accuracy"]["correct"] == 3  # up, down, not_a_chart
    assert s["direction_accuracy_chart_rows"]["n"] == 6
    assert s["direction_accuracy_chart_rows"]["correct"] == 2
    assert s["accuracy_by_expected"]["up"]["accuracy"] == 0.5
    assert s["accuracy_by_expected"]["sideways"]["correct"] == 0
    assert s["accuracy_by_expected"]["not_a_chart"]["accuracy"] == 0.5
    assert s["accuracy_by_expected"]["up"]["ci_low"] < 0.5 < s["accuracy_by_expected"]["up"]["ci_high"]


def test_not_a_chart_scoring_not_skipped():
    s = S.score(FIX)
    d = s["not_a_chart_detection"]
    assert d["n"] == 2 and d["correct"] == 1
    assert d["false_not_a_chart_on_charts"] == 1  # the sideways row predicted not_a_chart
    m = s["confusion_matrix"]["counts"]
    assert m["not_a_chart"]["not_a_chart"] == 1 and m["not_a_chart"]["up"] == 1
    assert m["sideways"]["not_a_chart"] == 1 and m["sideways"]["none"] == 1


def test_wilson_known_values():
    lo, hi = S.wilson(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-3) and hi == pytest.approx(0.7634, abs=1e-3)
    lo, hi = S.wilson(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.2775, abs=1e-3)
    lo, hi = S.wilson(10, 10)
    assert hi == 1.0 and lo == pytest.approx(0.7225, abs=1e-3)
    assert S.wilson(0, 0) == (None, None)


def test_baselines_from_labels():
    recs = [rec("up", None), rec("up", None), rec("down", None), rec("sideways", None), rec("not_a_chart", None)]
    b = S.score(recs)["baselines"]
    assert b["always_up"]["correct"] == 2 and b["always_up"]["n"] == 4
    assert b["majority_class"]["predicts"] == "up" and b["majority_class"]["correct"] == 2
    assert b["sma20_slope"] is None


def test_sma_direction_and_baseline_scoring():
    n = 40
    rising = [100 + i for i in range(n)]
    hs, ls = [c + 0.5 for c in rising], [c - 0.5 for c in rising]
    assert S.sma_direction(hs, ls, rising) == "up"
    falling = rising[::-1]
    assert S.sma_direction([c + 0.5 for c in falling], [c - 0.5 for c in falling], falling) == "down"
    flat = [100 + (0.3 if i % 2 else -0.3) for i in range(n)]
    assert S.sma_direction([c + 1 for c in flat], [c - 1 for c in flat], flat) == "sideways"
    assert S.sma_direction([1] * 5, [0] * 5, [0.5] * 5) is None  # too few bars
    recs = [rec("up", resp("up"), sma_baseline="up"), rec("down", resp("up"), sma_baseline="up"),
            rec("down", resp("down"))]
    sb = S.score(recs)["baselines"]["sma20_slope"]
    assert sb["n"] == 2 and sb["correct"] == 1 and sb["model_accuracy_same_rows"] == 0.5


def test_sma_baseline_from_csv(tmp_path):
    (tmp_path / "c1.csv").write_text("bar,open,high,low,close\n" + "\n".join(
        f"{i},{100+i},{101+i},{99+i},{100+i}" for i in range(30)))
    assert S.sma_baseline_for(tmp_path, "c1.png") == "up"
    assert S.sma_baseline_for(tmp_path, "missing.png") is None


def test_calibration_brier_ece_hand_checked():
    recs = [rec("up", resp("up", 0.9)), rec("up", resp("down", 0.9)),   # band 0.8-1.0: acc 0.5, mean conf 0.9
            rec("up", resp("up", 0.1)), rec("up", resp("up", 0.1))]     # band 0.0-0.2: acc 1.0, mean conf 0.1
    c = S.calibration(recs)
    assert c["n"] == 4
    assert c["brier"] == pytest.approx((0.01 + 0.81 + 0.81 + 0.81) / 4)
    assert c["ece"] == pytest.approx(0.5 * 0.4 + 0.5 * 0.9)
    assert c["bands"][0]["n"] == 2 and c["bands"][0]["accuracy"] == 1.0
    assert c["bands"][4]["n"] == 2 and c["bands"][4]["accuracy"] == 0.5
    assert c["bands"][2]["n"] == 0
    assert S.calibration([])["brier"] is None


def test_confidence_one_goes_in_top_band():
    assert S.calibration([rec("up", resp("up", 1.0))])["bands"][4]["n"] == 1


def test_banned_wording():
    assert S.banned_hits(resp(summary="Consider to BUY now")) == ["buy"]
    assert S.banned_hits(resp(extra="It will definitely rise and is guaranteed")) == ["will definitely", "guaranteed"]
    assert S.banned_hits(resp(summary="Buyers and sellers are balanced")) == []  # word boundaries
    assert S.banned_hits(resp(summary="Selling pressure; buying interest")) == ["selling", "buying"]
    assert S.banned_hits(resp(summary="Take  profit at an Entry Point")) == ["take profit", "entry point"]
    assert S.banned_hits(resp(summary="profit taking, point of entry")) == []
    s = S.score([rec("up", resp(summary="sell the rip")), rec("up", resp())])
    assert s["banned_wording_rate"] == 0.5


def test_banned_list_matches_contract():
    text = (ROOT.parent / "CONTRACT.md").read_text().lower()
    line = [l for l in text.splitlines() if l.startswith("- banned wording")][0]
    for w in S.BANNED:
        assert w.replace("buying", "buy").replace("selling", "sell") in line or w in line


def test_mcnemar_exact_hand_checked():
    # b=1, c=6: n=7, P(X<=1)=(1+7)/128=0.0625, two-sided 0.125
    assert S.mcnemar_exact(1, 6) == pytest.approx(0.125)
    assert S.mcnemar_exact(6, 1) == pytest.approx(0.125)
    # b=0, c=8: 2/256
    assert S.mcnemar_exact(0, 8) == pytest.approx(2 / 256)
    assert S.mcnemar_exact(4, 4) == 1.0
    assert S.mcnemar_exact(0, 0) == 1.0


def test_compare_cli(tmp_path):
    def write(name, correct):
        recs = [{"filename": f"f{i}.png", "expected": "up", "response": resp("up" if ok else "down")}
                for i, ok in enumerate(correct)]
        p = tmp_path / name
        p.write_text(json.dumps({"meta": {"model": "m"}, "records": recs}))
        return str(p)
    a = write("a.json", [True] * 7 + [False] * 3)
    b = write("b.json", [False] * 6 + [True] * 1 + [False] * 3)
    out = subprocess.run([sys.executable, str(ROOT / "compare.py"), a, b], capture_output=True, text=True).stdout
    assert "A correct only = 6, B correct only = 0" in out
    assert "p = 0.0312" in out  # 2 * 1/64
    assert "WARNING" in out  # 6 discordant < 10


def test_agreement_and_meta():
    recs = [rec("up", resp("up"), repeat_labels=["up", "up", "up"]),
            rec("up", resp("up"), repeat_labels=["up", "down", "up"])]
    ag = S.score(recs)["agreement"]
    assert ag["unanimous_rate"] == 0.5
    assert ag["mean_modal_share"] == pytest.approx((1 + 2 / 3) / 2)
    assert S.score([rec("up", resp("up"))])["agreement"] is None
    s = S.score([rec("up", resp("up", meta=("mA", "p9"))), rec("up", resp("up", meta=("mA", "p9")))])
    assert s["meta_seen"] == [{"model": "mA", "prompt_version": "p9"}]


def test_empty_and_report():
    assert S.score([])["direction_accuracy"] is None
    rpt = S.render_report(S.score(FIX), FIX)
    for h in ("Confusion matrix", "Baselines", "Confidence reliability", "Wilson", "m1 / p1"):
        assert h in rpt
    S.render_report(S.score([]), [])  # must not crash on empty input
