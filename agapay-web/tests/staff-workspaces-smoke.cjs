/* Production UI with synthetic loopback fixtures; never contacts a real service. */
const assert=require('node:assert/strict'),http=require('node:http'),path=require('node:path'),fs=require('node:fs'),{spawn}=require('node:child_process');
const {chromium}=require('playwright'),{default:AxeBuilder}=require('@axe-core/playwright');
let browser,next,queueDown=false,monitoringDown=false,conflict=true,owner={revision:0,owner_id:null,owner_name:null,changed_at:null};
const writes=[],errors=[],scans=[],queries=[],contrast=[];
/* WCAG AA on the RENDERED Flood forecast panel: every text element is measured from its
   computed colour against its effective (first opaque ancestor) background, converted to
   sRGB through a canvas because Tailwind v4 computes oklch(). A probe with the panel's
   amber "SYNTHETIC PREVIEW" classes covers the preview state the fixture does not open. */
async function forecastContrast(page,surface,theme){
 const rows=await page.evaluate(()=>{
  const panel=document.querySelector('section[aria-label="Flood forecast"]');if(!panel)return null;
  const probe=document.createElement('span');probe.className='font-data text-xs text-amber-400';probe.textContent='SYNTHETIC PREVIEW';probe.dataset.probe='preview';panel.appendChild(probe);
  const ctx=document.createElement('canvas').getContext('2d',{willReadFrequently:true});
  const rgba=c=>{ctx.clearRect(0,0,1,1);ctx.fillStyle='#000';ctx.fillStyle=c;ctx.fillRect(0,0,1,1);const d=ctx.getImageData(0,0,1,1).data;return [d[0],d[1],d[2],d[3]/255];};
  const lum=([r,g,b])=>[r,g,b].map(v=>{v/=255;return v<=0.03928?v/12.92:((v+0.055)/1.055)**2.4;}).reduce((a,v,i)=>a+v*[0.2126,0.7152,0.0722][i],0);
  const hex=c=>'#'+c.slice(0,3).map(v=>v.toString(16).padStart(2,'0')).join('');
  const background=el=>{for(let n=el;n;n=n.parentElement){const c=getComputedStyle(n).backgroundColor;const v=rgba(c);if(v[3]>=0.99)return v;}return rgba(getComputedStyle(document.body).backgroundColor);};
  const out=[];
  for(const el of panel.querySelectorAll('*')){
   const text=[...el.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent.trim()).join(' ').trim();
   const style=getComputedStyle(el);if(!text||style.visibility==='hidden'||style.display==='none'||!el.getClientRects().length)continue;
   const fg=rgba(style.color),bg=background(el);const fgMix=fg.slice(0,3).map((v,i)=>Math.round(v*fg[3]+bg[i]*(1-fg[3])));
   const [a,b]=[lum(fgMix),lum(bg)].sort((x,y)=>y-x),ratio=(a+0.05)/(b+0.05);
   const size=parseFloat(style.fontSize),weight=Number(style.fontWeight)||400,large=size>=24||(size>=18.66&&weight>=700);
   out.push({text:text.slice(0,40),probe:el.dataset.probe==='preview',fg:hex(fgMix),bg:hex(bg),ratio:Math.round(ratio*100)/100,required:large?3:4.5});
  }
  probe.remove();return out;
 });
 if(rows)contrast.push({surface,theme,rows});
 return rows;
}
const doc=path.resolve('../agapay-docs/design/staff-decisions');fs.mkdirSync(doc,{recursive:true});
const fixture=http.createServer(async(req,res)=>{
 const url=new URL(req.url,'http://fixture'),now=Date.now(),stamp=new Date(now).toISOString(),old=new Date(now-3600000).toISOString();
 const json=(body,status=200)=>{res.writeHead(status,{'content-type':'application/json'});res.end(JSON.stringify(body));};
 const channel=(state,reason,at=stamp,age=0)=>({state,reason,observed_at:at,age_seconds:age});
 if(url.pathname==='/api/auth/me')return json({id:1,version:1,name:'Synthetic CI Officer',email:'ci@example.invalid',role:req.headers.authorization==='Bearer resident-ci'?'resident':'officer',is_active:true,created_at:stamp,updated_at:stamp});
 if(url.pathname==='/api/sos')return json({items:[],total:0,counts:{ACTIVE:2,ACKNOWLEDGED:0,RESOLVED:0}});
 if(url.pathname==='/api/monitoring/stations'){
  if(monitoringDown)return json({detail:'Synthetic monitoring outage'},503);
  return json({checked_at:stamp,stale_after_seconds:30,stations:[{
   station_id:'SYNTHETIC',station_name:'Synthetic Canal Station',barangay:'Synthetic area',municipality:'Fixture city',latitude:null,longitude:null,
   administrative_status:'active',connection_status:'online',is_online:true,is_stale:true,age_seconds:3600,
   heartbeat_at:stamp,heartbeat_age_seconds:0,heartbeat_fresh:true,latest_sample_at:stamp,latest_sample_age_seconds:0,
   last_valid_depth_at:old,depth_age_seconds:3600,depth_fresh:false,depth_status:'retained',rainfall_observed_at:null,rainfall_age_seconds:null,rainfall_fresh:false,
   hazard_state:'unresolved',active_hazard_tier:'EVACUATE',active_alert_id:71,observation_tier:'EVACUATE',hazard_policy_state:'provisional',hazard_review_required:false,
   alert_tier:'EVACUATE',trend:'unknown',trend_reason:'Latest water sample invalid; no current trend',current_depth_cm:104,latest_depth_cm:null,latest_rainfall_mm:null,
   sensor_quality:'invalid',last_ping:stamp,observed_at:old,firmware_version:'synthetic-build',source:'device',source_class:'physical_device',source_trusted:true,
   depth_source_class:'physical_device',depth_source_trusted:true,depth_source_id:'SYNTHETIC_DEVICE',stream:'operational',
   threshold_advisory_cm:60,threshold_warning_cm:85,threshold_evacuate_cm:100,
   configuration:{status:'mismatch',revision:4,config_hash:'a'.repeat(64),applied_config_hash:'b'.repeat(64),validation_status:'bench_only',local_alert_profile:'depth',sensor_fault:'blind_zone'},
   channel_health:{water_sensor:channel('invalid','Latest sample invalid; retained depth one hour old',old,3600),rain_counter:channel('stale','Independent rain feed expired',old,3600),device_heartbeat:channel('healthy','Device heartbeat received'),broker_ingestion:channel('healthy','Authenticated MQTT observation'),calibration:{state:'documented',reason:'Synthetic records; physical validation pending',reference_datum:'Synthetic datum',rain_configured_mm_per_tip:0.7,physical_validation:'pending'}},
   lifecycle:{state:'active',revision:2,hazard_policy:'Keep unresolved incidents visible',external_sensor_notifications:true,local_alarm_policy:'Independent device alarm'},
   history:[0,10,20,600,610].map((sec,i)=>({sequence_no:i,water_depth_cm:i===2?null:100+i,rainfall_mm:null,sensor_quality:i===2?'invalid':'valid',device_uptime_ms:i*10000,recorded_at:new Date(now-3600000+sec*1000).toISOString(),measured_at:new Date(now-3600000+sec*1000).toISOString(),received_at:stamp}))
  }]});
 }
 if(url.pathname==='/api/alerts/command-queue'){
  queries.push(url.search);
  if(queueDown)return json({detail:'Synthetic incident service outage'},503);
  const scope=url.searchParams.get('scope')||'operational';
  return json({checked_at:stamp,scope,counts:{operational:1,unverified:0},total:scope==='operational'?1:0,has_more:false,items:scope==='operational'?[{id:71,station_id:'SYNTHETIC',station_name:'Synthetic Canal Station',severity:'EVACUATE',triggered_at:old,last_transition_at:old,latest_telemetry_id:91,latest_depth_cm:104,ownership:owner,areas:[{id:'FIXTURE_AREA',name:'Synthetic registered area'}],source:'recorded_physical'}]:[]});
 }
 if(url.pathname==='/api/alerts/71/ownership'){
  let raw='';for await(const chunk of req)raw+=chunk;const body=JSON.parse(raw);writes.push(body);
  if(conflict)return json({detail:'Episode changed. Refresh and manually review.'},409);
  owner={revision:17,owner_id:body.action==='take'?1:null,owner_name:body.action==='take'?'Synthetic CI Officer':null,changed_at:stamp};return json(owner);
 }
 if(url.pathname==='/api/stations/SYNTHETIC/workspace'){
  const sample=(id,measured,quality)=>({id,measured_at:measured,received_at:stamp,quality,disposition:'current',source_id:'SYNTHETIC_DEVICE',registry_version:3,transport:'mqtt',source_class:'physical_device'});
  return json({station_id:'SYNTHETIC',checked_at:stamp,identity:{device_id:'SYNTHETIC_DEVICE',version:3,state:'commissioned',coordinates_verified:false,datum:'Synthetic datum',calibration_note:'Bench fixture only; no physical validation',commissioned_at:old},latest_sample:sample(92,stamp,'invalid'),last_valid:sample(91,old,'valid'),latest_received:sample(92,stamp,'invalid'),events:[{id:8,action:'station_lifecycle_changed',actor:'Synthetic reviewer',reason:'Synthetic maintenance inspection recorded',created_at:old}],total:1,has_more:false});
 }
 if(url.pathname==='/api/stations/SYNTHETIC/hazard-policy')return json({state:'provisional',version:0,evidence:'Prototype defaults; physical review pending',rules:{recovery_samples:3,recovery_seconds:30}});
 if(url.pathname==='/api/stations/SYNTHETIC/operations')return json({state:'active',revision:2,identity_version:3,station_name:'Synthetic Canal Station',ingestion:'retain',hazard_policy:'review',external_sensor_notifications:true,local_alarm_policy:'Independent device alarm'});
 return json({detail:'Synthetic optional feature unavailable'},503);
});
const listen=s=>new Promise(r=>s.listen(0,'127.0.0.1',()=>r(s.address().port))),pause=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{try{
 const apiPort=await listen(fixture),spare=http.createServer(),port=await listen(spare);await new Promise(r=>spare.close(r));const base=`http://127.0.0.1:${port}`;
 next=spawn(process.execPath,[path.resolve('node_modules/next/dist/bin/next'),'start','--hostname','127.0.0.1','--port',String(port)],{env:{...process.env,AGAPAY_API_URL:`http://127.0.0.1:${apiPort}`,NEXT_TELEMETRY_DISABLED:'1'},stdio:'ignore',windowsHide:true});
 let ready=false;for(let i=0;i<60;i++){try{if((await fetch(base+'/login')).ok){ready=true;break;}}catch{}await pause(500);}assert(ready,'production server ready');
 browser=await chromium.launch({headless:true,...(process.env.AGAPAY_BROWSER_CHANNEL?{channel:process.env.AGAPAY_BROWSER_CHANNEL}:{})});
 const context=await browser.newContext({viewport:{width:1440,height:1000}});await context.route(/^https?:\/\/(?!127\.0\.0\.1)/,r=>r.abort());await context.addCookies([{name:'agapay_session',value:'officer-ci',url:base,httpOnly:true}]);
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/dashboard');await page.getByText('Incident ownership, health and audit tools',{exact:true}).click();await page.getByRole('heading',{name:'Prioritized incident queue'}).waitFor();await page.getByText('Synthetic registered area (FIXTURE_AREA)',{exact:true}).waitFor();
 await page.getByText(/2 active SOS/).waitFor();
 assert.equal(await page.getByText('Unassigned',{exact:true}).count(),1);
 await page.getByLabel('Reason for taking review responsibility').fill('Synthetic UI review');await page.getByRole('button',{name:'Take responsibility',exact:true}).click();
 await page.getByText('Episode changed. Refresh and manually review.',{exact:true}).waitFor();
 await pause(5500);assert.equal(writes.length,1,'a stale mutation is never automatically retried');
 assert.equal(await page.getByRole('button',{name:'Take responsibility',exact:true}).count(),0,'conflict remains blocked across automatic polling');
 conflict=false;await page.getByRole('button',{name:'Refresh and review',exact:true}).click();await page.getByLabel('Reason for taking review responsibility').fill('Reviewed current record');await page.getByRole('button',{name:'Take responsibility',exact:true}).click();
 await page.getByText('Responsibility recorded. Refresh and review the saved ownership.',{exact:true}).waitFor();await page.getByRole('button',{name:'Refresh and review',exact:true}).click();await page.getByRole('button',{name:'Release responsibility',exact:true}).waitFor();
 assert.equal(writes.length,2);assert.equal(writes[1].expected_telemetry_id,91);
 await page.getByRole('button',{name:'Unverified / legacy review',exact:true}).click();await page.getByText('No active episodes in this evidence scope. Missing observations and service faults still require review.',{exact:true}).waitFor();assert(queries.some(q=>q.includes('scope=unverified')),'scope forwarded by authenticated proxy');
 await page.getByRole('button',{name:'Recorded physical sources',exact:true}).click();await page.getByRole('button',{name:'Inspect reading',exact:true}).waitFor();
 for(const theme of ['light','dark']){
  await page.evaluate(t=>{localStorage.setItem('agapay-theme',t);document.documentElement.dataset.theme=t;},theme);
  await page.screenshot({path:path.join(doc,`command-${theme}.png`)});
  const a=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();scans.push({surface:'command',theme,violations:a.violations});
  await forecastContrast(page,'command',theme);
 }
 queueDown=true;await page.getByRole('button',{name:'Refresh queue',exact:true}).click();await page.getByText('Incident service unavailable. The current queue cannot be confirmed.',{exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Take responsibility',exact:true}).count(),0);
 queueDown=false;await page.goto(base+'/stations/SYNTHETIC');await page.getByText('Device configuration, maintenance and evidence',{exact:true}).click();await page.getByRole('heading',{name:'Can this reading be trusted?'}).waitFor();await page.getByText('SYNTHETIC_DEVICE · identity version 3 · commissioned',{exact:true}).waitFor();
 assert.match(await page.locator('#main-content').innerText(),/Latest eligible sample measured/);assert.match(await page.locator('#main-content').innerText(),/Last valid depth received/);
 await page.getByText('Timestamped measurement data and gaps',{exact:true}).click();await page.getByText('No observations in gap',{exact:true}).waitFor();
 assert.equal(await page.getByText('Rain counter',{exact:true}).count(),1);assert.match(await page.locator('#main-content').innerText(),/physical validation pending/);
 for(const theme of ['light','dark']){
  await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
  await page.locator('#main-content').evaluate(el=>el.scrollTo(0,0));await page.screenshot({path:path.join(doc,`station-${theme}.png`)});
  const a=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();scans.push({surface:'station',theme,violations:a.violations});
  await forecastContrast(page,'station',theme);
 }
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>document.documentElement.style.fontSize='200%');await page.emulateMedia({reducedMotion:'reduce'});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'no document overflow at narrow 200% text');
 await page.screenshot({path:path.join(doc,'station-narrow.png')});
 fs.writeFileSync(path.join(doc,'accessibility-results.json'),JSON.stringify(scans,null,2));
 fs.writeFileSync(path.join(process.env.AGAPAY_CONTRAST_OUTPUT||doc,'forecast-contrast.json'),JSON.stringify(contrast,null,2));
 assert(contrast.length>=2&&new Set(contrast.map(c=>c.theme)).size===2,'Flood forecast panel measured in light and dark');
 for(const c of contrast){
  const label=t=>c.rows.some(r=>r.text.replace(/\s+/g,'')===t);
  assert(label('ADVISORYONLY')&&label('+30min')&&label('+90min')&&c.rows.some(r=>r.probe),`${c.surface}/${c.theme}: muted labels and preview state measured`);
  const low=c.rows.filter(r=>r.ratio<r.required);
  assert.deepEqual(low,[],`${c.surface}/${c.theme}: rendered forecast text meets WCAG AA contrast`);
 }
 assert.deepEqual(scans.flatMap(s=>s.violations),[],'both-theme automated accessibility checks');assert.deepEqual(errors,[],'no browser runtime errors');
 const resident=await browser.newContext();await resident.addCookies([{name:'agapay_session',value:'resident-ci',url:base,httpOnly:true}]);const denied=await resident.newPage();await denied.goto(base+'/dashboard');await denied.waitForURL('**/login**');
 console.log('PASS: incident evidence scope, ownership conflict/manual review/save, independent channel/times, chart gaps, outage, resident boundary; four both-theme axe scans with zero violations and narrow 200% layout. All data synthetic.');
 }finally{if(browser)await browser.close();if(next){next.kill();await new Promise(r=>{if(next.exitCode!==null)return r();next.once('exit',r);setTimeout(r,5000).unref();});}fixture.closeAllConnections();await new Promise(r=>fixture.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
