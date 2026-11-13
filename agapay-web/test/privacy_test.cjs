const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript');
const code=fs.readFileSync('src/app/api/account/[...path]/route.ts','utf8');
function proxy(){const calls=[];let authenticated=true;const exports={};vm.runInNewContext(ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{exports,require:name=>({
 'next/headers':{cookies:async()=>({get:()=>authenticated?{value:'synthetic-session'}:undefined,delete(){},set(){}})},
 'next/server':{NextResponse:class extends Response{static json(data,init){return new Response(JSON.stringify(data),init);}}},
 '@/lib/account-server':{sessionCookie:'agapay_session',backendRequest:async(...args)=>{calls.push(args);return new Response(JSON.stringify({detail:{code:'refresh_required'}}),{status:409});}},
}[name]??require(name)),URL,URLSearchParams,Request,Response,process:{env:{NODE_ENV:'test'}}});
const call=async(path,method='GET',origin='http://127.0.0.1')=>{const url='http://127.0.0.1/api/account/'+path,request=new Request(url,{method,headers:{host:'127.0.0.1',origin},...(method==='GET'?{}:{body:'{"expected_version":1}'})});request.nextUrl=new URL(url);return exports[method](request,{params:Promise.resolve({path:path.split('?')[0].split('/')})});};return{calls,call,signOut(){authenticated=false;}};}

test('privacy proxy preserves owner scope, bounded cursor and stale conflicts',async()=>{const h=proxy();
 assert.equal((await h.call('privacy/export?after=7&limit=50&user_id=99','POST')).status,409);
 assert.equal(h.calls[0][0],'privacy/export?after=7&limit=50');assert.equal(h.calls[0][5],true);
 assert.equal((await h.call('privacy/admin/cases/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','PATCH')).status,409);
 assert.equal((await h.call('privacy/admin/holds/5','PATCH')).status,409);
 const n=h.calls.length;assert.equal((await h.call('privacy/admin/cases/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/application-erasure','POST','https://attacker.test')).status,403);assert.equal(h.calls.length,n);
 assert.equal((await h.call('privacy/admin/delete-everything','POST')).status,404);
 h.signOut();assert.equal((await h.call('privacy/cases')).status,401);
});

