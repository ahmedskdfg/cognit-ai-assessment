/* Cognit single-server web client. No build step, no API keys in browser. */
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const html = (s) => String(s).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let sessionId = localStorage.getItem('cognit-session') || '';
let question = null, currentAttempt = null, stage='assessment', questionNumber=1;
let lastRun = null, editor = null, codeText = '', planText='', helpMode='lookup', worker=null, runnerReady=false;
let nextRunId=0, runnerPromise=null;
const defaultCode = (q) => `${q.function_signature}\n    # Write your solution here\n    pass\n`;

async function api(path, data) {
  const response = await fetch(path, {method:data?'POST':'GET',headers:{'Content-Type':'application/json'},body:data?JSON.stringify(data):undefined});
  let result;
  try {result=await response.json();} catch {throw Error(`Unexpected server response (${response.status})`)}
  if (!response.ok || !result.ok) {
    const detail=result.detail || result.error || {};
    throw Error(detail.message || detail.code || `HTTP ${response.status}`);
  }
  return result.data;
}
function reportError(error) { $('#runnerStatus').textContent=error.message || String(error); }
function setCode(value) {codeText=value;if(editor)editor.setValue(value);else $('#fallbackEditor').value=value;}
function getCode() {return editor?editor.getValue():$('#fallbackEditor').value;}
function showStudent() {
  $('#studentView').classList.remove('hidden');$('#teacherView').classList.add('hidden');
  $('#studentTab').classList.add('active');$('#teacherTab').classList.remove('active');
}
async function showTeacher() {
  $('#studentView').classList.add('hidden');$('#teacherView').classList.remove('hidden');
  $('#teacherTab').classList.add('active');$('#studentTab').classList.remove('active');
  if(sessionId)await refreshTeacher();
}
function renderQuestion(q, state, attemptId=null) {
  question=q;currentAttempt=attemptId;stage=state.stage;questionNumber=state.question_number;
  lastRun=null;planText='';$('#planDraft').value='';$('#planDraftBox').classList.add('hidden');
  $('#welcome').classList.add('hidden');$('#workspace').classList.remove('hidden');
  $('#questionTitle').textContent=q.title;
  $('#questionMeta').textContent=`Difficulty ${q.difficulty} · ${q.skill_tags.join(', ')} · ${q.example_tests.length} verified sample and edge cases`;
  $('#progressLabel').textContent=`Question ${questionNumber} of ${state.total_questions}`;
  $('#progressFill').style.width=`${Math.min(100,questionNumber/state.total_questions*100)}%`;
  $('#skillTag').textContent=q.skill_tags[0];
  $('#statement').textContent=q.statement;$('#signature').textContent=q.function_signature;
  $('#examples').innerHTML=q.example_tests.slice(0,2).map(t=>`<div><code>${html(JSON.stringify(t.args))}</code><span>→</span><code>${html(JSON.stringify(t.expected))}</code></div>`).join('');
  setCode(defaultCode(q));$('#explanation').value='';$('#testStats').textContent='Not run yet';
  $('#testOutput').textContent='Run your code to see test results and exceptions.';
  $('#scoreCard').classList.add('hidden');$('#nextBtn').classList.toggle('hidden',!attemptId);
  $('#submitBtn').disabled=false;$('#helpResponse').textContent='Reference lookup is always available. Hints and Plan Mode unlock after a submission.';
  $('#docLinks').innerHTML='';$('#helpRules').textContent=attemptId?'You can now use hints or Plan Mode before revising your code.':'Plan Mode and hints unlock after your first submitted attempt.';
  showStudent();
  if(stage==='complete')showComplete();
}
function showComplete() {
  $('#questionTitle').textContent='Assessment complete';
  $('#questionMeta').textContent='Open Teacher view for scores and review history.';
  $('#nextBtn').classList.add('hidden');$('#submitBtn').disabled=true;$('#runBtn').disabled=true;
  $('#scoreCard').classList.remove('hidden');$('#scoreCard').innerHTML='<b>Completed four questions.</b> Review the dashboard to inspect real submissions, assistance history and conceptual scores.';
}
async function initialize() {
  if (!sessionId) return;
  try {
    const data=await api(`/api/session/${encodeURIComponent(sessionId)}`);
    renderQuestion(data.question,data.state,data.current_attempt_id);
  } catch {localStorage.removeItem('cognit-session');sessionId='';}
}
$('#startForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const button=$('#startForm button');button.disabled=true;
  try {
    const data=await api('/api/session/start',{student_alias:$('#alias').value.trim()});
    sessionId=data.session_id;localStorage.setItem('cognit-session',sessionId);
    renderQuestion(data.question,data.state);initWorker();
  } catch(e) {alert(e.message);} finally {button.disabled=false;}
});
$('#studentTab').onclick=showStudent;
$('#teacherTab').onclick=showTeacher;
$('#refreshTeacher').onclick=refreshTeacher;
$('#fallbackEditor').oninput=e=>{codeText=e.target.value;lastRun=null;};

function initWorker() {
  if(worker)return;
  runnerReady=false;$('#runnerStatus').textContent='Loading Python in a Web Worker…';
  worker = new Worker('/static/runner.worker.js');
  worker.onmessage=(e)=>{
    const msg=e.data;
    if(msg.type==='ready'){runnerReady=true;$('#runnerStatus').textContent='Python ready · browser worker';}
    else if(msg.type==='fatal'){$('#runnerStatus').textContent=`Pyodide failed to load: ${msg.message}`;if(runnerPromise){runnerPromise.reject(Error(msg.message));runnerPromise=null;}}
    else if((msg.type==='results'||msg.type==='error')&&runnerPromise&&msg.runId===runnerPromise.runId){
      clearTimeout(runnerPromise.timeout);
      if(msg.type==='error')runnerPromise.reject(Error(msg.message));else runnerPromise.resolve(msg.results);
      runnerPromise=null;
    }
  };
  worker.onerror=(e)=>{$('#runnerStatus').textContent='Python worker error: '+e.message;if(runnerPromise){runnerPromise.reject(Error(e.message));runnerPromise=null;}};
}
function terminateWorker() {
  if(worker)worker.terminate();worker=null;runnerReady=false;initWorker();
}
async function runTests() {
  if(!question)throw Error('Start a session first');
  initWorker();
  if(!runnerReady){
    await new Promise((resolve,reject)=>{
      const start=Date.now();
      const timer=setInterval(()=>{
        if(runnerReady){clearInterval(timer);resolve();}
        else if(Date.now()-start>25000){clearInterval(timer);reject(Error('Python runtime load timed out. Check internet access to the Pyodide CDN.'));}
      },200);
    });
  }
  const runId=++nextRunId;
  const payload={code:getCode(),tests:question.example_tests,function_name:question.function_name};
  return new Promise((resolve,reject)=>{
    const timeout=setTimeout(()=>{runnerPromise=null;terminateWorker();reject(Error('Execution timed out after 8 seconds. Worker terminated.'));},8000);
    runnerPromise={resolve,reject,runId,timeout};worker.postMessage({type:'run',runId,payload});
  });
}
function renderResults(results){
  lastRun={code:getCode(),results};
  const passes=results.filter(r=>r.pass).length;
  $('#testStats').textContent=`${passes}/${results.length} passed`;
  $('#testOutput').innerHTML=results.map((r,i)=>`<div class="test-row"><span class="${r.pass?'passed':'failed'}">${r.pass?'✓':'✕'} ${html(r.id)}</span><span>${r.error?html(r.error):r.pass?'Passed':'Expected '+html(JSON.stringify(question.example_tests[i].expected))+', got '+html(JSON.stringify(r.actual))}</span></div>${r.stdout?`<div class="stdout">stdout: ${html(r.stdout)}</div>`:''}`).join('');
  $('#runnerStatus').textContent=`${passes}/${results.length} tests passed · untrusted browser evidence`;
}
$('#runBtn').onclick=async ()=>{
  const btn=$('#runBtn');btn.disabled=true;$('#runnerStatus').textContent='Executing Python…';
  try {const results=await runTests();renderResults(results);} catch(e){lastRun=null;$('#testOutput').textContent=e.message;reportError(e);}
  finally {btn.disabled=false;}
};
$('#submitBtn').onclick=async ()=>{
  const btn=$('#submitBtn');btn.disabled=true;
  try {
    if(!lastRun || lastRun.code!==getCode()) {
      $('#runnerStatus').textContent='Running updated code before submission…';
      renderResults(await runTests());
    }
    const data=await api('/api/attempt',{
      session_id:sessionId,question_id:question.id,code:getCode(),explanation:$('#explanation').value,plan:planText,
      client_test_results:lastRun.results.map(({id,pass:passed,actual,error})=>({id,pass:passed,actual,error})),help_events:[]
    });
    currentAttempt=data.attempt_id;
    $('#scoreCard').classList.remove('hidden');
    $('#scoreCard').innerHTML=`<div class="score-heading"><strong>${data.provisional_score}/100</strong><span>Provisional score · ${html(data.concept_method)}</span></div>
      <div class="score-line"><span>Functional correctness</span><b>${data.breakdown.functional}/50</b></div>
      <div class="score-line"><span>Edge cases</span><b>${data.breakdown.edge_cases}/20</b></div>
      <div class="score-line"><span>Conceptual explanation</span><b>${data.breakdown.conceptual}/30</b></div>
      <p>${html(data.feedback)}</p><p class="small">${html(data.flags.join(' · '))}</p>`;
    $('#nextBtn').classList.remove('hidden');
    $('#helpRules').textContent='Hints and Plan Mode are unlocked. You may revise and resubmit (maximum three submissions per question), or continue.';
  }catch(e){alert(e.message);}finally{btn.disabled=false;}
};
$('#nextBtn').onclick=async ()=>{
  if(!currentAttempt)return;
  const btn=$('#nextBtn');btn.disabled=true;
  try {
    const data=await api('/api/next',{session_id:sessionId,previous_attempt_id:currentAttempt});
    if(data.complete){showComplete();await showTeacher();}
    else renderQuestion(data.question,data.state);
  }catch(e){alert(e.message);}finally{btn.disabled=false;}
};
$$('[data-mode]').forEach(el=>el.onclick=()=>{
  helpMode=el.dataset.mode;
  $$('[data-mode]').forEach(b=>b.classList.toggle('selected',b===el));
  $('#helpQuery').placeholder=helpMode==='lookup'?'How does Python set membership work?':helpMode==='plan'?'My plan is to check each element…':'I am stuck on the empty input case.';
});
$('#usePlanBtn').onclick=()=>{planText=$('#planDraft').value.trim();$('#planSaved').textContent=planText?'Plan saved for your next code submission.':'Plan cleared.';};
$('#askBtn').onclick=async ()=>{
  if(!question)return;
  const btn=$('#askBtn');btn.disabled=true;
  try {
    const data=await api('/api/assist',{session_id:sessionId,question_id:question.id,mode:helpMode,query:$('#helpQuery').value,current_attempt_id:currentAttempt});
    $('#helpResponse').textContent=`${data.decision.toUpperCase()} · ${data.content}`;
    if(helpMode==='plan' && data.decision!=='deny')$('#planDraftBox').classList.remove('hidden');
    $('#docLinks').innerHTML=(data.citations || []).map(x=>`<p><a href="${html(x.url)}" target="_blank" rel="noopener noreferrer">${html(x.title)} ↗</a><small>${html(x.snippet)}</small></p>`).join('');
  }catch(e){$('#helpResponse').textContent=e.message;}finally{btn.disabled=false;}
};
async function refreshTeacher() {
  if(!sessionId)return;
  try {
    const data=await api(`/api/teacher/session/${encodeURIComponent(sessionId)}`);
    $('#teacherEmpty').classList.add('hidden');$('#teacherContent').classList.remove('hidden');
    $('#weightedScore').textContent=data.score_breakdown.weighted_percent+'%';
    $('#attemptCount').textContent=String(data.attempts.length);
    $('#assistedCount').textContent=String(data.assisted_vs_independent.assisted);
    $('#independentCount').textContent=String(data.assisted_vs_independent.independent);
    $('#attemptList').innerHTML=data.attempts.length?data.attempts.map((a,i)=>`<article class="attempt"><div class="attempt-header"><span><b>Attempt ${i+1}</b> · ${html(a.skill)} · level ${a.difficulty}</span><strong>${a.effective_score.toFixed(1)}/100</strong></div>
      <div class="muted">Code tests: ${a.test.points}/70 · concept: ${a.concept_score}/30 · ${a.assistance_used?'assisted':'independent'}</div>
      <p class="small">${html(a.concept.method)} · ${html(a.flags.join(', '))}</p><details><summary>Inspect explanation and feedback</summary><p>${html(a.explanation || '(none)')}</p><p>${html(a.feedback)}</p></details>
      <div class="review-controls"><label>Teacher concept override (0–30) <input type="number" data-concept="${html(a.id)}" min="0" max="30" value="${a.review?Math.max(0,a.review.new_score-a.test.points):a.concept_score}" step="1"></label><input type="text" data-note="${html(a.id)}" placeholder="Audit note"><button class="secondary" data-review="${html(a.id)}">Save review</button></div></article>`).join(''):'<p>No attempts yet.</p>';
    Object.entries(data.mastery_by_skill).forEach(()=>{});
    $('#masteryList').innerHTML=Object.entries(data.mastery_by_skill).map(([skill,m])=>`<div class="mastery"><b>${html(skill)}</b><span>${m.independent_passes}/${m.independent_attempts} independent test passes</span><small>${html(m.mastery_indicator.replaceAll('_',' '))}</small></div>`).join('');
    $('#helpHistory').innerHTML=data.help_log.length?data.help_log.map(h=>`<div class="history"><b>${html(h.mode)}</b> · ${html(h.decision)}<small>${html(h.query)}</small></div>`).join(''):'<p class="muted">No assistance requests recorded.</p>';
    $$('[data-review]').forEach(b=>b.onclick=async()=>{
      const id=b.dataset.review;
      try {
        const concept=Number($$('[data-concept]').find(x=>x.dataset.concept===id).value);
        const note=$$('[data-note]').find(x=>x.dataset.note===id).value;
        if(!Number.isFinite(concept)||concept<0||concept>30)throw Error('Concept score must be between 0 and 30');
        await api('/api/teacher/review',{attempt_id:id,override_concept_score:concept,reviewer_note:note,approved:true});
        await refreshTeacher();
      }catch(e){alert(e.message);}
    });
  }catch(e){$('#teacherEmpty').textContent=e.message;}
}
function initMonaco() {
  const script=document.createElement('script');
  script.src='https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs/loader.js';
  script.onload=()=>{
    if(!window.require)return;
    window.require.config({paths:{vs:'https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs'}});
    window.require(['vs/editor/editor.main'],()=>{
      try {
        const text=$('#fallbackEditor').value;
        editor=window.monaco.editor.create($('#editor'),{value:text,language:'python',theme:'vs-dark',automaticLayout:true,minimap:{enabled:false},fontSize:14,
          lineNumbers:'on',scrollBeyondLastLine:false,tabSize:4,padding:{top:16},wordWrap:'on'});
        editor.onDidChangeModelContent(()=>{lastRun=null;});
      }catch(e){console.warn('Monaco unavailable, textarea fallback enabled',e);}
    });
  };
  script.onerror=()=>{console.warn('Monaco unavailable, textarea fallback enabled');};
  document.head.appendChild(script);
}
initMonaco();initialize().then(()=>{if(sessionId)initWorker();});
