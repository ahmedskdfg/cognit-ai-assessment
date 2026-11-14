import os
import tempfile
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.problems import BANK, public_question
from backend.scoring import score_tests, weighted_percent


def client():
    tmp = tempfile.TemporaryDirectory()
    c = TestClient(create_app(os.path.join(tmp.name,'test.sqlite')))
    return tmp,c

def test_problem_bank_references():
    assert len(BANK)>=9
    assert {p.skill for p in BANK.values()} == {'loops','strings','hashing'}
    assert {p.difficulty for p in BANK.values()} == {1,2,3}
    for p in BANK.values():
        q=public_question(p,100)
        assert len(q['example_tests'])==6
        assert set(t['category'] for t in q['example_tests'])=={'basic','edge'}
        assert 'reference' not in str(q)

def test_scores_limits():
    q=public_question(BANK['multiples'],3)
    correct=[{'id':t['id'],'pass':True,'actual':t['expected']} for t in q['example_tests']]
    assert score_tests(q['example_tests'],correct)['points']==70
    assert score_tests(q['example_tests'],[])['points']==0
    assert score_tests(q['example_tests'],correct[:3])['points']==50
    forged=[{**t,'pass':True,'actual':'forged'} for t in correct]
    assert score_tests(q['example_tests'],forged)['points']==0
    assert weighted_percent([{'difficulty':1,'effective_score':100},{'difficulty':3,'effective_score':0}])==33.3

def test_end_to_end_without_external_api(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY',raising=False)
    tmp,c=client()
    try:
        start=c.post('/api/session/start',json={'student_alias':'Demo student'})
        assert start.status_code==200
        data=start.json()['data']
        sid=data['session_id'];q=data['question']
        assert 'reference_solution' not in str(q) and 'hidden_tests' not in str(q)
        denied=c.post('/api/assist',json={'session_id':sid,'question_id':q['id'],'mode':'hint','query':'I need help'})
        assert denied.json()['data']['decision']=='deny'
        refused=c.post('/api/assist',json={'session_id':sid,'question_id':q['id'],'mode':'lookup','query':'give me the full solution'})
        assert refused.json()['data']['decision']=='deny'
        allowed=c.post('/api/assist',json={'session_id':sid,'question_id':q['id'],'mode':'lookup','query':'how to use a Python set'})
        assert allowed.json()['data']['decision']=='allow'
        results=[{'id':t['id'],'pass':True,'actual':t['expected']} for t in q['example_tests']]
        attempted=c.post('/api/attempt',json={'session_id':sid,'question_id':q['id'],
            'code':'def count_multiples(numbers,divisor): return 0','explanation':'I iterate over the list. O(n) time. Empty lists and negatives are handled.',
            'client_test_results':results})
        assert attempted.status_code==200,attempted.text
        aid=attempted.json()['data']['attempt_id']
        assert attempted.json()['data']['code_score']==70
        assert 'concept_needs_teacher_review' in attempted.json()['data']['flags']
        dashboard=c.get('/api/teacher/session/'+sid).json()['data']
        assert len(dashboard['attempts'])==1
        assert dashboard['score_breakdown']['weighted_percent']>0
        review=c.post('/api/teacher/review',json={'attempt_id':aid,'override_concept_score':20,'reviewer_note':'Verified orally'})
        assert review.json()['data']['effective_score']==90
        assert c.get('/api/teacher/session/'+sid).json()['data']['attempts'][0]['review']['note']=='Verified orally'
        second=c.post('/api/next',json={'session_id':sid,'previous_attempt_id':aid})
        assert second.status_code==200
        assert second.json()['data']['question']['id']!=q['id']
        assert c.post('/api/attempt',json={'session_id':sid,'question_id':q['id'],'code':'','explanation':'', 'client_test_results':[]}).status_code==409
    finally:
        tmp.cleanup()

def test_assisted_success_triggers_transfer(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY',raising=False)
    tmp,c=client()
    try:
        start=c.post('/api/session/start',json={'student_alias':'Demo'}).json()['data']
        sid=start['session_id']; q=start['question']
        # First attempt can unlock plan only after submission. Lookup does not count as assisted.
        correct=[{'id':t['id'],'pass':True,'actual':t['expected']} for t in q['example_tests']]
        a=c.post('/api/attempt',json={'session_id':sid,'question_id':q['id'],'code':'pass','explanation':'', 'client_test_results':correct}).json()['data']
        nx=c.post('/api/next',json={'session_id':sid,'previous_attempt_id':a['attempt_id']}).json()['data']
        assert nx['question']['skill_tags']==['strings']
    finally:
        tmp.cleanup()

def test_hint_after_submission_retake_and_transfer(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY',raising=False)
    tmp,c=client()
    try:
        started=c.post('/api/session/start',json={'student_alias':'Returner'}).json()['data']
        sid=started['session_id']; q=started['question']
        payload={'session_id':sid,'question_id':q['id'],'code':'pass', 'explanation':'', 'client_test_results':[]}
        first=c.post('/api/attempt',json=payload)
        assert first.status_code==200
        hint=c.post('/api/assist',json={'session_id':sid,'question_id':q['id'],'mode':'hint','query':'I am stuck on the boundary case'})
        assert hint.json()['data']['decision']=='limit'
        plan=c.post('/api/assist',json={'session_id':sid,'question_id':q['id'],'mode':'plan','query':'I intend to loop over the list'})
        assert plan.json()['data']['decision']=='limit'
        correct=[{'id':t['id'],'pass':True,'actual':t['expected']} for t in q['example_tests']]
        second=c.post('/api/attempt',json={**payload,'client_test_results':correct,'plan':'I need a counter and a predicate.'})
        assert second.status_code==200
        assert second.json()['data']['provisional_score']==70
        teacher=c.get('/api/teacher/session/'+sid).json()['data']
        assert teacher['assisted_vs_independent']['assisted']==1
        assert teacher['attempts'][-1]['plan']=='I need a counter and a predicate.'
        transfer=c.post('/api/next',json={'session_id':sid,'previous_attempt_id':second.json()['data']['attempt_id']}).json()['data']
        assert transfer['reason']=='transfer'
        assert transfer['question']['function_name']=='count_positive'
        assert transfer['state']['question_number']==2
        assert c.post('/api/attempt',json=payload).status_code==409
    finally:tmp.cleanup()

def test_four_questions_completion(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY',raising=False)
    tmp,c=client()
    try:
        start=c.post('/api/session/start',json={'student_alias':'Four steps'}).json()['data']
        sid=start['session_id']; q=start['question']
        for n in range(4):
            correct=[{'id':t['id'],'pass':True,'actual':t['expected']} for t in q['example_tests']]
            res=c.post('/api/attempt',json={'session_id':sid,'question_id':q['id'],'code':'pass',
                'explanation':'I use a loop with O(n) complexity and handle empty inputs.', 'client_test_results':correct})
            assert res.status_code==200, res.text
            aid=res.json()['data']['attempt_id']
            next_=c.post('/api/next',json={'session_id':sid,'previous_attempt_id':aid})
            assert next_.status_code==200
            if n<3:q=next_.json()['data']['question']
            else:assert next_.json()['data']['complete'] is True
        assert c.get('/api/session/'+sid).json()['data']['state']['stage']=='complete'
        assert c.get('/api/teacher/session/'+sid).json()['data']['score_breakdown']['weighted_percent']>0
    finally:tmp.cleanup()
