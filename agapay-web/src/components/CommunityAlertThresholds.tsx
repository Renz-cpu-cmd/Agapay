import type { Station } from "@/data/mockData";

const tiers = [
  { key: "normal", label: "Normal", color: "#57ff7b", height: 73, guidance: "Safe, routine flow" },
  { key: "advisory", label: "Advisory", color: "#ffe57b", height: 148, guidance: "Caution, rising waters" },
  { key: "warning", label: "Warning", color: "#ffb06b", height: 219, guidance: "Standby for evacuation" },
  { key: "evacuate", label: "Evacuate", color: "#ff5d5d", height: 263, guidance: "Mandatory evacuation" },
] as const;

export default function CommunityAlertThresholds({ station }: { station: Station }) {
  const { advisory, warning, evacuate } = station.thresholds;
  const sourceLabel = station.dataSource === "simulator" ? "Virtual station" : station.dataSource === "device" ? "Configured station" : "Demo";
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
      style={{ background: "#00112e", border: "1px solid #004aba", borderRadius: 10 }}
    >
      <h2 id="community-threshold-title" className="text-center text-[13px] font-medium leading-[17px]" style={{ color: "#60a5fa" }}>
        Community Alert Threshold Tiers
      </h2>
      <p className="mt-1 text-center text-[11px] leading-[14px]" style={{ color: "#94a3b8" }}>
        {sourceLabel} thresholds · {station.id}
      </p>

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
          <li key={tier.key} className="flex items-center gap-2.5 text-[11px] leading-4" style={{ color: "#d5dce6" }}>
            <img src={`/figma/alert-thresholds/${tier.key}.svg`} alt="" width={6} height={6} className="size-1.5 shrink-0" />
            <span><span className="sr-only">{tier.label}: </span>{tier.guidance}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
