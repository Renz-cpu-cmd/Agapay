// Host tests for the advisory forecast downlink parser: only a well-formed, current,
// same-station, same-configuration forecast yields numbers; everything else is labelled.
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
#include "forecast_message.h"

using oled::ForecastState;

static const char* STATION = "STATION_001";
static const char* CONFIG = "c5eed6b3f6b820c6a77342c4e30b64cbd9c46657eec086e115b5fff590d7557b";
static const int64_t NOW = 1767400000;  // synchronized UTC

static std::string available(int64_t published = NOW - 5, int64_t validUntil = NOW + 115, int ttl = 120,
                             const char* points = "[[30,83.0,79.0,88.0],[60,86,82,91],[90,89.0,85.0,94.0]]",
                             const char* config = CONFIG, const char* station = STATION) {
  char out[1024];
  std::snprintf(out, sizeof(out),
      "{\"v\":1,\"station_id\":\"%s\",\"status\":\"available\",\"advisory_only\":true,\"published_at\":%lld,"
      "\"generated_at\":%lld,\"valid_until\":%lld,\"ttl_s\":%d,\"config\":\"%s\",\"model\":\"abcdef0123456789\",\"points\":%s}",
      station, static_cast<long long>(published), static_cast<long long>(published - 20), static_cast<long long>(validUntil),
      ttl, config, points);
  return out;
}

static oled::ForecastView parse(const std::string& message, int64_t utc = NOW, uint32_t nowMs = 50000) {
  return forecast::parse(reinterpret_cast<const uint8_t*>(message.data()), message.size(), STATION, CONFIG, nowMs, utc);
}

int main() {
  int checks = 0;
#define CHECK(x) do { assert(x); ++checks; } while (0)
  oled::ForecastView view = parse(available());
  CHECK(view.state == ForecastState::AVAILABLE && view.count == 3 && view.points[1].depthCm == 86.0F);
  CHECK(view.lifetimeMs == 115000);  // clipped to valid_until on a synchronized clock
  CHECK(view.fresh(50000 + 114999) && !view.fresh(50000 + 115000));
  CHECK(parse(available(), 0).lifetimeMs == 120000);  // unsynchronized clock: relative TTL only
  CHECK(parse(available(NOW - 5, NOW + 115, 120, "[[30,83,79,88]]")).count == 1);

  for (const char* status : {"not_trained", "unavailable", "insufficient_data", "stale_data", "invalid_data", "service_error"}) {
    char message[200];
    std::snprintf(message, sizeof(message), "{\"v\":1,\"station_id\":\"%s\",\"status\":\"%s\",\"advisory_only\":true,\"published_at\":%lld}",
                  STATION, status, static_cast<long long>(NOW));
    view = parse(message);
    CHECK(view.state == ForecastState::NOT_AVAILABLE && std::strcmp(view.status, status) == 0 && view.count == 0 && !view.fresh(50000));
  }

  auto rejected = [&](const std::string& message, const char* why, int64_t utc = NOW) {
    const oled::ForecastView v = parse(message, utc);
    return v.state == ForecastState::REJECTED && std::strcmp(v.rejected, why) == 0 && !v.fresh(50000) && v.count == 0;
  };
  CHECK(rejected(available(NOW - 5, NOW + 115, 120, "[[30,83,79,88]]", "a000000000000000000000000000000000000000000000000000000000000000"), "config mismatch"));
  CHECK(rejected(available(NOW - 200, NOW - 1, 120), "expired"));
  CHECK(rejected(available(NOW + 1000, NOW + 1200, 120), "clock mismatch"));
  CHECK(rejected(available(NOW - 5, NOW + 115, 120, "[[30,83,79,88]]", CONFIG, "STATION_002"), "bad message"));
  CHECK(rejected(available(NOW - 5, NOW + 115, 120, "[[30,90,79,88]]"), "bad message"));       // point outside its interval
  CHECK(rejected(available(NOW - 5, NOW + 115, 120, "[[60,83,79,88],[30,83,79,88]]"), "bad message"));  // not ascending
  CHECK(rejected(available(NOW - 5, NOW + 115, 120, "[[45,83,79,88]]"), "bad message"));       // unknown horizon
  CHECK(rejected(available(NOW - 5, NOW + 115, 120, "[[30,-1,-2,0]]"), "bad message"));        // negative depth
  CHECK(rejected(available(NOW - 5, NOW + 115, 120, "[]"), "bad message"));
  CHECK(rejected(available(NOW - 5, NOW + 115, 9000), "bad message"));                          // TTL above 2 h
  CHECK(rejected(available(NOW - 5, NOW + 115, 500), "bad message"));                           // TTL beyond valid_until
  CHECK(rejected("{\"v\":2}", "bad message") && rejected("not json", "bad message"));
  std::string noFlag = available();
  noFlag.replace(noFlag.find("\"advisory_only\":true"), 20, "\"advisory_only\":false");
  CHECK(rejected(noFlag, "bad message"));
  CHECK(rejected(std::string(1500, ' '), "bad message"));
  std::printf("forecast message host tests: %d checks passed\n", checks);
  return 0;
}
