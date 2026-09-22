# AGAPAY practice SOS

The SOS flow runs locally with FastAPI, SQLite, Next.js and Flutter. No Supabase,
Firebase, cloud hosting, or assembled sensor hardware is needed. Google map previews
use a prototype Maps Demo Key; descriptions and coordinates remain available if its
quota is unavailable.
AGAPAY accounts are still required when using the screens: residents submit from
mobile; officers and administrators review on web.

## Try the flow

Start the backend and web using [Accounts setup](ACCOUNTS_SETUP.md). Open
<http://localhost:3000/register> to create your first administrator in the browser.
The form includes password confirmation and a Show passwords control. Terminal
setup remains optional. After registration you are signed in automatically.

You can use that administrator for practice SOS review,
or create an officer from **Users**. Register a resident in the mobile app.
Temporary QA accounts used during implementation were kept in a separate database
and are not accounts for normal use.

1. Open **SOS** on mobile and tap the large SOS button.
2. Enter a practice location or landmark and an optional scenario message.
3. Optionally choose **Use my device location**, or enter both latitude and longitude
   manually. Coordinates are optional; a location description is required. With a
   device fix, choose whether to keep sharing foreground location while the SOS is open.
4. Review the details and tap **Send practice SOS**. **Request received** appears only
   after the API saves the request and returns its reference.
5. Open **SOS Beacons** on web. The queue and an open request map refresh about every
   five seconds, including the latest foreground GPS fix when sharing is active.
6. Open the request, inspect its details, and choose **Acknowledge**.
7. Mobile shows the acknowledgement and the staff member's name and timestamp.
8. On web, add an optional resolution note and choose **Mark resolved**. The mobile
   timeline updates. Reopening either app preserves the saved request and history.

All requests are forcibly marked **practice** by the backend. There is no live-mode
switch. This implementation does not call, text, push notifications, dispatch a team,
or track responders. Acknowledgement means a signed-in staff member changed the saved
status. It does not confirm dispatch or arrival. Use fictional practice scenarios.

## Location and connectivity

Device location starts with a foreground capture initiated by the resident. If the
resident enables the switch before sending, mobile uploads a new fix after movement
while the app remains in the foreground and the SOS is active or acknowledged. The
resident can stop sharing, app backgrounding pauses it, and resolution ends it.
Android uses coarse/fine location permissions; iOS uses when-in-use permission with
CocoaPods configured to exclude always-location permission. No background location
is requested.
If permission is denied, location services are off, or capture times out, the resident
can enter a description and optional coordinates. Captured location is included only
after confirming submission. GPS accuracy and capture time come from the device;
manual coordinates never claim GPS accuracy. New GPS submissions older than ten
minutes or more than one minute ahead of server time are rejected for correction.
Foreground updates must be no more than two minutes old. The API rejects out-of-order
fixes so a delayed request cannot replace a newer resident position.

The staff detail screen and mobile SOS detail screen load an online Google map for
submitted coordinates. The description and coordinates remain readable without map
access. Map coordinates are sent to Google when the preview or external map link is
opened. It is not an offline map.

The mobile **Evacuation Map** uses the shared Google JavaScript WebView and shows the
resident's captured GPS position and UCU Gym. Its dark vector style and map controls
match the staff website. Urdaneta City's 2017 ecological profile lists UCU Gym as an
evacuation-use facility and marks the UCNHS Oval as not used for evacuation. The pin
uses the UCU campus coordinate, so residents must confirm current shelter activation
and the safe entrance with CDRRMO. The in-app cyan path is computed by Google for
walking from the resident's latest GPS fix, and its returned distance and duration are
shown below the map. **Open walking directions** hands the same origin and destination
to the device's map app for navigation. Refreshing the device location recalculates the
route. The monitoring view loads only backend stations that have coordinates and uses
their latest valid telemetry; fabricated station pins are not shown.

The device location plugin requires a secure browser context (HTTPS or a browser's
trusted localhost exception). On a physical phone, `127.0.0.1` points to the phone;
use a reachable backend address and configure CORS for a browser preview. Native
release builds require HTTPS. Android debug defaults to emulator host `10.0.2.2:8000`.
See the [Geolocator package documentation](https://pub.dev/packages/geolocator/versions/14.0.2)
and [Maps Demo Key documentation](https://developers.google.com/maps/demo-key).

## Failure and retry behavior

- Before transmitting, mobile stores the immutable payload and random request
  reference in secure storage under the resident's account ID.
- If no successful response arrives, the screen says **Receipt unconfirmed** and
  retains that reference. This covers a request that reached the server but whose
  response was lost. It never claims that a failed HTTP exchange proves non-delivery.
- **Retry same request** resends the original details and reference. The API returns
  the existing saved request if that reference already succeeded. Different details
  with the same reference produce a conflict.
- Reopening the app restores the pending reference. A history refresh can reconcile
  it with a saved record. Retrying also works if the record is older than the loaded
  history. There is no automatic offline delivery queue.
- Explicit validation/permission rejection allows corrected details when the saved
  reference can be cleared. A storage failure before transmission prevents sending.
- Once transmission starts, the screen cannot pretend to cancel it. Switching tabs
  preserves in-flight state. Logout clears displayed account data; pending references
  stay scoped to their original account so that resident can recover later.
- Failed refreshes preserve last-known data and show an error and last-sync time.

## API contract

Every endpoint requires an active bearer session and returns `Cache-Control: no-store`.
Web accesses these through its existing HttpOnly-cookie proxy at `/api/account/sos`.

| Method | Endpoint | Access / behavior |
| --- | --- | --- |
| POST | `/api/sos` | Resident only. Creates a practice request; 201 new, 200 identical retry. |
| GET | `/api/sos?status=ACTIVE&limit=50&offset=0` | Resident sees own requests; staff sees all. Status optional; limit 1–100. |
| GET | `/api/sos/{id}` | Owner or staff; other residents receive 404. |
| PATCH | `/api/sos/{id}/location` | Owner only while unresolved. Saves a fresh, newer GPS fix. |
| PATCH | `/api/sos/{id}` | Staff only. `ACTIVE → ACKNOWLEDGED → RESOLVED`. |

Create body: UUID `request_id`, `location` (3–300 characters), optional `message`
(up to 1,000), paired nullable `latitude`/`longitude`, `location_source` (`manual` or
`gps`), and GPS-only `accuracy_m`/timezone-aware `location_recorded_at`.
Resident identity, phone, barangay, practice flag, status, and receive time are set
by the server. The request keeps a snapshot of contact details at submission.

List responses contain `items`, filtered `total`, and `counts` for all three statuses
within the caller's access scope. Both clients load history in pages of 50. Web
dashboard/sidebar counts come from the backend totals, not just the visible rows.

Update body: `status` (`ACKNOWLEDGED` or `RESOLVED`) and optional `resolution_note`
(up to 500 characters). Transitions use conditional database updates to avoid two
officers overwriting the original actor/time. Repeating the current transition
returns its original record. Resolving before acknowledgement or going backwards
returns 409. Records retain received, acknowledged and resolved timestamps and actors.

Location-update body: `latitude`, `longitude`, `accuracy_m`, and timezone-aware
`location_recorded_at`. The server sets `location_source` to `gps`; identity, status,
and location description cannot be changed through this endpoint.

## Storage and deployment scope

`sos_requests` is added by the existing development `create_all` startup. Existing
accounts and telemetry tables are retained. New installations need no migration
command for this table. Schema versioning with Alembic, production access policy,
retention policy, operational dispatch and notifications remain deployment work.
The current staff scope covers all practice requests; barangay-specific staff
permissions have not been implemented.

The local SQLite file and pending mobile payload contain contact/location information.
Do not commit them. This feature is a development practice workflow, not an emergency
service ready for public use. Sensor readings, flood alerts and forecasts elsewhere
in the frontend still use the existing demonstration data.

## Verification

- Backend suite: 64 passing tests covering accounts, telemetry, SOS access, validation,
  retry deduplication, identity snapshots, audit transitions, filters and revocation.
- Flutter suite: 19 passing tests including delayed/failed sending, identical retry
  after controller restart, lost-response reconciliation, stale reads, account
  separation, status updates and narrow-phone layouts.
- Next.js production build and TypeScript checks passed.
- Browser exercise used isolated temporary accounts: mobile submission → web queue
  and coordinate map → acknowledgement → resolution with note → mobile timeline.
- Android debug APK was installed on an API 36 emulator and the Google map, real GPS
  marker, UCU Gym destination, guide, and backend-only station state were visually
  checked. Physical-device GPS and iOS
  execution still require device/macOS verification.
