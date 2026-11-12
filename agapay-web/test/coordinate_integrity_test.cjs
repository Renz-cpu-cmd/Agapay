// R1: the registry is the only source of an operational station position. No bundled,
// demo or "planned" coordinate or place name is ever substituted for missing data.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const load = require('./support/load-source.cjs');
// Modules run in a separate VM realm; compare plain values, not prototypes.
const plain = value => JSON.parse(JSON.stringify(value));
const src = path.join(__dirname, '../src');
const { registryLocation, displayStation } = load(path.join(src, 'lib/station-display.ts'));
const { stationCoordinates, locationLabel } = load(path.join(src, 'lib/station-map.ts'));

const at = '2026-10-21T00:00:00Z';
const row = (changes = {}) => ({
  station_id: 'STATION_001', station_name: 'Registry station', barangay: null, municipality: null,
  latitude: null, longitude: null, threshold_advisory_cm: 60, threshold_warning_cm: 85, threshold_evacuate_cm: 100,
  alert_tier: 'EVACUATE', observation_tier: 'EVACUATE', active_hazard_tier: 'EVACUATE', hazard_state: 'observed',
  current_depth_cm: 105, latest_rainfall_mm: 0,
  source: 'device', source_class: 'physical_device', source_trusted: true, depth_source_trusted: true, stream: 'operational',
  sensor_quality: 'valid', depth_fresh: true, rainfall_fresh: true, depth_status: 'fresh',
  last_valid_depth_at: at, rainfall_observed_at: at, depth_age_seconds: 0, rainfall_age_seconds: 0,
  heartbeat_at: at, heartbeat_age_seconds: 0, connection_status: 'online', is_online: true,
  history: [{ recorded_at: at, measured_at: at, received_at: at, water_depth_cm: 105, sensor_quality: 'valid' }],
  trend: 'rising',
  rainfall_product: { product: 'current_hour_received_tips', rainfall_mm: 0, tip_count: 0, interval_start: at,
    interval_end: '2026-10-21T00:00:02Z', quality: 'partial', source: 'physical_rain_gauge',
    coverage: 'received tips only', coverage_complete: false, calibration_version: 'synthetic-test', mm_per_tip: .7 },
  ...changes,
});

test('valid registry coordinates map exactly, with registry verification', () => {
  const verified = displayStation(row({ latitude: 15.97, longitude: 120.57, coordinate_status: 'verified' }));
  assert.deepEqual(plain(stationCoordinates(verified)), [15.97, 120.57]);
  assert.equal(verified.coordinates.status, 'verified');
  assert.equal(locationLabel(verified), 'Confirmed registry location');
  const unverified = displayStation(row({ latitude: 15.97, longitude: 120.57, coordinate_status: 'unverified' }));
  assert.equal(locationLabel(unverified), 'Unconfirmed registry location');
  // An older server without the field fails closed to unverified, never "verified" or "planned".
  const legacy = displayStation(row({ latitude: 15.97, longitude: 120.57 }));
  assert.equal(legacy.coordinates.status, 'unverified');
});

test('zero is a valid latitude or longitude', () => {
  for (const [latitude, longitude] of [[0, 120.5], [15.9, 0], [0, 0], [-90, 180], [90, -180]]) {
    const station = displayStation(row({ latitude, longitude, coordinate_status: 'verified' }));
    assert.deepEqual(plain(stationCoordinates(station)), [latitude, longitude], `${latitude},${longitude}`);
  }
});

test('missing or invalid coordinates never produce a pin or an invented place', () => {
  const cases = {
    'both missing': [{ latitude: null, longitude: null }, 'missing'],
    'latitude missing': [{ latitude: null, longitude: 120.5 }, 'invalid'],
    'longitude missing': [{ latitude: 15.9, longitude: null }, 'invalid'],
    'latitude out of range': [{ latitude: 90.0001, longitude: 120.5 }, 'invalid'],
    'longitude out of range': [{ latitude: 15.9, longitude: -180.5 }, 'invalid'],
    'NaN': [{ latitude: Number.NaN, longitude: 120.5 }, 'invalid'],
    'Infinity': [{ latitude: 15.9, longitude: Number.POSITIVE_INFINITY }, 'invalid'],
    'string': [{ latitude: '15.9', longitude: 120.5 }, 'invalid'],
    'server says missing': [{ latitude: null, longitude: null, coordinate_status: 'missing' }, 'missing'],
    'server says invalid': [{ latitude: null, longitude: null, coordinate_status: 'invalid' }, 'invalid'],
  };
  for (const [name, [changes, expected]] of Object.entries(cases)) {
    assert.deepEqual(plain(registryLocation(row(changes))), { coordinates: null, status: expected }, name);
    const station = displayStation(row(changes));
    assert.equal(stationCoordinates(station), null, name);
    assert.equal(station.coordinateStatus, expected, name);
    assert.match(locationLabel(station), /no map pin/, name);
    // The bundled STATION_001 demo point (15.98165, 120.560573) and place names never leak.
    assert.equal(station.location, 'Location unavailable', name);
    assert.equal(station.barangay, 'Unavailable', name);
    assert.doesNotMatch(JSON.stringify(station), /15\.98165|120\.560573|San Vicente|Urdaneta City University/, name);
  }
});

test('a valid measurement and active hazard survive a missing location', () => {
  const station = displayStation(row());
  assert.equal(stationCoordinates(station), null);
  assert.equal(station.depth.value, 105);
  assert.equal(station.depthFresh, true);
  assert.equal(station.activeHazardTier, 'EVACUATE');
  assert.equal(station.observationTier, 'EVACUATE');
  assert.equal(station.waterHistory[0].level, 105);
});

test('review status and geographic verification are independent', () => {
  // A configuration-unreviewed station can still have a verified registry location, and vice versa.
  const station = displayStation(row({ latitude: 15.97, longitude: 120.57, coordinate_status: 'verified',
    configuration: { status: 'matched', validation_status: 'prototype' } }));
  assert.equal(station.coordinates.status, 'verified');
  assert.equal(station.configuration.validation_status, 'prototype');
});

test('the monitoring context never merges bundled fixtures into operational stations', () => {
  const context = fs.readFileSync(path.join(src, 'context/MonitoringContext.tsx'), 'utf8');
  assert.doesNotMatch(context, /fallbackStations|stations as /);
  assert.doesNotMatch(fs.readFileSync(path.join(src, 'lib/station-display.ts'), 'utf8'), /fallback/);
  // Demo coordinates remain only in the labelled fixture file.
  const demo = fs.readFileSync(path.join(src, 'data/mockData.ts'), 'utf8');
  assert.match(demo, /status: "planned"/);
  const planned = displayStation(row({ latitude: 15.98165, longitude: 120.560573, coordinate_status: 'unverified' }));
  assert.equal(planned.coordinates.status, 'unverified'); // API data is never labelled "planned"
});

test('station switching recomputes each station from its own registry row', () => {
  const rows = [row({ station_id: 'A', latitude: 15.9, longitude: 120.5, coordinate_status: 'verified' }),
    row({ station_id: 'B' }), row({ station_id: 'C', latitude: 0, longitude: 0, coordinate_status: 'unverified' })];
  const stations = rows.map(source => displayStation(source));
  assert.deepEqual(plain(stations.map(s => [s.id, stationCoordinates(s), s.coordinateStatus])),
    [['A', [15.9, 120.5], 'verified'], ['B', null, 'missing'], ['C', [0, 0], 'unverified']]);
});
