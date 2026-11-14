# Cognit

**A working university Python assessment prototype for the Imperial AI Hackathon, 14–15 November 2026.** Cognit scores executable behaviour, collects conceptual explanations and checks for independent transfer after guided practice. Students can access bounded documentation help. Teachers can inspect attempts and override provisional conceptual grades with an audit record.

> **Demonstration software, not a secure examination platform.** Python executes in a browser Pyodide Web Worker, so test evidence can be tampered with by someone controlling their browser. Assessment question cases are client-visible, the teacher dashboard lacks authentication, and SQLite persistence is local. Do not use this to assess real students without an isolated trusted code runner, authentication, role-based access and a security review.

## Run locally

Requirements: Python 3.10+ and internet access in the **student's browser** for the Pyodide and Monaco CDNs. The backend needs internet only if using Anthropic grading.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

Open **http://localhost:8000**. The API health endpoint is `http://localhost:8000/health`. OpenAPI documentation is at `http://localhost:8000/docs`.

The app is a single-server frontend, with no Node build required. Monaco automatically falls back to a plain editor if its CDN is unavailable. **Python execution still requires a working Pyodide CDN.** Infinite loops are stopped by terminating the worker after an 8-second run timeout.

### Optional Anthropic AI conceptual grading

Set `ANTHROPIC_API_KEY` in the backend process environment before starting the server. Optionally set `ANTHROPIC_MODEL` to a model available to your API account. Keys never enter the frontend. The backend calls the model to grade conceptual explanations using a 15-point idea, 10-point complexity and 5-point edge-case rubric.

Without the key, or if an API call fails, Cognit uses a **clearly labelled offline keyword-based preview**, which is **not AI grading** and requires human review. The restricted reference, plan and hint responses work offline from vetted text. Never claim that offline mode meets the AI-grading requirement.

For a local persistent SQLite file, set `COGNIT_DB_PATH=/absolute/path/to/cognit.sqlite3`. A default `cognit.sqlite3` is created in the project directory. Do not place this on an ephemeral host and claim it is persistent.

## What works

- Student session with four question stages and three skills: loops, strings and hashing.
- Nine vetted tasks at three difficulty levels with six deterministic tests per task.
- Monaco Python editor with plain-text fallback.
- Pyodide Web Worker execution with exceptions, stdout and timeout protection for responsiveness.
- Basic correctness 50%, edge tests 20%, rubric-based conceptual understanding 30%.
- Difficulty weights ×1, ×1.5, ×2 and assisted-to-independent transfer selection.
- Reference lookup restricted to Python documentation. Hints and high-level Plan Mode after first submission. Direct solution requests refused by a basic policy filter.
- Multiple submissions per question (maximum three), scores and help events in SQLite.
- Teacher dashboard showing attempted questions, assistance, provisional grades and heuristic mastery signals, plus teacher override with audit history.
- Optional Anthropic model for conceptual grading, with deterministic clearly-labelled fallback.

## Project layout

```text
backend/main.py       FastAPI contracts, session routing, adaptive state, dashboard
backend/problems.py   Vetted task bank and reference test generation
backend/scoring.py    Objective scoring and difficulty weighted totals
backend/ai.py         Approved docs, restricted assistance, optional concept AI grading
backend/store.py      SQLite schema and persistence
frontend/index.html   Assessment and teacher interface
frontend/app.js       Browser interactions, API requests and editor
frontend/runner.worker.js  Pyodide execution without server-side student code
frontend/styles.css  Interface styles
tests/test_api.py      Scoring and API integration tests
```

## Development and test

```bash
PYTHONPATH=. pytest -q
node --check frontend/app.js
node --check frontend/runner.worker.js
```

For a smoke run:

```bash
python -m uvicorn backend.main:app --port 8000
curl http://localhost:8000/health
```

The integration tests use synthetic, trusted test payloads to verify endpoint contracts. This **does not prove** browser Pyodide works in a particular browser or that real student test submissions cannot be forged. Use a real browser for final UI and Pyodide verification.

## API

Every successful endpoint responds `{"ok":true,"data":...}`. HTTP errors use FastAPI `detail` with an error code and message.

- `POST /api/session/start` -> session ID and public question
- `GET /api/session/{session_id}` -> restore active question
- `POST /api/attempt` -> deterministic test points and optional AI conceptual grading
- `POST /api/assist` -> approved docs, restricted hint or plan
- `POST /api/next` -> next/transfer question, or assessment completion
- `GET /api/teacher/session/{session_id}` -> saved evidence and heuristic mastery
- `POST /api/teacher/review` -> override and audit trail
- `GET /api/info` and `/health` -> capability disclosure

The browser receives all execution test cases in the public question payload and submits test results. This makes the local demonstration deterministic, but **not trustworthy for exams**. The backend recomputes the pass flag from reported actual values and expected cases, but cannot independently verify that the student code produced those values.

## Responsible claims

Cognit combines deterministic programming tests, concept rubrics, bounded reference help, and transfer checks. It **does not** prove student authenticity, prevent all cheating, stop all answer leakage or provide a validated psychometric measurement. Heuristic mastery indicators are descriptive. Assistance counts do not lower grades by themselves. Every AI evaluation remains subject to teacher review.

## Demo guide

See [`docs/DEMO.md`](docs/DEMO.md) for a 2-minute recording script, manual browser test checklist and submission tasks. The team must upload a verified video and submit via Devpost separately. No external deployment or submission has been performed by the code alone.
