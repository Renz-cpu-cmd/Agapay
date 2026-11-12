const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript');
function load(file){const result={};vm.runInNewContext(ts.transpileModule(fs.readFileSync('src/lib/'+file+'.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{exports:result,require:name=>load(name.replace('./',''))});return result;}
const forecast=load('forecast-workspace'),operations=load('operations-console');
const product=JSON.parse(fs.readFileSync('../agapay-docs/contracts/published-forecast-cases.json','utf8')).find(row=>row.valid).value;
function workspace(p){return {station_id:p.station_id,checked_at:p.checked_at,publication_status:'available',current_forecast_id:p.forecast_id,
 deployment:{model_id:p.model_card_id,version:p.deployment_version,model_review_version:3},model:{state:'approved',version:3}};}
test('publication state uses original expiry, exact binding and current review version',()=>{
 const p=structuredClone(product),data=workspace(p),envelope={product:p,current:true};const now=Date.parse(p.checked_at);
 assert.equal(forecast.publicationState(data,p,envelope,now),'current');
 assert.equal(forecast.publicationState({...data,checked_at:p.valid_until},p,envelope,Date.parse(p.valid_until)),'historical','a fresh read never extends a published expiry');
 assert.equal(forecast.publicationState({...data,model:{state:'revoked',version:4}},p,envelope,now),'historical');
 assert.equal(forecast.publicationState({...data,deployment:{...data.deployment,version:999}},p,envelope,now),'historical');
 assert.equal(forecast.publicationState(data,p,envelope,now+46000),'unconfirmed');
 assert.equal(forecast.publicationState(data,p,envelope,now-1),'unconfirmed');
});
test('publication evidence rejects another station or incomplete uncertainty and preserves real zero',()=>{
 const parsed=forecast.publishedEvidence({product},product.station_id);assert.equal(parsed.forecasts[0].water_depth_cm,product.forecasts[0].water_depth_cm);
 assert.throws(()=>forecast.publishedEvidence({product},'ANOTHER_STATION'));
 assert.throws(()=>forecast.publishedEvidence({product:{...product,uncertainty:null}},product.station_id));
 assert.equal(forecast.publicationState(workspace(product),product,{product,current:false},Date.parse(product.checked_at)),'historical');
});
test('queue diagnostics expire and duration histogram bounds do not fabricate latency',()=>{
 const now=Date.now();assert(operations.evidenceIsCurrent(new Date(now).toISOString(),now));
 assert(!operations.evidenceIsCurrent(new Date(now-46000).toISOString(),now));assert(!operations.evidenceIsCurrent(new Date(now+1).toISOString(),now));
 assert.equal(operations.latencyBound(0,0),'No observations');assert.match(operations.latencyBound(null,20),/unavailable/);
 assert.equal(operations.latencyBound(0,20),'≤0.000 s bucket upper bound');
});
test('fresh heartbeat alone cannot claim successful worker progress',()=>{
 const now=Date.now(),checked=new Date(now).toISOString(),worker={state:'healthy',fresh:true,age_seconds:1,last_success_at:new Date(now-60000).toISOString()};
 assert.equal(operations.agedWorkerState(worker,checked,now,true),'no recent successful progress');
 worker.last_success_at=checked;assert.equal(operations.agedWorkerState(worker,checked,now,true),'healthy');
 assert.equal(operations.agedWorkerState(worker,checked,now+46000,true),'unconfirmed / stale');
 assert.equal(operations.agedWorkerState({...worker,state:'failed'},checked,now,true),'failed');
});
