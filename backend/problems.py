"""Vetted, parameterised questions. Reference functions and all test generation stay on the API.

The browser receives tests for a transparent hackathon demo, not a secure exam.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable
import random

@dataclass(frozen=True)
class Problem:
    key: str
    skill: str
    difficulty: int
    title: str
    statement: str
    function_name: str
    signature: str
    hint: str
    plan: str
    concept_key: str
    rubric: str
    cases: list[tuple[list[Any], str]]
    reference: Callable[..., Any]
    transfer: str | None = None


def count_multiples(numbers, divisor):
    return sum(1 for x in numbers if x % divisor == 0)

def count_positive(numbers):
    return sum(1 for x in numbers if x > 0)

def reverse_words(text):
    return ' '.join(reversed(text.split()))

def balanced_parentheses(text):
    depth = 0
    for c in text:
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth < 0:
                return False
    return depth == 0

def first_repeated(items):
    seen = set()
    for x in items:
        if x in seen:
            return x
        seen.add(x)
    return None

def first_unique(items):
    counts = Counter(items)
    return next((x for x in items if counts[x] == 1), None)

def pair_sum_exists(numbers, target):
    seen = set()
    for x in numbers:
        if target - x in seen:
            return True
        seen.add(x)
    return False

def longest_unique_span(text):
    starts = {}
    left = best = 0
    for right, char in enumerate(text):
        if char in starts and starts[char] >= left:
            left = starts[char] + 1
        starts[char] = right
        best = max(best, right - left + 1)
    return best

def longest_increasing_run(numbers):
    if not numbers:
        return 0
    best = current = 1
    for i in range(1, len(numbers)):
        current = current + 1 if numbers[i] > numbers[i-1] else 1
        best = max(best, current)
    return best

BANK: dict[str, Problem] = {}
def add(p: Problem) -> None:
    BANK[p.key] = p

add(Problem('multiples', 'loops', 1, 'Count multiples',
    'Return the number of integers in numbers divisible by divisor. Divisor is non-zero. Do not modify the input.',
    'count_multiples', 'def count_multiples(numbers, divisor):',
    'Consider what condition makes one number qualify, and how an accumulator changes.',
    'List the input and output types, then describe a single pass and one boundary test.',
    'iteration and divisibility', 'Explain iteration, divisibility, O(n) time and empty-list behaviour.',
    [([[1,2,3,4,5,6],2], 'basic'), ([[7,14,21,28],7], 'basic'), ([[1,3,5],2], 'basic'), ([[],3], 'edge'), ([[-6,0,8,-12],-3], 'edge'), ([[0],5], 'edge')],
    count_multiples, 'positive'))
add(Problem('positive', 'loops', 1, 'Count positive values',
    'Return the number of strictly positive integers in numbers. Zero is not positive.',
    'count_positive', 'def count_positive(numbers):',
    'Decide exactly which comparisons should count as positive.',
    'State the predicate and the counter invariant. Include a boundary input.',
    'iteration and comparison', 'Explain single-pass counting, O(n) time, zero and negative inputs.',
    [([[-1,2,3,-4]],'basic'), ([[1,2,3]],'basic'), ([[-1,-2]],'basic'), ([[]],'edge'), ([[0,0,0]],'edge'), ([[-100,0,100]],'edge')],
    count_positive, 'multiples'))
add(Problem('reverse_words', 'strings', 1, 'Reverse word order',
    'Return words in reverse order separated by exactly one space. Ignore extra whitespace in the input.',
    'reverse_words', 'def reverse_words(text):',
    'Think about splitting into words before deciding how to join them.',
    'Outline tokenisation, order transformation, and whitespace edge cases.',
    'string tokenisation', 'Explain split/join, word order, handling whitespace and O(n) processing.',
    [(['one two three'],'basic'), (['hello world'],'basic'), (['a b'],'basic'), ([''],'edge'), (['   many    spaces  here '],'edge'), ([' single '],'edge')],
    reverse_words))
add(Problem('balanced', 'strings', 2, 'Balanced parentheses',
    'Given a string containing only ( and ), return True when every opening parenthesis has a matching closing one in the correct order.',
    'balanced_parentheses', 'def balanced_parentheses(text):',
    'An aggregate balance is not enough unless you also check prefixes.',
    'Describe an invariant for every prefix and what happens at the end.',
    'prefix invariant', 'Explain balance invariant, negative prefixes, final zero, and O(n) time.',
    [(['(())'],'basic'), (['()()'],'basic'), (['(()'],'basic'), ([''],'edge'), ([')('],'edge'), (['((()))'],'edge')],
    balanced_parentheses, 'reverse_words'))
add(Problem('repeat', 'hashing', 2, 'First repeated item',
    'Return the first integer encountered for the second time while reading items left to right. If no value repeats, return None.',
    'first_repeated', 'def first_repeated(items):',
    'Which previously visited values do you need to remember?',
    'Describe the data structure for membership checks and when you stop.',
    'set membership', 'Explain seen-set membership, first second-occurrence, average O(n) time, and no-repeat case.',
    [([[2,1,2,1]],'basic'), ([[5,3,4,3,5]],'basic'), ([[1,2,3]],'basic'), ([[]],'edge'), ([[0,0]],'edge'), ([[-1,2,-1]],'edge')],
    first_repeated, 'unique'))
add(Problem('unique', 'hashing', 2, 'First unique item',
    'Return the first integer in the original list whose total frequency equals one. Return None if every item is repeated.',
    'first_unique', 'def first_unique(items):',
    'Think about learning each value’s total frequency before choosing an answer.',
    'Describe two passes and the information the first pass must store.',
    'frequency counting', 'Explain frequency table, original order, O(n) expected time and all-duplicate case.',
    [([[4,1,4,2,1]],'basic'), ([[2,3,2,4]],'basic'), ([[1,1,1]],'basic'), ([[]],'edge'), ([[0]],'edge'), ([[-1,-1,0,0,8]],'edge')],
    first_unique, 'repeat'))
add(Problem('pair_sum', 'hashing', 3, 'Find a matching pair',
    'Return True if two different positions in numbers contain values summing to target. Otherwise return False.',
    'pair_sum_exists', 'def pair_sum_exists(numbers, target):',
    'What complement would each number need, and what prior information could help?',
    'Write down the complement idea, the two-distinct-positions constraint, and a duplicate test.',
    'hash complement', 'Explain complement lookup, two distinct positions, expected O(n), negatives and duplicates.',
    [([[2,7,11,15],9],'basic'), ([[3,3],6],'basic'), ([[1,2,3],9],'basic'), ([[],0],'edge'), ([[3],6],'edge'), ([[-2,7,4],5],'edge')],
    pair_sum_exists, 'repeat'))
add(Problem('unique_span', 'strings', 3, 'Longest distinct-character span',
    'Return the length of the longest contiguous substring with no repeated characters.',
    'longest_unique_span', 'def longest_unique_span(text):',
    'A moving start index can prevent rechecking substrings from scratch.',
    'Describe a sliding window invariant and what happens when a character repeats.',
    'sliding window', 'Explain last-seen indices, sliding window, O(n) time, empty input and repeated characters.',
    [(['abcabcbb'],'basic'), (['pwwkew'],'basic'), (['abcdef'],'basic'), ([''],'edge'), (['aaaa'],'edge'), (['🙂a🙂b'],'edge')],
    longest_unique_span, 'balanced'))
add(Problem('increasing_run', 'loops', 3, 'Longest increasing run',
    'Return the length of the longest contiguous strictly increasing run of integers. Equal neighbours break a run.',
    'longest_increasing_run', 'def longest_increasing_run(numbers):',
    'Track both the current run and the best run seen so far.',
    'Explain the reset condition, update order, and empty input.',
    'one-pass state', 'Explain adjacent comparison, reset, O(n) time, and empty/equal-value cases.',
    [([[1,2,3,1,2]],'basic'), ([[3,2,1]],'basic'), ([[1,2,2,3]],'basic'), ([[]],'edge'), ([[8]],'edge'), ([[-3,-2,-1,0]],'edge')],
    longest_increasing_run, 'positive'))

SKILLS = ('loops', 'strings', 'hashing')

def select_problem(difficulty: int, skill: str | None = None, avoid: set[str] | None = None, prefer: str | None = None) -> Problem:
    avoid = avoid or set()
    if prefer and prefer in BANK and prefer not in avoid:
        return BANK[prefer]
    choices = [p for p in BANK.values() if p.difficulty == difficulty and p.key not in avoid and (skill is None or skill == p.skill)]
    if not choices:
        choices = [p for p in BANK.values() if p.key not in avoid and (skill is None or skill == p.skill)]
    if not choices:
        choices = [p for p in BANK.values() if p.key not in avoid]
    return sorted(choices, key=lambda p: (abs(p.difficulty-difficulty), p.key))[0]

def public_question(p: Problem, seed: int) -> dict[str, Any]:
    random.Random(seed)  # Seed is retained for versioned, future variations.
    return {
        'id': f'{p.key}:{seed}', 'seed': seed, 'skill_tags': [p.skill], 'difficulty': p.difficulty,
        'title': p.title, 'statement': p.statement, 'function_signature': p.signature,
        'function_name': p.function_name,
        'example_tests': [{'id': f't{i}', 'args': args, 'expected': p.reference(*args), 'category': category}
                          for i, (args, category) in enumerate(p.cases)],
        'hint_policy': 'Hint and Plan Mode unlock after the first submitted attempt.', 'max_points': 100,
    }

def parse_id(qid: str) -> tuple[Problem, int]:
    try:
        key, seed_str = qid.split(':', 1)
        seed = int(seed_str)
        if not 0 <= seed < 2**31:
            raise ValueError()
        return BANK[key], seed
    except (ValueError, KeyError) as exc:
        raise ValueError('Unknown question ID') from exc
