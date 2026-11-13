const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const root = path.resolve(__dirname, '../src');
let monitoring;
const cache = new Map();
const empty = () => null;
function load(file) {
  file = path.resolve(file);
  if (cache.has(file)) return cache.get(file);
  const result = {};
  cache.set(file, result);
  const localRequire = name => {
    if (name === '@/lib/accounts') return {accountRequest:()=>Promise.reject(new Error('not requested during SSR'))};
    if (name === '@/context/AccountContext') return {useAccount:()=>({user:{role:'admin'}})};
    if (name === '@/context/MonitoringContext') return { useMonitoring: () => monitoring };
    if (name === '@/context/DemoContext') return { useDemo: () => ({ alerts: [] }) };
    if (name === '@/context/SosContext') return { useSos: () => ({ page: null, error: '' }) };
    if (name === '@/context/ThemeContext') return { useTheme: () => ({ theme: 'light' }) };
    if (name === '@/context/HybridProjectionContext') return { useHybridProjection: () => ({ available: false, active: false, config: { depthSource: 'sensor' }, clock: Date.parse('2026-10-21T00:00:00Z') }) };
    if (name === 'next/link') return ({ children }) => React.createElement('span', null, children);
    if (name === 'next/navigation') return { useRouter: () => ({ push() {} }) };
    if (name === 'next/dynamic') return () => empty;
    if (/^\.\/(RainfallActivityPanel|CommunityAlertThresholds|DeliveryConsole)$/.test(name)) return { __esModule: true, default: empty };
    if (name === './DesignUI') return { FigmaIcon: empty };
    if (name === 'recharts') return new Proxy({}, { get: (_, key) => ({ children }) => React.createElement(key === 'AreaChart' ? 'svg' : 'div', null, children) });
    if (name.startsWith('@/') || name.startsWith('.')) {
      const base = name.startsWith('@/') ? path.join(root, name.slice(2)) : path.resolve(path.dirname(file), name);
      return load(['.ts', '.tsx'].map(ext => base + ext).find(fs.existsSync));
    }
    return require(name);
  };
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText, { exports: result, require: localRequire, process, console, Date });
  return result;
}
const { displayStation } = load(path.join(root, 'lib/station-display.ts'));
const { stationMeasurement, measurementText, measurementNote, currentDepthSummary, measurementReport } = load(path.join(root, 'lib/measurements.ts'));
const at = '2026-10-21T00:00:00Z';
const row = (changes = {}) => ({
  station_id: 'ZERO', station_name: 'Test station', barangay: 'Test barangay', municipality: 'Test city',
  latitude: null, longitude: null, threshold_advisory_cm: 60, threshold_warning_cm: 85, threshold_evacuate_cm: 100,
  alert_tier: 'NORMAL', current_depth_cm: 0, latest_rainfall_mm: 0,
  source: 'device', source_class: 'physical_device', source_trusted: true, depth_source_trusted: true, stream: 'operational',
  sensor_quality: 'valid', depth_fresh: true, rainfall_fresh: true, depth_status: 'fresh',
  last_valid_depth_at: at, rainfall_observed_at: at, depth_age_seconds: 0, rainfall_age_seconds: 0,
  heartbeat_at: at, heartbeat_age_seconds: 0, connection_status: 'online', is_online: true,
  history: [], trend: 'stable', rainfall_product:{product:'current_hour_received_tips',rainfall_mm:changes.latest_rainfall_mm===null?null:0,tip_count:0,interval_start:'2026-10-21T00:00:00Z',interval_end:'2026-10-21T00:00:02Z',quality:'partial',source:'physical_rain_gauge',coverage:'missing coverage; received tips only',coverage_complete:false,calibration_version:'synthetic-test',mm_per_tip:.7}, ...changes,
});
const rows = [
  row({ station_id: 'MISSING', current_depth_cm: null, latest_rainfall_mm: null, sensor_quality: null, last_valid_depth_at: null, rainfall_observed_at: null, depth_fresh: false }),
  row(),
  row({ station_id: 'STALE', current_depth_cm: 105, depth_fresh: false, depth_age_seconds: 3600, last_valid_depth_at: '2026-10-20T23:00:00Z' }),
  row({ station_id: 'INVALID', current_depth_cm: null, sensor_quality: 'invalid', depth_fresh: false, last_valid_depth_at: null }),
];
const stations = rows.map(source => displayStation(source));

test('missing, valid zero, stale nonzero and invalid are distinct, including report/export rows', () => {
  assert.equal(stations.map(s => s.depth.state).join(','), 'missing,current,stale,invalid');
  assert.equal(stations.map(s => measurementText(s.depth)).join(','), '—,0.0,105.0,—');
  assert.equal(new Set(stations.map(s => measurementNote(s.depth))).size, 4);
  for (const station of stations) {
    const report = Object.fromEntries(measurementReport(station, stations));
    assert.equal(report['Water depth'], station.depth.value === null ? '—' : `${station.depth.value.toFixed(1)} cm`);
    assert.ok(report['Depth state / reason / time'].includes(station.depth.reason));
    assert.equal(report['Current depth coverage'], '1/4 stations with current valid depth');
    assert.equal(report['Current maximum depth'], '0.0 cm');
    assert.equal(report['Recorded window maximum depth'], '—');
    assert.equal(report['Recorded window maximum tier'], 'UNKNOWN');
  }
  assert.equal(Object.fromEntries(measurementReport(stations[0], stations))['Rainfall received this UTC hour'], '—');
  assert.equal(Object.fromEntries(measurementReport(stations[1], stations))['Rainfall received this UTC hour'], '0.000 mm');
});

test('empty coverage has no extrema or mean and retained invalid heartbeats keep the actual value time', () => {
  const summary = currentDepthSummary(stations.filter(s => s.id !== 'ZERO'));
  assert.equal(summary.maximum, null); assert.equal(summary.minimum, null); assert.equal(summary.average, null);
  const source = row({ current_depth_cm: 105, sensor_quality: 'invalid', depth_fresh: false, depth_age_seconds: 3600, last_valid_depth_at: '2026-10-20T23:00:00Z' });
  const depth = stationMeasurement(source, 'depth');
  assert.equal(depth.state, 'retained'); assert.equal(depth.value, 105); assert.equal(depth.quality, 'valid');
  assert.equal(depth.latestSampleQuality, 'invalid'); assert.equal(depth.measuredAt, '2026-10-20T23:00:00Z');
  assert.equal(stationMeasurement(source, 'rain').state, 'current'); // Independent channel, including valid zero rain.
  assert.equal(stationMeasurement(row({ source_trusted: false }), 'depth').state, 'unverified');
});

test('invalid historical samples stay as chart gaps and are excluded from recorded extrema and coverage', () => {
  const station = displayStation(row({ history: [
    { water_depth_cm: 0, rainfall_mm: 0, sensor_quality: 'valid', recorded_at: at },
    { water_depth_cm: 999, rainfall_mm: 0, sensor_quality: 'invalid', recorded_at: at },
    { water_depth_cm: 12, rainfall_mm: 0, sensor_quality: 'valid', recorded_at: at },
  ] }));
  assert.equal(station.waterHistory.map(p => p.level).join(','), '0,,12');
  const report = Object.fromEntries(measurementReport(station, [station]));
  assert.equal(report['Recorded window maximum depth'], '12.0 cm');
  assert.equal(report['Recorded window depth coverage'], '2/3 valid samples');
});

test('dashboard, cards, detail, analytics, map and health render all four states without numerical missing-value fallbacks', () => {
  for (const station of stations) {
    monitoring = { stations, selectedStationId: station.id, selectStation() {}, sensorAlerts: [], dataMode: 'device', loading: false, snapshot: { stations: rows, checked_at: at, stale_after_seconds: 30 }, error: '' };
    const components = [
      ['Dashboard', { onViewStation() {} }], ['Stations', {}], ['Stations', { initialStationId: station.id }],
      ['ForecastTrendPanel', { stationId: station.id }], ['StationMap', { selectedStationId: station.id, onSelectStation() {}, onViewStation() {} }], ['SystemHealth', {}],
    ];
    for (const [name, props] of components) {
      const html = renderToStaticMarkup(React.createElement(load(path.join(root, `components/${name}.tsx`)).default, props));
      assert.ok(html.includes(station.depth.reason), `${name} must expose ${station.depth.state} reason`);
      assert.ok(html.includes(measurementText(station.depth)), `${name} must expose actual value or dash`);
      if (station.depth.measuredAt) assert.ok(html.includes(station.depth.measuredAt), `${name} must expose actual measurement time`);
    }
  }
});


test('analytics never exports the short live snapshot as a database history report',()=>{
  monitoring={stations,loading:false};
  const html=renderToStaticMarkup(React.createElement(load(path.join(root,'components/Analytics.tsx')).default));
  assert.ok(html.includes('No report loaded'));
  // The separate live comparison may show a dated last-known value, but it
  // must not become a current bar or a downloadable database report.
  const comparison=html.match(/<section[^>]*aria-label="Current station comparison"[^>]*>([\s\S]*?)<\/section>/)[1];
  assert.ok(comparison.includes('105.0 cm'));
  assert.ok(comparison.includes('Last known'));
  assert.equal((comparison.match(/role="progressbar"/g)||[]).length,1);
  assert.ok(comparison.includes('aria-valuenow="0"'));
  for(const value of ['CURRENT WATER DEPTH','FLOOD EVENT','Rainfall journal'])assert.ok(html.includes(value));
  assert.ok(!html.includes('DOWNLOAD SELECTED SCOPE CSV'));
});
