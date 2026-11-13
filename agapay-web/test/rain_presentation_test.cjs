// A8: the rain-gauge figure states coverage, calibration and origin from structured
// metadata; missing metadata is never presented as verified accuracy.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const load = require('./support/load-source.cjs');
const src = path.join(__dirname, '../src');
const { rainPresentation } = load(path.join(src, 'lib/rain-presentation.ts'));

const hash = 'c5eed6b3f6b820c6a77342c4e30b64cbd9c46657eec086e115b5fff590d7557b';
const product = (changes = {}) => ({ quality: 'partial', coverage_complete: false, tip_count: 50, mm_per_tip: 0.7, calibration_version: hash, ...changes });
const config = (validation_status, changes = {}) => ({ status: 'matched', validation_status, config_hash: hash, ...changes });

test('prototype: partial coverage, provisional conversion, not called manual readings', () => {
  const r = rainPresentation(product(), config('prototype'));
  assert.equal(r.title, 'Rain-gauge Activity');
  assert.equal(r.badge, 'Prototype');
  assert.equal(r.amountSuffix, 'mm rainfall-equivalent');
  assert.equal(r.tips, '50 recorded tips');
  assert.equal(r.coverage, 'Partial coverage');
  assert.equal(r.caveat, 'Provisional conversion: 0.7 mm/tip. Not calibrated against measured water. Prototype configuration: tips are not validated as measured rainfall.');
  assert.doesNotMatch(r.caveat, /manual|by hand|bench test reading/i);
  assert.equal(r.calibrated, false);
});

test('field review alone is not physical calibration', () => {
  const r = rainPresentation(product({ quality: 'complete', coverage_complete: true }), config('field_reviewed'));
  assert.deepEqual([r.title, r.badge, r.amountSuffix, r.calibrated], ['Rain-gauge Activity', 'Unvalidated', 'mm rainfall-equivalent', false]);
  assert.equal(r.calibration, 'Provisional conversion: 0.7 mm/tip. Not calibrated against measured water.');
  // The current backend contract only reports physical_validation "pending".
  assert.equal(rainPresentation(product(), config('field_reviewed'), 'pending').calibrated, false);
});

test('measured-water validation plus field review, match and same calibration: calibrated', () => {
  const r = rainPresentation(product({ quality: 'complete', coverage_complete: true }), config('field_reviewed'), 'validated');
  assert.deepEqual([r.title, r.badge, r.amountSuffix, r.coverage, r.origin, r.calibrated],
    ['Rainfall Activity', null, 'mm', 'Complete coverage', null, true]);
  assert.equal(r.calibration, 'Calibrated conversion: 0.7 mm/tip (measured-water validation).');
  // Physical validation never overrides a prototype or mismatched configuration.
  assert.equal(rainPresentation(product(), config('prototype'), 'validated').calibrated, false);
});

test('every incomplete or mismatched path stays provisional', () => {
  assert.equal(rainPresentation(product({ calibration_version: 'other' }), config('field_reviewed'), 'validated').calibrated, false);
  assert.equal(rainPresentation(product(), config('field_reviewed', { status: 'mismatch' }), 'validated').calibrated, false);
  assert.equal(rainPresentation(product({ calibration_version: null }), config('field_reviewed'), 'validated').calibrated, false);
  assert.equal(rainPresentation(product(), config('field_reviewed', { config_hash: null }), 'validated').calibrated, false);
  const unconfigured = rainPresentation(product(), null);
  assert.deepEqual([unconfigured.calibrated, unconfigured.badge, unconfigured.origin],
    [false, 'Unvalidated', 'Not confirmed as measured rainfall.']);
  const missing = rainPresentation(null, config('field_reviewed'));
  assert.deepEqual([missing.coverage, missing.tips, missing.calibrated], ['Coverage unknown', null, false]);
  assert.match(missing.calibration, /conversion unknown/);
  // A complete flag cannot override a partial quality.
  assert.equal(rainPresentation(product({ coverage_complete: true }), config('prototype')).coverage, 'Partial coverage');
});

test('the dashboard panel renders the caveat and passes station configuration', () => {
  const panel = fs.readFileSync(path.join(src, 'components/RainfallActivityPanel.tsx'), 'utf8');
  assert.ok(panel.includes('rainPresentation(') && panel.includes('data-testid="rain-caveat"') && panel.includes('rain.amountSuffix'));
  for (const file of ['components/Dashboard.tsx', 'components/Analytics.tsx']) {
    const text = fs.readFileSync(path.join(src, file), 'utf8');
    assert.ok(text.includes('configuration={') && text.includes('physicalValidation={'), file);
  }
});
