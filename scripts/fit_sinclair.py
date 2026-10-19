"""Recover the Sinclair coefficients vlstat used, per gender and year, from saved pages.

Use it to (1) check our known coefficient cycles reproduce vlstat's points and (2) find
the 2025+ values, which IWF hasn't published as far as we know. Reads local files only.

Usage: python -m scripts.fit_sinclair
"""

import math
import sys
from collections import defaultdict

from core.scoring import total
from scraper.parse_and_seed import RAW_DIR
from scraper.parse_results import parse_results_page


def fit(points: list[tuple[float, float]]) -> tuple[float, float, float]:
    """points: (bodyweight, log10(sinclair/total)). Returns (a, b, rms error of the factor)."""
    best = (math.inf, 0.0, 0.0)
    for b100 in range(10_000, 25_000):  # b from 100.00 to 249.99 kg
        b = b100 / 100
        xs = [math.log10(bw / b) ** 2 if bw < b else 0.0 for bw, _ in points]
        sxx = sum(x * x for x in xs)
        if sxx == 0:
            continue
        a = sum(x * r for x, (_, r) in zip(xs, points, strict=True)) / sxx
        sse = sum((a * x - r) ** 2 for x, (_, r) in zip(xs, points, strict=True))
        if sse < best[0]:
            best = (sse, a, b)
    sse, a, b = best
    return a, b, math.sqrt(sse / len(points))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    groups: dict[tuple[int, str], list[tuple[float, float]]] = defaultdict(list)
    for page in RAW_DIR.glob("*/*.html"):
        year = int(page.parent.name)
        for row in parse_results_page(page.read_text(encoding="utf-8")).rows:
            e, src = row.entry, row.source
            ours = total(e.attempts)
            if src.points_kind != "sinclair" or not (
                ours and src.points and e.bodyweight and e.gender
            ):
                continue
            if src.total != ours:
                print(f"  total mismatch {year} {e.lifter_name}: vlstat {src.total}, ours {ours}")
                continue
            groups[(year, e.gender)].append(
                (float(e.bodyweight), math.log10(float(src.points) / ours))
            )

    print("year gender   n          a         b   rms")
    for (year, gender), pts in sorted(groups.items()):
        if len(pts) < 5:
            print(f"{year} {gender}  {len(pts):4d}  (too few points)")
            continue
        a, b, rms = fit(pts)
        print(f"{year} {gender}  {len(pts):4d}  {a:.9f}  {b:8.2f}  {rms:.1e}")


if __name__ == "__main__":
    main()
