// Host preview: renders every OLED page/state with the REAL firmware renderer into the
// SH1106 full frame buffer and writes them as raw frames for tools/oled_preview.py.
// Build/run through tools/oled_preview.py (no ESP32 required, nothing is uploaded).
#include <cstdio>
#include <cstring>
#include "oled_render.h"

namespace {
oled::Inputs base() {
  oled::Inputs in;
  in.nowMs = 3723000;  // 01:02:03 uptime
  in.localTier = oled::Tier::NORMAL;
  in.benchProfile = false;
  in.prototypeGeometry = true;
  in.anySample = true; in.sampleValid = true; in.sampleMs = in.nowMs - 400;
  in.everValid = true; in.lastValidMs = in.sampleMs;
  in.lastValidDepthCm = 42.6F; in.lastValidDistanceCm = 107.4F;
  in.rainLifetimeTips = 1234; in.rainBootTips = 1222; in.rainPersistenceOk = true;
  in.rainTipSinceBoot = true; in.rainLastTipMs = in.nowMs - 240000;
  in.rainWindowReady = true; in.rainTipsLast60Min = 3;
  in.stationId = "STATION_001"; in.firmwareVersion = "0.4.0"; in.configRevision = 1;
  in.sensorHeightCm = 150; in.minDistanceCm = 20;
  in.advisoryCm = 60; in.warningCm = 85; in.evacuateCm = 100;
  in.benchAdvisoryCm = 60; in.benchWarningCm = 35; in.benchRedCm = 25;
  in.mmPerTip = 0.7F;
  in.wifiUp = true; in.mqttUp = true; in.rssiDbm = -58; std::strcpy(in.ip, "192.168.1.47");
  return in;
}
oled::Inputs onPage(oled::Inputs in, unsigned page, unsigned progressMs = 1800) {
  const uint32_t cycle = oled::PAGE_COUNT * oled::PAGE_MS;
  in.nowMs = (in.nowMs / cycle) * cycle + page * oled::PAGE_MS + progressMs;
  in.sampleMs = in.nowMs - 400; in.lastValidMs = in.sampleMs; in.rainLastTipMs = in.nowMs - 240000;
  return in;
}
void depth(oled::Inputs& in, float cm, oled::Tier tier) { in.lastValidDepthCm = cm; in.lastValidDistanceCm = 150 - cm; in.localTier = tier; }
void fault(oled::Inputs& in, const char* why, float lastCm, uint32_t agoMs) {
  in.sampleValid = false; in.sensorFault = why; in.lastValidDepthCm = lastCm; in.lastValidMs = in.nowMs - agoMs;
}

void forecastAvailable(oled::Inputs& in, uint32_t ageMs) {
  in.forecast.state = oled::ForecastState::AVAILABLE;
  std::strcpy(in.forecast.status, "available");
  in.forecast.receivedMs = in.nowMs - ageMs;
  in.forecast.lifetimeMs = 120000;
  const float points[3][4] = {{30, 83.0F, 79.0F, 88.0F}, {60, 86.0F, 82.0F, 91.0F}, {90, 89.0F, 85.0F, 94.0F}};
  in.forecast.count = 3;
  for (int i = 0; i < 3; ++i) {
    in.forecast.points[i].horizonMin = static_cast<uint8_t>(points[i][0]);
    in.forecast.points[i].depthCm = points[i][1]; in.forecast.points[i].lowerCm = points[i][2]; in.forecast.points[i].upperCm = points[i][3];
  }
}

void emit(FILE* out, u8g2_t* g, const char* name, const oled::Inputs& in) {
  oledRender(g, in);
  std::fprintf(out, "%s\n", name);
  std::fwrite(u8g2_GetBufferPtr(g), 1, 1024, out);
}
}  // namespace

int main(int argc, char** argv) {
  if (argc != 2) { std::fprintf(stderr, "usage: oled_preview <frames.bin>\n"); return 2; }
  FILE* out = std::fopen(argv[1], "wb");
  if (!out) return 1;
  static u8g2_t g;
  u8g2_Setup_sh1106_128x64_noname_f(&g, U8G2_R0, u8x8_byte_empty, u8x8_dummy_cb);
  oled::Inputs in;

  in = onPage(base(), 0); emit(out, &g, "01-dashboard-normal", in);
  in = onPage(base(), 0); depth(in, 72.4F, oled::Tier::ADVISORY); emit(out, &g, "02-dashboard-advisory", in);
  in = onPage(base(), 0); depth(in, 91.0F, oled::Tier::WARNING); emit(out, &g, "03-dashboard-warning", in);
  in = onPage(base(), 0); depth(in, 72.4F, oled::Tier::ADVISORY); fault(in, "no_echo", 72.4F, 6000); emit(out, &g, "04-dashboard-sensor-error", in);
  in = onPage(base(), 0); in.anySample = false; in.everValid = false; in.localTier = oled::Tier::UNKNOWN; emit(out, &g, "05-dashboard-waiting", in);
  in = onPage(base(), 0); in.sampleMs = in.nowMs - 9000; emit(out, &g, "06-dashboard-stale", in);
  in = onPage(base(), 1); in.rainWindowReady = false; in.rainTipsLast60Min = 0; in.rainWindowMinutesLeft = 23; emit(out, &g, "07-rain-window-filling", in);
  in = onPage(base(), 1); emit(out, &g, "08-rain-hourly", in);
  in = onPage(base(), 1); in.rainPersistenceOk = false; emit(out, &g, "09-rain-nvs-failure", in);
  in = onPage(base(), 2); depth(in, 91.0F, oled::Tier::WARNING); emit(out, &g, "10-alert-warning", in);
  in = onPage(base(), 2); depth(in, 64.0F, oled::Tier::ADVISORY); emit(out, &g, "11-alert-advisory", in);
  in = onPage(base(), 2); fault(in, "blind_zone", 42.6F, 3000); emit(out, &g, "12-alert-sensor-error", in);
  in = onPage(base(), 4); emit(out, &g, "13-network-online", in);
  in = onPage(base(), 4); in.wifiUp = false; in.mqttUp = false; emit(out, &g, "14-network-offline", in);
  in = onPage(base(), 5); emit(out, &g, "15-health-ok", in);
  in = onPage(base(), 5); fault(in, "blind_zone", 42.6F, 12000); emit(out, &g, "16-health-blind-zone", in);
  in = onPage(base(), 0, 200); depth(in, 103.2F, oled::Tier::EVACUATE); emit(out, &g, "17-evacuate-band-on", in);
  in = onPage(base(), 0, 700); depth(in, 103.2F, oled::Tier::EVACUATE); emit(out, &g, "18-evacuate-band-off", in);
  in = onPage(base(), 0, 200); depth(in, 103.2F, oled::Tier::EVACUATE); fault(in, "no_echo", 103.2F, 14000); emit(out, &g, "19-evacuate-latched-sensor-error", in);
  in = onPage(base(), 0); in.benchProfile = true; in.lastValidDistanceCm = 31.0F; in.lastValidDepthCm = 119.0F; in.localTier = oled::Tier::WARNING;
  emit(out, &g, "20-bench-demo-dashboard", in);
  in = onPage(base(), 3); forecastAvailable(in, 12000); emit(out, &g, "21-forecast-available", in);
  in = onPage(base(), 3); in.forecast.state = oled::ForecastState::NOT_AVAILABLE; std::strcpy(in.forecast.status, "not_trained");
  in.forecast.receivedMs = in.nowMs - 9000; emit(out, &g, "22-forecast-not-trained", in);
  in = onPage(base(), 3); forecastAvailable(in, 200000); emit(out, &g, "23-forecast-expired", in);
  in = onPage(base(), 3); in.forecast.state = oled::ForecastState::REJECTED; in.forecast.rejected = "config mismatch";
  in.forecast.receivedMs = in.nowMs - 4000; emit(out, &g, "24-forecast-rejected-config", in);
  in = onPage(base(), 3); in.wifiUp = false; in.mqttUp = false; emit(out, &g, "25-forecast-none-offline", in);
  std::fclose(out);
  return 0;
}
