#!/usr/bin/env python3
"""Paired McNemar test (exact) on per-image correctness between two results.json files.

Usage: python compare.py results_a/results.json results_b/results.json
Pairs records by filename; correctness = predicted label equals expected label (not_a_chart rows included).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score as S  # noqa: E402

MIN_DISCORDANT = 10


def load(path):
    d = json.loads(Path(path).read_text())
    return d, {r["filename"]: S.is_correct(r) for r in d["records"]}


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    da, a = load(argv[1])
    db, b = load(argv[2])
    common = sorted(set(a) & set(b))
    for name, d in (("A", da), ("B", db)):
        m = d.get("meta", {})
        print(f"{name}: model={m.get('model')} prompt_version={m.get('prompt_version')} hints={m.get('hints')} n={len(d['records'])}")
    if len(common) != len(a) or len(common) != len(b):
        print(f"WARNING: only {len(common)} images in common (A {len(a)}, B {len(b)}); testing on the intersection.")
    both = sum(a[f] and b[f] for f in common)
    neither = sum(not a[f] and not b[f] for f in common)
    a_only = sum(a[f] and not b[f] for f in common)
    b_only = sum(b[f] and not a[f] for f in common)
    p = S.mcnemar_exact(a_only, b_only)
    print(f"Paired images: {len(common)}; both correct {both}, neither {neither}")
    print(f"Discordant: A correct only = {a_only}, B correct only = {b_only} (total {a_only + b_only})")
    print(f"Exact McNemar two-sided p = {p:.4f}")
    if a_only + b_only < MIN_DISCORDANT:
        print(f"WARNING: only {a_only + b_only} discordant pairs (< {MIN_DISCORDANT}); the test has almost no power, "
              "so a large p-value says nothing about whether A and B differ.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
