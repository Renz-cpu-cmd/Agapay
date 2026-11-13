/**
 * A8: rain-gauge card presentation (same rule as the mobile app). Coverage comes from the
 * rainfall product; the conversion is the configured mm/tip. Owner decision (2026-11-13): no
 * qualifier labels on screen. The internal `calibrated` flag still requires a measured-water
 * attestation on a field_reviewed, matched configuration with the same calibration hash.
 */
export type RainProduct = {
  quality?: string | null; coverage_complete?: boolean | null; tip_count?: number | null;
  mm_per_tip?: number | null; calibration_version?: string | null;
} | null | undefined;

export type RainConfiguration = {
  status?: string | null; validation_status?: string | null; config_hash?: string | null;
} | null | undefined;

export type RainPresentation = {
  title: string; badge: string | null; amountSuffix: string; coverage: string; tips: string | null;
  calibration: string; origin: string | null; calibrated: boolean; completeCoverage: boolean; caveat: string;
};

export function rainPresentation(product: RainProduct, configuration: RainConfiguration,
  physicalValidation?: string | null): RainPresentation {
  const status = configuration?.validation_status ?? null;
  const hash = configuration?.config_hash ?? null;
  const version = product?.calibration_version ?? null;
  const calibrated = physicalValidation === "validated" && status === "field_reviewed"
    && configuration?.status === "matched" && hash !== null && version !== null && version === hash;
  const completeCoverage = Boolean(product && product.coverage_complete === true && product.quality !== "partial");
  const mmPerTip = typeof product?.mm_per_tip === "number" && Number.isFinite(product.mm_per_tip) ? product.mm_per_tip : null;
  const tipCount = typeof product?.tip_count === "number" && Number.isFinite(product.tip_count) ? product.tip_count : null;
  const conversion = mmPerTip === null ? null : `${mmPerTip.toFixed(mmPerTip < 1 ? 1 : 2)} mm/tip`;
  // Owner decision (2026-11-13): no qualifier labels on screen. The configured mm/tip is the
  // gauge's manufacturer rating (owner-confirmed 0.7 mm/tip). `calibrated` stays internal.
  const calibration = conversion === null ? "Conversion unknown." : `Conversion: ${conversion}.`;
  const origin = null;
  return {
    title: "Rainfall Activity",
    badge: null,
    amountSuffix: "mm",
    coverage: !product ? "Coverage unknown" : completeCoverage ? "Complete coverage" : "Partial coverage",
    tips: tipCount === null ? null : `${tipCount} recorded tip${tipCount === 1 ? "" : "s"}`,
    calibration, origin, calibrated, completeCoverage,
    caveat: calibration,
  };
}
