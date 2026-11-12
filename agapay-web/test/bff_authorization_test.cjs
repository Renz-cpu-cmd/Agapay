// P1 authorization contract for the web BFF (/api/account/*). The BFF does not decide
// roles itself: it forwards the HttpOnly session token and asks FastAPI for staff-only
// access with X-Agapay-Require-Staff. These tests pin that contract so the BFF can never
// turn a backend refusal into success, trust client-supplied identity, or serve data
// when authorization cannot be established.
const assert=require('node:assert/strict');
const {test}=require('node:test');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript');
const source=file=>fs.readFileSync(path.join(__dirname,'../src',file),'utf8');
const ROUTE='app/api/account/[...path]/route.ts';

function evaluate(code,dependencies,env={NODE_ENV:'test'},extra={}){
  const exports={};
  vm.runInNewContext(ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText,
    {exports,require:name=>dependencies[name]??require(name),process:{env},URL,URLSearchParams,Response,Request,Headers,Date,AbortSignal,...extra});
  return exports;
}

function bff({cookie,backend,env}={}){
  const calls=[],deleted=[];
  const jar={get:name=>name==='agapay_session'&&cookie!==undefined?{value:cookie}:undefined,set(){},delete:name=>deleted.push(name)};
  const module=evaluate(source(ROUTE),{
    'next/headers':{cookies:async()=>jar},
    'next/server':{NextResponse:class extends Response{static json(data,init){const headers=new Headers(init?.headers);headers.set('content-type','application/json');return new Response(JSON.stringify(data),{...init,headers});}}},
    '@/lib/account-server':{sessionCookie:'agapay_session',backendRequest:async(...args)=>{calls.push(args);return backend?backend(...args):new Response('{"items":[]}',{status:200});}},
  },env);
  const request=(p,{method='GET',headers={}}={})=>{
    const url='http://127.0.0.1/api/account/'+p;
    const init={method,headers:{host:'127.0.0.1',...(method==='GET'?{}:{origin:'http://127.0.0.1'}),...headers}};
    if(method!=='GET')init.body='{}';
    const handler=module[method];
    return handler?handler(Object.assign(new Request(url,init),{nextUrl:new URL(url)}),{params:Promise.resolve({path:p.split('/')})}):undefined;
  };
  return {module,request,calls,deleted};
}

const STAFF_READS=['alerts','alerts/active','alerts/command-queue','alerts/7','alerts/7/transitions','sos','sos/3','users','me',
  'security','audit','monitoring/stations','official-notices','operations/status','notification-deliveries','privacy/cases',
  'sos-response/incidents','stations/STATION_001/workspace','response-resources'];

test('anonymous and empty-cookie requests are refused before any backend call',async()=>{
  for(const cookie of [undefined,'']){
    const h=bff({cookie});
    const response=await h.request('alerts');
    assert.equal(response.status,401);assert.equal(h.calls.length,0);
    assert.equal(response.headers.get('cache-control'),'no-store');
  }
});

test('every staff data path asks FastAPI for staff-only access with the cookie session',async()=>{
  for(const p of STAFF_READS){
    const h=bff({cookie:'session-from-cookie'});
    assert.equal((await h.request(p)).status,200,p);
    const [upstream,token,method,,,requireStaff]=h.calls[0];
    assert.equal(token,'session-from-cookie',p);assert.equal(method,'GET',p);
    assert.equal(requireStaff,true,`${p} must carry X-Agapay-Require-Staff`);
    assert.ok(!upstream.startsWith('auth/alerts'),p);
  }
});

test('only the reviewed public identity paths are forwarded without the staff requirement',async()=>{
  const h=bff({});
  await h.request('capabilities');
  assert.equal(h.calls[0][5],false);
  const s=bff({cookie:'x'});await s.request('setup');
  assert.equal(s.calls.length,0,'setup is answered locally outside development');
});

test('backend 401/403 are propagated, never converted into success',async()=>{
  for(const status of [401,403]){
    const h=bff({cookie:'resident-session',backend:async()=>new Response(JSON.stringify({detail:status===403?'Staff access is required.':'Expired'}),{status})});
    const response=await h.request('alerts');
    assert.equal(response.status,status);
    const body=await response.json();assert.equal(body.items,undefined);
    assert.equal(response.headers.get('cache-control'),'no-store');
    assert.deepEqual(h.deleted,status===401?['agapay_session']:[],'only an expired session clears the cookie');
  }
});

test('authorization failure modes fail closed with no data',async()=>{
  const down=bff({cookie:'s',backend:async()=>{throw new Error('connect ECONNREFUSED');}});
  const response=await down.request('alerts');
  assert.equal(response.status,503);
  assert.deepEqual(await response.json(),{detail:'Unable to reach the server. Please try again.'});
  const broken=bff({cookie:'s',backend:async()=>new Response('<html>proxy error</html>',{status:502})});
  assert.equal((await broken.request('alerts')).status,503,'non-JSON upstream errors do not leak through');
  const failing=bff({cookie:'s',backend:async()=>new Response('{"detail":"boom"}',{status:500})});
  assert.equal((await failing.request('alerts')).status,500);
});

test('client-supplied identity headers are never trusted or forwarded',async()=>{
  const h=bff({cookie:'resident-session'});
  await h.request('alerts',{headers:{authorization:'Bearer officer-token','x-agapay-require-staff':'0','x-agapay-role':'admin'}});
  const [,token,,,,requireStaff]=h.calls[0];
  assert.equal(token,'resident-session');assert.equal(requireStaff,true);
  assert.equal(h.calls[0].length,6,'only path, cookie token, method, body, client IP and the staff flag reach the backend');
});

test('unsupported methods and unknown paths are rejected without a backend call',async()=>{
  const h=bff({cookie:'officer-session'});
  for(const [p,method] of [['alerts','PATCH'],['alerts','POST'],['alerts/7','PATCH'],['not-a-route','GET'],['../auth/me','GET']]){
    const response=await h.request(p,{method});
    assert.equal(response.status,404,`${method} ${p}`);
  }
  assert.equal(h.calls.length,0);
  assert.equal(h.module.DELETE,undefined);assert.equal(h.module.PUT,undefined);
});

test('administrator setup is never offered by a production server',async()=>{
  const h=bff({env:{NODE_ENV:'production',AGAPAY_API_URL:'http://127.0.0.1:8000'}});
  const response=await h.request('setup');
  assert.equal(response.status,200);assert.equal((await response.json()).available,false);
  assert.equal(h.calls.length,0);
});

test('the BFF has no mock or fixture data fallback',()=>{
  const route=source(ROUTE);
  assert.doesNotMatch(route,/mockData|DemoContext|fixture/i);
});

test('backendRequest sends the staff requirement only when asked and never caches',async()=>{
  const fetched=[];
  const module=evaluate(source('lib/account-server.ts'),{
    'server-only':{},react:{cache:fn=>fn},'next/headers':{cookies:async()=>({get:()=>undefined})},'next/navigation':{redirect(){}},
  },{NODE_ENV:'production',AGAPAY_API_URL:'http://127.0.0.1:8000'},{fetch:async(url,init)=>{fetched.push({url,init});return new Response('{}');}});
  await module.backendRequest('alerts','tok','GET',undefined,undefined,true);
  await module.backendRequest('auth/capabilities',undefined,'GET',undefined,undefined,false);
  assert.equal(fetched[0].url,'http://127.0.0.1:8000/api/alerts');
  assert.equal(fetched[0].init.headers['X-Agapay-Require-Staff'],'1');
  assert.equal(fetched[0].init.headers.Authorization,'Bearer tok');
  assert.equal(fetched[0].init.cache,'no-store');
  assert.equal(fetched[1].init.headers['X-Agapay-Require-Staff'],undefined);
  assert.equal(fetched[1].init.headers.Authorization,undefined);
});
