const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript'),React=require('react');
const {webcrypto,createHash}=require('node:crypto');
const {renderToStaticMarkup}=require('react-dom/server');
const source=file=>fs.readFileSync('src/'+file,'utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
class AccountError extends Error{constructor(message,status){super(message);this.status=status;}}
function evaluate(code,dependencies){const exports={};vm.runInNewContext(ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,
  {exports,require:name=>dependencies[name]??require(name),URL,URLSearchParams,Response,Request,Date,TextEncoder,crypto:webcrypto,structuredClone,process:{env:{NODE_ENV:'test'}}});return exports;}
const row={id:17,alert_id:8,station_id:'TEST_001',severity:'WARNING',state:'UNKNOWN',version:4,queued_at:'2026-10-22T00:00:00Z',expires_at:'2026-10-22T00:05:00Z',expired:true,
  review_status:'unreviewed',review_required:true,provider_accepted:true,operator_attested_acceptance:false,conflicting_evidence:false,receipt_stages:[],attempts:[{attempt_no:1,outcome:'accepted',provider_reference:'projects/test/messages/synthetic'}],reviews:[]};
const page=()=>({items:[structuredClone(row)],next_before_id:null,checked_at:'2026-10-22T00:06:00Z',scope:'authorized jurisdiction'});
function harness(request,role='admin'){
  const slots=[],effects=[];let index=0,first=true,tree;
  const hooks={...React,useState(value){const k=index++;if(!(k in slots))slots[k]=value;return[slots[k],v=>slots[k]=typeof v==='function'?v(slots[k]):v];},
    useRef(value){const k=index++;if(!(k in slots))slots[k]={current:value};return slots[k];},useCallback:fn=>fn,useEffect(fn){if(first)effects.push(fn);}};
  const module=evaluate(source('components/DeliveryConsole.tsx'),{react:hooks,'@/hooks/useEvidenceClock':{useEvidenceClock:()=>Date.parse('2026-10-22T00:06:01Z')},'@/lib/operations-console':evaluate(source('lib/operations-console.ts'),{}),'@/lib/accounts':{accountRequest:request,AccountError},'@/context/AccountContext':{useAccount:()=>({user:{role}})},
    '@/lib/visible-poll':{visiblePoll:fn=>{fn(new AbortController().signal).catch(()=>{});return()=>{};}}});
  const render=()=>{index=0;tree=module.default();first=false;};render();effects.forEach(effect=>effect());
  function all(node=tree){return !node||typeof node!=='object'?[]:[node,...React.Children.toArray(node.props?.children).flatMap(all)];}
  return {render,find:fn=>all().find(fn),html:()=>renderToStaticMarkup(tree)};
}
test('provider acceptance leaves all missing callback stages explicitly unknown; officers cannot reconcile',async()=>{
  const h=harness(async()=>page(),'officer');await flush();h.render();const html=h.html();
  assert.match(html,/Provider accepted/);for(const stage of ['RECEIVED','OPENED','ACKNOWLEDGED'])assert.ok(html.includes(stage+': unknown / not instrumented'));
  assert.doesNotMatch(html,/Review evidence #17/);assert.match(html,/No stage confirms evacuation or responder dispatch/);
});
test('review hashes external reference and blocks stale writes until an explicit refresh',async()=>{
  const calls=[];const h=harness(async(path,method,body)=>{calls.push({path,method,body});if(method==='POST')throw new AccountError('Refresh required',409);return page();});
  await flush();h.render();h.find(n=>n.type==='button'&&React.Children.toArray(n.props.children).join('')==='Review evidence #17').props.onClick();h.render();
  h.find(n=>n.type==='textarea').props.onChange({target:{value:'Reviewed provider delivery record'}});h.find(n=>n.type==='input').props.onChange({target:{value:'external-record-123'}});h.render();
  h.find(n=>n.type==='form').props.onSubmit({preventDefault(){}});await new Promise(resolve=>setTimeout(resolve,25));h.render();
  const posts=calls.filter(c=>c.method==='POST');assert.equal(posts.length,1);assert.equal(posts[0].body.expected_version,4);
  assert.equal(posts[0].body.evidence_sha256,createHash('sha256').update('external-record-123').digest('hex'));assert.ok(!JSON.stringify(posts[0].body).includes('external-record-123'));
  assert.match(h.html(),/Refresh and review manually/);assert.equal(h.find(n=>n.type==='textarea').props.disabled,true);
  h.find(n=>n.type==='form').props.onSubmit({preventDefault(){}});await flush();assert.equal(calls.filter(c=>c.method==='POST').length,1);
  h.find(n=>n.type==='button'&&n.props.children==='Refresh and review deliveries').props.onClick();await flush();h.render();assert.equal(h.find(n=>n.type==='form'),undefined);
});
test('delivery BFF requires a staff session, preserves backend conflict, and forwards only supported filters',async()=>{
  const calls=[];let signedIn=true;
  const module=evaluate(source('app/api/account/[...path]/route.ts'),{'next/headers':{cookies:async()=>({get:()=>signedIn?{value:'server-cookie'}:undefined,delete(){}})},
    'next/server':{NextResponse:class extends Response{static json(data,init){return new Response(JSON.stringify(data),init);}}},
    '@/lib/account-server':{sessionCookie:'agapay_session',backendRequest:async(...args)=>{calls.push(args);return new Response(JSON.stringify({detail:{message:'Refresh required',current:{version:5}}}),{status:409});}}});
  const call=async(path,method='GET',origin='http://127.0.0.1')=>{const url='http://127.0.0.1/api/account/'+path;const request=new Request(url,{method,headers:{host:'127.0.0.1',origin},...(method==='POST'?{body:'{"expected_version":4}'}:{})});request.nextUrl=new URL(url);return module[method](request,{params:Promise.resolve({path:path.split('?')[0].split('/')})});};
  signedIn=false;assert.equal((await call('notification-deliveries')).status,401);assert.equal(calls.length,0);
  signedIn=true;assert.equal((await call('notification-deliveries?limit=30&before_id=18&state=UNKNOWN&user_id=2')).status,409);
  assert.equal(calls[0][0],'notification-deliveries?before_id=18&limit=30&state=UNKNOWN');assert.equal(calls[0][5],true);
  assert.equal((await call('notification-deliveries/17/reconcile','POST','https://attacker.test')).status,403);
  const result=await call('notification-deliveries/17/reconcile','POST');assert.equal(result.status,409);assert.equal((await result.json()).detail.current.version,5);
  assert.equal(calls.length,2);assert.equal((await call('notification-deliveries/17/resend','POST')).status,404);
});
