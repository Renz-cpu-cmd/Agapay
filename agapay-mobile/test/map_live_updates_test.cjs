// Regression for the physical-device "LOADING GOOGLE MAP…" hang: marker labels carry live
// values (heartbeat age, measurement time) that change every second. Rebuilding the map for
// each label change re-showed the loading state, cancelled the readiness wait and re-moved
// the camera, so on a real phone the map never became ready. Label-only refreshes must now
// update the existing pins in place.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function harness() {
  const html = fs.readFileSync(path.join(__dirname, '../assets/maps/agapay_google_map.html'), 'utf8');
  const maps = [], pins = [], messages = [], timers = new Map(), tileListeners = [];
  let routeRequests = 0, nextTimer = 1, now = 0;
  const status = { textContent: '', hidden: false, classList: { add(c) { if (c === 'hidden') status.hidden = true; }, remove(c) { if (c === 'hidden') status.hidden = false; } }, replaceChildren() {} };
  const elements = { status, map: { replaceChildren() {} }, provider: { textContent: '' } };
  const document = { documentElement: { dataset: {} }, getElementById: id => elements[id] };
  class FakeMap {
    constructor(element, options) { this.options = options; this.camera = options; this.cameraMoves = 0; maps.push(this); }
    getCenter() { return this.camera.center; } getZoom() { return this.camera.zoom; } getTilt() { return this.camera.tilt; }
    getHeading() { return this.camera.heading; } getMapTypeId() { return 'roadmap'; }
    moveCamera(camera) { this.camera = camera; this.cameraMoves++; }
    fitBounds() { this.cameraMoves++; }
  }
  class Polyline { constructor(options) { this.map = options.map; } setMap(value) { this.map = value; } }
  class PinElement { constructor(options) { this.options = options; } }
  class AdvancedMarkerElement { constructor(options) { Object.assign(this, options); pins.push(this); } addEventListener() {} }
  const libraries = {
    maps: { Map: FakeMap, Polyline, MapTypeId: {}, RenderingType: { VECTOR: 'vector' } },
    marker: { PinElement, AdvancedMarkerElement },
    core: { ColorScheme: { LIGHT: 'light', DARK: 'dark' }, ControlPosition: {} },
    routes: { Route: { computeRoutes: async () => { routeRequests++; return { routes: [{ distanceMeters: 1, durationMillis: 1000, warnings: [], createPolylines: () => [new Polyline({})], viewport: null }] }; } } },
  };
  const google = { maps: {
    importLibrary: async name => libraries[name],
    LatLngBounds: class { extend() {} },
    event: { clearInstanceListeners() {}, addListenerOnce(map, name, fn) { if (name === 'tilesloaded') tileListeners.push(fn); } },
  } };
  const window = { google, AgapayBridge: { postMessage(value) { messages.push(JSON.parse(value)); } } };
  const context = vm.createContext({
    window, document, google,
    setTimeout: (fn, ms) => { const id = nextTimer++; timers.set(id, { fn, ms, due: now + ms }); return id; },
    clearTimeout: id => timers.delete(id),
  });
  vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);
  const fireTiles = () => tileListeners.splice(0).forEach(fn => fn());
  const fireFallback = () => { for (const [id, t] of timers) if (t.ms === 8000) { timers.delete(id); t.fn(); } };
  // Virtual clock: advance time and run timers that fell due.
  const tick = ms => { now += ms; for (const [id, t] of [...timers]) if (t.due <= now) { timers.delete(id); t.fn(); } };
  return { window, maps, pins, messages, status, timers, fireTiles, fireFallback, tick, routes: () => routeRequests };
}

const live = (age, measured, extra = {}) => ({
  apiKey: 'test-only', theme: 'dark', center: { latitude: 15.97, longitude: 120.57 }, zoom: 15, tilt: 0, fitAll: true,
  selectedMarkerId: 'AGP_REVIEWED', overlays: [],
  markers: [
    { id: 'AGP_PROTOTYPE', title: `Prototype · Heartbeat age: ${age} sec ago · Measured: ${measured}`, position: { latitude: 15.97, longitude: 120.565 }, color: '#94a3b8', glyph: 'U', selected: false },
    { id: 'AGP_REVIEWED', title: `Reviewed · Heartbeat age: ${age} sec ago · Measured: ${measured}`, position: { latitude: 15.9756, longitude: 120.5712 }, color: '#f97316', glyph: 'W', selected: true },
  ],
  ...extra,
});

test('label-only live refreshes keep a ready map visible, in place, without moving the camera', async () => {
  const h = harness();
  await h.window.agapayRender(live(1, 'T1'));
  assert.equal(h.status.hidden, false, 'first load shows the loading state');
  h.fireTiles();
  assert.equal(h.status.hidden, true);
  assert.equal(h.messages.at(-1).type, 'ready');
  const map = h.maps[0], moves = map.cameraMoves, pinCount = h.pins.length;
  for (let second = 2; second <= 30; second++) await h.window.agapayRender(live(second % 5, `T${second}`));
  assert.equal(h.maps.length, 1, 'no map recreation');
  assert.equal(h.status.hidden, true, 'loading state never re-shown by live label refreshes');
  assert.equal(map.cameraMoves, moves, 'the camera (and any user panning) is left alone');
  assert.equal(h.pins.length, pinCount, 'existing pins are reused');
  assert.match(h.pins.at(-1).title, /Heartbeat age: 0 sec ago · Measured: T30/, 'labels stay current');
  assert.equal(h.messages.filter(m => m.type === 'error').length, 0);
  assert.equal(h.messages.at(-1).type, 'ready');
});

test('per-second refreshes during the initial load do not cancel the readiness wait', async () => {
  // Tiles never report loaded (e.g. a slow device); live data keeps arriving every second.
  // The 8 s fallback must still complete the load instead of being reset forever.
  const h = harness();
  await h.window.agapayRender(live(1, 'T1'));
  for (let second = 2; second <= 12; second++) {
    h.tick(1000);
    await h.window.agapayRender(live(second, `T${second}`));
  }
  assert.ok(h.messages.some(m => m.type === 'ready'), 'ready within the fallback window despite live refreshes');
  assert.equal(h.status.hidden, true, 'loading state cleared and not re-shown');
  assert.equal(h.messages.at(-1).type, 'ready');
});

test('structural changes still take the full path: selection moves the camera, route is requested once', async () => {
  const h = harness();
  await h.window.agapayRender(live(1, 'T1'));
  h.fireTiles();
  const map = h.maps[0], moves = map.cameraMoves;
  const switched = live(2, 'T2', { selectedMarkerId: 'AGP_PROTOTYPE' });
  switched.markers = switched.markers.map(m => ({ ...m, selected: m.id === 'AGP_PROTOTYPE' }));
  await h.window.agapayRender(switched);
  assert.ok(map.cameraMoves > moves, 'station switching still recentres the map');
  assert.equal(h.status.hidden, false, 'structural change waits for tiles again');
  h.fireTiles();
  const route = { id: 'route-1', origin: { latitude: 15.97, longitude: 120.57 }, destination: { latitude: 15.98, longitude: 120.58 }, travelMode: 'WALKING' };
  await h.window.agapayRender(live(3, 'T3', { route }));
  h.fireTiles();
  assert.equal(h.routes(), 1);
  for (let second = 4; second <= 10; second++) await h.window.agapayRender(live(second, `T${second}`, { route }));
  assert.equal(h.routes(), 1, 'live label refreshes never re-request walking directions');
});

test('theme changes still recreate the map and wait for it to be ready again', async () => {
  const h = harness();
  await h.window.agapayRender(live(1, 'T1'));
  h.fireTiles();
  await h.window.agapayRender(live(2, 'T2', { theme: 'light' }));
  assert.equal(h.maps.length, 2);
  assert.equal(h.maps[1].options.colorScheme, 'light');
  assert.equal(h.status.hidden, false);
  await h.window.agapayRender(live(3, 'T3', { theme: 'light' }));
  h.fireTiles();
  assert.equal(h.status.hidden, true);
});
