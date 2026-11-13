const assert=require('node:assert/strict');
const {test}=require('node:test');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript');
const React=require('react');const {renderToStaticMarkup}=require('react-dom/server');
let monitoring;
function load(file){
  const result={};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src',file),'utf8'),{
    compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX},
  }).outputText,{exports:result,require:name=>name==='./operational-vocabulary'?load('lib/operational-vocabulary.ts'):name==='./OperationsDetails'?{default:()=>null}:name==='@/hooks/useEvidenceClock'?{useEvidenceClock:()=>Date.now()}:name==='./DeliveryConsole'?{default:()=>null}:name==='@/context/MonitoringContext'?{useMonitoring:()=>monitoring}:name.startsWith('@/lib/')?load(name.slice(2)+'.ts'):require(name)});
  return result;
}
const {ageChannels}=load('lib/channel-health.ts');
const {historySeries,reportCsv,localInputToUtc}=load('lib/history-report.ts');
const at='2026-10-21T00:00:00Z';
const health=()=>({device_heartbeat:{state:'healthy',reason:'Device message received',observed_at:at,age_seconds:0},
  water_sensor:{state:'healthy',reason:'Water sample valid',observed_at:at,age_seconds:0,value:50,unit:'cm'},
  rain_counter:{state:'healthy',reason:'Independent counter zero',observed_at:at,age_seconds:0,value:0,unit:'tips'},
  broker_ingestion:{state:'no_data',reason:'No MQTT evidence from HTTP data',observed_at:null,age_seconds:null},
  calibration:{state:'documented',reason:'Documentation is not physical calibration',physical_validation:'pending'}});
test('rain expires independently while a new water heartbeat stays healthy; API failures cannot preserve current health',()=>{
  const channels=health();channels.rain_counter.age_seconds=50;
  const display=ageChannels(channels,0,30,false);
  assert.equal(display.device_heartbeat.state,'healthy');assert.equal(display.water_sensor.state,'healthy');
  assert.equal(display.rain_counter.state,'stale');assert.equal(display.rain_counter.value,0);
  assert.equal(ageChannels(channels,0,30,true).device_heartbeat.state,'unknown');
});
test('system health preserves maintenance separately from unexpected outages and shows independent zero rain',()=>{
  const measure={value:50,measuredAt:at,ageSeconds:0,state:'current',quality:'valid',latestSampleQuality:'valid',reason:'Fresh valid depth'};
  monitoring={stations:[{id:'SYNTHETIC',name:'Synthetic station',administrativeStatus:'maintenance',channelHealth:health(),depth:measure}],refresh(){},loading:false};
  monitoring.stations[0].channelHealth.device_heartbeat.state='stale';
  const html=renderToStaticMarkup(React.createElement(load('components/SystemHealth.tsx').default));
  assert.match(html,/Unexpected heartbeat outages<\/h2><strong[^>]*>0/);
  assert.match(html,/Maintenance<\/h2><strong[^>]*>1/);
  assert.ok(html.includes('0 tips'));assert.ok(html.includes('Independent counter zero'));
  assert.ok(html.includes('No MQTT evidence from HTTP data'));
});
const bucket=(time,value)=>({bucket_start:time,bucket_end:new Date(Date.parse(time)+60000).toISOString(),mean_depth_cm:value,minimum_depth_cm:value,maximum_depth_cm:value,
  sample_count:value===null?0:1,valid_count:value===null?0:1,invalid_count:0,review_count:0,unverified_count:0,
  first_measured_at:value===null?null:time,last_measured_at:value===null?null:time,quality:value===null?'missing':'valid',sources:{physical_device:1},source_details:{'physical_device|mqtt|SYNTHETIC|registry-v1':1}});
const report={checked_at:at,scope:{start_at:at,end_at:'2026-10-21T00:03:00Z',start_local:'2026-10-21T08:00:00+08:00',end_local:'2026-10-21T08:03:00+08:00',timezone:'Asia/Manila',station_ids:['A','B'],event_id:42,bucket_seconds:60,aggregation:'mean, no interpolation',coverage_basis:'buckets containing qualifying samples'},
  stations:[{station_id:'A',station_name:'Station A',unit:'cm',minimum_depth_cm:0,maximum_depth_cm:0,mean_depth_cm:0,valid_count:1,sample_count:1,covered_buckets:1,expected_buckets:3,sources:{physical_device:1},source_details:{},buckets:[bucket(at,0),bucket('2026-10-21T00:02:00Z',null)]},
  {station_id:'B',station_name:'Station B',unit:'cm',minimum_depth_cm:8,maximum_depth_cm:8,mean_depth_cm:8,valid_count:1,sample_count:1,covered_buckets:1,expected_buckets:3,sources:{physical_device:1},source_details:{},buckets:[bucket('2026-10-21T00:01:00Z',8)]}]};
test('history series uses measurement bucket timestamps rather than source row positions and preserves holes',()=>{
  const series=historySeries(report);
  assert.equal(series.length,3);assert.equal(series[0].A,0);assert.equal(series[0].B,undefined);
  assert.equal(series[1].B,8);assert.equal(series[1].A,undefined);assert.equal(series[2].A,null);
});
test('CSV exports only the loaded range, event, units, quality, source identity and coverage; zero is not a gap',()=>{
  const csv=reportCsv(report);
  for(const text of ['"event_id","42"','"timezone","Asia/Manila"','"Station A","cm","0","0","0"','"missing"','"—"','"physical_device|mqtt|SYNTHETIC|registry-v1"','"covered_buckets"'])assert.ok(csv.includes(text),text);
  assert.ok(!csv.includes('24-hour'));assert.equal(localInputToUtc('2026-10-21T08:00','Asia/Manila'),at.replace('Z','.000Z'));
  assert.equal(localInputToUtc('2026-10-21T08:00','UTC'),'2026-10-21T08:00:00.000Z');
  const unsafe={...report,stations:[{...report.stations[0],station_name:'=1+1',minimum_depth_cm:-2}]};
  const safeCsv=reportCsv(unsafe);
  assert.ok(safeCsv.includes('"\'=1+1","cm","-2"'));
});
