const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const channels = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lib/channel-health.ts'), 'utf8'), {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports:channels});
const exportsObject = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lib/monitoring.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText, { exports: exportsObject, require: () => channels });
const { monitoringSourceIsFresh: fresh,monitoringStationForDisplay: display } = exportsObject;
const now = Date.parse('2026-10-12T00:00:00Z');
const snapshot = (overrides = {}) => ({
  checked_at: new Date(now).toISOString(), stale_after_seconds: 30,
  stations: [{ source: 'device', source_class:'physical_device',source_trusted:true,depth_source_trusted:true,stream:'operational',
    is_online:true,heartbeat_fresh:true,heartbeat_age_seconds:10,depth_age_seconds:10,depth_fresh:true,
    depth_status:'fresh',sensor_quality:'valid',current_depth_cm:95,age_seconds:10,...overrides }],
});

test('recent physical telemetry is live, with the backend stale boundary respected', () => {
  assert.equal(fresh(snapshot(), 'device', now), true);
  assert.equal(fresh(snapshot(), 'device', now + 20000), true);
  assert.equal(fresh(snapshot(), 'device', now + 21000), false);
});
test('an API failure cannot keep retained telemetry labeled live', () => {
  assert.equal(fresh(snapshot(), 'device', now, true), false);
});
test('offline and missing-data stations cannot be live', () => {
  assert.equal(fresh(snapshot({ is_online: false }), 'device', now), false);
  assert.equal(fresh(snapshot({ depth_age_seconds: null }), 'device', now), false);
  assert.equal(fresh(null, 'device', now), false);
});
test('simulator origin is distinct from physical telemetry', () => {
  assert.equal(fresh(snapshot({ source: 'simulator' }), 'device', now), false);
  assert.equal(fresh(snapshot({ source: 'simulator' }), 'simulator', now), true);
});
test('malformed timestamps never establish freshness', () => {
  assert.equal(fresh({ ...snapshot(), checked_at: 'invalid' }, 'device', now), false);
});

test('a new snapshot arriving between display clock ticks remains fresh on every surface', () => {
  const next={...snapshot({age_seconds:0}),checked_at:new Date(now+500).toISOString()};
  assert.equal(fresh(next,'device',now),true);
  assert.equal(display(next.stations[0],next.checked_at,30,now).is_online,true);
});

test('station cards expire with the header while keeping the last real reading and tier', () => {
  const original={...snapshot().stations[0],connection_status:'online',current_depth_cm:95,alert_tier:'WARNING'};
  const view=display(original,new Date(now).toISOString(),30,now+21000);
  assert.equal(view.is_online,false);assert.equal(view.connection_status,'offline');
  assert.equal(view.age_seconds,31);assert.equal(view.is_stale,true);
  assert.equal(view.current_depth_cm,95);assert.equal(view.alert_tier,'WARNING');
  assert.equal(original.is_online,true); // never mutate the server snapshot
});
test('unavailable, malformed and administratively inactive sources stay unavailable', () => {
  const original={...snapshot().stations[0],connection_status:'online'};
  assert.equal(display(original,new Date(now).toISOString(),30,now,true).is_online,false);
  assert.equal(display(original,'invalid',30,now).is_online,false);
  const maintenance=display({...original,is_online:false,connection_status:'maintenance'},new Date(now).toISOString(),30,now);
  assert.equal(maintenance.connection_status,'maintenance');assert.equal(maintenance.is_online,false);
});

test('invalid online heartbeat preserves the true age and timestamp of a retained hazard',()=>{
  const validAt='2026-10-11T23:00:00Z';
  const original={...snapshot().stations[0],connection_status:'online',heartbeat_age_seconds:0,
    depth_age_seconds:3600,depth_fresh:false,depth_status:'stale',sensor_quality:'invalid',
    current_depth_cm:105,last_valid_depth_at:validAt,observed_at:validAt,hazard_state:'unresolved',active_alert_id:12};
  const view=display(original,new Date(now).toISOString(),30,now+10000);
  assert.equal(view.is_online,true);assert.equal(view.heartbeat_age_seconds,10);
  assert.equal(view.depth_age_seconds,3610);assert.equal(view.age_seconds,3610);
  assert.equal(view.observed_at,validAt);assert.equal(view.last_valid_depth_at,validAt);
  assert.equal(view.depth_fresh,false);assert.equal(view.hazard_state,'unresolved');
  assert.equal(fresh({...snapshot(),stations:[original]},'device',now),false);
});

test('an asserted device string without registry trust cannot become physical LIVE',()=>{
  for(const changes of [{source_trusted:false},{source_class:'unverified'},{depth_source_trusted:false}])
    assert.equal(fresh(snapshot(changes),'device',now),false);
});
