import Link from "next/link";

export default function HybridDemoPage() {
  return <main style={{ height: "100dvh", display: "flex", flexDirection: "column", background: "var(--surface, #edf3f8)" }}>
    <nav aria-label="Projection navigation" style={{ padding: "12px 20px", display: "flex", gap: 20, background: "#122b43", color: "white", fontSize: 14 }}>
      <Link href="/dashboard" style={{ color: "white" }}>← AGAPAY dashboard</Link>
      <a href="/hybrid-demo/index.html" target="_blank" rel="noreferrer" style={{ color: "white" }}>Open in its own tab</a>
    </nav>
    <iframe title="AGAPAY hybrid water-depth projection" src="/hybrid-demo/index.html" style={{ flex: 1, width: "100%", border: 0 }} />
  </main>;
}
