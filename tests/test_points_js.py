"""The point calculator (app/static/js/points.js) must give the same factors as
core.scoring, which the database views also match. Runs the JS in Node; skipped without it."""

import json
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest

from core.models import Gender
from core.scoring import Q_POINTS, SinclairCoefficient, q_points_factor, sinclair_factor

NODE = shutil.which("node")
JS = Path(__file__).parent.parent / "app" / "static" / "js" / "points.js"
BODYWEIGHTS = (38.0, 44.3, 55.0, 63.9, 80.45, 109.2, 160.0, 201.161, 230.0)
SINCLAIR = [(0.700752735, 201.161), (0.787004341, 153.757)]

pytestmark = pytest.mark.skipif(NODE is None, reason="node not installed")


def _run_js(expression: str) -> list[float]:
    script = f"const m = require({json.dumps(str(JS))}); console.log(JSON.stringify({expression}));"
    out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_js_sinclair_factor_matches_core():
    cases = [(bw, a, b) for a, b in SINCLAIR for bw in BODYWEIGHTS]
    js = _run_js(f"{json.dumps(cases)}.map(x => m.sinclairFactor(...x))")
    for (bw, a, b), got in zip(cases, js, strict=True):
        expected = sinclair_factor(bw, SinclairCoefficient(Gender.MALE, a, b, 2026, 2028))
        assert got == pytest.approx(expected, rel=1e-12), (bw, a, b)


def test_js_q_points_factor_matches_core():
    cases = [(bw, asdict(Q_POINTS[g]), g) for g in Gender for bw in BODYWEIGHTS]
    js = _run_js(f"{json.dumps([[bw, c] for bw, c, _ in cases])}.map(x => m.qPointsFactor(...x))")
    for (bw, _, gender), got in zip(cases, js, strict=True):
        assert got == pytest.approx(q_points_factor(bw, Q_POINTS[gender]), rel=1e-12), (bw, gender)
