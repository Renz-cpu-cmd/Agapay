/* Production browser workflow with loopback synthetic HTTP fixtures only. */
const assert=require('node:assert/strict'),http=require('node:http'),path=require('node:path'),{spawn}=require('node:child_process'),fs=require('node:fs');
const {chromium}=require('playwright');
const {default:AxeBuilder}=require('@axe-core/playwright');
const sample=JSON.parse(fs.readFileSync('../agapay-docs/contracts/published-forecast-cases.json','utf8')).find(row=>row.valid).value;
let mode='available',next,browser;const errors=[];const privacyCases=[];
const fixture=http.createServer((req,res)=>{
 const url=new URL(req.url,'http://fixture'),at=new Date(),stamp=at.toISOString();
 const json=(body,status=200)=>{res.writeHead(status,{'content-type':'application/json'});res.end(JSON.stringify(body));};
 if(url.pathname==='/api/auth/me')return json({id:1,version:1,name:'Synthetic CI Officer',email:'ci@example.invalid',role:req.headers.authorization==='Bearer resident-ci'?'resident':'officer',is_active:true,created_at:stamp,updated_at:stamp});
 if(url.pathname.startsWith('/api/monitoring/stations'))return json({checked_at:stamp,stale_after_seconds:30,stations:[]});
 if(url.pathname==='/api/forecasts/'+sample.forecast_id){
  if(mode==='error')return json({detail:'Synthetic fixture outage'},503);
  const product=structuredClone(sample);product.checked_at=product.generated_at=product.data_cutoff=product.input_last_recorded_at=stamp;product.valid_until=new Date(+at+(mode==='expired'?1000:60000)).toISOString();product.input_window_start=new Date(+at-55*60000).toISOString();product.forecasts.forEach(p=>p.target_at=new Date(+at+p.horizon_minutes*60000).toISOString());
  return json({product,current:mode!=='withdrawn',read_at:stamp});
 }
 if(url.pathname==='/api/sos')return json({items:[],total:0,counts:{ACTIVE:0,ACKNOWLEDGED:0,RESOLVED:0}});
 if(url.pathname==='/api/alerts/command-queue')return json({checked_at:stamp,scope:url.searchParams.get('scope')||'operational',counts:{operational:0,unverified:0},items:[],total:0,has_more:false});
 if(url.pathname==='/api/privacy/notice')return json({deployment:{status:'unapproved_development',privacy_contact:null,support_contact:null,operator_hours:'No operational response hours committed'},policy:{resolved_sos_location_days:7,resolved_sos_narrative_days:30},data:['Account and latest SOS location'],recipients:['Configured providers only'],rights:'Requests require review',limits:'Development policy unapproved'});
 if(url.pathname==='/api/privacy/cases'){
  if(req.method==='GET')return json(privacyCases);
  const item={id:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',kind:'access',version:1,state:'OPEN',decision_code:null,due_at:new Date(+at+15*86400000).toISOString()};privacyCases.push(item);return json(item,202);
 }
 if(url.pathname.startsWith('/api/alerts'))return json({items:[],total:0});
 if(url.pathname==='/api/operations/diagnostics')return json({checked_at:stamp,status:'degraded',ready:false,components:[],alerts:[]});
 return json({detail:'Synthetic optional dependency unavailable'},503);
});
const listen=server=>new Promise(resolve=>server.listen(0,'127.0.0.1',()=>resolve(server.address().port)));
const pause=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{try{
 const apiPort=await listen(fixture),spare=http.createServer(),webPort=await listen(spare);await new Promise(r=>spare.close(r));const base=`http://127.0.0.1:${webPort}`;
 next=spawn(process.execPath,[path.resolve('node_modules/next/dist/bin/next'),'start','--hostname','127.0.0.1','--port',String(webPort)],{env:{...process.env,AGAPAY_API_URL:`http://127.0.0.1:${apiPort}`,NEXT_TELEMETRY_DISABLED:'1'},stdio:'ignore',windowsHide:true});
 let ready=false;for(let i=0;i<60;i++){try{if((await fetch(base+'/login')).ok){ready=true;break;}}catch{}await pause(500);}assert(ready,'isolated production server ready');
 browser=await chromium.launch({headless:true,...(process.env.AGAPAY_BROWSER_CHANNEL?{channel:process.env.AGAPAY_BROWSER_CHANNEL}:{})});
 const context=await browser.newContext();await context.route(/^https?:\/\/(?!127\.0\.0\.1)/,route=>route.abort());await context.addCookies([{name:'agapay_session',value:'officer-ci',url:base,httpOnly:true}]);
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 const record=base+'/forecasts/'+sample.forecast_id;await page.goto(record);await page.getByRole('heading',{name:'Published forecast record'}).waitFor();await page.getByText('Within its original validity at read time',{exact:true}).waitFor();
 assert.equal(await page.locator('tbody tr').count(),3);assert((await page.locator('tbody').innerText()).includes('0–2 cm'),'valid zero interval rendered');

 const accessibility=[];
 for(const theme of ['light','dark']){
  await page.evaluate(theme=>{localStorage.setItem('agapay-theme',theme);document.documentElement.dataset.theme=theme;},theme);
  await page.emulateMedia({reducedMotion:'reduce'});
  const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
  accessibility.push({theme,violations:result.violations.map(v=>({id:v.id,impact:v.impact,description:v.description,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))});
 }
 for(const route of ['/dashboard','/alerts','/sos','/system-health','/settings']){
  await page.goto(base+route);await page.locator('#main-content').waitFor();await pause(600);assert.equal(await page.getByText('This page could not load. Try again to reload its data.').count(),0,route+' rendered critical content');
  for(const theme of ['light','dark']){
   await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
   const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
   accessibility.push({route,theme,violations:result.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))});
  }
 }
 await page.goto(base+'/settings');await page.getByText('Privacy and data requests',{exact:true}).first().click();await page.getByRole('heading',{name:'Privacy and data requests'}).waitFor();
 await page.getByLabel('Current password',{exact:true}).fill('SYNTHETIC-TEST-PASSWORD');await page.getByRole('button',{name:'Record privacy request',exact:true}).click();
 await page.getByRole('status').filter({hasText:'Request recorded:'}).waitFor();assert.equal(await page.getByLabel('Current password',{exact:true}).inputValue(),'','password cleared after privacy request');
 assert.equal(privacyCases.length,1,'one explicit case request');assert((await page.locator('#main-content').innerText()).includes('not confirmation of erasure'));
 console.log('PASS: explicit privacy case receipt, no implied erasure and password clearing');
 fs.writeFileSync(process.env.AGAPAY_A11Y_REPORT||'a11y-results.json',JSON.stringify(accessibility,null,2));
 assert.deepEqual(accessibility.flatMap(r=>r.violations),[],'WCAG automated checks in both themes');
 await page.goto(record);await page.keyboard.press('Control+Home');await page.reload();await page.getByRole('heading',{name:'Published forecast record'}).waitFor();
 await page.keyboard.press('Tab');assert.equal(await page.locator(':focus').innerText(),'Skip to main content');await page.keyboard.press('Enter');assert.equal(await page.locator(':focus').getAttribute('id'),'main-content');
 const logout=page.getByRole('button',{name:'LOG OUT',exact:true});await logout.click();const dialog=page.getByRole('dialog');await dialog.waitFor();
 for(let i=0;i<8;i++){await page.keyboard.press('Tab');assert(await dialog.locator(':focus').count(),'dialog retains keyboard focus');}
 await page.keyboard.press('Escape');assert.equal(await page.getByRole('dialog').count(),0);assert(await logout.evaluate(el=>el===document.activeElement),'dialog restores trigger focus');
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>document.documentElement.style.fontSize='200%');
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'narrow large-text page has no document overflow');
 await page.screenshot({path:process.env.AGAPAY_A11Y_SCREENSHOT||'a11y-narrow.png',fullPage:true});
 await page.setViewportSize({width:1280,height:800});await page.evaluate(()=>document.documentElement.style.fontSize='');
 console.log('PASS: both-theme axe, keyboard skip/dialog/focus return, reduced-motion and narrow large-text checks');
 mode='withdrawn';await page.reload();await page.getByText('Historical, expired or withdrawn — do not use as a current forecast',{exact:true}).waitFor();assert.equal(await page.locator('tbody tr').count(),3,'original values retained as history');
 mode='error';await page.reload();await page.getByRole('alert').waitFor();assert.equal(await page.locator('tbody tr').count(),0,'outage does not fabricate numbers');
 const guest=await browser.newContext();const resident=await guest.newPage();await resident.goto(record);await resident.waitForURL('**/login**');await guest.addCookies([{name:'agapay_session',value:'resident-ci',url:base,httpOnly:true}]);await resident.goto(base+'/ml-evaluation');await resident.waitForURL('**/login**');
 assert.deepEqual(errors,[]);console.log('PASS: published zero/interval, withdrawal history, outage, anonymous and resident staff-access browser flows');
 }finally{if(browser)await browser.close();if(next){next.kill();await new Promise(resolve=>{if(next.exitCode!==null)return resolve();next.once('exit',resolve);setTimeout(resolve,5000).unref();});}fixture.closeAllConnections();await new Promise(r=>fixture.close(r));}
})().catch(error=>{console.error(error);process.exitCode=1;});
