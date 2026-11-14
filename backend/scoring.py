"""Deterministic prototype scoring.

Browser test reports are untrusted evidence, not secure invigilation. Attempts on
the same question are revisions, not separate weight-bearing questions.
"""
from __future__ import annotations
from typing import Any

WEIGHTS = {'basic': 50, 'edge': 20}
DIFFICULTY_WEIGHTS = {1: 1.0, 2: 1.5, 3: 2.0}


def score_tests(public_cases: list[dict], reported: list[dict]) -> dict[str, Any]:
    # Reject ambiguous duplicate IDs instead of accepting whichever report arrived last.
    by_id: dict[str, dict] = {}
    duplicate_ids: set[str] = set()
    for result in reported:
        if not isinstance(result, dict) or not isinstance(result.get('id'), str):
            continue
        case_id = result['id']
        if case_id in by_id:
            duplicate_ids.add(case_id)
        else:
            by_id[case_id] = result

    score = 0.0
    categories = {}
    mismatches = []
    for category, weight in WEIGHTS.items():
        cases = [t for t in public_cases if t['category'] == category]
        passed = 0
        for case in cases:
            result = by_id.get(case['id'])
            if case['id'] in duplicate_ids or not result or result.get('pass') is not True or result.get('error'):
                mismatches.append(case['id'])
            elif result.get('actual') == case['expected'] and type(result.get('actual')) is type(case['expected']):
                passed += 1
            else:
                mismatches.append(case['id'])
        earned = round(weight * passed / len(cases), 2) if cases else 0
        score += earned
        categories[category] = {'passed': passed, 'total': len(cases), 'points': earned, 'possible': weight}
    return {'points': round(score, 2), 'categories': categories, 'failed_ids': mismatches,
            'evidence_trust': 'untrusted_browser_runner'}


def weighted_percent(attempts: list[dict]) -> float:
    """Weight one final revision per question, not every resubmission.

    When question_id is missing (e.g. standalone scoring examples), treat entries
    as separate questions for backwards compatibility. Attempts are expected in
    ascending chronological order, as returned by backend/main.py.
    """
    final_by_question: dict[str, dict] = {}
    for index, attempt in enumerate(attempts):
        question_id = attempt.get('question_id', f'__index_{index}')
        final_by_question[question_id] = attempt

    numerator = denominator = 0.0
    for attempt in final_by_question.values():
        weight = DIFFICULTY_WEIGHTS[attempt['difficulty']]
        numerator += weight * attempt['effective_score']
        denominator += weight * 100
    return round(100 * numerator / denominator, 1) if denominator else 0.0
