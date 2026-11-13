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

// Owner decision (2026-11-13): no qualifier labels on the rain card; the configured
// 0.7 mm/tip is the gauge's manufacturer rating. `calibrated` stays an internal flag.
test('prototype: plain rainfall card with tips, coverage and conversion', () => {
  const r = rainPresentation(product(), config('prototype'));
  assert.deepEqual([r.title, r.badge, r.amountSuffix, r.origin], ['Rainfall Activity', null, 'mm', null]);
  assert.equal(r.tips, '50 recorded tips');
  assert.equal(r.coverage, 'Partial coverage');
  assert.equal(r.caveat, 'Conversion: 0.7 mm/tip.');
  assert.equal(r.calibrated, false);
  for (const text of [r.title, r.amountSuffix, r.calibration, r.caveat]) {
    assert.doesNotMatch(text, /calibrat|prototype|bench|unvalidated|equivalent|re-checked/i);
  }
});

test('calibrated flag still requires measured-water validation', () => {
  assert.equal(rainPresentation(product(), config('field_reviewed')).calibrated, false);
  assert.equal(rainPresentation(product(), config('field_reviewed'), 'pending').calibrated, false);
  const r = rainPresentation(product({ quality: 'complete', coverage_complete: true }), config('field_reviewed'), 'validated');
  assert.deepEqual([r.title, r.badge, r.amountSuffix, r.coverage, r.calibration, r.calibrated],
    ['Rainfall Activity', null, 'mm', 'Complete coverage', 'Conversion: 0.7 mm/tip.', true]);
  assert.equal(rainPresentation(product(), config('prototype'), 'validated').calibrated, false);
  assert.equal(rainPresentation(product({ calibration_version: 'other' }), config('field_reviewed'), 'validated').calibrated, false);
  assert.equal(rainPresentation(product(), config('field_reviewed', { status: 'mismatch' }), 'validated').calibrated, false);
  assert.equal(rainPresentation(product({ calibration_version: null }), config('field_reviewed'), 'validated').calibrated, false);
  assert.equal(rainPresentation(product(), config('field_reviewed', { config_hash: null }), 'validated').calibrated, false);
});

test('missing configuration or product never invents a figure', () => {
  const unconfigured = rainPresentation(product(), null);
  assert.deepEqual([unconfigured.calibrated, unconfigured.badge, unconfigured.origin], [false, null, null]);
  const missing = rainPresentation(null, config('field_reviewed'));
  assert.deepEqual([missing.coverage, missing.tips, missing.calibrated, missing.calibration], ['Coverage unknown', null, false, 'Conversion unknown.']);
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
