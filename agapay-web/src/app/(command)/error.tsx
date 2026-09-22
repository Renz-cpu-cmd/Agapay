"use client";
export default function AccountError({ reset }: { reset: () => void }) {
  return <div className="p-8 text-sm" style={{ color: "#94a3b8" }}><p>The account service is unavailable. Check that the backend is running and try again.</p><button onClick={reset} className="mt-4 px-4 py-2" style={{ background: "#0ea5e9", color: "white" }}>Try again</button></div>;
}
