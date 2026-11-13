const assert=require('node:assert/strict');
const {test}=require('node:test');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ts=require('typescript');
const exportsObject=require('./support/load-source.cjs')(path.join(__dirname,'../src/lib/station-map.ts'));
test('online invalid or stale depth is unknown on maps; connectivity remains separate',()=>{
  const station={isOnline:true,depthFresh:false,status:'EVACUATE'};
  assert.equal(exportsObject.stationMarkerTier(station),'UNKNOWN');
  assert.equal(station.status,'EVACUATE'); // Preserve the historical hazard for details.
  assert.equal(exportsObject.stationMarkerTier({...station,depthFresh:true}),'EVACUATE');
  assert.equal(exportsObject.stationMarkerTier({...station,isOnline:false}),'OFFLINE');
});
