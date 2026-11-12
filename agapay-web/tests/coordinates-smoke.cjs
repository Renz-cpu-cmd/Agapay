/* R1 coordinate integrity on the actual production build. Loopback-only synthetic data;
   external requests (including Google Maps) are blocked. Evidence goes to a temp folder
   (override with AGAPAY_SMOKE_OUTPUT), never into the repository. */
const assert=require('node:assert/strict'),http=require('node:http'),path=require('node:path'),fs=require('node:fs'),os=require('node:os'),{spawn}=require('node:child_process');
const {chromium}=require('playwright'),{default:AxeBuilder}=require('@axe-core/playwright');
const output=process.env.AGAPAY_SMOKE_OUTPUT||path.join(os.tmpdir(),'agapay-coordinates-smoke');fs.mkdirSync(output,{recursive:true});
let next,browser;const errors=[],results=[];
const STATIONS=[
  {id:'REG_VERIFIED',lat:15.97,lon:120.57,status:'verified',barangay:'Synthetic verified area',depth:40},
  {id:'REG_UNVERIFIED',lat:0,lon:120.55,status:'unverified',barangay:'Synthetic unverified area',depth:70},
  {id:'NO_LOCATION',lat:null,lon:null,status:'missing',barangay:null,depth:105,episode:'EVACUATE'},
  {id:'BAD_LOCATION',lat:null,lon:null,status:'invalid',barangay:null,depth:20},
  // The id that used to receive the bundled demo point and place names.
  {id:'STATION_001',lat:null,lon:null,status:'missing',barangay:null,depth:10},
];
const fixture=http.createServer((req,res)=>{
  const url=new URL(req.url,'http://fixture'),stamp=new Date().toISOString();
  const json=(body,status=200)=>{res.writeHead(status,{'content-type':'application/json'});res.end(JSON.stringify(body));};
  if(url.pathname==='/api/auth/me')return json({id:1,version:1,name:'Synthetic Reviewer',email:'review@example.invalid',role:'officer',is_active:true,created_at:stamp,updated_at:stamp});
  if(url.pathname==='/api/monitoring/stations')return json({checked_at:stamp,stale_after_seconds:30,stations:STATIONS.map(s=>({
    station_id:s.id,station_name:`${s.id} station`,barangay:s.barangay,municipality:s.barangay?'Fixture city':null,
    latitude:s.lat,longitude:s.lon,coordinate_status:s.status,connection_status:'online',is_online:true,administrative_status:'active',
    is_stale:false,heartbeat_at:stamp,heartbeat_age_seconds:0,heartbeat_fresh:true,latest_sample_at:stamp,latest_sample_age_seconds:0,
    last_valid_depth_at:stamp,depth_age_seconds:0,depth_fresh:true,depth_status:'fresh',hazard_state:s.episode?'observed':'none',
    active_hazard_tier:s.episode??null,observation_tier:s.depth>=100?'EVACUATE':s.depth>=60?'ADVISORY':'NORMAL',alert_tier:s.episode??'NORMAL',
    current_depth_cm:s.depth,latest_depth_cm:s.depth,sensor_quality:'valid',source:'device',source_class:'physical_device',source_trusted:true,
    depth_source_trusted:true,stream:'operational',rainfall_observed_at:null,rainfall_age_seconds:null,rainfall_fresh:false,latest_rainfall_mm:null,
    history:[{recorded_at:stamp,measured_at:stamp,received_at:stamp,water_depth_cm:s.depth,sensor_quality:'valid'}],trend:'unknown',
    threshold_advisory_cm:60,threshold_warning_cm:85,threshold_evacuate_cm:100,
  }))});
  if(url.pathname==='/api/sos')return json({items:[],total:0,counts:{ACTIVE:0,ACKNOWLEDGED:0,RESOLVED:0}});
  if(url.pathname==='/api/alerts/command-queue')return json({checked_at:stamp,scope:'operational',counts:{operational:0,unverified:0},items:[],total:0,has_more:false});
  if(url.pathname.startsWith('/api/alerts'))return json({items:[],total:0});
  return json({detail:'Synthetic optional dependency unavailable'},503);
});
const listen=s=>new Promise(r=>s.listen(0,'127.0.0.1',()=>r(s.address().port))),pause=ms=>new Promise(r=>setTimeout(r,ms));
const DEMO=/15\.98165|120\.560573|San Vicente West|Urdaneta City University|Irrigation canal/;
(async()=>{try{
  const apiPort=await listen(fixture),spare=http.createServer(),port=await listen(spare);await new Promise(r=>spare.close(r));const base=`http://127.0.0.1:${port}`;
  next=spawn(process.execPath,[path.resolve('node_modules/next/dist/bin/next'),'start','--hostname','127.0.0.1','--port',String(port)],{env:{...process.env,AGAPAY_API_URL:`http://127.0.0.1:${apiPort}`,NEXT_TELEMETRY_DISABLED:'1'},stdio:'ignore',windowsHide:true});
  let ready=false;for(let i=0;i<60;i++){try{if((await fetch(base+'/login')).ok){ready=true;break;}}catch{}await pause(500);}assert(ready,'production server ready');
  browser=await chromium.launch({headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  await context.route(/^https?:\/\/(?!127\.0\.0\.1)/,r=>r.abort());
  await context.addCookies([{name:'agapay_session',value:'synthetic-review',url:base,httpOnly:true}]);
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/dashboard');await page.getByRole('heading',{name:'STATION MAP'}).waitFor();
  const select=page.getByRole('combobox',{name:'Station on map'});
  await page.waitForFunction(()=>document.querySelectorAll('select[aria-label="Station on map"] option').length>=6,{},{timeout:20000});
  const options=await select.locator('option').allTextContents();
  assert.deepEqual(options.slice(1),['REG_VERIFIED','REG_UNVERIFIED','NO_LOCATION · Location pending','BAD_LOCATION · Location pending','STATION_001 · Location pending']);
  const footer=page.locator('.station-map-footer');
  // The dashboard always keeps a station selected, so the mapped count is proven by the
  // options above: exactly 2 of 5 stations have no "Location pending" suffix.
  assert.equal(options.slice(1).filter(o=>!o.includes('Location pending')).length,2,'only registry pairs are mappable');
  const expect={REG_VERIFIED:'Confirmed registry location',REG_UNVERIFIED:'Unconfirmed registry location',
    NO_LOCATION:'Location unavailable · no map pin',BAD_LOCATION:'Recorded location invalid · no map pin',STATION_001:'Location unavailable · no map pin'};
  for(const [id,label] of Object.entries(expect)){
    await select.selectOption(id);await page.waitForTimeout(150);
    const text=await footer.innerText();assert(text.includes(label),`${id}: ${text}`);
    if(id==='NO_LOCATION')assert(text.includes('105.0 cm'),'measurement preserved without a location');
  }
  assert.doesNotMatch(await page.locator('#main-content').innerText(),DEMO,'no bundled demo coordinate or place name leaks');
  await page.goto(base+'/stations');await page.getByRole('heading',{name:'STATION_001 station',exact:true}).waitFor();
  const stationsText=await page.locator('#main-content').innerText();
  assert.doesNotMatch(stationsText,DEMO);
  // The detail page is where the bundled demo place used to appear for STATION_001.
  await page.goto(base+'/stations/STATION_001');await page.getByRole('heading',{name:'STATION_001 station',exact:true}).first().waitFor();
  const detail=await page.locator('#main-content').innerText();
  assert.doesNotMatch(detail,DEMO);assert(detail.includes('Location unavailable'),'missing place is stated, not invented');
  for(const route of ['/dashboard','/stations'])for(const theme of ['light','dark'])for(const narrow of [false,true]){
    await page.goto(base+route);await page.waitForTimeout(500);
    await page.evaluate(t=>{localStorage.setItem('agapay-theme',t);document.documentElement.dataset.theme=t;},theme);
    await page.setViewportSize(narrow?{width:320,height:900}:{width:1440,height:1000});
    await page.evaluate(large=>document.documentElement.style.fontSize=large?'200%':'',narrow);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${route} ${theme} ${narrow} fits`);
    const name=`${route.slice(1)}-${theme}${narrow?'-320-200pct':'-1440'}`;
    await page.screenshot({path:path.join(output,name+'.png'),fullPage:false});
    const scan=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
    results.push({route,theme,narrow,violations:scan.violations.map(v=>({id:v.id,nodes:v.nodes.length,targets:v.nodes.slice(0,3).map(n=>n.target.join(' '))}))});
  }
  await page.setViewportSize({width:1440,height:1000});await page.evaluate(()=>document.documentElement.style.fontSize='');
  fs.writeFileSync(path.join(output,'coordinates-axe.json'),JSON.stringify(results,null,2));
  assert.deepEqual(errors,[],'browser runtime errors');
  const violations=results.flatMap(r=>r.violations.map(v=>`${r.route} ${r.theme}${r.narrow?' 320px/200%':''}: ${v.id} x${v.nodes}`));
  console.log('PASS: R1 coordinate integrity on the production build: registry pins only (2 of 5), verified/unverified/missing/invalid labels, measurement kept without a location, no demo coordinate or place-name leak, dashboard and stations in light/dark at 1440px and 320px/200% without overflow. Google Maps tiles were blocked (no external network).');
  console.log('AXE (reported, not asserted here):',violations.length?violations.join('; '):'no violations');
  console.log('Evidence:',output);
}finally{
  if(browser)await browser.close();if(next){next.kill();await new Promise(r=>{if(next.exitCode!==null)return r();next.once('exit',r);setTimeout(r,5000).unref();});}
  fixture.close();
}})().catch(e=>{console.error(e);process.exitCode=1;});
