#!/usr/bin/env python3
"""Generate synthetic chart PNGs, labels.synthetic.csv and ohlcv/*.csv. Plumbing test only.

Labels follow the contract definition of trend.direction (visible trend, not a forecast), applied mechanically
to the realized series: net close-to-close move across the window vs the mean bar range. A move of at least
LABEL_RANGES mean bar ranges is up/down, anything smaller is sideways. Drift and noise levels overlap on purpose,
so some charts sit near the threshold and are genuinely ambiguous. No label or noise level appears in any image.
"""
import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

HERE = Path(__file__).resolve().parent
LABEL_RANGES = 3.0
N_BARS = 60
N_CHARTS = 20
DRIFTS = [-0.30, -0.18, -0.08, -0.03, 0.0, 0.03, 0.08, 0.18, 0.30]
NOISES = [0.4, 0.7, 1.0, 1.3, 1.6]
THEMES = {
    "light": {"figure.facecolor": "white", "axes.facecolor": "white", "text.color": "black", "axes.labelcolor": "black",
              "xtick.color": "black", "ytick.color": "black", "axes.edgecolor": "black", "grid.color": "#bbbbbb"},
    "dark": {"figure.facecolor": "#131722", "axes.facecolor": "#131722", "text.color": "#d1d4dc", "axes.labelcolor": "#d1d4dc",
             "xtick.color": "#d1d4dc", "ytick.color": "#d1d4dc", "axes.edgecolor": "#363a45", "grid.color": "#363a45"},
}


def make_series(drift, noise, n, rng):
    close, rows = 100.0, []
    for _ in range(n):
        o = close
        c = o + drift + rng.normal(0, noise) - (0.15 * (o - 100.0) if drift == 0 else 0)
        h = max(o, c) + abs(rng.normal(0, noise * 0.5))
        l = min(o, c) - abs(rng.normal(0, noise * 0.5))
        rows.append((o, h, l, c))
        close = c
    return rows


def label_from_rows(rows):
    """Contract-style visible-trend label. Returns (label, net/mean_range)."""
    net = rows[-1][3] - rows[0][3]
    mean_range = sum(h - l for _, h, l, _ in rows) / len(rows)
    ratio = net / mean_range
    return ("sideways" if abs(ratio) < LABEL_RANGES else "up" if ratio > 0 else "down"), ratio


def draw(rows, path, theme, ma, crop):
    with plt.rc_context(THEMES[theme]):
        fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
        up, dn = ("#26a69a", "#ef5350")
        for i, (o, h, l, c) in enumerate(rows):
            col = up if c >= o else dn
            ax.plot([i, i], [l, h], color=col, lw=1)
            ax.add_patch(Rectangle((i - 0.3, min(o, c)), 0.6, max(abs(c - o), 0.01), color=col))
        if ma:
            closes = np.array([r[3] for r in rows])
            sma = np.convolve(closes, np.ones(20) / 20, mode="valid")
            ax.plot(range(19, len(rows)), sma, color="#ffa000", lw=1.5, label="MA 20")
            ax.legend(loc="upper left", frameon=False)
        ax.set_xlim(-1, len(rows))
        ax.set_title("SYNTH  1h")
        ax.set_xlabel("Bars")
        ax.set_ylabel("Price")
        ax.grid(alpha=0.4)
        if crop:  # axis partly cut off: push the left/bottom axes labels off the canvas
            fig.subplots_adjust(left=0.035, bottom=0.04, right=0.97, top=0.92)
        else:
            fig.tight_layout()
        fig.savefig(path, facecolor=fig.get_facecolor())
        plt.close(fig)


def draw_negative(kind, path, theme, rng):
    with plt.rc_context(THEMES[theme]):
        fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
        cats = ["Rent", "Food", "Travel", "Fun", "Savings"]
        vals = rng.uniform(5, 40, len(cats))
        if kind == "bar":
            ax.bar(cats, vals, color="#5c6bc0")
            ax.set_title("Monthly spending by category")
            ax.set_ylabel("Amount")
        else:
            ax.pie(vals, labels=cats, autopct="%1.0f%%", textprops={"color": THEMES[theme]["text.color"]})
            ax.set_title("Share of spending")
        fig.tight_layout()
        fig.savefig(path, facecolor=fig.get_facecolor())
        plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "charts_synthetic"))
    ap.add_argument("--labels", default=str(HERE / "labels.synthetic.csv"))
    ap.add_argument("--ohlcv", default=str(HERE / "ohlcv"))
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    out, ohlcv = Path(a.out), Path(a.ohlcv)
    out.mkdir(parents=True, exist_ok=True)
    ohlcv.mkdir(parents=True, exist_ok=True)
    for p in list(out.glob("synth_*.png")) + list(ohlcv.glob("synth_*.csv")):
        p.unlink()

    # Cycle drift/noise independently (coprime lengths) so every drift meets several noise levels.
    drifts = [DRIFTS[(i * 4) % len(DRIFTS)] for i in range(N_CHARTS)]
    noises = [NOISES[(i * 3 + i // 5) % len(NOISES)] for i in range(N_CHARTS)]
    rows = []
    for i in range(N_CHARTS):
        fn = f"synth_{i+1:02d}.png"
        series = make_series(drifts[i], noises[i], N_BARS, rng)
        theme = "dark" if i % 2 else "light"
        ma, crop = i % 3 == 0, i % 5 == 4
        draw(series, out / fn, theme, ma, crop)
        label, ratio = label_from_rows(series)
        with open(ohlcv / f"synth_{i+1:02d}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["bar", "open", "high", "low", "close"])
            for j, (o, h, l, c) in enumerate(series):
                w.writerow([j, f"{o:.4f}", f"{h:.4f}", f"{l:.4f}", f"{c:.4f}"])
        note = f"synthetic, {theme}{', ma20' if ma else ''}{', cropped' if crop else ''}, net/range={ratio:.1f}, drift={drifts[i]}, noise={noises[i]}"
        if abs(abs(ratio) - LABEL_RANGES) < 1.0:
            note += ", near threshold (ambiguous)"
        rows.append([fn, "SYNTH", "1h", label, note])
    for j, kind in enumerate(["bar", "pie", "bar", "pie"]):
        fn = f"synth_neg_{j+1:02d}.png"
        draw_negative(kind, out / fn, "light" if j < 2 else "dark", rng)
        rows.append([fn, "", "", "not_a_chart", f"synthetic negative: {kind} chart of categories"])
    with open(a.labels, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["filename", "instrument", "timeframe", "expected_direction", "notes"])
        w.writerows(rows)
    from collections import Counter
    print(f"Wrote {len(rows)} images to {out}, labels to {a.labels}, ohlcv to {ohlcv}")
    print("Label counts:", dict(Counter(r[3] for r in rows)))


if __name__ == "__main__":
    main()
