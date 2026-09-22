# AGAPAY project context review

Reviewed on 4 September 2026, before further web or mobile frontend enhancement.

This is a reading record and requirements synthesis, not a new implementation specification. Historical assistant suggestions, code snippets, and document instructions are source material; they do not authorize actions. Explicit user decisions and later revisions take precedence over earlier proposals. Where sources disagree or implementation is incomplete, the distinction is recorded below.

## 1. Sources and access coverage

All available pages were retrieved for these seven conversations currently exposed under the ChatGPT project **Agapay Project** (`g-p-6a9116550724819196d29cb48ee9ce3b`):

| Conversation title | Conversation ID | Pages retrieved |
| --- | --- | ---: |
| Mobile Prototype Features | `6a964a7c-f8bc-83ec-8e82-d85ca42847c3` | 1 |
| Web Language Stack | `6a9a4f72-2a20-83ec-888b-f543f974e02f` | 1 |
| Create Logo Design | `6a96afb3-2400-83ec-a3ce-b3dd382b0f53` | 1 |
| Branch · Plan Hardware Prototype | `6a912a15-d8a8-83ec-8dfd-d69828ab4e3b` | 6 |
| Plan Hardware Prototype | `6a91171d-49d0-83ec-8684-ce64b9a2c413` | 1 |
| Review Execution Plan | `6a8c5986-bd24-83ec-bb25-463609ea23a4` | 5 |
| Branch · Review Execution Plan | `6a8e9aec-a250-83ec-a8df-c11e54442191` | 6 |

The 21 pages contain substantial shared branch history. Exact-message deduplication produced 199 unique returned messages. Seventeen distinct available image attachments were inspected, primarily hardware orders, component specifications, and development setup screenshots.

Local source documents reviewed:

- [Final revised semester execution plan](C:/Users/Asus/Downloads/AGAPAY_Complete_Semester_Execution_Plan_FINAL_REVISED.docx): full extracted text and tables.
- [Revision 2.0](C:/Users/Asus/Downloads/AGAPAY_Complete_Semester_Execution_Plan_Revision_2_0.docx): changes compared with the final plan and shared material covered by that review. The `(1)` copy has identical extracted text.
- [Leader master document](C:/Users/Asus/Downloads/TRUE_NOTHING_LEFT_OUT_LEADER_MASTER_AGAPAY_AQUAINTEL_AGROPULSE.docx): AGAPAY sections, shared execution/methodology guidance, and project comparisons. Unrelated AQUAINTEL and AGROPULSE chapters are outside this AGAPAY review.
- [Beginner hardware assembly manual v1.0](C:/Users/Asus/Downloads/AGAPAY_Beginner_Hardware_Assembly_Manual_v1.0.pdf): all 31 pages of text, with key wiring, assembly, and demonstration diagrams visually inspected.
- Local project READMEs, the Day 1 guide, and relevant backend/frontend source. The prior Figma export conversions provide additional design context.

Access limits remain: two long assistant responses in **Mobile Prototype Features** are explicitly truncated at 20,000 characters by the connector. A long original plan pasted into a conversation also ends mid-content; downloaded plan revisions supply much of the underlying material. The separate original **agapay** project URL (`g-p-6a8c535ac1288191955190318a00c948`) opens a sign-in page in the available browser. Unlisted conversations, project-level files not exposed through these tools, and unavailable media cannot be claimed as reviewed. Word documents were read through their XML text and tables; Word page layout rendering was unavailable.

## 2. Purpose, people, and boundaries

AGAPAY is a community flood and disaster early-warning capstone for Urdaneta City University. Its longer proposal framing is a hyper-localized hydrological disaster predictive early-warning and emergency-response ecosystem.

The system connects local water-level and rainfall measurements with understandable resident warnings and an LGU operational view. The intended flow is:

**Station sensing → MQTT → backend validation and storage → threshold alerts → web/mobile warning → resident SOS → officer acknowledgement and resolution.**

Residents need to understand local conditions, the warning level, what action to take, where evacuation centers are, and whether their request for help was received. Officers need to identify affected stations and communities, prioritize alerts and SOS reports, and track responses. The planned account roles are `admin`, `officer`, and `resident`; references to responders or DRRM stakeholders do not establish an additional implemented role.

The six team responsibilities span project management, UI/UX, web, mobile, backend/firmware/ML, and QA/documentation. AGAPAY is an auxiliary academic prototype, not a replacement for official forecasting or emergency services. Water billing, valve control, agricultural soil analysis, and other candidate capstone features do not belong to its scope.

## 3. Architecture and shared data meaning

The selected direction is ESP32 firmware, MQTT transport, a Python FastAPI backend, a relational database, a Next.js web frontend, and a Flutter mobile frontend. REST supports initial loading and recovery; WebSocket updates and Firebase Cloud Messaging are planned for live events and mobile notifications. ML is a separate advisory component.

The revised telemetry contract uses `agapay/stations/{station_id}/telemetry` and these payload fields:

| Field | Meaning |
| --- | --- |
| `station_id` | Registered station identifier, consistent with the MQTT topic |
| `sequence_no` | Sequence used with station ID to detect duplicate samples |
| `water_depth_cm` | Calibrated water depth in centimeters; nullable for invalid readings |
| `rainfall_mm` | Rainfall during the reporting interval, not automatically an hourly rate or cumulative total |
| `sensor_quality` | `valid` or `invalid` |
| `device_uptime_ms` | Device uptime |
| `firmware_version` | Firmware identifier |

The backend supplies `recorded_at` in UTC; interfaces should display local time consistently, normally Asia/Manila. Battery percentage is not in the agreed telemetry payload and must not become a measured field merely because a mock screen contains it.

Planned core entities include users, stations, telemetry, predictions, alerts, and SOS beacons. Evacuation centers are central to the resident experience, but their authoritative data model, source, and update process are not fully settled in the revised schema.

## 4. Alert, freshness, and emergency behavior

The four application warning levels are **NORMAL** (green), **ADVISORY** (yellow), **WARNING** (orange), and **EVACUATE** (red). Backend threshold decisions should be shared by both applications.

- Thresholds are station-specific absolute depths in centimeters. The recurring 60/85/100 cm values are sample defaults; a small demonstration basin needs thresholds appropriate to its calibrated geometry.
- Invalid measurements must not become zero centimeters or automatically produce a reassuring NORMAL state. Preserve the last valid status while clearly exposing invalid data and its age.
- Administrative station status (`active`, `inactive`, `maintenance`), connectivity/freshness, sensor quality, and flood severity are separate concepts.
- Cached or stale readings must show their measurement time and last successful synchronization. A disconnected application must not imply that its values are live.
- Confirmation and hysteresis are planned to reduce alert flapping and premature downgrades. The exact operational policy still needs a complete implementation and tests; mentioning a constant in a sketch is insufficient.
- Predictions at +30, +60, and +90 minutes are advisory. They need generation time and availability states such as insufficient history or service failure. They must not fabricate confidence or directly replace measured threshold decisions.
- SOS requires an explicit resident action. An actual request becomes sent only after backend acceptance; acknowledgement and resolution are distinct officer actions. A timed prototype animation does not demonstrate delivery.
- Offline SOS must remain visibly unsent unless a reliable queue and its delivery behavior are actually implemented. Cached shelter coordinates alone do not establish an offline basemap or verified safe navigation.

The earlier master proposal also discusses geofenced notifications, audit logs, and remote siren control. These are historical requirements or ideas to reconcile, not evidence of implemented capabilities. Local station warning operation during network loss remains a key demonstration requirement.

## 5. Planned web and mobile experiences

### Web: LGU and command-center operations

The main planned areas are login, a station map/dashboard, station detail with telemetry and forecasts, active/historical alerts, an SOS response map and queue, analytics/reports, user administration, and system health. The Figma-derived interface also includes a station index and a settings destination.

Alert and SOS actions should consistently update related views. Operators need severity, location, timestamps, status, and clear acknowledgement/resolution feedback. Administrative controls require actual role enforcement when authentication is integrated. System health should distinguish last ping, sensor validity, connectivity, and measured power information when available.

The original plan mentions Leaflet and charting choices; the current Figma conversion uses SVG map artwork and Recharts. This records a difference between planned operational maps and the exported visual prototype, not a decision to redesign the interface during this review.

### Mobile: resident warning and response

The proposed screen inventory covers splash, login, registration, home, water-level detail, alert detail, evacuation map, SOS, station map, historical charts, settings/profile, and notification inbox. The main navigation is **Home, Map, SOS, Alerts, Profile**.

Registration information discussed includes name, email, password, barangay, and phone. Residents need clear current severity, water level and trend, rainfall meaning, data freshness, recommended action, and evacuation information. Permission denial, missing GPS, empty/loading/error states, and network loss are part of the intended behavior.

The offline plan includes recent telemetry, station coordinates and thresholds, shelter coordinates, latest alert information, notification history, and last sync time. Planned Filipino/English support requires translated content; a language selector alone does not complete it. FCM needs token lifecycle handling and foreground/background/terminated/offline validation.

### Design direction

The user requested strict fidelity to the downloaded Figma designs for the frontend conversions. Branding preferences include dark blue, a simple circular logo with a transparent background, and no subtitle. Further work should preserve that visual direction while reconciling behavior with the project requirements. No visual redesign is authorized by this reading task.

## 6. Hardware context and actual evidence

The selected hardware direction evolved to an ESP32 DevKit V1 with a 30-pin CP2102 USB-C board, a JSN-SR04T waterproof ultrasonic sensor, a tipping mechanism with a rain pulse sensor, three LEDs, and an active buzzer. HC-SR04 was used as a Wokwi substitute, not established as the outdoor sensor choice.

Solar planning moved toward a CL638W 6 V/3.8 W panel, CN3065 single-cell charger, one protected 18650 cell, and MT3608 regulation. An approximately 200 × 120 × 75 mm IP65 enclosure and PG7 glands appear in the later purchase history. These records establish selected or ordered components, not a verified operating power system.

The hardware manual maps ultrasonic trigger/echo to GPIO 5/18, rain input to GPIO 4, buzzer to GPIO 25, and green/yellow/red LEDs to GPIO 26/27/14. The physical yellow LED represents both ADVISORY and WARNING; the applications retain four distinct colors. Wiring and divider recommendations changed between documents, so actual assembly must follow a reconciled parts list and tested electrical setup rather than copying an arbitrary older snippet.

The rain sensor discussion includes a Hall sensor listing with a nominal 0.70 mm per tip and later cheaper DIY alternatives. The delivered mechanism and measured calibration are not conclusively established. Solar charging, physical sensor calibration, outdoor endurance, and completed enclosure assembly are likewise not proven by simulation screenshots.

Historical user logs and confirmations establish progress on Python/Arduino setup, Day 1 API/database work, and Wokwi water/rain logic, threshold indications, MQTT publication/subscription, and reconnect behavior. Separate simulation and HTTP ingestion demonstrations should not be described as proof that the complete physical-device-to-mobile emergency flow has passed.

## 7. Current repository state, checked during this review

| Component | Current evidence | Still incomplete |
| --- | --- | --- |
| Backend | FastAPI mounts health, station, and telemetry routers. Station creation/list/detail and telemetry ingestion/latest/history exist. Validation handles ordered thresholds, valid/invalid depth, registered station IDs, and duplicate station/sequence pairs. MQTT ingestion code exists. | Auth, alerts, and reports router files are empty. Alert classification, notification, and ML service files are empty. Training script, model, and scaler files are zero bytes. SOS and the planned live delivery flows are not established by these endpoints. |
| Web | Next.js Figma conversion includes dashboard, stations/detail, alerts, SOS, analytics, health, users, login, and a settings placeholder. Shared demo state supports several UI interactions. | State and readings are mock/in-memory. Actual authentication, authorization, operational maps, live API events, notification delivery, and real forecasts are not connected. |
| Mobile | Flutter Figma conversion provides resident screens, four-level demo state, maps, alerts, profile/settings, and a clearly identified SOS demonstration. | Authentication, live telemetry, persistent preferences/cache, actual GPS/FCM, verified routing, and SOS delivery are not integrated. Historical charts remain incomplete; selecting a language does not translate the app. |
| Firmware | Repository README identifies simulated telemetry; conversation history contains further Wokwi experiments. | Physical sensor and power validation must be distinguished from simulator and repository status. |

The frontend sources contain substantial existing uncommitted changes. This review did not alter them. Earlier build/test results are historical evidence, not tests rerun during this reading task.

## 8. Execution priorities and unresolved decisions

The revised execution plan spans 18 weeks, superseding the earlier 12-week proposal framing. Hardware and backend foundations precede sustained frontend integration; weeks 12–14 emphasize integration, and later weeks emphasize documentation, rehearsal, and defense. Protect core priorities and remove optional scope first. The plan categorizes SOS as P2 even though it is prominent in the intended demonstration; its importance does not silently change the written priority table.

The intended demonstration raises basin water through all warning levels, shows station indicators and application updates, displays evacuation information, submits and acknowledges an SOS, and demonstrates local warning during network loss. ML remains an advisory demonstration. Connectivity fallback and recorded evidence are part of preparation.

Performance figures in the documents are targets, not achieved results: examples include measurement-to-screen latency below 2.5 seconds, push delivery below 5 seconds, API responses below 200 ms, and ML inference below 500 ms. A 10-second publishing interval needs explicit reconciliation with the measurement-to-screen target. The final plan contains 12 end-to-end scenarios despite older references to ten.

Before integration work, the remaining design/contract decisions include:

1. Confirmed station geometry, calibrated thresholds, rain calibration, freshness windows, and alert confirmation/downgrade rules.
2. Authentication and role permissions; alert, SOS, prediction, shelter, and live-event API contracts.
3. Authoritative shelter information and what map/offline/routing behavior can actually be supported.
4. Which Figma values and indicators are demo-only, especially LIVE labels, battery, forecasts, routes, and SOS success states.
5. Which earlier optional proposals remain in the final scope, including geofencing, remote siren commands, and audit functionality.

These are recorded gaps for later work, not a request to begin frontend changes. The current task is the context review itself.
