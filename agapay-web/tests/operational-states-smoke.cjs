/* Actual production pages, loopback-only synthetic data. No provider calls. */
const assert=require('node:assert/strict'),http=require('node:http'),path=require('node:path'),fs=require('node:fs'),{spawn}=require('node:child_process');
const {chromium}=require('playwright'),{default:AxeBuilder}=require('@axe-core/playwright');
const contract=JSON.parse(fs.readFileSync('../agapay-docs/contracts/operational-presentation-cases.json','utf8'));
const output=path.resolve('../agapay-docs/design/shared-vocabulary');fs.mkdirSync(output,{recursive:true});
let next,browser,down=false,empty=false;const errors=[],results=[];
const fixture=http.createServer((req,res)=>{
  const url=new URL(req.url,'http://fixture'),at=new Date(),stamp=at.toISOString();
  const json=(body,status=200)=>{res.writeHead(status,{'content-type':'application/json'});res.end(JSON.stringify(body));};
  if(url.pathname==='/api/auth/me')return json({id:1,version:1,name:'Synthetic Reviewer',email:'review@example.invalid',role:'officer',is_active:true,created_at:stamp,updated_at:stamp});
  if(url.pathname==='/api/monitoring/stations'){
    if(down)return json({detail:'Synthetic API outage'},503);
    return json({checked_at:stamp,stale_after_seconds:30,stations:empty?[]:contract.cases.filter(r=>r.id!=='api-outage').map(row=>({
      station_id:row.id,station_name:row.id,barangay:'Synthetic area',municipality:'Fixture city',latitude:null,longitude:null,
      connection_status:row.connectivity,is_online:row.connectivity==='online',administrative_status:'active',is_stale:!row.current,
      heartbeat_at:stamp,heartbeat_age_seconds:row.connectivity==='online'?0:3600,heartbeat_fresh:row.connectivity==='online',
      latest_sample_at:stamp,latest_sample_age_seconds:0,last_valid_depth_at:row.depth===null?null:new Date(+at-(row.current?0:3600000)).toISOString(),
      depth_age_seconds:row.depth===null?null:row.current?0:3600,depth_fresh:row.current,depth_status:row.current?'fresh':row.depth===null?'missing':'retained',
      hazard_state:row.hazardState,active_hazard_tier:row.episodeTier,observation_tier:row.current?(row.depth>=100?'EVACUATE':'NORMAL'):'UNKNOWN',
      alert_tier:row.episodeTier??'NORMAL',current_depth_cm:row.depth,latest_depth_cm:row.quality==='invalid'?null:row.depth,
      sensor_quality:row.quality,source:'device',source_class:'physical_device',source_trusted:true,depth_source_trusted:true,stream:'operational',
      rainfall_observed_at:null,rainfall_age_seconds:null,rainfall_fresh:false,latest_rainfall_mm:null,history:[],trend:'unknown',
      threshold_advisory_cm:60,threshold_warning_cm:85,threshold_evacuate_cm:100,
    }))});
  }
  if(url.pathname==='/api/sos')return json({items:[],total:0,counts:{ACTIVE:0,ACKNOWLEDGED:0,RESOLVED:0}});
  if(url.pathname==='/api/alerts/command-queue')return json({checked_at:stamp,scope:'operational',counts:{operational:0,unverified:0},items:[],total:0,has_more:false});
  if(url.pathname.startsWith('/api/alerts'))return json({items:[],total:0});
  return json({detail:'Synthetic optional dependency unavailable'},503);
});
const listen=s=>new Promise(r=>s.listen(0,'127.0.0.1',()=>r(s.address().port))),pause=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{try{
  const apiPort=await listen(fixture),spare=http.createServer(),port=await listen(spare);await new Promise(r=>spare.close(r));const base=`http://127.0.0.1:${port}`;
  next=spawn(process.execPath,[path.resolve('node_modules/next/dist/bin/next'),'start','--hostname','127.0.0.1','--port',String(port)],{env:{...process.env,AGAPAY_API_URL:`http://127.0.0.1:${apiPort}`,NEXT_TELEMETRY_DISABLED:'1'},stdio:'ignore',windowsHide:true});
  let ready=false;for(let i=0;i<60;i++){try{if((await fetch(base+'/login')).ok){ready=true;break;}}catch{}await pause(500);}assert(ready,'production server ready');
  browser=await chromium.launch({headless:true,...(process.env.AGAPAY_BROWSER_CHANNEL?{channel:process.env.AGAPAY_BROWSER_CHANNEL}:{})});
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  await context.route(/^https?:\/\/(?!127\.0\.0\.1)/,r=>r.abort());
  await context.addCookies([{name:'agapay_session',value:'synthetic-review',url:base,httpOnly:true}]);
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/stations');await page.getByRole('heading',{name:'normal-zero',exact:true}).waitFor();
  for(const [index,row] of contract.cases.filter(r=>r.id!=='api-outage').entries()){
    const card=page.locator('.station-card').filter({has:page.getByRole('heading',{name:row.id,exact:true})});
    assert((await card.innerText()).includes(row.label),row.id);
    // Full evidence is progressive disclosure: collapsed by default, opened by the user.
    // Alternate mouse and keyboard so both interaction paths are exercised.
    const evidence=card.locator('details.station-evidence'),summary=evidence.locator('summary');
    assert.equal(await evidence.evaluate(d=>d.open),false,`${row.id}: measurement evidence collapsed by default`);
    const viaKeyboard=index%2===1;
    if(viaKeyboard){await summary.focus();await page.keyboard.press('Enter');}else await summary.click();
    assert.equal(await evidence.evaluate(d=>d.open),true,`${row.id}: evidence opens by ${viaKeyboard?'keyboard':'mouse'}`);
    const text=await card.innerText();
    assert(text.includes(`Latest sample validity: ${row.quality}`),row.id);
    assert(text.includes(`Connectivity: ${row.connectivity==='no_data'?'no_data':row.connectivity}`),row.id);
    assert(text.includes('Rain: No valid reading'),row.id+' independent missing rain');
    if(row.episodeTier)assert(text.includes(`Episode tier: ${row.episodeTier}`));
    if(row.depth===0){
      // A valid zero is a measurement, never "unavailable".
      assert.equal((await card.locator('.station-values dd.depth').innerText()).trim(),'0.0 cm','valid zero visible');
      const depthNote=(text.match(/Depth: ([^\n]*)/)||[])[1]??'';
      assert(depthNote&&!/No valid reading|unavailable|missing/i.test(depthNote),`${row.id}: zero depth is not treated as missing (${depthNote})`);
    }
    // Close with the keyboard and restore the default (collapsed) card layout.
    await summary.focus();await page.keyboard.press('Space');
    assert.equal(await evidence.evaluate(d=>d.open),false,`${row.id}: evidence closes by keyboard`);
  }
  // Fresh load so the first Tab starts from the document, as a keyboard user arrives.
  await page.goto(base+'/stations');await page.getByRole('heading',{name:'normal-zero',exact:true}).waitFor();
  await page.keyboard.press('Tab');assert(await page.getByRole('link',{name:'Skip to main content'}).evaluate(el=>el===document.activeElement),'skip link is first keyboard target');
  await page.keyboard.press('Enter');assert(await page.locator('#main-content').evaluate(el=>el===document.activeElement),'skip link moves focus to content');
  // Accessibility-tree evidence: the disclosure is exposed while collapsed, and opening it
  // (as a reviewer would) exposes the full facts checked below in every theme and size.
  const collapsedTree=await page.locator('#main-content').ariaSnapshot();
  assert(collapsedTree.includes('Measurement evidence'),'collapsed evidence disclosure is exposed to assistive technology');
  assert(!collapsedTree.includes('Latest sample validity: invalid'),'collapsed evidence content stays out of the tree');
  await page.locator('.station-card').filter({has:page.getByRole('heading',{name:'invalid-heartbeat',exact:true})}).locator('details.station-evidence summary').click();
  for(const theme of ['light','dark']){
    await page.evaluate(t=>{localStorage.setItem('agapay-theme',t);document.documentElement.dataset.theme=t;},theme);
    for(const narrow of [false,true]){
      await page.setViewportSize(narrow?{width:320,height:900}:{width:1440,height:1000});
      await page.evaluate(large=>document.documentElement.style.fontSize=large?'200%':'',narrow);
      await page.emulateMedia({reducedMotion:'reduce'});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'document fits');
      const layout=await page.locator('#main-content').evaluate(el=>({width:el.clientWidth,scroll:el.scrollWidth,overflow:[...el.querySelectorAll('*')].filter(n=>n.getBoundingClientRect().right>el.getBoundingClientRect().right+1).slice(0,8).map(n=>n.className)}));
      assert(layout.scroll<=layout.width,JSON.stringify({theme,narrow,...layout}));
      // Readable accessibility tree evidence, not an NVDA/TalkBack session.
      const tree=await page.locator('#main-content').ariaSnapshot();
      assert(tree.includes('Episode tier: EVACUATE'));assert(tree.includes('Latest sample validity: invalid'));
      fs.writeFileSync(path.join(output,`stations-${theme}${narrow?'-narrow':''}.aria.txt`),tree);
      await page.screenshot({path:path.join(output,`stations-${theme}${narrow?'-narrow':''}.png`)});
      const scan=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
      results.push({surface:'station state matrix',theme,width:narrow?320:1440,textScale:narrow?2:1,violations:scan.violations});
    }
  }
  await page.setViewportSize({width:1440,height:1000});await page.evaluate(()=>document.documentElement.style.fontSize='');
  down=true;await page.waitForFunction(()=>document.querySelector('.station-card')?.textContent.includes('Connectivity: unconfirmed'),{},{timeout:20000});
  assert(!(await page.locator('.station-status-facts').allTextContents()).some(t=>t.includes('Water depth: Observed')),'outage cannot retain an Observed claim');
  assert((await page.locator('.station-card').allTextContents()).some(t=>t.includes('Episode tier: EVACUATE (unresolved)')),'outage preserves unresolved episode');
  down=false;empty=true;await page.reload();await page.getByText('0 STATIONS',{exact:false}).waitFor();assert.equal(await page.locator('.station-card').count(),0);
  fs.writeFileSync(path.join(output,'accessibility-results.json'),JSON.stringify(results,null,2));
  assert.deepEqual(results.flatMap(s=>s.violations),[],'automated accessibility checks');assert.deepEqual(errors,[],'browser runtime errors');
  console.log('PASS: shared vocabulary, six independent observation states, missing rain, retained API-outage state, empty registry, four light/dark desktop/narrow 200% axe scans, accessible tree evidence and keyboard focus. Synthetic data only; no human comprehension or native screen-reader test.');
}finally{
  if(browser)await browser.close();if(next){next.kill();await new Promise(r=>{if(next.exitCode!==null)return r();next.once('exit',r);setTimeout(r,5000).unref();});}
  fixture.closeAllConnections();await new Promise(r=>fixture.close(r));
}})().catch(e=>{console.error(e);process.exitCode=1;});
