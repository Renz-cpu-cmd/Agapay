# Operational hierarchy and accessibility acceptance matrix

Target: WCAG 2.2 AA for web plus practical 48 logical-pixel mobile controls. This is a verification plan and scoped software evidence, not a declaration of compliance.

## Shared operational hierarchy

1. Establish current area/station and whether observations are unknown, invalid, retained/stale or current. Show the original timestamp, source and quality; heartbeat freshness never substitutes for measurement age.
2. Present the currently recorded sensor episode and its unresolved/recovery status, separately from an authority-issued notice. Official notices require issuer, area, effective time, expiry and correction/cancellation history.
3. Offer the relevant recorded action: view instructions/contact/shelter information or enter the clearly labeled SOS drill. Queued is not received, acknowledged is not dispatched, and a generic route is not proven flood-safe.
4. Present published forecasts with identity, cutoff, uncertainty and expiry after observations/action context. Private model experiments and exercise controls remain separate; protected mobile builds hide exercise entry.
5. Put trend detail and engineering provenance after critical context. Expandable timestamped chart data provides an alternative to the drawing; source/configuration detail must not obscure current status or action.

## Matrix

Use every theme and both current/unknown/stale/invalid states. Record tester, assistive technology/version, device/browser, viewport/text scale, release/revision, result, evidence and remediation issue. Only an observed result closes a row.

| Flow/control | Automated evidence | Required manual evidence |
|---|---|---|
| Published forecast/history/outage | Production Chromium fixture workflow, both-theme axe, zero distinct from missing, revoked/history display | NVDA/JAWS + browser reading order; meaningful caption/header associations and interval comprehension |
| Main navigation | Skip link, visible focus rules, keyboard entry, scrolling narrow navigation | Keyboard-only every page, focus never hidden behind panels; all actions reachable at 400% zoom/320 CSS px |
| Dialogs | Logout Tab trap, Escape and trigger focus return | All dialogs/error dialogs, Shift+Tab, focus after validation failure; no inaccessible background interaction |
| Home observation/source | Existing unknown/zero/invalid/stale contracts plus narrow/large-text widget flows | TalkBack/VoiceOver accurately state station, retained age, quality and unresolved hazard without color |
| Mobile charts | Elapsed-time coordinate checks, duplicate/reordered timing rejected, timestamp text rows, null vs zero, gap disconnection implementation | Reader navigates every point/time/unit; identify a long outage without assuming a flat trend |
| Text/contrast | Shared palette and semantic token 4.5:1 assertions in both themes; web axe tested state | Real rendered contrast for every message/control and selected/disabled/error state, 3:1 non-text boundaries as applicable; platform font/bold/high-contrast settings |
| Touch controls | Padded Material targets, larger home/back controls and target size assertions | Effective 48px mobile targets, switch access, one-handed use; web 24px AA rule/exceptions measured on all controls |
| Responsive text | 320px/200% widget scenarios; narrow enlarged browser page | All critical screens at 200% and device maximum text, landscape, keyboard open and 400% web zoom; no hidden instructions or clipped actions |
| Reduced motion | CSS motion disabled; native SOS pulse respects OS setting | OS reduced-motion/animation setting, no flashing hazard or essential status loss |
| SOS/outbox | Existing idempotency/offline/lifecycle contract tests | Reader announces queued/received/unknown distinctly, contact fallback usable offline, confirm/resolution dialogs understood |
| Maps unavailable | Shared freshness and station/shelter list fallback | GPS denied, quota exhausted and no network; complete task from text/contacts without map |
| Authentication/settings | Existing account/preferences tests | Password manager/autofill, visible error association, permission and app preference distinction |

## Resident/officer comprehension drill (pending)

Recruit representative residents and officers, including older users and assistive-technology users. Use synthetic, clearly labeled scenarios and no external emergency dispatch. Ask each person to: identify whether a station is current; date a retained reading; distinguish a sensor tier from an official order; locate a verified shelter/contact during a map outage; inspect a queued SOS without claiming receipt; and explain uncertainty/expiry on a forecast.

Record task completion time, errors, assistance, exact misinterpretations and participant feedback. Set acceptance budgets with the responsible organization, remediate critical misunderstandings, and repeat the failed tasks. No user trial or TalkBack/VoiceOver run was performed by the automated test suite.
