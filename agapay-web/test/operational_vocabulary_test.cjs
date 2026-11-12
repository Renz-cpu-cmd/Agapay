const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const load=require('./support/load-source.cjs');
const vocabulary=load(path.resolve('src/lib/operational-vocabulary.ts'));
const {measurementLabel,measurementText}=load(path.resolve('src/lib/measurements.ts'));
const {stationStatusDescription}=load(path.resolve('src/lib/station-map.ts'));
const contract=JSON.parse(fs.readFileSync('../agapay-docs/contracts/operational-presentation-cases.json','utf8'));
test('public vocabulary matches the shared web/mobile review contract',()=>{
  assert.equal(JSON.stringify(vocabulary.operationalVocabulary),JSON.stringify(contract.vocabulary));
});
for(const row of contract.cases)test(`independent presentation: ${row.id}`,()=>{
  const depth={value:row.depth,state:row.current?'current':row.depth===null?'missing':'retained',measuredAt:row.measuredAt,latestSampleQuality:row.quality};
  const station={depth,depthFresh:row.current,status:'EVACUATE',observationTier:'EVACUATE',activeHazardTier:row.episodeTier,hazardState:row.hazardState,connectionStatus:row.connectivity,lastPing:'original age',sourceTrusted:true,depthSourceTrusted:true};
  const description=stationStatusDescription(station);
  assert.equal(measurementLabel(depth),row.label);
  assert.ok(description.includes(`Connectivity: ${row.connectivity}`));
  assert.ok(description.includes(`Latest sample validity: ${row.quality}`));
  assert.ok(description.includes(`Episode tier: ${row.episodeTier??'None recorded'} (${row.hazardState})`));
  assert.ok(description.includes(`Observation tier: ${row.current?'EVACUATE':'UNKNOWN'}`));
  assert.ok(description.includes(`Measured: ${row.measuredAt??'unknown'}`));
  assert.ok(description.includes('Station datum: unconfirmed'));
  assert.equal(measurementText(depth),row.depth===null?'—':row.depth.toFixed(1));
});
test('missing/invalid measurement times can never acquire the Observed label',()=>{
  for(const time of [null,'not-a-time'])assert.equal(vocabulary.readingLabel(0,true,time),'Last known');
});
test('an API failure reports unconfirmed connectivity without claiming a physical device outage',()=>{
  const {monitoringStationForDisplay}=load(path.resolve('src/lib/monitoring.ts'));
  const {displayStation}=load(path.resolve('src/lib/station-display.ts'));
  const at='2026-10-23T00:00:00Z';
  const raw={station_id:'SYNTHETIC',history:[],connection_status:'online',is_online:true,heartbeat_age_seconds:0,
    current_depth_cm:105,depth_age_seconds:0,depth_fresh:true,last_valid_depth_at:at,sensor_quality:'valid',
    source_class:'physical_device',source_trusted:true,depth_source_trusted:true,stream:'operational'};
  const station=displayStation(monitoringStationForDisplay(raw,at,30,Date.parse(at),true));
  assert.equal(station.connectionStatus,'unconfirmed');assert.equal(station.isOnline,false);
  assert.equal(measurementLabel(station.depth),'Last known');assert.equal(raw.is_online,true);
});
