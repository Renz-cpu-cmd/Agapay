const assert=require('node:assert/strict');
const {test}=require('node:test');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript');
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
let stations=[];
function load(file){
  const exports={};
  const empty=()=>null;
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src',file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,{exports,require:name=>{
    if(name==='./operational-vocabulary')return load('lib/operational-vocabulary.ts');
    if(name==='@/context/MonitoringContext')return {useMonitoring:()=>({stations,selectedStationId:stations[0]?.id})};
    if(name==='@/context/HybridProjectionContext')return {useHybridProjection:()=>({config:{mode:'live',depthSource:'sensor'},available:false})};
    if(name==='next/link')return {default:empty};
    if(name.startsWith('./')&&file.includes('components/'))return {__esModule:true,default:empty};
    return require(name);
  }});
  return exports;
}
test('ambiguous water rainfall never becomes a panel input; journal zero carries interval source and coverage',()=>{
  const {stationMeasurement}=load('lib/measurements.ts');
  const raw={latest_rainfall_mm:999,rainfall_fresh:true,rainfall_observed_at:'2026-10-22T00:00:10Z',rainfall_age_seconds:0};
  assert.equal(stationMeasurement(raw,'rain').value,null);
  const p={product:'current_hour_received_tips',rainfall_mm:0,tip_count:0,interval_start:'2026-10-22T00:00:00Z',interval_end:'2026-10-22T00:00:10Z',quality:'partial',source:'physical_rain_gauge',coverage:'missing receive coverage',calibration_version:'review-42'};
  const measurement=stationMeasurement({...raw,rainfall_product:p},'rain');
  assert.equal(measurement.value,0);
  for(const detail of [p.interval_start,p.interval_end,p.source,p.coverage,p.calibration_version])assert.ok(measurement.reason.includes(detail));
});
test('ML configuration renders the selected station coefficient and unknown coefficient stays unavailable',()=>{
  const Component=load('components/MLConfiguration.tsx').default;
  stations=[{id:'STATION_OTHER',name:'Other station',channelHealth:{calibration:{rain_configured_mm_per_tip:1.25}}}];
  let html=renderToStaticMarkup(React.createElement(Component));
  assert.ok(html.includes('1.25'));assert.ok(!html.includes('0.70 mm'));
  stations=[{id:'NO_CALIBRATION',name:'No coefficient'}];
  html=renderToStaticMarkup(React.createElement(Component));
  assert.ok(html.includes('—'));assert.ok(!html.includes('0.70 mm'));
});
