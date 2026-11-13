# Prediction interface

AGAPAY now has a versioned prediction boundary connected to the Next.js station
forecast and the Flutter Home and Alert Details forecasts. A trained model is not
configured. Actual mode returns **Model not trained** with empty forecast values.
No hardware, cloud subscription, or ML service account is needed to develop this
interface. The applications still require their existing local AGAPAY accounts.

## Try the interface

Start the API and applications as described in [Accounts setup](ACCOUNTS_SETUP.md).
In the web app, sign in as staff and open **Stations → STATION_001**. In the mobile
app, sign in as a resident and open **Home** or **Alert Details**. Mobile currently
uses the seeded `STATION_001`; the other web stations remain design samples and
return Station not found until registered in the backend.

Choose **Preview sample scenarios** on web or the preview control on mobile.
Select available, model not trained, insufficient data, stale data, invalid data,
or service unavailable. Available preview returns fixed values of 96, 99, and
102 cm for interface testing. Every preview is labelled **SIMULATED PREVIEW**.
Return to actual mode to see the real model availability.

Previews read no telemetry and write no records. They never change alert levels
or trigger notifications. They require both `AGAPAY_ENVIRONMENT=development` and
`AGAPAY_PREDICTION_PREVIEW_ENABLED=true`. They are forbidden in production even
when the preview flag is true. Actual mode is the default on a fresh sign-in.

## Authenticated endpoint

```text
GET /api/predictions/{station_id}
GET /api/predictions/{station_id}?mode=preview&scenario=available
Authorization: Bearer <AGAPAY session token>
```

Any active AGAPAY account can read this endpoint. Web staff requests go through
the existing HttpOnly session-cookie proxy at
`/api/account/predictions/{station_id}`. There is no browser-exposed staff token.
Unknown stations return 404, unauthenticated requests 401, forbidden previews 403,
and unsupported modes/scenarios 422. Responses are not cached.

The response has `schema_version: "1.0"` and always contains exactly three ordered
forecast points, with `horizon_minutes` of 30, 60, and 90. Values represent water
depth in **centimetres**, measured from the station's calibrated depth reference;
they are not water surface elevation or raw sensor distance. A horizon is relative
to the latest input reading. Its absolute `target_at` is supplied by the backend.

| Field | Meaning |
| --- | --- |
| `status`, `reason` | Availability and a human-readable explanation |
| `source` | `none`, `model`, or `simulated` |
| `advisory_only` | Always `true`; forecasts do not assign alert tiers |
| `checked_at` | Server time used to assess this response |
| `generated_at`, `valid_until` | Generation and expiry times when available |
| `model_version` | Actual adapter version, or null; previews cannot claim one |
| `input_status` | Separate provisional assessment of the telemetry history |
| `input_window_start`, `input_last_recorded_at` | Input coverage and latest reading time |
| `sample_count`, `valid_sample_count` | Number of supplied and valid samples |
| `timestamp_basis` | `server_received`, `device_measured`, or `synthetic` |
| `rainfall_interval_seconds` | Rainfall accumulation period, null when unknown |
| `preview_allowed` | Whether the development preview control should be shown |
| `forecasts` | Horizon, nullable `target_at`, nullable `water_depth_cm` |

| Status | Numeric forecast values |
| --- | --- |
| `not_trained` | Null: no model adapter is configured |
| `insufficient_data` | Null: too few readings, too short a history, or excessive gaps |
| `stale_data` | Null: input is too old, including expiry during inference |
| `invalid_data` | Null: input validation or sensor quality checks failed |
| `service_error` | Null: adapter failed or returned an invalid result |
| `available` | Three finite values between 0 and 1000 cm, each with a target time |

An unavailable value is **null**, never zero. A real zero is a valid numeric result.
There are no accuracy, confidence, or model-performance claims in this contract.
Until a model is configured, `not_trained` takes precedence; `input_status` still
reports whether the available telemetry is usable, insufficient, stale, or invalid.

Both clients poll every 30 seconds and clear values when mode, account, or request
state changes. They hide numbers after expiry or a failed request. A relative
lifetime from the server response limits dependence on the device clock and is
reduced by time spent waiting for the response. Forecasts remain advisory; the
existing monitoring screens and alert tier controls still use demonstration data.

## Input and future model adapter

`app/prediction_schemas.py` defines `PredictionInput`, `ModelOutput`, and
`PredictionResponse`. Export their JSON Schemas with:

```powershell
python -m app.export_prediction_contracts
```

Exports are in [contracts](contracts/). Pydantic also enforces cross-field rules
such as ordered horizons and null values for unavailable results; those rules
are described here because JSON Schema alone does not express every validator.
The HTTP response is included in the API's `/docs` OpenAPI documentation.
The input contract is internal to the backend adapter; clients do not submit
arbitrary sensor histories through the prediction endpoint.

`app/services/ml_predictor.py` retrieves history and calls a `Predictor` dependency.
The current `UntrainedPredictor` has `version = None` and is never asked to infer.
A future adapter supplies a nonempty version and implements:

```python
def predict(self, history: PredictionInput) -> ModelOutput:
    ...
```

Replace `get_predictor()` with the reviewed adapter. Its result must contain all
three ordered horizons. The service validates the result, adds target times and
expiry, and rejects nonfinite, missing, duplicated, or out-of-range predictions.
An adapter can raise `PredictionUnavailable` for model-specific input requirements;
unexpected failures return `service_error` without disclosing internal errors.
The empty `app/ml/model.h5` and `scaler.pkl` placeholders are not loaded.

The current integration checks are **provisional**, not validated ML requirements:
last 60 minutes, at most 3,600 readings, at least 12 valid samples spanning 30
minutes, gaps no greater than 5 minutes, and latest reading at most 120 seconds old.
Any invalid sample in the selected window prevents inference. Available results
expire after at most 60 seconds, or sooner when the input reaches its age limit.
These checks must be reviewed against actual sensor cadence and the future model.

Input samples contain an aware timestamp, water depth, rainfall amount, rainfall
interval if known, and sensor quality. Timestamps must strictly increase and not
be in the future. Valid samples require a depth; invalid ones require null.

Two existing telemetry limitations must be resolved before training:

- `recorded_at` is the API receive time. It does not prove when hardware measured
  the value, especially after buffering or delayed delivery. Actual responses
  therefore label the timestamp basis `server_received`.
- The current `rainfall_mm` contract does not define its accumulation period.
  Real inputs therefore carry `rainfall_interval_seconds: null`. A model using
  rainfall must require a defined accumulation period and compatible preprocessing;
  it must not infer that period from HTTP or MQTT message frequency.

Training and evaluation remain future work: define sensor measurement timestamps,
rainfall semantics, cadence and calibration; collect suitable representative data;
choose features and evaluation splits; then train and evaluate a versioned model.
Synthetic preview values do not establish accuracy or operational suitability.

## Verification

The backend suite passes 48 tests, including authentication, all preview states,
preview restrictions, chronological inputs, valid zero predictions, stale/invalid
history, malformed outputs, and expiry during inference. The Flutter suite passes
18 tests, including response parsing, request races, sign-out clearing, expiry,
network failure, preview states, unchanged alert levels, and a 320-pixel layout.
Flutter analysis reports no issues. Next.js, Flutter web, and Android debug APK
builds pass. Browser checks confirm actual, available-preview, stale-preview and
return-to-actual behavior on web and mobile. HTTP checks also verify the web proxy's
staff restriction, all six scenarios, query validation, no-store response and logout.
The Android APK is compiled; native-device execution has not been verified.
