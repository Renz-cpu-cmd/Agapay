const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript'),React=require('react');
const source=file=>fs.readFileSync(path.join(__dirname,'../src',file),'utf8');
class AccountError extends Error{constructor(message,status){super(message);this.status=status;}}
function evaluate(code,dependencies,extra={}){
  const exports={};vm.runInNewContext(ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,{exports,require:name=>dependencies[name]??require(name),URL,URLSearchParams,Response,Date,structuredClone,process:{env:{NODE_ENV:'test'}},setTimeout:()=>0,clearTimeout:()=>{},...extra});return exports;
}
function harness(file,request,props={},name='default',dependencies={}){
  const slots=[],effects=[];let index=0,first=true,tree;
  const hooks={...React,useState(initial){const slot=index++;if(!(slot in slots))slots[slot]=typeof initial==='function'?initial():initial;return[slots[slot],v=>slots[slot]=typeof v==='function'?v(slots[slot]):v];},useRef(initial){const slot=index++;return slots[slot]??(slots[slot]={current:initial});},useEffect(fn){if(first)effects.push(fn);},useCallback(fn){return fn;}};
  const module=evaluate(source(file).replace('function SOSDetailModal(', 'export function SOSDetailModal('),{
    react:hooks,'@/lib/accounts':{accountRequest:request,AccountError},'@/context/AccountContext':{useAccount:()=>({user:{id:1,role:'officer'}})},
    '@/lib/sos':{sosTime:v=>v},'@/hooks/useDialog':{useDialog:()=>({current:null})},'./DesignUI':{FigmaIcon:()=>null},
    '@/lib/visible-poll':{visiblePoll:()=>()=>{}},'./GoogleSosLocationMap':()=>null,'./SosDrillWorkspace':()=>null,...dependencies,
  });
  function render(){index=0;tree=module[name](props);first=false;return tree;}
  function all(node=tree){return !node||typeof node!=='object'?[]:[node,...React.Children.toArray(node.props?.children).flatMap(all)];}
  render();for(const effect of effects)effect();
  return{render,find:fn=>all().find(fn),all,tree:()=>tree};
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const text=node=>React.Children.toArray(node?.props?.children).filter(v=>typeof v==='string').join('');
const enter=(h,label,value)=>{const node=h.find(n=>n.type==='label'&&text(n).includes(label));assert.ok(node,label);const field=React.Children.toArray(node.props.children).find(n=>n?.type==='input'||n?.type==='select');field.props.onChange({target:{value}});h.render();};

test('drill actions use their reviewed snapshot and require manual refresh after conflict',async()=>{
  let version=4;const writes=[];
  const request=async(route,method,body)=>{
    if(method==='POST'){writes.push(body);throw new AccountError('Changed; refresh',409);}
    if(route==='sos-response/policy')return{version:1,settings:{},activation_requirements:['Real procedures and witnessed drill']};
    if(route==='sos-response/staff')return[{id:2,name:'Drill participant'}];
    if(route==='sos-response/incidents')return[];
    if(route==='sos/7')return{id:7,version,status:'ACKNOWLEDGED'};
    return{started:true,request_version:version,phase:'ASSIGNED',events:[]};
  };
  const h=harness('components/SosDrillWorkspace.tsx',request,{requestId:7,onStarted:()=>{}});
  await flush();h.render();enter(h,'Action reason','Reviewed synthetic assignment');enter(h,'Responder','2');
  await h.find(n=>n.type==='form').props.onSubmit({preventDefault(){}});await flush();h.render();
  assert.equal(writes.length,1);assert.equal(writes[0].expected_version,4);
  assert.ok(h.find(n=>n.type==='button'&&text(n)==='Record drill action').props.disabled);
  const reason=h.find(n=>n.type==='label'&&text(n).includes('Action reason'));assert.equal(React.Children.toArray(reason.props.children).find(n=>n?.type==='input').props.value,'');
  h.find(n=>n.type==='form').props.onSubmit({preventDefault(){}});await flush();assert.equal(writes.length,1);
  version=6;h.find(n=>n.type==='button'&&text(n)==='Refresh and review drill').props.onClick();await flush();h.render();
  assert.equal(writes.length,1);assert.equal(h.find(n=>n.type==='button'&&text(n)==='Record drill action').props.disabled,false);
  enter(h,'Action reason','Manually reviewed newer snapshot');enter(h,'Responder','2');
  h.find(n=>n.type==='form').props.onSubmit({preventDefault(){}});await flush();assert.equal(writes[1].expected_version,6);
});

test('legacy status editor keeps its opening version despite background location refresh',async()=>{
  let current={id:7,version:2,status:'ACKNOWLEDGED',latitude:null,longitude:null,created_at:'2026-10-22T00:00:00Z'};
  const writes=[];
  const h=harness('components/SOSBeacons.tsx',async()=>current,{initial:{...current,version:1},onClose:()=>{},openMap:false},'SOSDetailModal',{
    '@/context/SosContext':{useSos:()=>({refresh:async()=>{},update:async(...args)=>{writes.push(args);throw new AccountError('Refresh required',409);}})},
  });
  await flush();h.render();h.find(n=>n.type==='textarea').props.onChange({target:{value:'Discard stale closure'}});h.render();
  h.find(n=>n.type==='button'&&text(n)==='MARK RESOLVED').props.onClick();await flush();h.render();
  assert.equal(writes.length,1);assert.equal(writes[0][3],1);assert.equal(h.find(n=>n.type==='textarea').props.value,'');
  assert.equal(h.find(n=>n.type==='button'&&text(n)==='MARK RESOLVED').props.disabled,true);
  h.find(n=>n.type==='button'&&text(n)==='Refresh and review request').props.onClick();await flush();h.render();
  h.find(n=>n.type==='button'&&text(n)==='MARK RESOLVED').props.onClick();await flush();assert.equal(writes[1][3],2);
});

test('SOS provider passes the selected version through without replaying a rejected update',async()=>{
  const writes=[];
  const h=harness('context/SosContext.tsx',async(route,method,body)=>{
    if(method==='PATCH'){writes.push(body);throw new AccountError('Changed',409);}
    return{items:[],total:0,counts:{ACTIVE:0,ACKNOWLEDGED:0,RESOLVED:0}};
  },{children:null},'SosProvider');
  await flush();h.render();await assert.rejects(h.tree().props.value.update(7,'RESOLVED','Reviewed closure',12));
  assert.equal(writes.length,1);assert.equal(writes[0].expected_version,12);
});

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

test('BFF forwards drill reads, policy edits and recorded actions under the correct backend namespace',async()=>{
  const h=proxy();
  for(const [route,method,body] of [['sos-response/policy','GET'],['sos-response/staff','GET'],['sos-response/incidents','POST',{label:'Drill',reason:'Synthetic'}],['sos-response/policy','PATCH',{expected_version:1}],['sos-response/7/start','POST',{expected_version:3}],['sos-response/7/actions','POST',{expected_version:4}]]){
    assert.equal((await h.call(route,method,body)).status,200);assert.equal(h.calls.at(-1).route,route);
  }
  assert.equal((await h.call('sos-response/7?before_event_id=9')).status,200);assert.equal(h.calls.at(-1).route,'sos-response/7?before_event_id=9');
  assert.equal((await h.call('sos-response/7/activate','POST',{})).status,404);
  assert.equal((await h.call('sos-response/7/actions','PATCH',{})).status,404);
});

test('BFF rejects drill mutation origin spoofing and resident staff-workspace access',async()=>{
  const h=proxy();
  assert.equal((await h.call('sos-response/7/actions','POST',{},'https://attacker.test')).status,403);assert.equal(h.calls.length,0);
  h.setRole('resident');assert.equal((await h.call('sos-response/policy')).status,403);assert.equal(h.calls.length,1);
});
