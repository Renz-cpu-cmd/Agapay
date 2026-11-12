const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript');
const api={};vm.runInNewContext(ts.transpileModule(fs.readFileSync('src/lib/staff-workspaces.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{exports:api});
test('measured history uses elapsed timestamps and breaks invalid and missing intervals',()=>{
 const rows=api.measuredSeries([{measuredAt:'2026-10-23T00:10:00Z',level:12},{measuredAt:'2026-10-23T00:00:00Z',level:0},{measuredAt:'2026-10-23T00:00:10Z',level:null},{time:'receipt only',recordedAt:'2026-10-23T00:00:01Z',measuredAt:null,level:5}],30);
 assert.equal(rows.length,4);assert.equal(rows[0].level,0);assert.equal(rows[1].level,null);
 assert.equal(rows[2].level,null);assert.equal(rows[2].gapStart,Date.parse('2026-10-23T00:00:10Z'));
 assert.equal(rows[3].at-rows[0].at,600000);
});
test('queue freshness expires and future or missing check times cannot authorize an action',()=>{
 const now=Date.parse('2026-10-23T00:00:30Z');
 assert.equal(api.readIsCurrent('2026-10-23T00:00:20Z',now),true);
 for(const at of [null,undefined,'bad','2026-10-23T00:00:00Z','2026-10-23T00:00:31Z'])assert.equal(api.readIsCurrent(at,now),false);
 assert.equal(api.elapsedLabel('2026-10-22T23:00:00Z',now),'1h 0m elapsed');
 assert.equal(api.elapsedLabel('2026-10-23T00:00:31Z',now),'Time unconfirmed');
});
test('maintenance and independent rain failure remain separate from heartbeat outages',()=>{
 const channel={state:'healthy'};
 const station={administrativeStatus:'active',channelHealth:{water_sensor:channel,device_heartbeat:channel,broker_ingestion:channel,rain_counter:{state:'stale'}}};
 assert.equal(api.stationFaults(station).join(),'rain counter: stale');
 assert.equal(api.stationFaults({...station,administrativeStatus:'maintenance'}).join(),'Administration: maintenance');
 assert.equal(api.stationFaults({administrativeStatus:'active'}).join(),'Independent health unavailable');
});
test('next action checks configuration, measurement time and retained-depth provenance',()=>{
 const station={configuration:{status:'matched'},depthFresh:true,sourceTrusted:true,depthSourceTrusted:false};
 assert.match(api.reviewAction(station),/source identity/);
 assert.match(api.reviewAction({...station,depthFresh:false}),/last-valid time/);
 assert.match(api.reviewAction({...station,configuration:{status:'mismatch'}}),/configuration/);
});
