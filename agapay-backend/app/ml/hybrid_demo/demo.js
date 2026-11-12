/* Shared, testable offline inference and volume-balance implementation. */
const HybridDemo = (() => {
  const parameterKeys = ['contributing_area_m2','basin_surface_area_m2','runoff_coefficient','outflow_m3_per_hour','maximum_depth_cm'];
  const defaults = [2,0.1,0.8,0,100];
  const labels = ['Contributing collection area (m²)','Basin surface area (m²)','Runoff coefficient (0–1)','Outflow rate (m³/hour)','Maximum basin depth (cm)'];
  function featureVector(history, asOf) {
    if(history.length!==24 || history.some(v=>!Number.isFinite(v)||v<0)) throw Error('Supply exactly 24 finite nonnegative hourly rainfall amounts.');
    const x = [...history].reverse();
    for(const h of [3,6,12,24]) x.push(history.slice(-h).reduce((a,b)=>a+b,0));
    const d = new Date(asOf);
    for(const [value,period] of [[d.getUTCHours(),24],[(d.getUTCDay()+6)%7,7],[d.getUTCMonth(),12]]) x.push(Math.sin(2*Math.PI*value/period),Math.cos(2*Math.PI*value/period));
    return x.map(Math.fround); // sklearn tree inference compares float32 inputs
  }
  function predict(forest, features) {
    const result = [0,0,0];
    for(const t of forest.trees){let n=0;while(t.left[n]!==-1)n=features[t.feature[n]]<=t.threshold[n]?t.left[n]:t.right[n];for(let h=0;h<3;h++)result[h]+=t.value[n][h]/forest.trees.length;}
    return result;
  }
  function validateBasin(b) {
    if(parameterKeys.some(k=>!Number.isFinite(b[k]))||b.contributing_area_m2<0||b.basin_surface_area_m2<=0||b.runoff_coefficient<0||b.runoff_coefficient>1||b.outflow_m3_per_hour<0||b.maximum_depth_cm<=0)throw Error('Invalid controlled-basin parameters. Areas/capacity must be positive, runoff 0–1, outflow nonnegative.');
    if(parameterKeys.some(k=>!['measured','estimated','assumed'].includes(b.parameter_basis?.[k])))throw Error('Every basin parameter needs a measured, estimated or assumed basis.');
  }
  function balance(depth,rain,minutes,b){
    validateBasin(b);
    if(![depth,rain,minutes].every(Number.isFinite)||depth<0||depth>b.maximum_depth_cm||rain<0||minutes<=0)throw Error('Starting depth must fit the basin, rainfall must be nonnegative, and interval positive.');
    const inflow=rain/1000*b.contributing_area_m2*b.runoff_coefficient,stored=depth/100*b.basin_surface_area_m2;
    const requested=b.outflow_m3_per_hour*minutes/60,outflow=Math.min(requested,stored+inflow),capacity=b.maximum_depth_cm/100*b.basin_surface_area_m2,remaining=stored+inflow-outflow;
    return {depth_cm:Math.min(b.maximum_depth_cm,Math.max(0,Math.min(capacity,remaining)/b.basin_surface_area_m2*100)),inflow_m3:inflow,outflow_m3:outflow,overflow_m3:Math.max(0,remaining-capacity),unmet_outflow_m3:requested-outflow};
  }
  function project(initial,rain,b,offset=0){
    if(rain.length<3||rain.some(v=>!Number.isFinite(v)||v<0)||!Number.isFinite(offset)||offset<0||offset>=60)throw Error('Three valid hourly rainfall predictions and a recent hourly origin are required.');
    balance(initial,0,1,b);let depth=initial;const points=[];
    for(const horizon of [30,60,90]){let cursor=offset+horizon-30,stop=offset+horizon;const totals={horizon_minutes:horizon,rainfall_mm:0,inflow_m3:0,outflow_m3:0,overflow_m3:0,unmet_outflow_m3:0};
      while(cursor<stop-1e-9){const hour=Math.floor(cursor/60),minutes=Math.min(stop-cursor,60-cursor%60),amount=rain[hour]*minutes/60,s=balance(depth,amount,minutes,b);depth=s.depth_cm;totals.rainfall_mm+=amount;for(const k of ['inflow_m3','outflow_m3','overflow_m3','unmet_outflow_m3'])totals[k]+=s[k];cursor+=minutes;}
      points.push({...totals,depth_cm:depth});}
    return points;
  }
  function validateSensor(station,nowMs,stale=30){
    const age=(nowMs-Date.parse(station?.observed_at))/1000;
    if(station?.source!=='device'||station.sensor_quality!=='valid'||station.is_stale||!station.is_online||!Number.isFinite(station.current_depth_cm)||station.current_depth_cm<0||!Number.isFinite(age)||age<0||age>stale)throw Error('No fresh, valid ESP32 depth. Refresh the device or use an explicitly manual depth.');
    return station.current_depth_cm;
  }
  function selectRain(data,mode,index,history,asOf){
    if(mode==='historical_replay')return data.rainfall_mm.slice(index+1,index+4);
    if(mode==='ml_backtest')return predict(data.forest,featureVector(data.rainfall_mm.slice(index-23,index+1),asOf));
    if(mode==='ml_current')return predict(data.forest,featureVector(history,asOf));
    throw Error('Unknown rainfall mode.');
  }
  function mount(data){
    const $=id=>document.getElementById(id), base=Date.parse(data.start_utc), hourly=3600000;
    let latestSensor=null,lastRun=null;
    const dateValue=ms=>new Date(ms).toISOString().slice(0,16);
    const stamp=ms=>new Date(ms).toISOString();
    $('asof').value='2025-07-01T12:00';$('asof').min='2025-01-01T00:00';$('asof').max=dateValue(base+(data.rainfall_mm.length-4)*hourly);
    $('current-origin').value=dateValue(Math.floor(Date.now()/hourly)*hourly);
    parameterKeys.forEach((key,i)=>{const label=document.createElement('label');label.htmlFor=key;label.textContent=labels[i];$('parameters').append(label);const row=document.createElement('div');row.className='row';const input=document.createElement('input');input.id=key;input.type='number';input.value=defaults[i];input.step='any';row.append(input);const basis=document.createElement('select');basis.id=key+'-basis';basis.className='basis';basis.setAttribute('aria-label',labels[i]+' provenance');for(const text of ['assumed','estimated','measured']){const option=document.createElement('option');option.value=text;option.textContent=text;basis.append(option);}row.append(basis);$('parameters').append(row);});
    const e=data.evaluation.test;
    for(const [name,label] of [['random_forest','Random forest'],['persistence','Persistence'],['zero_rainfall','Zero rainfall']]){const tr=document.createElement('tr');for(const v of [label,e[name].overall.mae_mm.toFixed(3),e[name].overall.rmse_mm.toFixed(3),e[name].wet_only.mae_mm.toFixed(3),e[name].wet_only.rmse_mm.toFixed(3)]){const td=document.createElement('td');td.textContent=v;tr.append(td);}$('metrics').append(tr);}
    $('hour-metrics').textContent=JSON.stringify(Object.fromEntries(Object.entries(e).map(([k,v])=>[k,v.by_horizon])),null,2);
    $('evaluation-note').textContent=`${data.metadata.splits.test.count.toLocaleString()} held-out origins; ${e.random_forest.overall.count.toLocaleString()} horizon labels. Persistence has lower +1h MAE (${e.persistence.by_horizon['1h'].overall.mae_mm.toFixed(3)}) than ML (${e.random_forest.by_horizon['1h'].overall.mae_mm.toFixed(3)}); pooled ML improves MAE/RMSE over both baselines. No water-depth validation performed.`;
    $('provenance').textContent=`Open-Meteo / ERA5 · ${data.metadata.location_id} (provisional point). Trained ${data.metadata.trained_at_utc}. Version ${data.metadata.version}. Source SHA-256 ${data.metadata.dataset.sha256}. Train: 2020–2023; selection: 2024; held-out test: 2025; +3h labels purged at split boundaries.`;
    function mode(){return $('mode').value==='historical_replay'?'historical_replay':$('input-source').value==='archive'?'ml_backtest':'ml_current';}
    function clear(){lastRun=null;for(const id of ['initial-value','p30','p60','p90'])$(id).textContent='—';for(const id of ['water-chart','history-chart','rain-chart'])$(id).replaceChildren();$('details').textContent='';$('projection-status').textContent='Generate a new projection for these inputs.';$('initial-label').textContent=$('initial-source').value==='sensor'?'Measured ESP32 depth':'Manual configured depth';$('initial-time').textContent=$('initial-source').value==='sensor'?'Awaiting a fresh device observation':'Configured starting condition';$('history-label').textContent=mode()==='ml_current'?'User-supplied hourly rainfall':'Archived ERA5 past inputs';$('future-title').textContent=mode()==='historical_replay'?'Replay rainfall':'ML forecast rainfall';$('future-label').textContent=mode()==='historical_replay'?'Archived future · simulation only':'Predicted · saved random forest';}
    function controls(){const m=mode();$('ml-input').hidden=$('mode').value!=='ml';$('archived').hidden=m==='ml_current';$('current').hidden=m!=='ml_current';$('sensor').hidden=$('initial-source').value!=='sensor';$('manual').hidden=$('initial-source').value!=='manual';$('mode-description').textContent=m==='historical_replay'?'Historical simulation: archived future rainfall drives a modeled basin. Starting depth is configured, not an archived water observation.':m==='ml_backtest'?'Historical ML backtest: only past archived rainfall enters the model. Future rainfall is predicted. This is not live 2026 rainfall.':'Current experimental projection: provide real recent hourly rainfall; archived rainfall cannot be used as a live substitute. Source transfer and basin response are unvalidated.';clear();}
    for(const id of ['mode','input-source','initial-source'])$(id).addEventListener('change',controls);
    $('station').addEventListener('input',()=>{latestSensor=null;$('sensor-status').textContent='Station changed; read a fresh matching device observation.';});
    document.querySelectorAll('input,textarea,select').forEach(el=>el.addEventListener('input',clear));
    $('wet').onclick=()=>{let best=24,score=-1;for(let i=24;i<data.rainfall_mm.length-4;i++){const value=data.rainfall_mm[i+1]+data.rainfall_mm[i+2]/2;if(value>score){score=value;best=i;}}$('asof').value=dateValue(base+best*hourly);clear();$('mode-description').textContent+=' Wet example chosen retrospectively for illustration, not predictive event selection.';};
    $('theme').onclick=()=>{document.body.classList.toggle('dark');$('theme').textContent=document.body.classList.contains('dark')?'Light mode':'Dark mode';};
    try{if(parent!==window&&parent.document.documentElement.dataset.theme==='dark')$('theme').click();}catch{}
    const ns='http://www.w3.org/2000/svg';
    function draw(id,values,labels,unit,bars=false,firstObserved=false){const svg=$(id);svg.replaceChildren();svg.setAttribute('viewBox','0 0 600 220');const max=Math.max(1,...values)*1.15,x=i=>50+i*(520/Math.max(1,values.length-1)),y=v=>180-v/max*145;function elem(tag,attrs,text){const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text)n.textContent=text;svg.append(n);return n;}
      for(let t=0;t<=3;t++){const v=max*t/3;elem('line',{x1:50,y1:y(v),x2:575,y2:y(v),stroke:'var(--line)'});elem('text',{x:44,y:y(v)+4,'text-anchor':'end',fill:'var(--muted)','font-size':11},v.toFixed(1));}
      elem('text',{x:50,y:18,fill:'var(--muted)','font-size':11},unit);
      if(bars){values.forEach((v,i)=>{const width=500/values.length,px=50+i*width;elem('rect',{x:px+2,y:y(v),width:Math.max(2,width-5),height:180-y(v),fill:'var(--blue)',rx:2});const n=elem('title',{},`${labels[i]}: ${v.toFixed(3)} ${unit}`);svg.lastChild.previousSibling.append(n);});}
      else{elem('polyline',{points:values.map((v,i)=>`${x(i)},${y(v)}`).join(' '),fill:'none',stroke:'var(--blue)','stroke-width':3,'stroke-dasharray':'7 5'});values.forEach((v,i)=>elem('circle',{cx:x(i),cy:y(v),r:5,fill:i===0&&firstObserved?'var(--green)':'var(--blue)'}));}
      const chosen=bars?[0,Math.floor((values.length-1)/2),values.length-1]:values.map((_,i)=>i);for(const i of [...new Set(chosen)])elem('text',{x:bars?50+(i+.5)*500/values.length:x(i),y:204,'text-anchor':'middle',fill:'var(--muted)','font-size':11},labels[i]);
    }
    $('read-sensor').onclick=async()=>{try{if(mode()!=='ml_current')throw Error('Fresh ESP32 initialization requires current supplied rainfall mode.');if(!$('basin-confirmed').checked)throw Error('Confirm this device measures the controlled demonstration basin.');const response=await fetch('/api/account/monitoring/stations?history_limit=60',{cache:'no-store',signal:AbortSignal.timeout(10000)});if(!response.ok)throw Error('Authenticated monitoring unavailable. Sign in to AGAPAY or use manual depth.');const snapshot=await response.json();const station=snapshot.stations.find(s=>s.station_id===$('station').value.trim());const depth=validateSensor(station,Date.now(),snapshot.stale_after_seconds);latestSensor={...station,stale_after_seconds:snapshot.stale_after_seconds};$('sensor-status').textContent=`Measured ${depth.toFixed(2)} cm at ${station.observed_at}; valid device source. Refresh before generating if stale.`;clear();}catch(e){latestSensor=null;$('sensor-status').textContent=e.message;clear();}};
    $('run').onclick=()=>{try{$('error').textContent='';const m=mode(),current=m==='ml_current',origin=Date.parse((current?$('current-origin'):$('asof')).value+'Z'),index=(origin-base)/hourly,now=Date.now();if(!Number.isFinite(origin)||new Date(origin).getUTCMinutes()!==0)throw Error('Choose a valid UTC hourly origin.');if(!current&&(!Number.isInteger(index)||index<24||index+3>=data.rainfall_mm.length))throw Error('Archived origin needs 24 previous hours and three future hours.');let history=current?$('current-rain').value.trim().split(/[\s,;]+/).filter(Boolean).map(Number):data.rainfall_mm.slice(index-23,index+1);if(current&&!(now>=origin&&now-origin<hourly))throw Error('Current rainfall must end at the latest completed UTC hour; stale/future origins are rejected.');featureVector(history,origin);let initial=Number($('initial').value),initialSource='manual configured depth';if($('initial-source').value==='sensor'){if(!current||!$('basin-confirmed').checked)throw Error('ESP32 initialization is available only for the confirmed controlled basin and current rainfall mode.');initial=validateSensor(latestSensor,now,latestSensor?.stale_after_seconds);initialSource='measured ESP32';}else if(!$('initial').value.trim())throw Error('Enter a manual starting depth.');
      const basin={parameter_basis:{}};for(const k of parameterKeys){if(!$(k).value.trim())throw Error('Enter all physical parameters.');basin[k]=Number($(k).value);basin.parameter_basis[k]=$(k+'-basis').value;}const rain=selectRain(data,m,index,history,origin),at=current?now:origin,points=project(initial,rain,basin,current?(now-origin)/60000:0);points.forEach(p=>p.target_at=stamp(at+p.horizon_minutes*60000));
      lastRun={notice:'EXPERIMENTAL — NOT VALIDATED FOR REAL-WORLD FLOOD WARNING',advisory_only:true,mode:m,created_at_utc:stamp(now),projection_origin_utc:stamp(at),rainfall_origin_utc:stamp(origin),initial_depth_cm:initial,initial_source:initialSource,initial_observed_at:initialSource==='measured ESP32'?latestSensor.observed_at:null,model_version:data.metadata.version,dataset_sha256:data.metadata.dataset.sha256,parameters:basin,hourly_rainfall_mm:rain,past_hourly_rainfall_mm:history,points,assumption:'Uniform distribution within each forecast hour; controlled basin only; manual depth is not an observation'};
      $('initial-label').textContent=initialSource==='measured ESP32'?'Measured ESP32 depth':'Manual configured depth';$('initial-value').textContent=initial.toFixed(2)+' cm';$('initial-time').textContent=lastRun.initial_observed_at||'Configured starting condition';for(const p of points)$('p'+p.horizon_minutes).textContent=p.depth_cm.toFixed(2)+' cm';
      draw('water-chart',[initial,...points.map(p=>p.depth_cm)],['Initial','+30 min','+60 min','+90 min'],'cm',false,true);draw('history-chart',history,history.map((_,i)=>new Date(origin-(23-i)*hourly).toISOString().slice(11,16)),'mm / hour',true);draw('rain-chart',rain,['+1 hour','+2 hours','+3 hours'],'mm / hour',true);$('history-label').textContent=current?'User-supplied hourly rainfall':'Archived ERA5 past inputs';$('future-title').textContent=m==='historical_replay'?'Replay rainfall':'ML forecast rainfall';$('future-label').textContent=m==='historical_replay'?'Archived future · simulation only':'Predicted · saved random forest';const overflow=points.reduce((s,p)=>s+p.overflow_m3,0),unmet=points.reduce((s,p)=>s+p.unmet_outflow_m3,0);$('projection-status').textContent=`${current?'Current experimental projection':m==='ml_backtest'?'Historical ML backtest':'Historical simulation'} · Origin ${stamp(at)} · Generated ${stamp(now)} · Overflow ${(overflow*1000).toFixed(3)} L; unmet outflow ${(unmet*1000).toFixed(3)} L. Only the starting point can be measured; all subsequent depths are modeled.`;$('details').textContent=JSON.stringify(lastRun,null,2);
    }catch(e){clear();$('error').textContent=e.message;}};
    $('download').onclick=()=>{if(!lastRun){$('error').textContent='Generate a valid run first.';return;}const blob=new Blob([JSON.stringify(lastRun,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='agapay-experimental-projection.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
    controls();$('run').click();
  }
  return {featureVector,predict,balance,project,validateSensor,selectRain,mount};
})();
if(typeof module!=='undefined')module.exports=HybridDemo;
