const assert=require('node:assert/strict');
const {test}=require('node:test');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript'),React=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
const source=file=>fs.readFileSync(path.join(__dirname,'../src',file),'utf8');
function evaluate(code,dependencies,extra={}){
  const exports={};vm.runInNewContext(ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,{exports,require:name=>dependencies[name]??require(name),process:{env:{NODE_ENV:'test'}},URL,URLSearchParams,Response,Date,...extra});return exports;
}
class AccountError extends Error{constructor(message,status,current){super(message);this.status=status;this.current=current;}}
const user={id:1,name:'Original name',email:'staff@example.com',phone:'+639123456789',barangay:'Test locality',role:'admin',version:1};
function component(file,request,props={},exportName='default'){
  const states=[],effects=[];let index=0,first=true,tree;
  const hooks={...React,useState(initial){const slot=index++;if(!(slot in states))states[slot]=initial;return[states[slot],v=>states[slot]=typeof v==='function'?v(states[slot]):v];},useEffect(fn){if(first)effects.push(fn);}};
  const context={user:{...user},setUser(value){context.user=value;}};
  const code=source('components/'+file).replace('function EditProfile(', 'export function EditProfile(');
  const dependencies={react:hooks,'@/lib/accounts':{accountRequest:request,AccountError},'@/context/AccountContext':{useAccount:()=>context},
    '@/context/ThemeContext':{ThemeSelector:()=>null},'@/lib/figma-assets':{figmaAssets:{logo:'/logo.png'}},
    './DesignUI':{FigmaIcon:()=>null,InformationDialog:()=>null,Modal:({children})=>children},'./GeographicPreferences':()=>null,'./AccountSecurity':()=>null,'./PrivacyCenter':()=>null,
    'next/link':({children,href})=>React.createElement('a',{href},children)};
  const module=evaluate(code,dependencies,{FormData:class{constructor(values){this.values=values;}get(key){return this.values[key]??null;}}});
  const render=()=>{index=0;tree=module[exportName](props);first=false;return tree;};render();for(const effect of effects)effect();
  function all(node=tree){return !node||typeof node!=='object'?[]:[node,...React.Children.toArray(node.props?.children).flatMap(all)];}
  return {context,render,find:predicate=>all().find(predicate),html:()=>renderToStaticMarkup(tree)};
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));

test('unconfigured Google and email recovery actions are absent from sign-in',async()=>{
  const h=component('Login.tsx',async()=>({available:false,recovery_available:false}),{onLogin(){}});await flush();h.render();
  assert.ok(!h.html().includes('Continue with Google'));assert.ok(!h.html().includes('Forgot password'));
  assert.ok(h.html().includes('Email recovery unavailable'));
});

test('password success only opens restricted MFA challenge; verification must succeed before navigation',async()=>{
  let navigations=0;const calls=[];
  const h=component('Login.tsx',async(path,method,body)=>{calls.push({path,method,body});return path==='login'?{challenge_token:'synthetic-challenge',mfa_enrollment_required:false}:path==='mfa/verify'?{user}:{};},{onLogin(){navigations++;}});
  await flush();h.render();h.find(n=>n.props?.id==='login-email').props.onChange({target:{value:user.email}});h.find(n=>n.props?.id==='login-password').props.onChange({target:{value:'synthetic-password'}});h.render();
  await h.find(n=>n.type==='form').props.onSubmit({preventDefault(){}});h.render();assert.equal(navigations,0);assert.ok(h.html().includes('Verify staff sign-in'));
  h.find(n=>n.type==='input'&&n.props.autoComplete==='one-time-code').props.onChange({target:{value:'123456'}});h.render();
  await h.find(n=>n.type==='form').props.onSubmit({preventDefault(){}});assert.equal(navigations,1);
  assert.equal(calls.find(c=>c.path==='mfa/verify').body.challenge_token,'synthetic-challenge');
});

test('open profile form uses its original version despite background account refresh and stops on 409',async()=>{
  let conflict=0;const calls=[];
  const h=component('Profile.tsx',async(path,method,body)=>{calls.push(body);throw new AccountError('Changed',409,{...user,version:2});},{onClose(){},onSaved(){},onConflict(){conflict++;}},'EditProfile');
  h.context.user={...user,version:2,name:'Newer server name'};h.render();
  await h.find(n=>n.type==='form').props.onSubmit({preventDefault(){},currentTarget:{name:'Stale edit',email:user.email,phone:user.phone,barangay:user.barangay,password:'discard-me',current_password:'current-password'}});
  assert.equal(calls.length,1);assert.equal(calls[0].expected_version,1);assert.equal(conflict,1);
});

function proxy(backend){
  const changes=[];
  const jar={get(){return undefined;},set(...args){changes.push(args);},delete(){}};
  const module=evaluate(source('app/api/account/[...path]/route.ts'),{
    'next/headers':{cookies:async()=>jar},'next/server':{NextResponse:class extends Response{static json(data,init){return new Response(JSON.stringify(data),init);}}},
    '@/lib/account-server':{backendRequest:backend,sessionCookie:'agapay_session'},
  });
  const call=(path,body,origin='http://127.0.0.1')=>module.POST(new Request('http://127.0.0.1/api/account/'+path,{method:'POST',headers:{host:'127.0.0.1',origin},body:JSON.stringify(body)}),{params:Promise.resolve({path:path.split('/')})});
  return {call,changes};
}
test('BFF does not create a session cookie for MFA challenges and never returns a verified bearer token to JavaScript',async()=>{
  const h=proxy(async(path)=>new Response(JSON.stringify(path==='auth/login'?{challenge_token:'restricted',mfa_enrollment_required:false}:{access_token:'server-only-bearer',expires_at:'2030-01-01T00:00:00Z',user,recovery_codes:['save-once']}),{status:path==='auth/login'?202:200}));
  const challenge=await h.call('login',{email:user.email,password:'test'});assert.equal(challenge.status,202);assert.equal(h.changes.length,0);
  const verified=await h.call('mfa/verify',{challenge_token:'restricted',code:'123456'});const data=await verified.json();
  assert.equal(data.access_token,undefined);assert.equal(data.recovery_codes[0],'save-once');assert.equal(h.changes[0][1],'server-only-bearer');assert.equal(h.changes[0][2].httpOnly,true);
});
test('public recovery mutations still require the exact application origin',async()=>{
  let calls=0;const h=proxy(async()=>{calls++;return new Response('{}');});
  assert.equal((await h.call('recovery/request',{email:user.email},'https://attacker.test')).status,403);assert.equal(calls,0);
});

test('client exposes sanitized conflict data without replaying the mutation',async()=>{
  let calls=0;const redirected=[];
  const module=evaluate(source('lib/accounts.ts'),{}, {fetch:async()=>{calls++;return new Response(JSON.stringify({detail:{message:'Changed; refresh manually',current:{...user,version:2}}}),{status:409});},window:{location:{assign:value=>redirected.push(value)}}});
  await assert.rejects(module.accountRequest('me','PATCH',{expected_version:1,name:'old'}),error=>error.status===409&&error.current.version===2);
  assert.equal(calls,1);assert.deepEqual(redirected,[]);
});
