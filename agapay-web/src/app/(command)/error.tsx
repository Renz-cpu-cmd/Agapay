"use client";
export default function PageError({ retry }: { retry: () => void }) {
  return <div className="p-8 text-sm" style={{ color: "var(--adaptive-text, #94a3b8)" }}><p role="alert">This page could not load. Try again to reload its data.</p><button onClick={retry} className="design-button mt-4" style={{ background: "#174f91", color: "white" }}>Try again</button></div>;
}
