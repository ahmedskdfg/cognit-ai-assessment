# Cognit demo and release checklist

## Two-minute walkthrough

1. **0:00–0:12:** Open student view. Say: 'Cognit lets students use approved help while measuring independent programming ability.' Start a synthetic session.
2. **0:12–0:35:** Solve the Count multiples task in the Monaco editor. Run code and demonstrate six deterministic browser tests. Explain that the browser runner is *not exam-secure*.
3. **0:35–0:55:** Submit an explanation with edge-case reasoning. Show the split 50/20/30 feedback. If no Anthropic key is available, label the conceptual assessment 'heuristic preview', not AI.
4. **0:55–1:10:** Request 'give me the full solution' in Reference mode and show the refusal. Then search 'set membership' and show approved docs links. Request Plan Mode after your first submission.
5. **1:10–1:30:** Revise and resubmit, then click Continue. If an assisted pass was recorded, show independent transfer at the same difficulty. Otherwise note adaptive progression after two independent passes.
6. **1:30–1:50:** Open the teacher view. Show stored attempts and assistance history. Override one concept score and refresh to show the audit record.
7. **1:50–2:00:** Show team names, architecture and truthful limitations. Do not claim measured leakage prevention without evaluation data.

## Browser manual acceptance checks

- [ ] Student alias and first question visible
- [ ] Monaco loads, or fallback editor works without visual corruption
- [ ] Pyodide CDN loads and executes `count_multiples`
- [ ] Six correct tests produce 70 objective points
- [ ] Wrong function name produces useful errors
- [ ] `while True: pass` times out and subsequent worker reinitialises
- [ ] Direct solution request denied
- [ ] Official documentation lookup contains real links
- [ ] Hint/Plan unavailable before first attempt, available after
- [ ] Revised attempt persists to teacher dashboard
- [ ] After assistance, passing attempt leads to transfer
- [ ] Teacher override saves with a review note
- [ ] Reload preserves the session and dashboard
- [ ] Check browser developer console for uncaught errors

## Suggested tested code for first problem (DEMO OPERATOR ONLY)

```python
def count_multiples(numbers, divisor):
    return sum(1 for n in numbers if n % divisor == 0)
```

Example explanation: 'I scan numbers once, count entries divisible by divisor and return that count. This is O(n) time and O(1) extra space. Empty input returns zero. Negative numbers and zero work with the remainder test.'

The verified example is for recording and manual QA, not made available inside the student assistant.

## Release gate

- [ ] End-to-end local video tested and playable
- [ ] Concept model connection verified or clearly labelled as offline fallback
- [ ] Frontend browser tested with network access
- [ ] Public repository contains no secrets or private files
- [ ] Record exact tested steps and failures
- [ ] Verify hosting if deployed, especially storage persistence and backend CORS
- [ ] Include actual video URL and repository on Devpost
- [ ] Register all four students on the submission
- [ ] Submit before 15 November 2026 12:00 GMT (team internal cutoff 11:15)
