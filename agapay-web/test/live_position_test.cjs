// Migration 0010: staff-only operator-phone GPS for a portable station.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const load = require('./support/load-source.cjs');
const src = path.join(__dirname, '../src');
const { livePosition, liveLabel, liveAge, isLive } = load(path.join(src, 'lib/live-position.ts'));

const raw = (changes = {}) => ({ latitude: 15.9801, longitude: 120.5607, accuracy_m: 6.4, captured_at: '2026-11-13T05:00:00Z',
  age_seconds: 4, fresh: true, tracking_active: true, source: 'operator_phone_gps', ...changes });

test('a fresh fix during an active session is labelled live', () => {
  const live = livePosition(raw());
  assert.equal(isLive(live), true);
  assert.equal(liveLabel(live), 'Live phone GPS · ±6 m · 4 s ago');
});

test('an old fix or ended session is never called live', () => {
  assert.equal(liveLabel(livePosition(raw({ fresh: false, age_seconds: 300 }))), 'Tracking active · no recent fix · last ±6 m 5 min ago');
  assert.equal(liveLabel(livePosition(raw({ fresh: false, tracking_active: false, age_seconds: 7200 }))), 'Last known phone GPS · ±6 m · 2 h ago');
  assert.equal(isLive(livePosition(raw({ tracking_active: false }))), false);
  assert.equal(liveAge(3 * 86400), '3 days ago');
});

test('missing, malformed or coarse fixes produce no live point', () => {
  for (const value of [null, undefined, raw({ latitude: 91 }), raw({ longitude: Number.NaN }), raw({ accuracy_m: 51 }),
    raw({ accuracy_m: 0 }), raw({ age_seconds: -1 }), raw({ latitude: null })]) {
    assert.equal(livePosition(value), null);
  }
});

test('live position is passed through separately from the registry position', () => {
  const display = fs.readFileSync(path.join(src, 'lib/station-display.ts'), 'utf8');
  assert.match(display, /livePosition: livePosition\(source\.live_position\)/);
  assert.match(display, /coordinates: location\.coordinates/);
});

test('the map updates live overlays in place and never remounts for a moving fix', () => {
  const map = fs.readFileSync(path.join(src, 'components/StationMap.tsx'), 'utf8');
  const key = map.match(/const mapStateKey = (.*);/)[1];
  assert.doesNotMatch(key, /live/i, 'a live fix must not change the map key');
  const canvas = fs.readFileSync(path.join(src, 'components/GoogleStationMapCanvas.tsx'), 'utf8');
  assert.match(canvas, /overlay\.marker\.position = position/);
  assert.match(canvas, /overlay\.circle\.setOptions\(\{ center: position, radius: live\.accuracyM/);
  assert.match(canvas, /useEffect\(\(\) => \{\r?\n    stationsRef\.current = stations;/);
  assert.match(map, /followStationId=\{following \? selectedId : ""\}/);
  assert.match(canvas, /panKey !== pannedRef\.current\) map\.panTo/, 'follow pans once per accepted fix');
});
