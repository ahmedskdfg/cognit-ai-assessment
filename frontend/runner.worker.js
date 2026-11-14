/* Pyodide worker. Browser-isolated demo execution, NOT a production-secure sandbox. */
let pyodide = null;
async function boot() {
  try {
    importScripts('https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.js');
    pyodide = await loadPyodide({indexURL:'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/'});
    postMessage({type:'ready'});
  } catch (error) { postMessage({type:'fatal',message:String(error)}); }
}
const PY_RUN = String.raw`
import json, traceback, contextlib, io
payload = json.loads(payload_json)
source = payload['code']
results = []
for case in payload['tests']:
    capture = io.StringIO()
    try:
        namespace = {}
        with contextlib.redirect_stdout(capture):
            exec(compile(source, '<student>', 'exec'), namespace)
            fn = namespace.get(payload['function_name'])
            if not callable(fn):
                raise NameError('Required function not defined: ' + payload['function_name'])
            actual = fn(*case['args'])
        json.dumps(actual)
        passed = type(actual) == type(case['expected']) and actual == case['expected']
        results.append({'id':case['id'], 'pass':passed, 'actual':actual,
                        'error':None, 'stdout':capture.getvalue()[:1200]})
    except Exception as exc:
        results.append({'id':case['id'], 'pass':False, 'actual':None,
                        'error':type(exc).__name__ + ': ' + str(exc)[:250],
                        'stdout':capture.getvalue()[:1200]})
json.dumps(results, ensure_ascii=False)
`;
onmessage = async (event) => {
  if (event.data.type !== 'run') return;
  if (!pyodide) { postMessage({type:'error',message:'Python has not finished loading.'}); return; }
  try {
    pyodide.globals.set('payload_json', JSON.stringify(event.data.payload));
    const data = await pyodide.runPythonAsync(PY_RUN);
    postMessage({type:'results',results:JSON.parse(data),runId:event.data.runId});
  } catch (error) { postMessage({type:'error',message:String(error),runId:event.data.runId}); }
};
boot();
