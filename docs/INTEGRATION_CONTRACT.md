# Cognit integration contract (freeze for hackathon demo)

**Owner:** Ahmed (scoring, integration and QA). **Last audited:** 14 November 2026. This documents the *current* `backend/main.py` API, not proposed endpoints. Aalia owns backend implementation, DS owns browser/UI, and Shreya owns assessment intelligence. Do not change another owner's source files to satisfy this contract without coordinating.

## Run and shared transport

- Origin: one FastAPI process at `http://localhost:8000`, serving the UI at `/` and static files at `/static/*`.
- API JSON successes have shape `{"ok": true, "data": { ... }}`.
- API errors are non-2xx, with FastAPI `{"detail": {"code": "...", "message": "..."}}` for explicit app errors. Schema validation uses FastAPI's own 422 response.
- Create a session first, then keep its `session_id`. Every active assessment API also uses the current `question.id`.
- Python runs **in browser Pyodide Web Worker**. The backend **does not** execute student code. The browser sends test results which are **untrusted** and must never be represented as exam-secure.
- Never put `ANTHROPIC_API_KEY` in the client bundle, HTML, Git history, screenshots or test fixtures.

## Exact current request/response contracts

### 1. Start `POST /api/session/start`

Request: `{"student_alias":"Demo Student"}`.

Response `data` has `session_id`, `question` and `state`. Public `question` contains `id`, `seed`, `skill_tags`, `difficulty` (1/2/3), `title`, `statement`, `function_signature`, `function_name`, `example_tests` (array), `hint_policy` and `max_points`. Each test includes `id`, `args` (positional arguments array), `expected`, `category` (`basic` or `edge`). `state` contains `stage`, `difficulty`, `allowed_help`, `question_number` and `total_questions`. Four questions total.

### 2. Execute Python in the browser (DS)

For each `question.example_tests` element, execute the submitted function named `question.function_name` with positional `args`. Compare the **actual JSON value** and **Python type** with `expected`. Return `{"id":"t0","pass":true,"actual":3,"error":null}` for successful matches and set `pass:false` with useful `error` for failures. The client runner must terminate long-running workers, recover after timeout and allow submission of failures. Do not execute untrusted student code on the FastAPI server.

### 3. Submit `POST /api/attempt`

Request:

```json
{
  "session_id": "session UUID",
  "question_id": "multiples:1234",
  "code": "def count_multiples(numbers, divisor):\n    return 0",
  "explanation": "I iterate once and handle empty lists.",
  "plan": "",
  "client_test_results": [
    {"id": "t0", "pass": false, "actual": 0, "error": null}
  ],
  "help_events": []
}
```

There are six cases in the current bank. Supply an entry for every run case. `pass` is the wire field name (not `pass_`). The server checks IDs, types and equality against its own expected results and scores only verified reported outcomes. It **cannot prove code produced those outputs**, so this is a demonstrator only.

Response `data` contains `attempt_id`, `provisional_score`, `code_score`, `concept_score`, `concept_method`, `breakdown` with `functional` / `edge_cases` / `conceptual`, `flags`, `feedback`, `mastery_snapshot`, `next_action` and `evidence_trust`.

Scoring: basic tests **50**, edge tests **20**, concept explanation **30**. Medium and hard difficulty contribute respectively **×1.5** and **×2** to aggregate percentage. Three submissions maximum per question. If Anthropic is unavailable, label concept result `heuristic_preview` and request teacher review, never call it AI grading.

### 4. Help `POST /api/assist`

Request: `{"session_id":"...","question_id":"...","mode":"lookup","query":"Python set membership"}`. `mode` is one of `lookup`, `hint`, `plan`. `current_attempt_id` is optional.

Response `data`: `decision` (`allow`, `deny`, `limit`), `content`, `citations`, `hint_level`, `reason_code`. Lookup works before an attempt. Hint and Plan Mode are locked until the first submitted attempt. Solution requests may be denied. Approved documentation citations are separate from the assistant reply.

### 5. Advance `POST /api/next`

Request: `{"session_id":"...","previous_attempt_id":"..."}`. The attempt must belong to the current question. Response `data` is either `{"complete":true,"state":{"stage":"complete"},"overall_percent":...}` or contains `question`, `reason` (`same`, `harder`, `remedial`, `transfer`) and `state`.

Assisted passing submissions can trigger a different, independent transfer problem. Two consecutive independent passing questions may increase difficulty. Do not claim adaptive mastery has been validated psychometrically.

### 6. Restore and teacher review

- `GET /api/session/{session_id}` returns current `question`, `state`, `current_attempt_id`.
- `GET /api/teacher/session/{session_id}` returns `session`, `attempts`, `score_breakdown`, `mastery_by_skill`, `assisted_vs_independent`, `help_log`, `review_flags`.
- `POST /api/teacher/review` accepts `{"attempt_id":"...","override_concept_score":20,"approved":true,"reviewer_note":"Checked orally"}`. Concept override is 0..30 and preserves objective points. Response has `review_status`, `effective_score`, `previous_score`, `audit_recorded`.
- `GET /health`, `GET /api/info` disclose runtime and prototype limitations.
- Teacher endpoints have **no authentication** in this demo. Use synthetic student data only.

## Owners and dependency checkpoints

| Owner | Input from Ahmed | Delivery back to Ahmed | Acceptance gate |
|---|---|---|---|
| **Aalia** | Existing endpoints and schema above | Working FastAPI process, database persistence, `/health`, `/docs` | `pytest -q`, local `POST /api/attempt` and teacher retrieval |
| **DS** | Question schema, test result object, submission and help routes | Browser editor + Pyodide worker, teacher dashboard, 2-minute video | Real browser can run code, time out a loop, submit, persist, show review |
| **Shreya** | 30-point rubric, existing `/api/assist` and concept API | Proven model result format, bounded-help tests, varied but **validated** question variants | Grading result respects 0..15 idea / 0..10 complexity / 0..5 edges and is clearly labelled when fallback |
| **Ahmed** | Integration gates and published contracts | Scoring QA, regression tests, handoff documentation, final review / Devpost package | Do not merge until tests pass and the actual browser demo is verified |

### P0 freeze

Do not rename API fields or change test IDs without alerting every owner. Prefer current single-origin FastAPI hosting over introducing cross-origin CORS before the deadline. Preserve the runnable local demo if deployment fails. Freeze feature work before final video and submission checks.

## Known contract limitations to be explicit about

1. The public test cases are disclosed to the client. The backend checks reported values but cannot validate the origin of execution evidence.
2. Question `seed` currently does **not** change the task input cases. Varied tasks exist in the bank, but genuine per-seed parameterisation is not yet implemented.
3. Teacher review is open and SQLite is a local file. Production-grade auth, isolation and reliable persistent hosting are outside this demo.
4. Model grading requires a *server-side* key and live validation. Offline keyword previews cannot be described as AI model grades.
