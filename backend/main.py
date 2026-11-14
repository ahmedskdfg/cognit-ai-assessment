"""Cognit hackathon prototype API and single-server static frontend."""
from __future__ import annotations
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .ai import bounded_help, grade_concept
from .problems import BANK, parse_id, public_question, select_problem
from .scoring import score_tests, weighted_percent
from .store import Store

ROOT = Path(__file__).resolve().parent.parent
now = lambda: datetime.now(timezone.utc).isoformat()
uid = lambda: str(uuid.uuid4())

class StartIn(BaseModel):
    student_alias: str = Field(min_length=1,max_length=60)
class TestResult(BaseModel):
    id: str
    pass_: bool = Field(alias='pass')
    actual: Any = None
    error: str | None = None
class HelpEvent(BaseModel):
    type: str
    timestamp: str
class AttemptIn(BaseModel):
    session_id: str
    question_id: str
    code: str = Field(max_length=20000)
    explanation: str = Field(max_length=4000)
    plan: str = Field(default='',max_length=4000)
    client_test_results: list[TestResult] = Field(max_length=50)
    help_events: list[HelpEvent] = Field(default_factory=list)
class NextIn(BaseModel):
    session_id: str
    previous_attempt_id: str
class AssistIn(BaseModel):
    session_id: str
    question_id: str
    mode: Literal['lookup','plan','hint']
    query: str = Field(max_length=1000)
    current_attempt_id: str | None = None
class ReviewIn(BaseModel):
    attempt_id: str
    override_concept_score: float | None = Field(default=None,ge=0,le=30)
    approved: bool = True
    reviewer_note: str = Field(default='',max_length=1000)

def envelope(data: Any):
    return {'ok':True, 'data':data}

def must_session(db: Store, sid: str) -> dict:
    row = db.one('SELECT * FROM sessions WHERE id=?',(sid,))
    if not row:
        raise HTTPException(404, detail={'code':'unknown_session','message':'Session not found'})
    return row

def attempts_for(db: Store, sid: str) -> list[dict]:
    rows = db.all('SELECT * FROM attempts WHERE session_id=? ORDER BY created_at, rowid',(sid,))
    for a in rows:
        a['test'] = json.loads(a.pop('test_json'))
        a['concept'] = json.loads(a.pop('concept_json'))
        a['flags'] = json.loads(a.pop('flags_json'))
        a['review'] = db.one('SELECT * FROM reviews WHERE attempt_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1',(a['id'],))
        a['effective_score'] = a['review']['new_score'] if a['review'] else a['score']
        a['assistance_used'] = bool(a['assistance_used'])
        a['difficulty'] = parse_id(a['question_id'])[0].difficulty
        a['skill'] = parse_id(a['question_id'])[0].skill
    return rows

def mastery_snapshot(attempts: list[dict]) -> dict:
    result = {}
    for skill in ('loops','strings','hashing'):
        group = [a for a in attempts if a['skill']==skill]
        independent = [a for a in group if not a['assistance_used']]
        assisted = [a for a in group if a['assistance_used']]
        passed = [a for a in independent if a['test']['points'] >= 56]
        result[skill] = {'attempts':len(group),'independent_passes':len(passed),
                         'independent_attempts':len(independent),'assisted_attempts':len(assisted),
                         'independent_average':round(sum(a['effective_score'] for a in independent)/len(independent),1) if independent else None,
                         'assisted_average':round(sum(a['effective_score'] for a in assisted)/len(assisted),1) if assisted else None,
                         'mastery_indicator':'developing' if len(passed)<2 else 'evidence_of_progress'}
    return result

def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(title='Cognit Prototype', version='0.1.0',description='Demo only. Browser execution evidence is untrusted.')
    db = Store(db_path or os.getenv('COGNIT_DB_PATH',str(ROOT/'cognit.sqlite3')))
    app.state.store = db

    @app.get('/health')
    def health():
        return envelope({'status':'ok','database':'sqlite','runner':'browser_pyodide','production_secure':False})

    @app.post('/api/session/start')
    def start(request: StartIn):
        sid = uid()
        problem = BANK['multiples']
        seed = uuid.uuid4().int % (2**31)
        q = public_question(problem, seed)
        db.execute('INSERT INTO sessions(id,alias,created_at,question_id,difficulty,history_json) VALUES(?,?,?,?,?,?)',
                   (sid,request.student_alias.strip(),now(),q['id'],1,json.dumps([])))
        return envelope({'session_id':sid,'question':q,
                         'state':{'stage':'assessment','difficulty':1,'allowed_help':['lookup'], 'question_number':1,'total_questions':4}})

    @app.get('/api/session/{session_id}')
    def session_state(session_id: str):
        s = must_session(db,session_id)
        a = attempts_for(db,session_id)
        p, seed = parse_id(s['question_id'])
        return envelope({'session_id':session_id,'question':public_question(p,seed),
                         'state':{'stage':s['stage'],'difficulty':s['difficulty'],
                                  'allowed_help':['lookup','hint','plan'] if any(x['question_id']==s['question_id'] for x in a) else ['lookup'],
                                  'question_number':len(json.loads(s['history_json']))+1,'total_questions':4},
                         'current_attempt_id':next((x['id'] for x in reversed(a) if x['question_id']==s['question_id']),None)})

    @app.post('/api/attempt')
    async def attempt(req: AttemptIn):
        s = must_session(db,req.session_id)
        if s['stage']=='complete' or s['question_id']!=req.question_id:
            raise HTTPException(409,detail={'code':'question_mismatch','message':'Question is no longer active'})
        old_count = db.one('SELECT COUNT(*) AS total FROM attempts WHERE session_id=? AND question_id=?',(req.session_id,req.question_id))['total']
        if old_count >= 3:
            raise HTTPException(409,detail={'code':'attempt_limit','message':'Three submissions maximum for this question. Continue to the next question.'})
        problem, seed = parse_id(req.question_id)
        question = public_question(problem, seed)
        results = [r.model_dump(by_alias=True) for r in req.client_test_results]
        test = score_tests(question['example_tests'],results)
        grader = await grade_concept(problem,req.explanation,test['categories'])
        helps = db.all('SELECT * FROM assistance WHERE session_id=? AND question_id=?',(req.session_id,req.question_id))
        assisted = any(h['decision'] in ('allow','limit') and h['mode'] in ('hint','plan') for h in helps)
        flags = ['untrusted_browser_execution']
        if grader['needs_review']:
            flags.append('concept_needs_teacher_review')
        if not req.explanation.strip():
            flags.append('missing_explanation')
        score = round(test['points']+grader['points'],2)
        feedback = f"{test['categories']['basic']['passed']}/3 basic and {test['categories']['edge']['passed']}/3 edge tests passed. {grader['feedback']}"
        aid = uid()
        db.execute('''INSERT INTO attempts(id,session_id,question_id,created_at,code,explanation,plan,test_json,concept_json,score,concept_score,assistance_used,flags_json,feedback)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                   (aid,req.session_id,req.question_id,now(),req.code,req.explanation,req.plan,json.dumps(test),json.dumps(grader),score,grader['points'],int(assisted),json.dumps(flags),feedback))
        all_a = attempts_for(db,req.session_id)
        return envelope({'attempt_id':aid,'provisional_score':score,'code_score':test['points'],
                         'concept_score':grader['points'],'concept_method':grader['method'],
                         'breakdown':{'functional':test['categories']['basic']['points'],'edge_cases':test['categories']['edge']['points'],'conceptual':grader['points']},
                         'flags':flags,'feedback':feedback,'mastery_snapshot':mastery_snapshot(all_a),
                         'next_action':'continue','evidence_trust':'untrusted_browser_runner'})

    @app.post('/api/assist')
    def assist(req: AssistIn):
        s = must_session(db,req.session_id)
        if req.question_id != s['question_id'] or s['stage']=='complete':
            raise HTTPException(409,detail={'code':'question_mismatch','message':'Question is no longer active'})
        problem, _ = parse_id(req.question_id)
        tried = db.one('SELECT id FROM attempts WHERE session_id=? AND question_id=?',(req.session_id,req.question_id)) is not None
        hints = db.all('SELECT id FROM assistance WHERE session_id=? AND question_id=? AND mode=? AND decision=?',
                       (req.session_id,req.question_id,'hint','limit'))
        response = bounded_help(problem,req.mode,req.query,tried,len(hints))
        db.execute('INSERT INTO assistance(id,session_id,question_id,created_at,mode,query,decision,response) VALUES(?,?,?,?,?,?,?,?)',
                   (uid(),req.session_id,req.question_id,now(),req.mode,req.query,response['decision'],response['content']))
        return envelope(response)

    @app.post('/api/next')
    def next_question(req: NextIn):
        s = must_session(db,req.session_id)
        if s['stage']=='complete':
            return envelope({'complete':True,'state':{'stage':'complete'}})
        attempt_row = db.one('SELECT * FROM attempts WHERE id=? AND session_id=?',(req.previous_attempt_id,req.session_id))
        if not attempt_row or attempt_row['question_id']!=s['question_id']:
            raise HTTPException(409,detail={'code':'attempt_mismatch','message':'Submit the current question first'})
        a = attempts_for(db, req.session_id)
        if len({x['question_id'] for x in a}) >= 4:
            db.execute('UPDATE sessions SET stage=? WHERE id=?',('complete',req.session_id))
            return envelope({'complete':True,'state':{'stage':'complete'},'overall_percent':weighted_percent(a)})
        current, _ = parse_id(s['question_id'])
        seen = {parse_id(x['question_id'])[0].key for x in a}
        qualifies = a[-1]['test']['points'] >= 56
        assistance = a[-1]['assistance_used']
        streak = s['streak']
        if assistance and qualifies:
            difficulty = current.difficulty
            problem = select_problem(difficulty,skill=current.skill,avoid=seen,prefer=current.transfer)
            reason = 'transfer'
            streak = 0
        elif qualifies:
            streak += 1
            difficulty = min(3, s['difficulty']+1) if streak >= 2 else s['difficulty']
            if streak >= 2:
                streak = 0
            cycle = ('strings','hashing','loops')
            preferred_skill = cycle[(len({x['question_id'] for x in a})-1) % len(cycle)]
            problem = select_problem(difficulty, skill=preferred_skill, avoid=seen)
            reason = 'harder' if difficulty>s['difficulty'] else 'same'
        else:
            difficulty = s['difficulty']
            problem = select_problem(difficulty,skill=current.skill,avoid=seen,prefer=current.transfer)
            reason = 'remedial'
            streak = 0
        seed = uuid.uuid4().int % (2**31)
        question = public_question(problem,seed)
        db.execute('UPDATE sessions SET question_id=?,difficulty=?,streak=?,history_json=? WHERE id=?',
                   (question['id'],difficulty,streak,json.dumps([*json.loads(s['history_json']),s['question_id']]),req.session_id))
        return envelope({'question':question,'reason':reason,
                         'state':{'stage':'assessment','difficulty':difficulty,'allowed_help':['lookup'],
                                  'question_number':len(json.loads(s['history_json']))+2,'total_questions':4}})

    @app.get('/api/teacher/session/{session_id}')
    def teacher_session(session_id: str):
        s = must_session(db,session_id)
        attempts = attempts_for(db,session_id)
        assistance = db.all('SELECT * FROM assistance WHERE session_id=? ORDER BY created_at,rowid',(session_id,))
        # The dashboard is open by design for this synthetic-data hackathon demo.
        return envelope({'session':{'id':s['id'],'alias':s['alias'],'stage':s['stage'],'created_at':s['created_at']},
                         'attempts':attempts,'score_breakdown':{'weighted_percent':weighted_percent(attempts),'weights':{'basic':50,'edge':20,'concept':30}},
                         'mastery_by_skill':mastery_snapshot(attempts),
                         'assisted_vs_independent':{'assisted':sum(a['assistance_used'] for a in attempts),'independent':sum(not a['assistance_used'] for a in attempts)},
                         'help_log':assistance,'review_flags':[{'attempt_id':a['id'],'flags':a['flags']} for a in attempts if a['flags']]})

    @app.post('/api/teacher/review')
    def teacher_review(req: ReviewIn):
        a = db.one('SELECT * FROM attempts WHERE id=?',(req.attempt_id,))
        if not a:
            raise HTTPException(404,detail={'code':'unknown_attempt','message':'Attempt not found'})
        prior = db.one('SELECT * FROM reviews WHERE attempt_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1',(req.attempt_id,))
        previous = prior['new_score'] if prior else a['score']
        concept = a['concept_score'] if req.override_concept_score is None else req.override_concept_score
        test = json.loads(a['test_json'])
        effective = round(test['points']+concept,2)
        db.execute('INSERT INTO reviews(id,attempt_id,created_at,previous_score,new_score,note,approved) VALUES(?,?,?,?,?,?,?)',
                   (uid(),req.attempt_id,now(),previous,effective,req.reviewer_note,int(req.approved)))
        return envelope({'review_status':'approved' if req.approved else 'needs_revision',
                         'effective_score':effective,'previous_score':previous,'audit_recorded':True})

    @app.get('/api/info')
    def info():
        return envelope({'name':'Cognit','version':'0.1.0','execution':'Pyodide browser Web Worker',
                         'execution_trusted':False,'concept_grading':'Anthropic when API key configured, otherwise labelled heuristic preview',
                         'question_bank_count':len(BANK),'skills':['loops','strings','hashing']})

    @app.get('/')
    def index():
        return FileResponse(ROOT/'frontend'/'index.html')
    app.mount('/static',StaticFiles(directory=ROOT/'frontend'),name='static')
    return app

app = create_app()
