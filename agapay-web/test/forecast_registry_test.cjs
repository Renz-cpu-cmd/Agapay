const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript'),React=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
const source=file=>fs.readFileSync('src/'+file,'utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
class AccountError extends Error{constructor(message,status){super(message);this.status=status;}}
function evaluate(code,dependencies){const exports={};vm.runInNewContext(ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,{exports,require:name=>dependencies[name]??require(name),URL,URLSearchParams,Request,Response,Date,structuredClone,process:{env:{NODE_ENV:'test'}}});return exports;}
const score={count:30,mae_cm:1,rmse_cm:2,bias_cm:-1,maximum_absolute_error_cm:3};
const candidate={id:'a'.repeat(64),version:4,state:'draft',card:{station_id:'TEST_STATION',datum:'Synthetic datum',configuration_hash:'b'.repeat(64),source_class:'synthetic_fixture',data_license:'Synthetic only',provenance:'Not real field data',calibration_history:'Synthetic calibration',training_cutoff:'2026-01-01T00:00:00Z',features:'depth_cm,rate_cm_per_minute',limitations:'Not field validated',allowed_use:'advisory_only',fallback:'unavailable'},evaluation:{model:{30:score},persistence:{30:score},rate:{30:score}}};
function harness(request,role='admin'){
  const slots=[],effects=[];let index=0,first=true,tree;
  const hooks={...React,useState(value){const k=index++;if(!(k in slots))slots[k]=value;return[slots[k],v=>slots[k]=typeof v==='function'?v(slots[k]):v];},useRef(value){const k=index++;if(!(k in slots))slots[k]={current:value};return slots[k];},useEffect(fn){if(first)effects.push(fn);}};
  const module=evaluate(source('components/ForecastRegistry.tsx'),{react:hooks,'./DecisionEvaluation':evaluate(source('components/DecisionEvaluation.tsx'),{}),'@/lib/accounts':{accountRequest:request,AccountError},'@/context/AccountContext':{useAccount:()=>({user:{role}})},'@/context/MonitoringContext':{useMonitoring:()=>({selectedStationId:'TEST_STATION'})}});
  const render=()=>{index=0;tree=module.default();first=false;};render();effects.forEach(effect=>effect());
  function all(node=tree){return !node||typeof node!=='object'?[]:[node,...React.Children.toArray(node.props?.children).flatMap(all)];}
  return {render,find:fn=>all().find(fn),html:()=>renderToStaticMarkup(tree)};
}
const catalog={operational:[candidate],experimental:{status:'unavailable',reason:'No configured experimental evaluation'}};

test('reviewing a deployed binding starts with the recorded model, not an implicit disable',async()=>{
  const calls=[];const h=harness(async(path,method,body)=>{calls.push({path,method,body});return path==='forecast-registry'?catalog:{station_id:'TEST_STATION',version:3,model_id:candidate.id};});
  await flush();h.render();assert.equal(h.find(n=>n.type==='select').props.value,candidate.id);
});
test('registry shows real-evidence requirements and officers receive no approval or deployment forms',async()=>{
  const h=harness(async path=>path==='forecast-registry'?catalog:{station_id:'TEST_STATION',version:3,model_id:null},'officer');await flush();h.render();
  assert.match(h.html(),/Synthetic datum/);assert.match(h.html(),/No operational model is approved by installing this code/);assert.equal(h.find(n=>n.type==='form'),undefined);assert.doesNotMatch(h.html(),/Record independent decision/);
});

test('evaluation discloses configured first-hour persistence advantage and changes with the artifact scores',async()=>{
  const rain=(mae)=>({overall:{count:12,mae_mm:mae,rmse_mm:mae},by_horizon:{'1h':{overall:{count:4,mae_mm:mae,rmse_mm:mae}}}});
  const data={...catalog,experimental:{status:'available',evaluation:{test:{random_forest:rain(.5),persistence:rain(.25)}}}};
  const h=harness(async path=>path==='forecast-registry'?data:null,'officer');await flush();h.render();
  assert.match(h.html(),/First-hour persistence has lower MAE \(0.25 mm\)/);assert.match(h.html(),/not establish flood-warning quality/);
  data.experimental.evaluation.test.persistence=rain(.75);h.find(n=>n.type==='button'&&n.props.children==='Refresh registry and review manually').props.onClick();await flush();h.render();
  assert.doesNotMatch(h.html(),/First-hour persistence has lower MAE/);assert.match(h.html(),/does not show a first-hour persistence advantage/);
});
test('independent review submits its captured version and blocks 409 replay until manual refresh',async()=>{
  const calls=[];const h=harness(async(path,method,body)=>{calls.push({path,method,body});if(method==='POST')throw new AccountError('Refresh required',409);return path==='forecast-registry'?catalog:{station_id:'TEST_STATION',version:3,model_id:null};});
  await flush();h.render();h.find(n=>n.type==='button'&&React.Children.toArray(n.props.children).join('')==='Review candidate aaaaaaaa').props.onClick();h.render();
  h.find(n=>n.type==='textarea').props.onChange({target:{value:'Reviewed independent field evaluation'}});h.find(n=>n.type==='input').props.onChange({target:{value:'c'.repeat(64)}});h.render();
  h.find(n=>n.type==='form').props.onSubmit({preventDefault(){}});await flush();h.render();
  assert.equal(calls.filter(c=>c.method==='POST').length,1);assert.equal(calls.find(c=>c.method==='POST').body.expected_version,4);
  assert.match(h.html(),/no mutation was retried/);h.find(n=>n.type==='form').props.onSubmit({preventDefault(){}});await flush();assert.equal(calls.filter(c=>c.method==='POST').length,1);
  h.find(n=>n.type==='button'&&n.props.children==='Refresh registry and review manually').props.onClick();await flush();h.render();assert.doesNotMatch(h.html(),/captured version/);
});
test('forecast BFF preserves namespaces, staff restriction, exact origin and backend conflicts',async()=>{
  const calls=[];const module=evaluate(source('app/api/account/[...path]/route.ts'),{'next/headers':{cookies:async()=>({get:()=>({value:'server-cookie'}),delete(){}})},'next/server':{NextResponse:class extends Response{static json(data,init){return new Response(JSON.stringify(data),init);}}},'@/lib/account-server':{sessionCookie:'agapay_session',backendRequest:async(...args)=>{calls.push(args);return new Response('{"detail":"Refresh required"}',{status:409});}}});
  const call=(path,method='GET',origin='http://127.0.0.1')=>{const request=new Request('http://127.0.0.1/api/account/'+path,{method,headers:{host:'127.0.0.1',origin},...(method==='POST'?{body:'{"expected_version":3}'}:{})});request.nextUrl=new URL(request.url);return module[method](request,{params:Promise.resolve({path:path.split('/')})});};
  assert.equal((await call('forecast-registry')).status,409);assert.equal(calls[0][0],'forecast-registry');assert.equal(calls[0][5],true);
  assert.equal((await call('forecast-deployments/TEST_STATION','POST','https://attacker.test')).status,403);assert.equal(calls.length,1);
  assert.equal((await call('forecast-deployments/TEST_STATION','POST')).status,409);assert.equal(calls[1][0],'forecast-deployments/TEST_STATION');assert.equal(calls.length,2);
  assert.equal((await call('forecast-registry/arbitrary-file-path','POST')).status,404);
});
