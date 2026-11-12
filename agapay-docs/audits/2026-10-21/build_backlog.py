"""Derive the review backlog from the audited findings, without editing source."""
import csv
import re
from pathlib import Path

folder = Path(__file__).resolve().parent
report = (folder / "AGAPAY-END-TO-END-AUDIT.md").read_text(encoding="utf-8")
headings = list(re.finditer(r"^### (F\d{2}) — (.+)\n", report, re.MULTILINE))
rows = []
implementation_status = {finding: "Code implemented; live activation pending" for finding in ("F01", "F02", "F03", "F04", "F05", "F06")}
implementation_status.update({finding: "Code implemented; client rollout pending" for finding in ("F07", "F08")})
implementation_status.update({finding: "Code implemented; provisional policy and live activation pending" for finding in ("F09", "F10", "F11")})
implementation_status.update({finding: "Code implemented; coordinated rollout and physical validation pending" for finding in ("F12", "F14")})
implementation_status["F13"] = "Code implemented; provisional rate thresholds and physical validation pending"
implementation_status["F15"] = "Code implemented; coordinated journal and firmware rollout pending"
implementation_status["F16"] = "Software guards and bench tests implemented; P0 physical geometry and operator acceptance pending"
implementation_status["F17"] = "Code implemented; coordinated rollout and operator lifecycle review pending"
implementation_status["F18"] = "Code implemented; native OS and installed-device acceptance pending"
implementation_status["F19"] = "English-only policy implemented; geographic registry and client rollout pending"
implementation_status["F20"] = "Code implemented; SMTP, proxy, MFA and native deployment acceptance pending"
implementation_status["F21"] = "Code implemented; coordinated client rollout and audit database privileges pending"
implementation_status["F22"] = "Atomic SOS guards and SQLite races verified; PostgreSQL acceptance and client rollout pending"
implementation_status["F23"] = "Configurable response drill implemented; operational mode disabled pending LGU procedures and witnessed drill"
implementation_status["F24"] = "Authority registry and fallback implemented; verified live inventory and map/provider acceptance pending"
implementation_status["F25"] = "Encrypted reader cache and durable SOS outbox implemented; installed-device offline and storage acceptance pending"
implementation_status["F26"] = "Unified mobile observation/freshness view implemented; installed-device outage acceptance pending"
implementation_status["F27"] = "Release TLS, scoped broker ACLs and nonce CSP implemented; intended-network deployment and secret-rotation acceptance pending"
implementation_status["F28"] = "Bounded depth journal and historical ACK ingestion implemented; filesystem, endurance and device outage acceptance pending"
implementation_status["F29"] = "Explicit versioned migrations and SQLite copy preservation verified; managed PostgreSQL restore/cutover acceptance pending"
for heading in headings:
    end = report.find("\n##", heading.end())
    section = report[heading.end():end if end != -1 else len(report)]
    meta = re.search(r"Priority: (P\d) \| Evidence: (.+?) \| Owner: (.+?) \| Effort: (\w+) \| Phase: (\d)", section)
    change = re.search(r"\*\*Change:\*\* (.+?)(?=\n\n|\Z)", section, re.S)
    acceptance = re.search(r"\*\*Acceptance:\*\* (.+?)(?=\n\n|\Z)", section, re.S)
    assert meta and change and acceptance, heading.group(1)
    rows.append({
        "id": heading.group(1), "priority": meta.group(1), "title": heading.group(2),
        "evidence": meta.group(2), "owner": meta.group(3), "relative_effort": meta.group(4),
        "phase": meta.group(5), "status": implementation_status.get(heading.group(1), "Open - audit recommendation"),
        "recommended_change": change.group(1).replace("\n", " "),
        "acceptance_criteria": acceptance.group(1).replace("\n", " "),
        "report_section": "AGAPAY-END-TO-END-AUDIT.md :: " + heading.group(1),
    })
assert len(rows) == 40
assert len({r["id"] for r in rows}) == 40
with (folder / "prioritized-backlog.csv").open("w", encoding="utf-8-sig", newline="") as target:
    writer = csv.DictWriter(target, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print(f"Created {len(rows)} backlog entries")
for priority in sorted({r["priority"] for r in rows}):
    print(priority, sum(r["priority"] == priority for r in rows))
