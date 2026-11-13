// AGAPAY SH1106 1.3" 128x64 OLED (I2C 0x3C, SDA GPIO21, SCL GPIO22).
// Six pages auto-advance every 5 s; EVACUATE takes over the screen until the local tier
// leaves EVACUATE. Frames are composed in RAM and sent whole (no flicker). If the panel is
// missing or unplugged, only this task's I2C writes fail; sensing and alarms continue.
#if AGAPAY_OLED
#include <Arduino.h>
#include <U8g2lib.h>
#include <Wire.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include "oled_display.h"
#include "oled_render.h"

namespace {
constexpr uint8_t OLED_SDA = 21;
constexpr uint8_t OLED_SCL = 22;
constexpr uint32_t FRAME_MS = 200;  // 5 fps: values update within 0.2 s, 1 Hz emergency blink

U8G2_SH1106_128X64_NONAME_F_HW_I2C display(U8G2_R0, U8X8_PIN_NONE, OLED_SCL, OLED_SDA);
portMUX_TYPE sharedMux = portMUX_INITIALIZER_UNLOCKED;
oled::Inputs shared;  // guarded by sharedMux; plain copies only (no allocation inside the lock)
oled::RainWindow rainWindow;

void displayTask(void*) {
  Wire.begin(OLED_SDA, OLED_SCL);
  display.setBusClock(400000);
  display.begin();
  display.setContrast(255);
  Serial.println("[OLED] SH1106 128x64 @0x3C SDA=21 SCL=22: 6 pages / 5 s (incl. advisory forecast), EVACUATE override");
  oled::Inputs frame;
  for (;;) {
    portENTER_CRITICAL(&sharedMux);
    frame = shared;
    portEXIT_CRITICAL(&sharedMux);
    frame.nowMs = millis();
    rainWindow.update(frame.nowMs, frame.rainLifetimeTips);
    frame.rainWindowReady = rainWindow.ready();
    frame.rainTipsLast60Min = rainWindow.tipsLastHour();
    frame.rainWindowMinutesLeft = rainWindow.minutesLeft();
    oledRender(display.getU8g2(), frame);
    display.sendBuffer();
    vTaskDelay(pdMS_TO_TICKS(FRAME_MS));
  }
}
}  // namespace

void oledBegin() {
  // Core 0 beside the network task; lowest application priority. Never blocks setup().
  if (xTaskCreatePinnedToCore(displayTask, "agapay-oled", 4096, nullptr, 1, nullptr, 0) != pdPASS) {
    Serial.println("[OLED] display task unavailable; sensing and alarms continue");
  }
}

void oledPublishLocal(const oled::Inputs& local) {
  portENTER_CRITICAL(&sharedMux);
  const bool wifiUp = shared.wifiUp, mqttUp = shared.mqttUp;
  const int16_t rssi = shared.rssiDbm;
  char ip[sizeof(shared.ip)];
  memcpy(ip, shared.ip, sizeof(ip));
  const oled::ForecastView forecast = shared.forecast;
  shared = local;
  shared.wifiUp = wifiUp; shared.mqttUp = mqttUp; shared.rssiDbm = rssi;
  memcpy(shared.ip, ip, sizeof(ip));
  shared.forecast = forecast;
  portEXIT_CRITICAL(&sharedMux);
}

void oledPublishForecast(const oled::ForecastView& forecast) {
  portENTER_CRITICAL(&sharedMux);
  shared.forecast = forecast;
  portEXIT_CRITICAL(&sharedMux);
}

void oledPublishNetwork(bool wifiUp, bool mqttUp, int16_t rssiDbm, const char* ip) {
  char copy[sizeof(shared.ip)] = {};
  if (ip) strncpy(copy, ip, sizeof(copy) - 1);
  portENTER_CRITICAL(&sharedMux);
  shared.wifiUp = wifiUp; shared.mqttUp = mqttUp; shared.rssiDbm = rssiDbm;
  memcpy(shared.ip, copy, sizeof(copy));
  portEXIT_CRITICAL(&sharedMux);
}
#endif
