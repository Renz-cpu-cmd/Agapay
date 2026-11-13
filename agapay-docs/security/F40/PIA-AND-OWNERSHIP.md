# PIA worksheet and service ownership record

Status: technical draft, not an approved privacy policy or legal determination. The review must include the responsible organization, privacy officer/reviewer, residents, response operators, infrastructure owner and actual processors. The [NPC guidance](https://privacy.gov.ph/5-pillars-of-compliance-2/) treats PIA as an ongoing assessment; deployment and material changes need renewed review.

## Scope and purposes

AGAPAY links resident account/contact data, area subscriptions, latest submitted SOS fixes, response/drill activity, delivery evidence and account security/audit information. Staff manage stations, resources, notices and model review on web; mobile is resident-only. Existing SOS response remains a configurable drill, not proof of accepted operational dispatch. Forecast availability/scientific approval and sensor calibration remain separate gates.

Review purposes/bases for each inventory row, necessity of exact coordinates/contact details, alternatives for residents who decline GPS/provider maps, visibility of staff names, vulnerable users and potential harm from location exposure, cross-border processors and actual storage regions. A simulation/default policy is not approval from an LGU or issuing authority.

## Preliminary risk register

| Risk / potential harm | Current treatment | Required organizational validation |
|---|---|---|
| Exact SOS location disclosed or used beyond response purpose | Owner/staff authorization, latest-fix model, explicit map action, closed-record retention, no raw location in privacy evidence | Jurisdiction/role tests with real operator duties; processor agreements/regions; resident comprehension |
| Abandoned account, email, phone or invitation retained indefinitely | Reviewed erasure cases; session/push revocation; expired identity-action maintenance | Inventory includes provider/log/export/PITR copies; approve justification and retention periods |
| Silent erasure over an unresolved request or justified hold | Active SOS/hold blocks erasure; version/CAS conflicts; offline bounded retention | Verify the actual hold grounds, reviewer, renewal process and resident explanations |
| Erased data reappears after restoring an old backup | Recovery quarantine; protected external withdrawal ledger required before release | Demonstrate ledger reapplication for post-snapshot cases and record residual retention decisions |
| Historical notifications/mail sent again after recovery | No pending replay; processing stays uncertain; tokens/sessions revoked; fences stop serving/delivery | Real provider-boundary drill without unsolicited resident messages; monitored reactivation procedure |
| Audit record leaks sensitive details or prevents justified minimization | Minimal privacy events; controlled, evidenced redaction exception preserving event metadata | Approve accountability retention and the exception, constrain free text, verify backup expiry |
| Service appears staffed/safe while nobody owns response or costs | Public unapproved state; production attestation gate; separate operational capability status | Name real accountable owners/hours/fallback contacts, budget/quota alerts and escalation coverage |
| Backup decrypts but complete service cannot recover | AES-GCM/checksums/row verification; preserved incident/ACK history; artifact/key escrow runbook | Managed PostgreSQL/PITR, key escrow, artifact hashes, mobile/provider re-registration, actual RPO/RTO |

Likelihood/impact scores and residual risk acceptance require stakeholder review; no fabricated score or approval is assigned here.

## Required decisions and evidence

| Decision | Development candidate / current state | Production approval evidence |
|---|---|---|
| Personal information controller/processor roles and privacy contact | Unassigned | Responsible entity/contact and reviewed notice/version |
| Issuing authority and staff jurisdiction | App prototype governance only | Actual mandate, area IDs, grants and authority lifecycle |
| Operator coverage, support and emergency fallback | No operational response hours committed | Real duty roster, hours, handoff, published fallback contacts and drill |
| Incident ownership/escalation and regulator/data-subject notification | Unassigned | Incident commander, privacy reviewer, internal escalation and confirmed applicable reporting procedures |
| RPO / RTO | Candidate 15 minutes / 4 hours | Measured full-service recovery against real data size, target infrastructure and key/artifact availability |
| Backup/PITR and key management | Candidate 30-day rolling retention; protected keys separate | Managed encryption/PITR schedule, billing owner, key escrow/rotation, expiry evidence and restore drill |
| Database, push, SMTP, Maps and cloud cost/quota ownership | Unassigned | Named responsible accounts, budgets, quota alarms, support access and vendor contracts |
| Retention and rights exceptions | Development 7/30-day closed SOS policy; reviewed holds | Approved purpose/justification, end-to-end external deletion and residual accountability policy |
| Access review | Versioned staff/MFA/authority inventory | Signed least-privilege review, disabled departed staff, MFA recovery drill and recorded snapshot/evidence hashes |
| Legal/privacy review | Pending | Approved PIA, notice, processor/transfer assessment and residual risk acceptance |

Copy the example attestation to a protected deployment location, fill it from actual decisions and retain the underlying evidence privately. Hashes are references, not signatures or certifications. Any changed policy hash or expired review blocks public production activation until the real record is reviewed again. The code cannot establish the truth of a supplied organizational attestation.
