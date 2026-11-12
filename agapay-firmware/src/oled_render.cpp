// AGAPAY SH1106 128x64 layouts. Full-buffer drawing: the whole frame is composed in RAM
// and sent once, so values never flicker. See docs/oled-display.md for the page mockups.
#include "oled_render.h"
#include <initializer_list>

namespace {
using oled::Inputs;
using oled::Reading;
using oled::Tier;

constexpr int W = 128;
constexpr int HEADER_H = 11;

// Fonts (all present in U8g2 2.36.19).
#define FONT_SMALL u8g2_font_5x8_tf      // 5 px wide: footers and labels
#define FONT_TEXT u8g2_font_6x10_tf      // 6 px wide: table rows and header
#define FONT_BOLD u8g2_font_helvB10_tr   // tier strip and secondary values
#define FONT_BOLD_SMALL u8g2_font_helvB08_tr  // fallback when a bold label is too wide
#define FONT_TITLE u8g2_font_helvB14_tr  // tier word on the alert / emergency pages
#define FONT_DIGITS u8g2_font_logisoso20_tn

int textWidth(u8g2_t* g, const char* s) { return static_cast<int>(u8g2_GetStrWidth(g, s)); }
void text(u8g2_t* g, int x, int y, const char* s) { u8g2_DrawStr(g, x, y, s); }
void centered(u8g2_t* g, int y, const char* s, int left = 0, int width = W) { text(g, left + (width - textWidth(g, s)) / 2, y, s); }
void right(u8g2_t* g, int y, const char* s, int edge = W - 1) { text(g, edge - textWidth(g, s) + 1, y, s); }

// Largest of the given fonts that fits; headline text must never clip on 128 px.
void fit(u8g2_t* g, const char* s, int maxWidth, const uint8_t* first, const uint8_t* second, const uint8_t* third = nullptr) {
  for (const uint8_t* font : {first, second, third}) {
    if (font == nullptr) continue;
    u8g2_SetFont(g, font);
    if (textWidth(g, s) <= maxWidth) return;
  }
}

void row(u8g2_t* g, int y, const char* label, const char* value) {
  u8g2_SetFont(g, FONT_TEXT);
  text(g, 0, y, label);
  right(g, y, value);
}

void dottedFrame(u8g2_t* g, int x, int y, int w, int h) {
  for (int i = x; i < x + w; i += 2) { u8g2_DrawPixel(g, i, y); u8g2_DrawPixel(g, i, y + h - 1); }
  for (int j = y; j < y + h; j += 2) { u8g2_DrawPixel(g, x, j); u8g2_DrawPixel(g, x + w - 1, j); }
}

// Wi-Fi bars (strength from RSSI) and an "M" for the MQTT session, drawn in the
// inverted header; a slash marks a link that is down.
void connectivity(u8g2_t* g, int x, const Inputs& in) {
  const int strength = !in.wifiUp ? 0 : in.rssiDbm >= -60 ? 4 : in.rssiDbm >= -70 ? 3 : in.rssiDbm >= -80 ? 2 : 1;
  for (int bar = 0; bar < 4; ++bar) {
    const int h = 2 + bar * 2;
    if (bar < strength) u8g2_DrawBox(g, x + bar * 3, 9 - h, 2, h);
    else u8g2_DrawPixel(g, x + bar * 3, 8);
  }
  if (!in.wifiUp) u8g2_DrawLine(g, x, 9, x + 10, 1);
  u8g2_SetFont(g, FONT_SMALL);
  text(g, x + 14, 9, "M");
  if (!in.mqttUp) u8g2_DrawLine(g, x + 13, 9, x + 19, 1);
}

void header(u8g2_t* g, const char* title, const Inputs& in, uint8_t page) {
  u8g2_DrawBox(g, 0, 0, W, HEADER_H);
  u8g2_SetDrawColor(g, 0);
  u8g2_SetFont(g, FONT_TEXT);
  text(g, 2, 9, in.outputSelfTest ? "OUTPUT TEST" : title);
  connectivity(g, 87, in);
  char index[6];
  snprintf(index, sizeof(index), "%u/%u", static_cast<unsigned>(page + 1), static_cast<unsigned>(oled::PAGE_COUNT));
  u8g2_SetFont(g, FONT_SMALL);
  right(g, 9, index, W - 2);
  u8g2_SetDrawColor(g, 1);
  // Time until the next page, as a hairline under the header.
  u8g2_DrawHLine(g, 0, HEADER_H, static_cast<u8g2_uint_t>(W * oled::pageProgress(in) / 1000));
}

void depthText(char* out, size_t size, float cm) { snprintf(out, size, "%.1f", static_cast<double>(cm)); }

// --- Page 1: dashboard --------------------------------------------------------------------
void dashboard(u8g2_t* g, const Inputs& in) {
  header(g, in.benchProfile ? "AGAPAY DEMO" : "AGAPAY", in, 0);
  const Reading r = oled::reading(in);
  u8g2_SetFont(g, FONT_SMALL);
  if (r == Reading::VALID || r == Reading::WAITING) {
    text(g, 0, 20, in.benchProfile ? "DISTANCE (DEMO)" : "WATER LEVEL");
  } else {  // Reason tag replaces the label so the cause is visible on the main page.
    const char* tag = r == Reading::STALE ? "STALE" : oled::faultText(in.sensorFault);
    u8g2_DrawBox(g, 0, 13, textWidth(g, tag) + 4, 9);
    u8g2_SetDrawColor(g, 0); text(g, 2, 20, tag); u8g2_SetDrawColor(g, 1);
  }
  char value[16];
  if (r == Reading::VALID) {
    // Demo tiers come from raw distance, so the demo shows the distance it alarms on.
    depthText(value, sizeof(value), in.benchProfile ? in.lastValidDistanceCm : in.lastValidDepthCm);
    u8g2_SetFont(g, FONT_DIGITS);
    text(g, 0, 44, value);
    const int unitX = textWidth(g, value) + 3;
    u8g2_SetFont(g, FONT_TEXT);
    text(g, unitX, 44, "cm");
  } else {  // No number at all rather than a stale or invented one.
    u8g2_SetFont(g, FONT_TITLE);
    text(g, 0, 40, "-- cm");
  }

  u8g2_DrawVLine(g, 84, 14, 32);
  u8g2_SetFont(g, FONT_SMALL);
  text(g, 89, 20, "RAIN");
  char rain[16];
  snprintf(rain, sizeof(rain), "%.1f", static_cast<double>((in.rainLifetimeTips - in.rainBootTips) * in.mmPerTip));
  u8g2_SetFont(g, FONT_BOLD);
  text(g, 89, 35, rain);
  u8g2_SetFont(g, FONT_SMALL);
  text(g, 89, 45, in.rainPersistenceOk ? "mm boot" : "mm !NVS");

  // Alert strip: outline = calm, filled = act now, dotted = no trustworthy reading.
  char label[24];
  snprintf(label, sizeof(label), "%s%s", in.benchProfile && r == Reading::VALID ? "DEMO " : "", oled::statusLabel(in));
  const bool known = r == Reading::VALID || oled::latchedEmergency(in);
  const bool urgent = known && (in.localTier == Tier::WARNING || in.localTier == Tier::EVACUATE);
  if (!known) dottedFrame(g, 0, 49, W, 15);
  else if (urgent) u8g2_DrawRBox(g, 0, 49, W, 15, 2);
  else {
    u8g2_DrawRFrame(g, 0, 49, W, 15, 2);
    if (in.localTier == Tier::ADVISORY) u8g2_DrawRFrame(g, 1, 50, W - 2, 13, 2);  // double rule
  }
  fit(g, label, W - 8, FONT_BOLD, FONT_BOLD_SMALL, FONT_TEXT);
  if (urgent) u8g2_SetDrawColor(g, 0);
  centered(g, 61, label);
  u8g2_SetDrawColor(g, 1);
}

// --- Page 2: rainfall ---------------------------------------------------------------------
void rainfall(u8g2_t* g, const Inputs& in) {
  header(g, "RAINFALL", in, 1);
  char value[24];
  const uint64_t bootTips = in.rainLifetimeTips - in.rainBootTips;
  snprintf(value, sizeof(value), "%.1f mm", static_cast<double>(bootTips * in.mmPerTip));
  row(g, 23, "Since boot", value);
  snprintf(value, sizeof(value), "%llu", static_cast<unsigned long long>(bootTips));
  row(g, 33, "Tips (boot)", value);
  if (in.rainWindowReady) snprintf(value, sizeof(value), "%.1f mm/h", static_cast<double>(in.rainTipsLast60Min * in.mmPerTip));
  else snprintf(value, sizeof(value), "in %lum", static_cast<unsigned long>(in.rainWindowMinutesLeft));
  row(g, 43, "Last 60 min", value);
  if (in.rainTipSinceBoot) {
    char age[8];
    oled::formatAge(in.nowMs, in.rainLastTipMs, age, sizeof(age));
    snprintf(value, sizeof(value), "%s ago", age);
  } else snprintf(value, sizeof(value), "none yet");
  row(g, 53, "Last tip", value);
  u8g2_SetFont(g, FONT_SMALL);
  if (!in.rainPersistenceOk) {
    centered(g, 63, "! COUNT NOT SAVED (NVS)");
  } else {
    snprintf(value, sizeof(value), "%.2f mm/tip", static_cast<double>(in.mmPerTip));
    text(g, 0, 63, value);
    snprintf(value, sizeof(value), "life %llu", static_cast<unsigned long long>(in.rainLifetimeTips));
    right(g, 63, value);
  }
}

// --- Page 3: flood alert ------------------------------------------------------------------
void floodAlert(u8g2_t* g, const Inputs& in) {
  header(g, "FLOOD ALERT", in, 2);
  const Reading r = oled::reading(in);
  const bool known = r == Reading::VALID || oled::latchedEmergency(in);
  const char* status = oled::statusLabel(in);
  fit(g, status, W - 8, FONT_TITLE, FONT_BOLD);
  if (!known) {
    dottedFrame(g, 0, 14, W, 21);
  } else if (in.localTier == Tier::WARNING || in.localTier == Tier::EVACUATE) {
    u8g2_DrawRBox(g, 0, 14, W, 21, 3);
    u8g2_SetDrawColor(g, 0);
  } else if (in.localTier == Tier::ADVISORY) {
    u8g2_DrawRFrame(g, 0, 14, W, 21, 3);
  }
  centered(g, 31, status);
  u8g2_SetDrawColor(g, 1);
  char line[32], number[12];
  u8g2_SetFont(g, FONT_TEXT);
  if (r == Reading::VALID) {
    depthText(number, sizeof(number), in.benchProfile ? in.lastValidDistanceCm : in.lastValidDepthCm);
    snprintf(line, sizeof(line), in.benchProfile ? "Distance %s cm" : "Level %s cm", number);
  } else {
    snprintf(line, sizeof(line), "Level unavailable");
  }
  centered(g, 46, line);
  u8g2_SetFont(g, FONT_SMALL);
  centered(g, 55, oled::guidance(in));
  if (in.benchProfile) {
    snprintf(line, sizeof(line), "DEMO dist A%.0f W%.0f R%.0f cm", static_cast<double>(in.benchAdvisoryCm),
             static_cast<double>(in.benchWarningCm), static_cast<double>(in.benchRedCm));
  } else {
    snprintf(line, sizeof(line), "Depth A%.0f W%.0f E%.0f cm", static_cast<double>(in.advisoryCm),
             static_cast<double>(in.warningCm), static_cast<double>(in.evacuateCm));
  }
  centered(g, 63, line);
}

// --- Page 4: advisory forecast -----------------------------------------------------------
// Display-only. Numbers appear only for an AVAILABLE, unexpired forecast for this station's
// applied configuration; alarms and the EVACUATE override never depend on it.
void forecastPage(u8g2_t* g, const Inputs& in) {
  header(g, "FORECAST", in, 3);
  const oled::ForecastView& f = in.forecast;
  char value[32], age[8];
  if (f.fresh(in.nowMs)) {
    static const uint8_t HORIZONS[] = {30, 60, 90};
    int y = 23;
    for (uint8_t horizon : HORIZONS) {
      const oled::ForecastPoint* point = nullptr;
      for (uint8_t i = 0; i < f.count; ++i) if (f.points[i].horizonMin == horizon) point = &f.points[i];
      char label[12];
      snprintf(label, sizeof(label), "+%u min", static_cast<unsigned>(horizon));
      if (point) snprintf(value, sizeof(value), "%.0f cm (%.0f-%.0f)", static_cast<double>(point->depthCm),
                          static_cast<double>(point->lowerCm), static_cast<double>(point->upperCm));
      else snprintf(value, sizeof(value), "--");
      row(g, y, label, value);
      y += 10;
    }
    oled::formatAge(in.nowMs, f.receivedMs, age, sizeof(age));
    u8g2_SetFont(g, FONT_SMALL);
    snprintf(value, sizeof(value), "ADVISORY  updated %s ago", age);
    centered(g, 54, value);
    centered(g, 63, "Alarms follow sensor only");
    return;
  }
  const char* headline;
  const char* detail;
  if (f.state == oled::ForecastState::NONE) {
    headline = "No forecast yet";
    detail = in.mqttUp ? "Waiting for server" : "Offline: no server";
  } else if (f.state == oled::ForecastState::AVAILABLE) {
    headline = "Forecast expired";
    detail = in.mqttUp ? "Waiting for an update" : "Offline: no server";
  } else if (f.state == oled::ForecastState::REJECTED) {
    headline = "Forecast rejected";
    detail = f.rejected;
  } else {
    headline = "No forecast";
    detail = oled::forecastStatusText(f.status);
  }
  dottedFrame(g, 0, 15, W, 20);
  fit(g, headline, W - 8, FONT_BOLD, FONT_BOLD_SMALL, FONT_TEXT);
  centered(g, 30, headline);
  fit(g, detail, W - 2, FONT_TEXT, FONT_SMALL);
  centered(g, 46, detail);
  u8g2_SetFont(g, FONT_SMALL);
  if (f.state != oled::ForecastState::NONE) {
    oled::formatAge(in.nowMs, f.receivedMs, age, sizeof(age));
    snprintf(value, sizeof(value), "last message %s ago", age);
    centered(g, 55, value);
  }
  centered(g, 63, "Alarms follow sensor only");
}

// --- Page 5: network ----------------------------------------------------------------------
void network(u8g2_t* g, const Inputs& in) {
  header(g, "NETWORK", in, 4);
  char value[24];
  if (in.wifiUp) snprintf(value, sizeof(value), "UP %ddBm", static_cast<int>(in.rssiDbm));
  else snprintf(value, sizeof(value), "DOWN");
  row(g, 23, "WiFi", value);
  row(g, 33, "MQTT", in.mqttUp ? "UP" : "DOWN");
  row(g, 43, "ID", in.stationId);
  row(g, 53, "IP", in.wifiUp && in.ip[0] ? in.ip : "--");
  u8g2_SetFont(g, FONT_SMALL);
  centered(g, 63, in.wifiUp && in.mqttUp ? "Telemetry link live" : "Offline: local alarms OK");
}

// --- Page 6: health -----------------------------------------------------------------------
void health(u8g2_t* g, const Inputs& in) {
  header(g, "HEALTH", in, 5);
  char value[24], age[8];
  switch (oled::reading(in)) {
    case Reading::VALID: snprintf(value, sizeof(value), "OK %.1fcm", static_cast<double>(in.lastValidDistanceCm)); break;
    case Reading::WAITING: snprintf(value, sizeof(value), "WAITING"); break;
    case Reading::STALE: snprintf(value, sizeof(value), "STALLED"); break;
    default: snprintf(value, sizeof(value), "%s", oled::faultText(in.sensorFault)); break;
  }
  row(g, 23, "Sonar", value);
  if (in.everValid) { oled::formatAge(in.nowMs, in.lastValidMs, age, sizeof(age)); snprintf(value, sizeof(value), "%s ago", age); }
  else snprintf(value, sizeof(value), "never");
  row(g, 33, "Last OK", value);
  row(g, 43, "Rain cnt", in.rainPersistenceOk ? "SAVED" : "NVS FAIL");
  oled::formatUptime(in.nowMs, value, sizeof(value));
  row(g, 53, "Uptime", value);
  u8g2_SetFont(g, FONT_SMALL);
  snprintf(value, sizeof(value), "FW%s r%u H%.0f%s", in.firmwareVersion, in.configRevision,
           static_cast<double>(in.sensorHeightCm), in.prototypeGeometry ? " BENCH" : "");
  centered(g, 63, value);
}

// --- Emergency override -------------------------------------------------------------------
void evacuate(u8g2_t* g, const Inputs& in) {
  const bool on = (in.nowMs / 500) % 2 == 0;  // 1 Hz band; text always legible
  if (on) u8g2_DrawRBox(g, 0, 0, W, 25, 3);
  else { u8g2_DrawRFrame(g, 0, 0, W, 25, 3); u8g2_DrawRFrame(g, 1, 1, W - 2, 23, 3); }
  u8g2_SetFont(g, FONT_TITLE);
  if (on) u8g2_SetDrawColor(g, 0);
  centered(g, 19, "EVACUATE");
  u8g2_SetDrawColor(g, 1);
  char line[32], number[12], age[8];
  u8g2_SetFont(g, FONT_BOLD);
  if (oled::reading(in) == Reading::VALID) {
    depthText(number, sizeof(number), in.benchProfile ? in.lastValidDistanceCm : in.lastValidDepthCm);
    snprintf(line, sizeof(line), in.benchProfile ? "dist %s cm" : "%s cm", number);
    centered(g, 41, line);
    u8g2_SetFont(g, FONT_SMALL);
    centered(g, 52, oled::guidance(in));
  } else {  // Latched: the alarm stays on, the level is NOT current.
    centered(g, 41, "SENSOR ERROR");
    u8g2_SetFont(g, FONT_SMALL);
    if (in.everValid) {
      depthText(number, sizeof(number), in.lastValidDepthCm);
      oled::formatAge(in.nowMs, in.lastValidMs, age, sizeof(age));
      snprintf(line, sizeof(line), "Last %s cm, %s ago", number, age);
    } else snprintf(line, sizeof(line), "No valid level");
    centered(g, 52, line);
  }
  centered(g, 63, in.benchProfile ? "DEMO distance alarm" : "Red LED + buzzer active");
}
}  // namespace

void oledRender(u8g2_t* u8g2, const oled::Inputs& in) {
  u8g2_ClearBuffer(u8g2);
  u8g2_SetFontMode(u8g2, 1);
  u8g2_SetDrawColor(u8g2, 1);
  if (oled::emergency(in)) { evacuate(u8g2, in); return; }
  switch (oled::page(in)) {
    case 0: dashboard(u8g2, in); break;
    case 1: rainfall(u8g2, in); break;
    case 2: floodAlert(u8g2, in); break;
    case 3: forecastPage(u8g2, in); break;
    case 4: network(u8g2, in); break;
    default: health(u8g2, in); break;
  }
}
