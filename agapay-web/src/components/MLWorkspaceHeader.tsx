import Link from "next/link";

export default function MLWorkspaceHeader({ page }: { page: "configuration" | "evaluation" | "published" }) {
  return <>
    <header className="ml-page-heading">
      <div><span className="ml-eyebrow">{page === "configuration" ? "PROJECTIONS" : page === "evaluation" ? "MODEL REGISTRY & REVIEWED CHANGES" : "PUBLISHED FORECAST EVIDENCE"}</span><h2>{page === "configuration" ? "Projections" : page === "evaluation" ? "Model evaluation" : "Published forecasts"}</h2><p>{page === "configuration" ? "Private basin settings never change the published resident forecast." : page === "evaluation" ? "Compare model evidence and review versioned station bindings." : "Reviewed products, measurement coverage, uncertainty and deployed evaluation."}</p></div>
    </header>
    <nav className="ml-tabs" aria-label="Machine learning workspace">
      <Link href="/ml-configuration" aria-current={page === "configuration" ? "page" : undefined}>Configuration</Link>
      <Link href="/ml-evaluation" aria-current={page === "evaluation" ? "page" : undefined}>Evaluation</Link>
      <Link href="/forecasts" aria-current={page === "published" ? "page" : undefined}>Published forecasts</Link>
    </nav>
  </>;
}
