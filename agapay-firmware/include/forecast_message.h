// Validates the advisory forecast downlink (agapay/stations/<id>/forecast, schema v1) into a
// display-only ForecastView. Host-tested. Anything not provably current, well-formed and for
// THIS station's applied configuration is rejected; numbers are kept only when available.
//
// Message (published by the backend every ~30 s, not retained):
//   {"v":1,"station_id":"STATION_001","status":"available","advisory_only":true,
//    "published_at":<unix s>,"generated_at":<unix s>,"valid_until":<unix s>,"ttl_s":<s>,
//    "config":"<64-hex applied configuration hash>","model":"<id prefix>",
//    "points":[[30,depth,lower,upper],[60,...],[90,...]]}
// Any other status carries no numbers.
#pragma once
#include <ArduinoJson.h>
#include <math.h>
#include <string.h>
#include "oled_model.h"

namespace forecast {

constexpr size_t MAX_MESSAGE_BYTES = 1024;
constexpr int64_t SYNCED_EPOCH_S = 1767225600;  // 2026-01-01: below this the RTC is not synchronized
constexpr int64_t MAX_TTL_S = 7200;
constexpr int64_t MAX_CLOCK_AHEAD_S = 300;

inline oled::ForecastView reject(uint32_t nowMs, const char* why) {
  oled::ForecastView view;
  view.state = oled::ForecastState::REJECTED;
  view.rejected = why;
  view.receivedMs = nowMs;
  return view;
}

inline bool depthOk(JsonVariantConst value, float& out) {
  if (!value.is<float>() && !value.is<int>()) return false;
  out = value.as<float>();
  return isfinite(out) && out >= 0.0F && out <= 1000.0F;
}

// utcNowS: device UTC seconds, or 0 when SNTP has not synchronized yet.
inline oled::ForecastView parse(const uint8_t* payload, size_t length, const char* stationId, const char* appliedConfigHash,
                                uint32_t nowMs, int64_t utcNowS) {
  if (payload == nullptr || length == 0 || length > MAX_MESSAGE_BYTES) return reject(nowMs, "bad message");
  JsonDocument doc;
  if (deserializeJson(doc, payload, length) != DeserializationError::Ok) return reject(nowMs, "bad message");
  const char* station = doc["station_id"] | "";
  const char* status = doc["status"] | "";
  if ((doc["v"] | 0) != 1 || strcmp(station, stationId) != 0 || !(doc["advisory_only"] | false)) return reject(nowMs, "bad message");
  static const char* const KNOWN[] = {"available", "not_trained", "unavailable", "insufficient_data", "stale_data",
                                      "invalid_data", "service_error"};
  bool known = false;
  for (const char* candidate : KNOWN) known = known || strcmp(status, candidate) == 0;
  if (!known) return reject(nowMs, "bad message");

  oled::ForecastView view;
  view.receivedMs = nowMs;
  strncpy(view.status, status, sizeof(view.status) - 1);
  if (strcmp(status, "available") != 0) {
    view.state = oled::ForecastState::NOT_AVAILABLE;
    return view;
  }
  const char* config = doc["config"] | "";
  if (appliedConfigHash == nullptr || strcmp(config, appliedConfigHash) != 0) return reject(nowMs, "config mismatch");
  const int64_t published = doc["published_at"] | static_cast<int64_t>(0);
  const int64_t validUntil = doc["valid_until"] | static_cast<int64_t>(0);
  int64_t ttl = doc["ttl_s"] | static_cast<int64_t>(0);
  if (published <= 0 || validUntil <= published || ttl <= 0 || ttl > MAX_TTL_S || ttl > validUntil - published) {
    return reject(nowMs, "bad message");
  }
  if (utcNowS >= SYNCED_EPOCH_S) {  // Clock known: trust the absolute expiry too.
    if (published > utcNowS + MAX_CLOCK_AHEAD_S) return reject(nowMs, "clock mismatch");
    if (utcNowS >= validUntil) return reject(nowMs, "expired");
    if (validUntil - utcNowS < ttl) ttl = validUntil - utcNowS;
  }
  JsonArrayConst points = doc["points"].as<JsonArrayConst>();
  if (points.isNull() || points.size() == 0 || points.size() > 3) return reject(nowMs, "bad message");
  uint8_t previous = 0;
  for (JsonArrayConst point : points) {
    if (point.isNull() || point.size() != 4) return reject(nowMs, "bad message");
    const int horizon = point[0] | 0;
    oled::ForecastPoint& out = view.points[view.count];
    if ((horizon != 30 && horizon != 60 && horizon != 90) || horizon <= previous ||
        !depthOk(point[1], out.depthCm) || !depthOk(point[2], out.lowerCm) || !depthOk(point[3], out.upperCm) ||
        !(out.lowerCm <= out.depthCm && out.depthCm <= out.upperCm)) {
      return reject(nowMs, "bad message");
    }
    out.horizonMin = static_cast<uint8_t>(horizon);
    previous = out.horizonMin;
    ++view.count;
  }
  view.state = oled::ForecastState::AVAILABLE;
  view.lifetimeMs = static_cast<uint32_t>(ttl) * 1000UL;
  return view;
}

}  // namespace forecast
