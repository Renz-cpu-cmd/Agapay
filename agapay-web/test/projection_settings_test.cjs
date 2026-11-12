const assert=require('node:assert/strict');
const {test}=require('node:test');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ts=require('typescript');
const exportsObject={};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/lib/projection-settings.ts'),'utf8'),{
  compilerOptions:{module:ts.ModuleKind.CommonJS},
}).outputText,{exports:exportsObject});
const {decodeProjectionSetups:decode,encodeProjectionSetups:encode,projectionStorageKey:key,withAutomaticDemoSetup:auto}=exportsObject;
const config={mode:'live',depthSource:'sensor',rainSource:'physical_rain_gauge',initial:'20',context:'2025-07-01T12:00',confirmed:true,
  basin:{contributing_area_m2:2,basin_surface_area_m2:.1,runoff_coefficient:.8,outflow_m3_per_hour:0,maximum_depth_cm:100},
  basis:{contributing_area_m2:'assumed',basin_surface_area_m2:'assumed',runoff_coefficient:'assumed',outflow_m3_per_hour:'assumed',maximum_depth_cm:'assumed'}};
const saved=c=>encode({STATION_001:{config:c,active:true}});
test('refresh restores only the same account setup, with no cached forecasts',()=>{
  const restored=decode(saved(config));
  assert.equal(restored.STATION_001.active,true);
  assert.equal(restored.STATION_001.config.depthSource,'sensor');
  assert.equal(restored.STATION_001.data,undefined);assert.notEqual(key(1),key(2));
});
test('unconfirmed, corrupt, unknown-source and invalid-basin setups cannot auto-start',()=>{
  assert.equal(decode(saved({...config,confirmed:false})).STATION_001.active,false);
  for(const raw of [null,'broken',saved({...config,rainSource:'unknown'}),saved({...config,initial:'NaN'}),
    saved({...config,basin:{...config.basin,basin_surface_area_m2:0}}),saved({...config,mode:'historical_context'})]) {
    assert.equal(Object.keys(decode(raw)).length,0);
  }
});
test('prototype keys are rejected and station setup remains independent',()=>{
  const raw=JSON.stringify({version:1,stations:{constructor:{config,active:true},STATION_001:{config,active:false}}});
  const restored=decode(raw);assert.equal(Object.hasOwn(restored,'constructor'),false);
  assert.equal(restored.STATION_001.active,false);
});

const physical={station_id:'STATION_001',source:'device',source_class:'physical_device',source_trusted:true,
  depth_source_trusted:true,depth_fresh:true,heartbeat_fresh:true,stream:'operational',is_online:true,sensor_quality:'valid',current_depth_cm:58};
test('a fresh verified local device starts the physical demo without manual configuration',()=>{
  const next=auto({},physical,true);
  assert.equal(next.STATION_001.active,true);
  assert.equal(next.STATION_001.config.depthSource,'sensor');
  assert.equal(next.STATION_001.config.rainSource,'physical_rain_gauge');
  assert.equal(next.STATION_001.config.mode,'live');
  assert.equal(next.STATION_001.config.basis.basin_surface_area_m2,'assumed');
  assert.equal(decode(encode(next)).STATION_001.active,true);
});
test('automatic setup respects Stop/custom settings and cannot invent fresh or remote inputs',()=>{
  const stopped={STATION_001:{config,active:false}};
  assert.equal(auto(stopped,physical,true),stopped);
  const empty={};
  for(const changed of [undefined,{...physical,source:'simulator'},{...physical,station_id:'STATION_002'},
    {...physical,is_online:false},{...physical,sensor_quality:'invalid'},{...physical,current_depth_cm:null},
    {...physical,current_depth_cm:NaN},{...physical,source_trusted:false},{...physical,depth_source_trusted:false},
    {...physical,depth_fresh:false},{...physical,stream:'exercise'}])assert.equal(auto(empty,changed,true),empty);
  assert.equal(auto(empty,physical,false),empty);
});
