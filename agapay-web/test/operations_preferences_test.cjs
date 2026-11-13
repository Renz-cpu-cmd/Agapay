const assert=require('node:assert/strict');
const {test}=require('node:test');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript');
const React=require('react');
// Render handlers against controlled request results without a browser or live account.
function harness(file,request,role='admin'){
  const states=[],effects=[];let index=0,first=true,tree;
  const hooks={...React,useState(initial){const slot=index++;if(!(slot in states))states[slot]=initial;return[states[slot],value=>{states[slot]=typeof value==='function'?value(states[slot]):value;}];},useEffect(fn){if(first)effects.push(fn);}};
  const exports={};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/components',file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,{exports,require:name=>name==='react'?hooks:name==='@/lib/accounts'?{accountRequest:request}:name==='@/context/AccountContext'?{useAccount:()=>({user:{role}})}:require(name)});
  const render=()=>{index=0;tree=exports.default({stationId:'TEST_STATION',onSaved(){}});first=false;return tree;};
  render();for(const effect of effects)effect();
  const all=(node=tree)=>!node||typeof node!=='object'?[]:[node,...React.Children.toArray(node.props?.children).flatMap(n=>all(n))];
  return{render,find(predicate){return all().find(predicate);}};
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const current={state:'active',revision:7,identity_version:3,station_name:'Test station',barangay:'Descriptive locality',municipality:'Test city',ingestion:'accepted',hazard_policy:'escalation_and_sustained_recovery',external_sensor_notifications:true,local_alarm_policy:'Offline local fail-safe remains active'};

test('station lifecycle sends displayed revisions and never automatically retries a conflict',async()=>{
  const requests=[];const h=harness('StationAdministration.tsx',async(...args)=>{requests.push(args);if(args[1]==='POST')throw new Error('Changed; refresh manually');return current;});
  await flush();h.render();
  h.find(n=>n.type==='input'&&!n.props.name).props.onChange({target:{value:'Reviewed maintenance reason'}});h.render();
  await h.find(n=>n.type==='button'&&n.props.children==='Apply lifecycle change').props.onClick();await flush();h.render();
  const write=requests.find(r=>r[1]==='POST');assert.equal(write[0],'stations/TEST_STATION/lifecycle');assert.equal(write[2].expected_revision,7);assert.equal(write[2].expected_identity_version,3);assert.equal(write[2].state,'maintenance');
  assert.equal(h.find(n=>n.type==='button'&&n.props.children==='Apply lifecycle change').props.disabled,true);
  assert.equal(requests.filter(r=>r[1]==='POST').length,1);
  await h.find(n=>n.type==='button'&&n.props.children==='Refresh station operations').props.onClick();await flush();h.render();
  assert.equal(requests.filter(r=>r[1]==='POST').length,1);
});

test('officers can read operations but do not receive administration controls',async()=>{
  const h=harness('StationAdministration.tsx',async()=>current,'officer');await flush();h.render();
  assert.equal(h.find(n=>n.type==='button'&&n.props.children==='Apply lifecycle change'),undefined);
  assert.ok(h.find(n=>n.type==='button'&&n.props.children==='Refresh station operations'));
});

test('area context saves the verified ID with conflict protection and never changes locale or subscription',async()=>{
  const requests=[];const preferences={revision:5,locale:'en',resident_area_id:null,requested_language:null};
  const h=harness('GeographicPreferences.tsx',async(...args)=>{requests.push(args);if(args[0]==='preferences/areas')return[{id:'VERIFIED_TEST',name:'Synthetic area'}];return preferences;});
  await flush();h.render();await h.find(n=>n.type==='select').props.onChange({target:{value:'VERIFIED_TEST'}});await flush();h.render();
  const write=requests.find(r=>r[1]==='PATCH');assert.equal(write[2].resident_area_id,'VERIFIED_TEST');assert.equal(write[2].expected_revision,5);assert.equal(write[2].locale,undefined);
  assert.ok(requests.every(r=>r[0].startsWith('preferences')));
  assert.ok(h.find(n=>n.type==='p'&&n.props.children==='Operational language: English. Filipino translation unavailable.'));
});
