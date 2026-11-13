const {test}=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript');
const source=p=>fs.readFileSync(path.join(__dirname,'../src',p),'utf8');
function evaluate(file,deps={},extra={}){const exports={};vm.runInNewContext(ts.transpileModule(source(file),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{exports,Headers,URL,Buffer,process:{env:{NODE_ENV:'production'}},require:n=>deps[n]??require(n),...extra});return exports;}
const policy=evaluate('lib/security-policy.ts').securityPolicy;
test('production CSP requires a fresh nonce, excludes eval/inline scripts and permits Maps channels',()=>{
 const value=policy('AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA');assert.match(value,/strict-dynamic/);assert.match(value,/nonce-A/);assert.doesNotMatch(value,/unsafe-eval/);assert.doesNotMatch(value.split(';').find(v=>v.includes('script-src')),/unsafe-inline/);
 for(const directive of ["object-src 'none'","frame-ancestors 'none'","form-action 'self'","base-uri 'self'","https:\/\/\*.googleapis.com"]){assert.ok(value.includes(directive.replaceAll('\\','')));}
 assert.match(policy('BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB',true),/unsafe-eval/);assert.match(policy('CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC',false,true),/unsafe-eval/);assert.throws(()=>policy('untrusted-header'));
});
test('proxy overwrites attacker nonce and CSP, uses a unique value per request and disables HTML caching',()=>{
 let internal;
 const module=evaluate('proxy.ts',{'@/lib/security-policy':{securityPolicy:policy},'next/server':{NextResponse:{next(options){internal=options.request.headers;return{headers:new Headers()};}}}});
 const request={headers:new Headers({'x-nonce':'attacker','Content-Security-Policy':"script-src * 'unsafe-inline'"})};
 const one=module.proxy(request),nonce=internal.get('x-nonce');assert.notEqual(nonce,'attacker');assert.match(one.headers.get('Content-Security-Policy'),new RegExp('nonce-'+nonce.replace(/[+]/g,'\\+')));assert.equal(one.headers.get('Cache-Control'),'private, no-store');assert.equal(internal.get('Content-Security-Policy'),one.headers.get('Content-Security-Policy'));
 module.proxy(request);assert.notEqual(internal.get('x-nonce'),nonce);
});
test('theme startup is server-neutral and the root layout applies the request nonce',()=>{
 const script=evaluate('lib/theme-startup.ts').themeStartupScript;
 const document={documentElement:{dataset:{}}};vm.runInNewContext(script,{document,localStorage:{getItem:()=> 'dark'}});assert.equal(document.documentElement.dataset.theme,'dark');
 assert.match(source('app/layout.tsx'),/script nonce=\{nonce\}/);assert.match(source('app/layout.tsx'),/await headers\(\)/);
});
test('production launcher accepts HTTPS or private same-host upstream only',async()=>{
 const {productionConfig}=await import('../scripts/production-config.mjs');
 const good={AGAPAY_ENVIRONMENT:'production',AGAPAY_WEB_ORIGIN:'https://web.agapay.test',AGAPAY_API_URL:'http://127.0.0.1:8000'};
 assert.equal(productionConfig(good).backendOrigin,'http://127.0.0.1:8000');
 for(const extra of [{NODE_TLS_REJECT_UNAUTHORIZED:'0'},{AGAPAY_ENVIRONMENT:'development'},{AGAPAY_WEB_ORIGIN:'http://web.agapay.test'},{AGAPAY_API_URL:'http://192.168.1.1:8000'},{AGAPAY_API_URL:'https://secret@example.test/api'}])assert.throws(()=>productionConfig({...good,...extra}));
});
