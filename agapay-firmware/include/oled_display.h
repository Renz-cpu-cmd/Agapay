// AGAPAY SH1106 OLED task (ESP32 only, AGAPAY_OLED=1). The display is a read-only view:
// sensing, local LEDs/buzzer and MQTT never wait for it, and it never changes their state.
#pragma once
#include "oled_model.h"

// Starts the display task on core 0 (beside the network task), so I2C transfers can never
// preempt the ultrasonic pulseIn timing or the sensor loop on core 1.
void oledBegin();
// Main loop: latest local measurement, alert tier, rain counter and configuration.
// Network fields in `local` are ignored.
void oledPublishLocal(const oled::Inputs& local);
// Network task only (it owns the Wi-Fi and MQTT clients).
void oledPublishNetwork(bool wifiUp, bool mqttUp, int16_t rssiDbm, const char* ip);
// Network task only: the latest validated advisory forecast (display-only).
void oledPublishForecast(const oled::ForecastView& forecast);
