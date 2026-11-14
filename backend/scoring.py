"""Deterministic P0 scoring. Client-side results are *untrusted* evidence in this demo."""
from __future__ import annotations
from typing import Any

WEIGHTS = {'basic': 50, 'edge': 20}
DIFFICULTY_WEIGHTS = {1: 1.0, 2: 1.5, 3: 2.0}

def score_tests(public_cases: list[dict], reported: list[dict]) -> dict[str, Any]:
    by_id = {r.get('id'): r for r in reported if isinstance(r, dict) and isinstance(r.get('id'), str)}
    score = 0.0
    categories = {}
    mismatches = []
    for category, weight in WEIGHTS.items():
        cases = [t for t in public_cases if t['category'] == category]
        passed = 0
        for case in cases:
            result = by_id.get(case['id'])
            if not result or result.get('pass') is not True or result.get('error'):
                mismatches.append(case['id'])
            else:
                # The runner supplies both actual and pass; do not rely on its pass flag alone.
                if result.get('actual') == case['expected'] and type(result.get('actual')) is type(case['expected']):
                    passed += 1
                else:
                    mismatches.append(case['id'])
        earned = round(weight * passed / len(cases), 2) if cases else 0
        score += earned
        categories[category] = {'passed': passed, 'total': len(cases), 'points': earned, 'possible': weight}
    return {'points': round(score, 2), 'categories': categories, 'failed_ids': mismatches,
            'evidence_trust': 'untrusted_browser_runner'}

def weighted_percent(attempts: list[dict]) -> float:
    numerator = denominator = 0.0
    for a in attempts:
        w = DIFFICULTY_WEIGHTS[a['difficulty']]
        numerator += w * a['effective_score']
        denominator += w * 100
    return round(100 * numerator / denominator, 1) if denominator else 0.0
