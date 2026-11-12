const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript'),React=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
async function renderDiagnostics(request){
  const slots=[],effects=[];let index=0,initial=true;
  const react={...React,useState(value){const key=index++;if(!(key in slots))slots[key]=value;return [slots[key],next=>slots[key]=next];},useEffect(effect){if(initial)effects.push(effect);}};
  const exports={};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync('src/components/SystemHealth.tsx','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,{exports,require:name=>({
    react,'./OperationsDetails':{default:()=>null},'@/hooks/useEvidenceClock':{useEvidenceClock:()=>Date.now()},'./DeliveryConsole':{default:()=>null},'@/lib/accounts':{accountRequest:request},'@/lib/visible-poll':{visiblePoll:run=>{run(new AbortController().signal).catch(()=>{});return()=>{};}},
    '@/context/MonitoringContext':{useMonitoring:()=>({stations:[],refresh(){},loading:false})},
    '@/lib/measurements':{},'@/lib/channel-health':{},
  }[name]??require(name))});
  exports.default();initial=false;effects.forEach(effect=>effect());await new Promise(resolve=>setImmediate(resolve));
  index=0;return renderToStaticMarkup(exports.default());
}
test('operator health renders a specific degraded workflow independently of station heartbeats',async()=>{
  const at=new Date().toISOString();
  const html=await renderDiagnostics(async()=>({checked_at:at,status:'degraded',ready:false,
    components:[{name:'notifications',state:'degraded',required:true,code:'NOTIFICATIONS_WORKER_STALE',message:'Delivery worker is not progressing'}],
    alerts:[{code:'NOTIFICATIONS_WORKER_STALE',severity:'critical',message:'Delivery worker is not progressing'}]}));
  assert.match(html,/readiness degraded/);assert.match(html,/NOTIFICATIONS_WORKER_STALE/);assert.match(html,/Required capability/);assert.ok(html.includes(at));
});
test('failed diagnostics show unknown readiness instead of a healthy workflow claim',async()=>{
  const html=await renderDiagnostics(async()=>{throw Error('synthetic dependency failure');});
  assert.match(html,/readiness cannot be confirmed/);assert.doesNotMatch(html,/readiness ready/);
});

test('expired dependency observations cannot retain a current healthy label',async()=>{
  const html=await renderDiagnostics(async()=>({checked_at:'2000-01-01T00:00:00Z',status:'healthy',ready:true,
    components:[{name:'mqtt',state:'healthy',required:true,code:null,message:'Last broker observation'}],alerts:[]}));
  assert.match(html,/Diagnostics expired/);assert.match(html,/unknown \(last reported healthy\)/);assert.doesNotMatch(html,/readiness ready/);
});
