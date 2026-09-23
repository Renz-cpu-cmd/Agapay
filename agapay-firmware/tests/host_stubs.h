#pragma once
// Host-only fakes. These tests never open sockets or access physical GPIO/NVS.
#include <cassert>
#include <cstdarg>
#include <cstdint>
#include <cstring>
#include <deque>
#include <string>
#include <vector>
#define IRAM_ATTR
#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define INPUT 0
#define INPUT_PULLUP 2
#define FALLING 2
#define WL_CONNECTED 3
#define WIFI_STA 1
#define pdTRUE 1
#define pdPASS 1
#define pdMS_TO_TICKS(x) (x)
using portMUX_TYPE = int;
#define portMUX_INITIALIZER_UNLOCKED 0
inline uint32_t fakeMs = 0, fakeUs = 0;
inline int pins[40] = {};
inline std::deque<unsigned long> echoes;
inline std::vector<std::string> serialLines;
inline void (*afterUnlock)() = nullptr;
inline uint32_t millis() { return fakeMs; }
inline uint32_t micros() { return fakeUs; }
inline void pinMode(int, int) {}
inline void digitalWrite(int pin, int value) { pins[pin] = value; }
inline void delayMicroseconds(unsigned) {}
inline void delay(unsigned) {}
inline int digitalPinToInterrupt(int pin) { return pin; }
inline void attachInterrupt(int, void (*)(), int) {}
inline unsigned long pulseIn(int, int, unsigned long timeout) {
  assert(timeout == 30000);
  if (echoes.empty()) return 0;
  auto value = echoes.front(); echoes.pop_front(); return value;
}
inline void portENTER_CRITICAL(portMUX_TYPE* mux) { assert(*mux == 0); ++*mux; }
inline void portEXIT_CRITICAL(portMUX_TYPE* mux) {
  assert(*mux == 1); --*mux;
  if (afterUnlock) { auto callback = afterUnlock; afterUnlock = nullptr; callback(); }
}
inline void portENTER_CRITICAL_ISR(portMUX_TYPE* mux) { portENTER_CRITICAL(mux); }
inline void portEXIT_CRITICAL_ISR(portMUX_TYPE* mux) { portEXIT_CRITICAL(mux); }
struct SerialFake {
  void begin(int) {}
  void println(const char* line) { serialLines.emplace_back(line); }
  void printf(const char* fmt, ...) {
    char text[1024]; va_list args; va_start(args, fmt);
    vsnprintf(text, sizeof(text), fmt, args); va_end(args); serialLines.emplace_back(text);
  }
};
inline SerialFake Serial;
struct ESPFake { uint64_t getEfuseMac() { return 123; } };
inline ESPFake ESP;
struct WiFiFake {
  int state = 0;
  int status() { return state; }
  void mode(int) {}
  void begin(const char*, const char*) {}
};
inline WiFiFake WiFi;
struct WiFiClient {};
struct PubSubClient {
  bool online = false, publishResult = true;
  std::string lastPayload, lastTopic;
  explicit PubSubClient(WiFiClient&) {}
  bool connected() { return online; }
  bool connect(const char*) { return online; }
  bool connect(const char*, const char*, const char*) { return online; }
  void setServer(const char*, int) {}
  void setBufferSize(int) {}
  void setSocketTimeout(int) {}
  void setKeepAlive(int) {}
  void loop() {}
  bool publish(const char* topic, const char* payload, bool retained) {
    assert(!retained); lastPayload = payload; lastTopic = topic; return publishResult;
  }
};
struct Preferences {
  uint32_t storedBoot = 0;
  bool openOk = true, writeOk = true;
  bool begin(const char*, bool) { return openOk; }
  uint32_t getUInt(const char*, uint32_t) { return storedBoot; }
  size_t putUInt(const char*, uint32_t value) {
    if (!writeOk) return 0;
    storedBoot = value; return sizeof(uint32_t);
  }
  void end() {}
};
struct FakeQueue { std::vector<unsigned char> data; size_t size; bool occupied = false; };
using QueueHandle_t = FakeQueue*;
inline QueueHandle_t xQueueCreate(int count, size_t size) {
  assert(count == 1); return new FakeQueue{{}, size, false};
}
inline void vQueueDelete(QueueHandle_t q) { delete q; }
inline int xQueueReceive(QueueHandle_t q, void* item, int) {
  if (!q->occupied) return 0;
  memcpy(item, q->data.data(), q->size); q->occupied = false; return pdTRUE;
}
inline int uxQueueMessagesWaiting(QueueHandle_t q) { return q->occupied; }
inline void xQueueOverwrite(QueueHandle_t q, const void* item) {
  auto bytes = static_cast<const unsigned char*>(item);
  q->data.assign(bytes, bytes + q->size); q->occupied = true;
}
inline int xTaskCreatePinnedToCore(void (*)(void*), const char*, int, void*, int, void*, int) { return pdPASS; }
inline void vTaskDelay(unsigned) {}
constexpr char WIFI_SSID[] = "TEST_ONLY";
constexpr char WIFI_PASSWORD[] = "";
constexpr char MQTT_HOST[] = "TEST_ONLY";
constexpr int MQTT_PORT = 1883;
constexpr char MQTT_USERNAME[] = "";
constexpr char MQTT_PASSWORD[] = "";
