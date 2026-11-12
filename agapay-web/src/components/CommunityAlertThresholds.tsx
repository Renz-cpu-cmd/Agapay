import type { Station } from "@/data/mockData";

const tiers = [
  { key: "normal", label: "Normal", color: "var(--adaptive-success, #57ff7b)", height: 73, guidance: "Below configured sensor advisory threshold; local hazards may remain" },
  { key: "advisory", label: "Advisory", color: "var(--adaptive-warning, #ffe57b)", height: 148, guidance: "Sensor advisory; monitor official local updates" },
  { key: "warning", label: "Warning", color: "var(--adaptive-orange, #ffb06b)", height: 219, guidance: "Sensor warning; prepare and check local authority guidance" },
  { key: "evacuate", label: "Evacuate", color: "var(--adaptive-danger, #ff5d5d)", height: 263, guidance: "EVACUATE-level sensor alert; follow local authority instructions" },
] as const;

export default function CommunityAlertThresholds({ station }: { station: Station }) {
  const { advisory, warning, evacuate } = station.thresholds;
  const sourceLabel = station.dataSource === "simulator" ? "Virtual station" : station.dataSource === "device" ? "Configured station" : "Unverified source";
  const ranges = {
    normal: `< ${advisory} cm`,
    advisory: `${advisory}–<${warning} cm`,
    warning: `${warning}–<${evacuate} cm`,
    evacuate: `≥ ${evacuate} cm`,
  };

  return (
    <section
      aria-labelledby="community-threshold-title"
      className="shrink-0 px-4 pt-[22px] pb-5"
      style={{ background: "var(--adaptive-surface, #00112e)", border: "1px solid #004aba", borderRadius: 10 }}
    >
      <h2 id="community-threshold-title" className="text-center text-[13px] font-medium leading-[17px]" style={{ color: "var(--adaptive-blue, #60a5fa)" }}>
        Sensor Observation Thresholds
      </h2>
      <p className="mt-1 text-center text-[11px] leading-[14px]" style={{ color: "var(--adaptive-muted, #94a3b8)" }}>
        {sourceLabel} thresholds · {station.id}. Sensor tiers are not official evacuation orders. Forecasts are experimental and shown separately.
      </p>

      <p className="subtle-note">Policy: {station.hazardPolicyState ?? "provisional"} · Observation: {station.observationTier ?? "UNKNOWN"} · Episode: {station.activeHazardTier ?? "None"} · {station.hazardDecision ?? "No policy decision yet"}</p>
      <div className="mt-[18px] grid h-[263px] grid-cols-[92px_minmax(0,1fr)] gap-2.5">
        <dl className="grid grid-rows-[44px_57px_68px_1fr]">
          {[...tiers].reverse().map((tier) => (
            <div key={tier.key}>
              <dt className="flex items-center gap-1.5 text-xs font-semibold leading-4" style={{ color: tier.color }}>
                <img src={`/figma/alert-thresholds/${tier.key}.svg`} alt="" width={6} height={6} className="size-1.5 shrink-0" />
                {tier.label}
              </dt>
              <dd className="mt-0.5 pl-3 text-[11px] leading-[14px] text-white">{ranges[tier.key]}</dd>
            </div>
          ))}
        </dl>
        {/* The Figma bars illustrate tier order; the labels give the water-depth ranges. */}
        <div aria-hidden="true" className="flex items-end justify-between">
          {tiers.map((tier) => (
            <div key={tier.key} className="w-[17px] rounded-[5px]" style={{ height: tier.height, background: tier.color }} />
          ))}
        </div>
      </div>

      <img src="/figma/alert-thresholds/divider.svg" alt="" width={221} height={1} className="mt-[14px] h-px w-full" />
      <ul className="mt-2.5 flex flex-col gap-2.5">
        {tiers.map((tier) => (
          <li key={tier.key} className="flex items-center gap-2.5 text-[11px] leading-4" style={{ color: "var(--adaptive-text, #d5dce6)" }}>
            <img src={`/figma/alert-thresholds/${tier.key}.svg`} alt="" width={6} height={6} className="size-1.5 shrink-0" />
            <span><span className="sr-only">{tier.label}: </span>{tier.guidance}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
