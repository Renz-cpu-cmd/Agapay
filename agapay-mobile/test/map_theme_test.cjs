const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

test('embedded map uses default tiles, recreates on theme changes, and keeps camera and pins', async () => {
  const html = fs.readFileSync(path.join(__dirname, '../assets/maps/agapay_google_map.html'), 'utf8');
  const instances = [];
  const messages=[];let failRoute=false;
  const pins = [];
  const roadLines=[];
  class Polyline {constructor(options){this.options=options;this.map=options.map;roadLines.push(this);}setMap(value){this.map=value;}}
  const elements = Object.fromEntries(['map', 'status', 'provider'].map(id => [id, {
    textContent: '', classList: { add() {}, remove() {} }, replaceChildren() {},
  }]));
  const document = { documentElement: { dataset: {} }, getElementById: id => elements[id] };
  class Map {
    constructor(element, options) { this.options = options; this.camera = options; instances.push(this); }
    getCenter() { return this.camera.center; }
    getZoom() { return this.camera.zoom; }
    getTilt() { return this.camera.tilt; }
    getHeading() { return this.camera.heading; }
    getMapTypeId() { return 'roadmap'; }
    moveCamera(camera) { this.camera = camera; }
  }
  class PinElement { constructor(options) { this.options = options; this.classList = { add() {} }; } }
  class AdvancedMarkerElement {
    constructor(options) { Object.assign(this, options); pins.push(this); }
    addEventListener() {}
  }
  const libraries = {
    routes:{Route:{computeRoutes:async(options)=>{assert.equal(options.travelMode,'WALKING');assert.equal('overlays' in options,false);if(failRoute)throw Error('Synthetic route provider failure');return {routes:[{distanceMeters:125,durationMillis:null,warnings:['Walking directions do not account for flooding'],createPolylines:({polylineOptions})=>[new Polyline(polylineOptions)]}]};}}},
    maps: { Map, Polyline, MapTypeId: {}, RenderingType: { VECTOR: 'vector' } },
    marker: { PinElement, AdvancedMarkerElement },
    core: { ColorScheme: { LIGHT: 'light', DARK: 'dark' }, ControlPosition: {} },
  };
  const google = { maps: {
    importLibrary: async name => libraries[name],
    event: { clearInstanceListeners() {}, addListenerOnce() {} },
  } };
  const window = { google,AgapayBridge:{postMessage(value){messages.push(JSON.parse(value));}} };
  const context = vm.createContext({ window, document, google, setTimeout: () => 1, clearTimeout() {} });
  vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);
  const config = {
    overlays:[{id:'reported-closure',title:'Source-reported closure',points:[{latitude:15,longitude:120},{latitude:15.1,longitude:120.1}],color:'#ef4444'}],
    apiKey: 'test-only', center: { latitude: 15.976, longitude: 120.571 }, zoom: 15, tilt: 0,
    markers: [{ id: 'station', title: 'Test station', position: { latitude: 15.976, longitude: 120.571 }, color: '#16a34a', glyph: '1' }],
  };
  await window.agapayRender(config);
  assert.equal(instances[0].options.colorScheme, 'light');
  assert.equal(document.documentElement.dataset.theme, 'light');
  const camera = { center: { lat: 16, lng: 120.6 }, zoom: 18, tilt: 30, heading: 90 };
  instances[0].moveCamera(camera);
  await window.agapayRender({ ...config, theme: 'dark' });
  assert.equal(instances.length, 2);
  assert.equal(instances[1].options.colorScheme, 'dark');
  assert.equal(instances[1].camera.zoom, 18);
  assert.deepEqual(instances[1].camera.center, camera.center);
  assert.equal(roadLines[0].map,null);
  assert.equal(roadLines[1].map,instances[1]);
  assert.equal(roadLines[1].options.strokeColor,'#ef4444');
  assert.equal(roadLines[1].options.path[0].lat,15);
  assert.equal(pins[0].map, null);
  assert.equal(pins[1].map, instances[1]);
  assert.equal(elements.provider.textContent, 'GOOGLE DEMO · DARK');
  await window.agapayRender({ ...config, theme: 'light' });
  assert.equal(instances[2].options.colorScheme, 'light');
  assert.equal(instances[2].camera.heading, 90);
  assert.equal(elements.provider.textContent, 'GOOGLE DEMO · DEFAULT');
  const route={id:'generic-route',origin:{latitude:15,longitude:120},destination:{latitude:15.1,longitude:120.1},travelMode:'WALKING'};
  await window.agapayRender({...config,route});
  const road=roadLines.at(-2),walking=roadLines.at(-1);
  assert.equal(road.map,instances.at(-1));assert.equal(walking.map,instances.at(-1));
  const ready=messages.findLast(m=>m.type==='route'&&m.status==='ready');
  assert.equal(ready.durationSeconds,null);assert.deepEqual(ready.warnings,['Walking directions do not account for flooding']);
  await window.agapayRender(config);assert.equal(road.map,null);assert.equal(walking.map,null);
  failRoute=true;await window.agapayRender({...config,route});assert.equal(messages.at(-1).status,'error');
  window.gm_authFailure();assert.equal(messages.at(-1).type,'error');assert.match(elements.status.textContent,/KEY WAS REJECTED/);
});
