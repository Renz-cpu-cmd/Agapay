# AGAPAY Web

Next.js frontend rebuilt against the 14 screen and dialog frames on the [Agapay_Website Figma page](https://www.figma.com/design/YSzodsskD44OjBCaCyBHau/Agapay?node-id=112-47). The interface uses the design's black canvas, navy panels, blue borders, Inter typography, compact navigation, and locally exported logo, icons, and map artwork. Existing account, practice SOS, and prediction API integrations are preserved.

## Run locally

Requires Node.js 20.9 or newer.

```sh
npm install
npm run dev
```

Open http://localhost:3000. Login requires an active administrator or officer account from FastAPI. With the backend running, use **Create administrator account** or `/register` for first-time local setup. The form provides password confirmation and Show/Hide controls, then signs you in automatically. Registration closes after setup; additional staff are created through **Users → Add User**. See [Accounts setup](../agapay-docs/ACCOUNTS_SETUP.md). There are no prefilled demo credentials.

```sh
npm run build
npm start
npm run typecheck
```

## Screens

- `/login` — supplied sign-in screen
- `/register` — one-time local administrator registration; disabled in production
- `/dashboard` — monitoring summary, station map, alert queue, water-level chart
- `/stations` and `/stations/STATION_001` — station cards and directly addressable details
- `/alerts` — active/historical filters, manual alert creation and resolution
- `/sos` — beacon list, details, acknowledgment and resolution
- `/analytics` — station/period controls, charts and CSV report download
- `/system-health` — connectivity and stale sensor data
- `/users` — search, role filters, create/edit users and activation controls
- `/settings` — account overview, profile/password editing, preferences, information dialogs, and logout confirmation

## Frontend scope

Monitoring pages poll the authenticated backend snapshot every five seconds. A
simulator feed displays VIRTUAL STATION, physical-device telemetry displays LIVE,
and the UI reports no data or connection failures without turning them into a normal
flood reading. Dashboard charts, station details, maps, system health, automatic
sensor alerts, analytics history, interval rainfall, and CSV reports use the received
telemetry. The bundled records are shown only while the API is unavailable and are
marked DEMO. SOS continues to display PRACTICE. The dashboard opens with Google's photorealistic 3D view centered on Urdaneta City and provides a matching dark vector view with terrain/satellite/hybrid modes, Street View, fullscreen, and touchpad gestures. Staff SOS details use the same Google Maps JavaScript integration to display submitted resident coordinates. The header clock shows current Philippine time.

The dashboard includes the Community Alert Threshold Tiers panel and a map with pan, zoom, reset, and station selection. A station is plotted only when the backend supplies latitude and longitude. `STATION_001` is the planned UCU Irrigation Canal Station using the channel mapped across Urdaneta City University's northern frontage. Its precise installation point still needs an on-site survey. Hardware is needed for field measurements; the [virtual-station guide](../agapay-docs/TELEMETRY_SIMULATOR.md) exercises the complete software path now.

Google Maps loads only when `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` is configured. `NEXT_PUBLIC_GOOGLE_MAP_ID` defaults to Google's development map ID and should be replaced with a restricted production vector map ID later. The key is necessarily browser-visible and must be restricted to the Maps JavaScript API and approved website origins. A loading or authentication failure shows a retry control and an external Google Maps link. The dashboard does not request device geolocation. An SOS map sends the submitted coordinates to Google only after staff choose to display that map. See the [Google Maps loader](https://developers.google.com/maps/documentation/javascript/load-maps-js-api) and [WebGL map guide](https://developers.google.com/maps/documentation/javascript/webgl).

Station forecasts use the authenticated [prediction API](../agapay-docs/PREDICTION_INTERFACE.md). Actual mode currently shows Model not trained; development previews explicitly label sample values. The panel handles unavailable, stale, invalid and expired results without retaining numeric forecasts. Forecasts do not change alert tiers.

Manual alert changes remain in `src/context/DemoContext.tsx` and reset on reload;
sensor-derived alerts come from the monitoring snapshot. Accounts, profiles and practice SOS persist through the backend. `SosContext` polls saved requests and server counts; officers acknowledge and resolve requests with an audit timeline. SOS location details can open an online coordinate map. See [Practice SOS setup](../agapay-docs/SOS_SETUP.md). Protected pages require staff sessions; user management additionally requires administrator access. The web session uses an HttpOnly cookie through same-origin API handlers. Push notifications and operational response mapping remain separate integration work.

Google sign-in and push delivery are not configured. Their controls explain availability instead of simulating a successful connection. Location sharing is managed in the resident mobile app; the website currently supports English. About, privacy, and terms dialogs describe the prototype and are not published operational policies.

Fonts load from Google Fonts as in the export. The command-center layout targets desktop widths of 1024px or greater. The sidebar and header stay fixed while the main content area scrolls vertically; narrower windows can scroll the content horizontally. Sidebar links become more compact in short windows so Settings and Logout remain visible. Changing routes resets the content scroll position.

## Structure

- `src/app` — Next.js App Router layouts and route entries
- `src/components` — Figma screens adapted to client components with shared dialogs in `DesignUI.tsx`
- `src/index.css` and `src/figma.css` — design tokens, typography, Tailwind CSS, screen layouts, and viewport adjustments
- `src/lib/figma-assets.ts` and `public/figma/website` — locally stored Figma assets
- `src/components/StationMap.tsx`, `GooglePhotorealisticMapCanvas.tsx`, `GoogleStationMapCanvas.tsx`, `GoogleSosLocationMap.tsx`, `src/lib/google-maps.ts`, and `src/lib/station-map.ts` — Google photorealistic 3D, dark station and SOS maps, coordinate validation, controls, and loading state
- `src/context` — signed-in account, backend monitoring, practice SOS, and manual demo-alert state
- `src/lib/account-server.ts` — backend access and page authorization
- `src/app/api/account` — session cookie, account, staff SOS and prediction API handlers
- `src/components/ForecastPanel.tsx` — forecast availability, expiry and sample previews
- `src/hooks/useDialog.ts` — dialog keyboard focus and Escape handling
- `src/lib/navigation.ts` — route mapping

The ZIP's Figma-specific scripts, tool configuration, and instruction documents were not imported or executed. Vite entry points were replaced with Next.js. The latest visual reference is the Agapay_Website Figma page rather than the original ZIP alone.

## Rebuild verification

The production build and headless Edge browser checks passed on September 5, 2026. Checks covered all main screens, dialogs, profile saves, manual alert creation/resolution, practice SOS acknowledgement/resolution, submitted map coordinates, filtered CSV downloads, station forecasts, user creation/deactivation, logout, and officer route restrictions. Desktop layouts were checked at widths of 1440, 1366, and 1024 pixels. Account and SOS mutations used a separate temporary database; existing user records were not used for the tests. Temporary servers, database, and credentials were removed afterward. Google map dragging, zooming, reset, station selection, 3D/dark mode changes, resizing, page scrolling, and repeated map navigation were also checked successfully.
