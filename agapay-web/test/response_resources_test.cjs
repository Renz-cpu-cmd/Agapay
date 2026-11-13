const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript'),React=require('react');
const source=file=>fs.readFileSync(path.join(__dirname,'../src',file),'utf8');
class AccountError extends Error{constructor(message,status){super(message);this.status=status;}}
function evaluate(code,dependencies,extra={}){
  const exports={};vm.runInNewContext(ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,{exports,require:name=>dependencies[name]??require(name),URL,URLSearchParams,Response,Date,structuredClone,process:{env:{NODE_ENV:'test'}},setTimeout:()=>0,clearTimeout:()=>{},setInterval:()=>0,clearInterval:()=>{},crypto:{randomUUID:()=>"test-new-id"},...extra});return exports;
}
function harness(file,request,props={},name='default',dependencies={}){
  const slots=[],effects=[];let index=0,first=true,tree;
  const hooks={...React,useState(initial){const slot=index++;if(!(slot in slots))slots[slot]=typeof initial==='function'?initial():initial;return[slots[slot],v=>slots[slot]=typeof v==='function'?v(slots[slot]):v];},useRef(initial){const slot=index++;return slots[slot]??(slots[slot]={current:initial});},useEffect(fn){if(first)effects.push(fn);},useCallback(fn){return fn;}};
  const module=evaluate(source(file).replace('function SOSDetailModal(', 'export function SOSDetailModal('),{
    react:hooks,'@/lib/accounts':{accountRequest:request,AccountError},'@/context/AccountContext':{useAccount:()=>({user:{id:1,role:'officer'}})},
    '@/lib/sos':{sosTime:v=>v},'@/hooks/useDialog':{useDialog:()=>({current:null})},'./DesignUI':{FigmaIcon:()=>null},
    './GoogleSosLocationMap':()=>null,'./SosDrillWorkspace':()=>null,...dependencies,
  });
  function render(){index=0;tree=module[name](props);first=false;return tree;}
  function all(node=tree){return !node||typeof node!=='object'?[]:[node,...React.Children.toArray(node.props?.children).flatMap(all)];}
  render();for(const effect of effects)effect();
  return{render,find:fn=>all().find(fn),all,tree:()=>tree};
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const text=node=>React.Children.toArray(node?.props?.children).filter(v=>typeof v==='string').join('');
const enter=(h,label,value)=>{const node=h.find(n=>n.type==='label'&&text(n).includes(label));assert.ok(node,label);const field=React.Children.toArray(node.props.children).find(n=>n?.type==='input'||n?.type==='select');field.props.onChange({target:{value}});h.render();};

function proxy(){
  const calls=[];let role='admin';
  const module=evaluate(source('app/api/account/[...path]/route.ts'),{
    'next/headers':{cookies:async()=>({get:()=>({value:'server-session'}),delete(){},set(){}})},
    'next/server':{NextResponse:class extends Response{static json(data,init){return new Response(JSON.stringify(data),init);}}},
    '@/lib/account-server':{sessionCookie:'agapay_session',backendRequest:async(route,token,method,body,signal,requireStaff)=>{calls.push({route,method,body,requireStaff});return new Response(JSON.stringify({}),{status:requireStaff&&role==='resident'?403:200,headers:{'X-Request-ID':'synthetic-id'}});}},
  });
  async function call(route,method='GET',body,origin='http://127.0.0.1'){
    const url='http://127.0.0.1/api/account/'+route;
    const request=Object.assign(new Request(url,{method,headers:{host:'127.0.0.1',origin},...(body?{body:JSON.stringify(body)}:{})}),{nextUrl:new URL(url)});
    return module[method](request,{params:Promise.resolve({path:route.split('?')[0].split('/')})});
  }
  return{calls,call,setRole:value=>role=value};
}


const context={authorities:[{id:'AUTH',name:'Synthetic public issuer',authority_class:'public_authority',area_ids:['AREA']}],areas:[{id:'AREA',name:'Synthetic area',area_class:'geographic'}]};
const row=()=>({id:'SHELTER',kind:'shelter',authority_id:'AUTH',mode:'Actual',area_ids:['AREA'],version:4,source:'Synthetic record',verification:'verified',effective_state:'active',issuer_name:'Synthetic public issuer',verified_at:'2026-10-22T01:00:00Z',expires_at:'2099-10-22T02:00:00Z',route_safety:'not_established',data:{name:'Synthetic shelter',address:'Synthetic entrance',point:{latitude:15.976,longitude:120.571},state:'active',activated_at:'2026-10-22T10:00:00+08:00',contacts:[{name:'Test contact',contact:'TEST ONLY',hours:'Exercise hours'}],services:[],instructions:'Synthetic reviewed instructions',access_constraints:'Synthetic access restriction'}});

test('resource review requires persisted fields and conflicts block all replay until manual refresh',async()=>{
  const writes=[];let version=4;
  const h=harness('components/ResponseResources.tsx',async(route,method,body)=>{
    if(method==='POST'){writes.push({route,body});throw new AccountError('Changed. Refresh required.',409);}
    return route.endsWith('maintenance-context')?context:{items:[{...row(),version}],total:1};
  });
  await flush();h.render();h.find(n=>n.type==='button'&&text(n)==='Review record').props.onClick();h.render();
  const latitude=h.find(n=>n.type==='label'&&text(n)==='Latitude');assert.equal(React.Children.toArray(latitude.props.children)[1].props.step,'any');
  const activation=h.find(n=>n.type==='label'&&text(n)==='Activation time (UTC)');assert.equal(React.Children.toArray(activation.props.children)[1].props.value,'2026-10-22T02:00');
  enter(h,'Actor review/change reason','Synthetic review reason');enter(h,'Verification expires','2099-10-22T02:00');
  assert.equal(h.find(n=>n.type==='button'&&text(n)==='Verify this revision').props.disabled,false);
  enter(h,'Name','Unsaved name');assert.equal(h.find(n=>n.type==='button'&&text(n)==='Verify this revision').props.disabled,true);
  h.find(n=>n.type==='button'&&text(n)==='Verify this revision').props.onClick();await flush();assert.equal(writes.length,0);
  h.find(n=>n.type==='form').props.onSubmit({preventDefault(){}});await flush();h.render();assert.equal(writes[0].body.expected_version,4);assert.equal(writes[0].body.data.name,'Unsaved name');
  assert.ok(h.find(n=>n.type==='button'&&text(n)==='Review record').props.disabled);
  h.find(n=>n.type==='form').props.onSubmit({preventDefault(){}});await flush();assert.equal(writes.length,1);
  version=6;h.find(n=>n.type==='button'&&text(n)==='Refresh and review registry').props.onClick();await flush();h.render();
  h.find(n=>n.type==='button'&&text(n)==='Review record').props.onClick();h.render();enter(h,'Name','Manually reviewed');enter(h,'Actor review/change reason','New explicit review');
  h.find(n=>n.type==='form').props.onSubmit({preventDefault(){}});await flush();assert.equal(writes[1].body.expected_version,6);
});

test('registry verification expires locally while the page stays open',()=>{
  const module=evaluate(source('components/ResponseResources.tsx'),{react:React,'@/lib/accounts':{AccountError}});
  const record={...row(),expires_at:'2026-10-22T02:00:00Z'};
  assert.equal(module.resourceVerification(record,Date.parse('2026-10-22T01:59:59Z')),'verified');
  assert.equal(module.resourceVerification(record,Date.parse('2026-10-22T02:00:00Z')),'expired');
  assert.equal(module.resourceVerification({...record,verification:'withdrawn'},Date.now()),'withdrawn');
});

test('BFF preserves response registry namespace, bounded filters, revision pagination and method/origin/staff controls',async()=>{
  const h=proxy();
  for(const [route,method,body]of [['response-resources?kind=road&mode=Actual&area_id=AREA&include_drafts=true&limit=50&offset=50','GET'],['response-resources/maintenance-context','GET'],['response-resources/SHELTER/revisions?limit=20&offset=20','GET'],['response-resources','POST',{expected_version:4}],['response-resources/SHELTER/review','POST',{expected_version:5,action:'verify'}]]){
    assert.equal((await h.call(route,method,body)).status,200);assert.equal(h.calls.at(-1).route,route);
  }
  assert.equal((await h.call('response-resources/SHELTER/review','PATCH',{})).status,404);
  assert.equal((await h.call('response-resources','POST',{},'https://attacker.test')).status,403);
  h.setRole('resident');assert.equal((await h.call('response-resources')).status,403);
});

test('protected reads use one upstream authorization and preserve correlation on success',async()=>{
  const h=proxy();const response=await h.call('operations/diagnostics');
  assert.equal(response.status,200);assert.equal(h.calls.length,1);assert.equal(h.calls[0].requireStaff,true);
  assert.equal(response.headers.get('X-Request-ID'),'synthetic-id');assert.equal(h.calls[0].route,'operations/diagnostics');
});
