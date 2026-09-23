/* Optional browser smoke check: plain Node assertions + Playwright, no test framework.
 * Runs the production Next server against an isolated in-memory HTTP API fixture.
 * No real backend, database, account, Maps request, or resident delivery is used.
 */
const assert = require('node:assert/strict');
const http = require('node:http');
const { spawn } = require('node:child_process');
const path = require('node:path');
const { chromium } = require(process.env.AGAPAY_PLAYWRIGHT_MODULE || 'playwright');
const stamp = '2026-09-23T01:02:03Z';
const account = { id: 1, name: 'Alert UI Test', email: 'ui@example.invalid', phone: '', barangay: '', role: 'officer', is_active: true, created_at: stamp, updated_at: stamp };
const episode = (id, status = 'ACTIVE', severity = 'WARNING') => ({
  id, station_id: id === 2 ? 'STATION_002' : 'STATION_001', status, source: 'sensor',
  current_severity: status === 'RESOLVED' ? 'NORMAL' : severity, highest_severity: severity,
  trigger_telemetry_id: id * 10, latest_telemetry_id: id * 10 + 1, trigger_sequence_no: id * 10,
  latest_sequence_no: id * 10 + 1, trigger_depth_cm: severity === 'EVACUATE' ? 105 : 61, latest_depth_cm: status === 'RESOLVED' ? 12 : 91,
  triggered_at: stamp, last_transition_at: stamp, resolved_at: status === 'RESOLVED' ? stamp : null,
});
let active = [episode(1), episode(2, 'ACTIVE', 'EVACUATE')];
let history = Array.from({length: 52}, (_, i) => episode(100 + i, 'RESOLVED', i === 0 ? 'EVACUATE' : 'WARNING'));
let unavailable = false, monitoringDown = false, delay = 0, running = 0, maxRunning = 0;
const requests = [], failures = [];
const fixture = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://fixture');
  const json = (body, status = 200) => { res.writeHead(status, {'content-type': 'application/json'}); res.end(JSON.stringify(body)); };
  if (url.pathname === '/api/auth/me') return json({...account, role: req.headers.authorization === 'Bearer resident-fixture' ? 'resident' : 'officer'});
  if (url.pathname === '/api/sos') return json({items: [], total: 0, counts: {ACTIVE: 0, ACKNOWLEDGED: 0, RESOLVED: 0}});
  if (url.pathname === '/api/monitoring/stations') {
    if (monitoringDown) return json({detail: 'Fixture outage'}, 503);
    return json({checked_at: stamp, stale_after_seconds: 60, stations: ['STATION_001', 'STATION_002'].map((id, i) => ({
      station_id: id, station_name: `Fixture Station ${i + 1}`, barangay: '', municipality: '', latitude: null, longitude: null,
      administrative_status: 'active', connection_status: 'online', is_online: true, is_stale: false, age_seconds: 1,
      alert_tier: 'WARNING', trend: 'stable', current_depth_cm: 91, latest_depth_cm: 91, latest_rainfall_mm: 0,
      sensor_quality: 'valid', last_ping: stamp, observed_at: stamp, firmware_version: 'fixture', source: 'simulator',
      threshold_advisory_cm: 60, threshold_warning_cm: 85, threshold_evacuate_cm: 100, history: [],
    }))});
  }
  if (!url.pathname.startsWith('/api/alerts')) return json({detail: 'Not found'}, 404);
  requests.push(url.pathname + url.search);
  running++; maxRunning = Math.max(maxRunning, running);
  if (delay) await new Promise(r => setTimeout(r, delay));
  running--;
  if (unavailable) return json({detail: 'Fixture outage'}, 503);
  const offset = Number(url.searchParams.get('offset') || 0), limit = Number(url.searchParams.get('limit') || 50);
  if (url.pathname.endsWith('/transitions')) {
    const id = Number(url.pathname.split('/')[3]);
    const items = Array.from({length: 52}, (_, i) => ({id: i + 1, alert_id: id, station_id: 'STATION_001', telemetry_id: i + 1, sequence_no: i + 1, previous_severity: i === 0 ? 'NORMAL' : i % 2 ? 'EVACUATE' : 'WARNING', new_severity: i === 51 ? 'NORMAL' : i % 2 ? 'WARNING' : 'EVACUATE', water_depth_cm: i === 51 ? 12 : i % 2 ? 91 : 105, transitioned_at: stamp}));
    return json({items: items.slice(offset, offset + limit), total: items.length});
  }
  const detail = url.pathname.match(/^\/api\/alerts\/(\d+)$/);
  if (detail) return json([...active, ...history].find(a => a.id === Number(detail[1])) || episode(Number(detail[1])));
  let items = url.pathname.endsWith('/active') ? active : history;
  if (url.searchParams.has('station_id')) items = items.filter(a => a.station_id === url.searchParams.get('station_id'));
  if (url.searchParams.has('severity')) items = items.filter(a => a.current_severity === url.searchParams.get('severity'));
  json({items: items.slice(offset, offset + limit), total: items.length});
});
const listen = server => new Promise(resolve => server.listen(0, '127.0.0.1', () => resolve(server.address().port)));
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
(async () => {
  let browser, next;
  try {
    const backendPort = await listen(fixture);
    const spare = http.createServer(); const webPort = await listen(spare); await new Promise(r => spare.close(r));
    const base = `http://127.0.0.1:${webPort}`;
    next = spawn(process.execPath, [path.resolve('node_modules/next/dist/bin/next'), 'start', '--hostname', '127.0.0.1', '--port', String(webPort)], {cwd: process.cwd(), env: {...process.env, AGAPAY_API_URL: `http://127.0.0.1:${backendPort}`, NEXT_TELEMETRY_DISABLED: '1'}, stdio: 'ignore', windowsHide: true});
    let ready = false;
    for (let i = 0; i < 60; i++) { try { if ((await fetch(`${base}/login`)).ok) { ready = true; break; } } catch {} await pause(500); }
    assert(ready, 'isolated Next server starts');
    browser = await chromium.launch({headless: true, ...(process.env.AGAPAY_BROWSER_CHANNEL ? {channel: process.env.AGAPAY_BROWSER_CHANNEL} : {})});
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}, timezoneId: 'America/Los_Angeles'});
    await context.addCookies([{name: 'agapay_session', value: 'staff-fixture', url: base, httpOnly: true, sameSite: 'Lax'}]);
    await context.route(/https:\/\/(maps|fonts|www\.google)/, route => route.abort());
    const page = await context.newPage();
    page.on('pageerror', error => failures.push(error.message));
    const sensors = page.getByRole('region', {name: 'Persistent sensor alerts'});
    const row = sensors.locator('tbody tr');
    await page.goto(`${base}/alerts`);
    await sensors.getByText('Fixture Station 1', {exact: true}).waitFor();
    assert.equal(await row.count(), 2);
    assert.equal(await page.locator('.header-meta').getByText('SENSOR EPISODES', {exact: true}).count(), 1);
    assert.equal(await sensors.getByRole('button', {name: /Resolve/}).count(), 0);
    assert((await sensors.innerText()).includes('09:02:03 PHT'), 'Manila time regardless of browser timezone');
    assert.equal(await page.locator('nav .nav-count.alerts').count(), 0, 'no demo count on operational navigation');
    await page.getByLabel('Alert tier', {exact: true}).selectOption('EVACUATE');
    await row.filter({hasText: 'STATION_002'}).waitFor();
    assert.equal(await row.count(), 1);
    assert(requests.some(p => p.includes('severity=EVACUATE')));
    await page.getByLabel('Alert tier', {exact: true}).selectOption('All');
    await page.getByLabel('Station filter').selectOption('STATION_001');
    await sensors.getByText('Fixture Station 1', {exact: true}).waitFor();
    assert.equal(await row.count(), 1);
    assert(requests.some(p => p.includes('station_id=STATION_001')));
    await page.getByLabel('Station filter').selectOption('All');
    await page.getByRole('button', {name: 'Historical', exact: true}).click();
    await sensors.getByRole('columnheader', {name: 'Peak Tier'}).waitFor();
    await sensors.getByText('1–50 of 52', {exact: true}).waitFor();
    assert.equal(await row.count(), 50);
    assert((await row.first().innerText()).includes('EVACUATE'));
    assert((await row.first().innerText()).includes('105 cm'));
    assert(!(await row.first().innerText()).includes('12 cm'));
    assert(!(await row.first().innerText()).includes('NORMAL'));
    await page.getByLabel('Peak alert tier').selectOption('EVACUATE');
    assert.equal(await row.count(), 1);
    assert(!requests.filter(p => p.startsWith('/api/alerts?')).some(p => p.includes('severity=')), 'historical tier is not current severity query');
    await sensors.getByRole('button', {name: 'Next', exact: true}).click();
    await sensors.getByText('No matching sensor alerts on this page.', {exact: false}).waitFor();
    await page.getByLabel('Peak alert tier').selectOption('All');
    await sensors.getByText('1–50 of 52', {exact: true}).waitFor();
    await page.getByLabel('Search stations').fill('missing-station');
    await sensors.getByText('No matching sensor alerts on this page.', {exact: false}).waitFor();
    await page.getByLabel('Search stations').fill('');
    await sensors.getByRole('button', {name: 'History', exact: true}).first().click();
    const dialog = page.getByRole('dialog', {name: 'Sensor alert history'});
    await dialog.getByText('NORMAL → EVACUATE', {exact: true}).waitFor();
    await dialog.getByText('Recovery depth:', {exact: true}).waitFor();
    assert((await dialog.innerText()).includes('Sequence 1'));
    if (process.env.AGAPAY_QA_SCREENSHOT) await page.screenshot({path: process.env.AGAPAY_QA_SCREENSHOT.replace('.png', '-history.png')});
    await dialog.getByRole('button', {name: 'Next', exact: true}).click();
    await dialog.getByText('51–52 of 52', {exact: true}).waitFor();
    await dialog.getByRole('button', {name: 'CLOSE', exact: true}).click();
    unavailable = true;
    await sensors.getByRole('button', {name: 'History', exact: true}).first().click();
    await dialog.getByText('Transition history unavailable.', {exact: false}).waitFor();
    await dialog.getByRole('button', {name: 'CLOSE', exact: true}).click();
    unavailable = false;
    await page.getByRole('button', {name: 'Manual Alert · Demo', exact: true}).click();
    await page.getByRole('button', {name: 'ISSUE DEMO ALERT', exact: true}).click();
    await page.getByRole('button', {name: 'CONFIRM ALERT', exact: true}).click();
    const demos = page.getByRole('region', {name: 'Manual demo alerts'});
    await demos.getByRole('button', {name: 'Resolve demo', exact: true}).waitFor();
    assert((await demos.innerText()).includes('Not delivered to residents'));
    await demos.getByRole('button', {name: 'Resolve demo', exact: true}).click();
    await page.getByRole('button', {name: 'RESOLVE DEMO', exact: true}).click();
    await page.getByRole('button', {name: 'Historical', exact: true}).click();
    await demos.getByText('DEMO · RESOLVED', {exact: false}).waitFor();
    unavailable = true;
    await page.getByRole('button', {name: 'Active', exact: true}).click();
    await sensors.getByRole('alert').waitFor();
    assert(!(await sensors.innerText()).includes('No active sensor alerts'));
    unavailable = false; active = [];
    await sensors.getByText('No active sensor alerts.', {exact: true}).waitFor({timeout: 10000});
    history = [];
    await page.getByRole('button', {name: 'Historical', exact: true}).click();
    await sensors.getByText('No historical sensor alerts.', {exact: true}).waitFor();
    await page.getByRole('button', {name: 'Active', exact: true}).click();
    active = [episode(1)]; monitoringDown = true;
    await page.reload();
    await sensors.getByRole('button', {name: 'History', exact: true}).waitFor();
    assert(!(await sensors.innerText()).includes('Fixture Station'), 'station ID fallback without fabricated metadata');
    // Hidden documents pause polling and immediately refresh on visibility return.
    await page.evaluate(() => { Object.defineProperty(document, 'hidden', {configurable: true, value: true}); document.dispatchEvent(new Event('visibilitychange')); });
    await pause(200); const beforeHidden = requests.length; await pause(5500);
    assert.equal(requests.length, beforeHidden);
    await page.evaluate(() => { Object.defineProperty(document, 'hidden', {configurable: true, value: false}); document.dispatchEvent(new Event('visibilitychange')); });
    await pause(500); assert(requests.length > beforeHidden);
    // A slow list request must not overlap the next polling interval.
    delay = 5500; maxRunning = 0;
    await page.reload();
    await sensors.getByText('Loading alerts…', {exact: true}).waitFor();
    await sensors.getByRole('button', {name: 'History', exact: true}).waitFor({timeout: 12000});
    assert.equal(maxRunning, 1); delay = 0;
    // Route changes cancel polling; existing navigation still works.
    await sensors.getByRole('button', {name: 'View', exact: true}).click();
    await page.waitForURL('**/stations/STATION_001');
    const countAfterLeave = requests.length; await pause(5500); assert.equal(requests.length, countAfterLeave);
    await page.getByRole('navigation').getByRole('link', {name: 'Alerts', exact: true}).click();
    await sensors.getByRole('button', {name: 'History', exact: true}).waitFor();
    // Exercise the real BFF authorization, read-only allowlist and query forwarding.
    assert.equal((await context.request.patch(`${base}/api/account/alerts/1`, {data: {status: 'RESOLVED'}})).status(), 404);
    assert.equal((await context.request.get(`${base}/api/account/alerts/active?limit=50&offset=0&unknown=ignored`)).status(), 200);
    assert(!requests.at(-1).includes('unknown='));
    const guest = await browser.newContext();
    assert.equal((await guest.request.get(`${base}/api/account/alerts`)).status(), 401);
    await guest.addCookies([{name: 'agapay_session', value: 'resident-fixture', url: base, httpOnly: true}]);
    assert.equal((await guest.request.get(`${base}/api/account/alerts`)).status(), 403);
    await guest.close();
    assert.equal(await page.evaluate(() => document.cookie.includes('agapay_session')), false);
    assert.deepEqual(failures, []);
    if (process.env.AGAPAY_QA_SCREENSHOT) {
      await page.screenshot({path: process.env.AGAPAY_QA_SCREENSHOT, fullPage: true});
      await page.setViewportSize({width: 1024, height: 768});
      await page.screenshot({path: process.env.AGAPAY_QA_SCREENSHOT.replace('.png', '-1024.png')});
    }
    console.log('PASS: persistent episodes, peak tier/trigger depth, filters, pagination, timeline, demos, loading/empty/outage, Manila time, polling, navigation, BFF authorization/read-only routes and HttpOnly session.');
  } finally {
    if (browser) await browser.close();
    if (next) next.kill();
    fixture.closeAllConnections();
    await new Promise(resolve => fixture.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
