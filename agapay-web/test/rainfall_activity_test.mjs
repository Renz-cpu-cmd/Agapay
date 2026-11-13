import assert from 'node:assert/strict';
import {test} from 'node:test';
import {selectRainActivity} from '../src/lib/rainfall-activity.ts';

const now=Date.parse('2026-10-13T12:10:00Z');
const source='physical_rain_gauge';
const snapshot=()=>({station_id:'STATION_001',data_source:source,connected:true,status:'fresh',
  checked_at:new Date(now).toISOString(),last_received_at:new Date(now).toISOString(),
  current_hour_start:'2026-10-13T12:00:00Z',incomplete_hour_mm:.7,
  completed_hours:[{timestamp_utc:'2026-10-13T12:00:00Z',rainfall_mm:null,valid:false,interval_seconds:3600}]});

test('missing hours remain unknown while a new tip appears as an ongoing hour',()=>{
  const first=selectRainActivity(snapshot(),'STATION_001',source,now,false);
  assert.equal(first.fresh,true);assert.equal(first.current,.7);
  assert.equal(first.chart[0].amount,null);assert.equal(first.chart[1].amount,.7);
  assert.equal(first.chart[1].partial,true);
});
test('stale, wrong-station and simulated feeds cannot claim fresh physical rainfall',()=>{
  for(const [snap,stamp] of [[snapshot(),now+31000],[{...snapshot(),station_id:'OTHER'},now],
    [{...snapshot(),data_source:'simulated_rain_gauge'},now],[{...snapshot(),last_received_at:new Date(now+1000).toISOString()},now]]){
    const result=selectRainActivity(snap,'STATION_001',source,stamp,false);
    assert.equal(result.fresh,false);assert.equal(result.current,null);
  }
});
test('hour rollover clears the previous incomplete-hour amount until a new snapshot arrives',()=>{
  const stamp=Date.parse('2026-10-13T12:59:59Z');
  const result=selectRainActivity({...snapshot(),last_received_at:new Date(stamp).toISOString()},'STATION_001',source,stamp+2000,false);
  assert.equal(result.fresh,true);assert.equal(result.current,null);
});
test('archived input can draw a demonstration chart but never supplies a current gauge total',()=>{
  const archive=[{timestamp_utc:'2025-07-01T12:00:00Z',rainfall_mm:2.4,valid:true,interval_seconds:3600}];
  const result=selectRainActivity(null,'STATION_001',source,now,true,archive);
  assert.equal(result.chartSource,'archive');assert.equal(result.chart[0].amount,2.4);
  assert.equal(result.current,null);assert.equal(result.received,null);assert.equal(result.fresh,false);
});
