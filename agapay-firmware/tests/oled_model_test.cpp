// Host tests for the OLED display model: an untrustworthy reading is never shown as a
// measured tier, EVACUATE overrides paging (also when latched across a sensor fault),
// and the 60-minute rain window reports nothing until a full hour has been observed.
#include <cassert>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include "oled_model.h"

using oled::Inputs;
using oled::Reading;
using oled::Tier;

static Inputs valid(Tier tier) {
  Inputs in;
  in.nowMs = 100000; in.anySample = true; in.sampleValid = true; in.sampleMs = 99500;
  in.everValid = true; in.lastValidMs = 99500; in.lastValidDepthCm = 50; in.localTier = tier;
  return in;
}

int main() {
  int checks = 0;
#define CHECK(x) do { assert(x); ++checks; } while (0)
  Inputs boot;
  CHECK(oled::reading(boot) == Reading::WAITING && std::strcmp(oled::statusLabel(boot), "NO DATA YET") == 0);
  CHECK(!oled::emergency(boot));

  Inputs in = valid(Tier::NORMAL);
  CHECK(oled::reading(in) == Reading::VALID && std::strcmp(oled::statusLabel(in), "NORMAL") == 0);
  in.sampleValid = false; in.sensorFault = "no_echo";  // fault after a NORMAL sample: never "NORMAL"
  CHECK(std::strcmp(oled::statusLabel(in), "SENSOR ERROR") == 0 && std::strcmp(oled::faultText(in.sensorFault), "NO ECHO") == 0);
  in = valid(Tier::ADVISORY); in.nowMs = in.sampleMs + oled::STALE_AFTER_MS + 1;  // sampling stopped
  CHECK(oled::reading(in) == Reading::STALE && std::strcmp(oled::statusLabel(in), "DATA STALE") == 0);

  in = valid(Tier::EVACUATE);
  CHECK(oled::emergency(in) && !oled::latchedEmergency(in));
  in.sampleValid = false; in.sensorFault = "blind_zone";  // firmware keeps red+buzzer latched
  CHECK(oled::emergency(in) && oled::latchedEmergency(in) && std::strcmp(oled::statusLabel(in), "EVACUATE") == 0);
  CHECK(std::strcmp(oled::faultText("blind_zone"), "TOO CLOSE") == 0 && std::strcmp(oled::faultText("odd"), "FAULT") == 0);

  in = valid(Tier::NORMAL);
  for (uint32_t t = 0; t < 36000; t += 5000) { in.nowMs = t; CHECK(oled::page(in) == (t / 5000) % 6); }
  in.nowMs = 2500; CHECK(oled::pageProgress(in) == 500);

  for (Tier tier : {Tier::NORMAL, Tier::ADVISORY, Tier::WARNING, Tier::EVACUATE}) {
    Inputs g = valid(tier);
    CHECK(std::strlen(oled::guidance(g)) <= 25);  // fits 128 px at the 5 px font
  }
  Inputs fault = valid(Tier::WARNING); fault.sampleValid = false;
  CHECK(std::strlen(oled::guidance(fault)) <= 25);

  oled::RainWindow window;
  uint64_t tips = 1000;
  for (uint32_t minute = 0; minute < 60; ++minute) {
    window.update(minute * 60000UL, tips);
    CHECK(!window.ready() && window.tipsLastHour() == 0 && window.minutesLeft() == 60 - minute);
    tips += minute % 10 == 0 ? 2 : 0;
  }
  window.update(60 * 60000UL, tips);
  CHECK(window.ready() && window.tipsLastHour() == 12 && window.minutesLeft() == 0);
  window.update(60 * 60000UL + 59000, tips + 100);  // not a new minute yet: ignored
  CHECK(window.tipsLastHour() == 12);
  window.update(61 * 60000UL, tips + 1);  // the oldest minute (with 2 tips) leaves the window
  CHECK(window.tipsLastHour() == 11);

  char text[24];
  oled::formatUptime(3723000, text, sizeof(text)); CHECK(std::strcmp(text, "01:02:03") == 0);
  oled::formatUptime(2 * 86400000UL + 1000, text, sizeof(text)); CHECK(std::strcmp(text, "2d 00:00:01") == 0);
  oled::formatAge(200000, 188000, text, sizeof(text)); CHECK(std::strcmp(text, "12s") == 0);
  oled::formatAge(4000000, 0, text, sizeof(text)); CHECK(std::strcmp(text, "1h") == 0);
  std::printf("oled model host tests: %d checks passed\n", checks);
  return 0;
}
