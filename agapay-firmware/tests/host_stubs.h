#pragma once
// Host-only fakes. These tests never open sockets or access physical GPIO/NVS.
#include <cassert>
#include <cstdarg>
#include <cstdint>
#include <cstring>
#include <deque>
#include <string>
#include <vector>
#include <map>
inline std::map<std::string,std::vector<uint8_t>> fakeDepthFiles;
inline bool fakeDepthWriteFailure=false, fakeDepthRenameFailure=false, fakeDepthRemoveFailure=false;
struct FakeDepthFile {
  std::string name; bool available=false;
  explicit operator bool() const {return available;}
  size_t size() const {return fakeDepthFiles[name].size();}
  size_t read(uint8_t* data,size_t length) {
    auto& bytes=fakeDepthFiles[name];if(bytes.size()!=length)return 0;
    memcpy(data,bytes.data(),length);return length;
  }
  size_t write(const uint8_t* data,size_t length) {
    if(fakeDepthWriteFailure)return 0;
    fakeDepthFiles[name].assign(data,data+length);return length;
  }
  void flush() {} void close() {}
};
struct FakeLittleFS {
  bool begin(bool format) {assert(!format);return true;}
  bool exists(const char* name) {return fakeDepthFiles.count(name);}
  bool mkdir(const char*) {return true;}
  FakeDepthFile open(const char* name,const char* mode) {
    if(mode[0]=='w')fakeDepthFiles[name]={};
    return {name,exists(name)};
  }
  bool rename(const char* from,const char* to) {
    if(fakeDepthRenameFailure)return false;
    if(!exists(from))return false;
    fakeDepthFiles[to]=fakeDepthFiles[from];fakeDepthFiles.erase(from);return true;
  }
  bool remove(const char* name) {return !fakeDepthRemoveFailure && fakeDepthFiles.erase(name)>0;}
};
inline FakeLittleFS LittleFS;
#include <sys/time.h>
#include <ctime>
inline std::tm* gmtime_r(const std::time_t* value, std::tm* output) {
  const std::tm* result = std::gmtime(value);
  if (result) *output = *result;
  return result ? output : nullptr;
}
inline int64_t fakeUtcMs = 1792530000000LL;
inline int fakeGettimeofday(struct timeval* value, void*) {
  value->tv_sec = fakeUtcMs / 1000;
  value->tv_usec = (fakeUtcMs % 1000) * 1000;
  return 0;
}
#define gettimeofday fakeGettimeofday
inline void configTime(long, int, const char*, const char*) {}
#define AGAPAY_DEVICE_ID "TEST_STATION_001"
#define AGAPAY_CONFIG_VERSION 1
#define IRAM_ATTR
#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define INPUT 0
#define INPUT_PULLUP 2
#define FALLING 2
#define WL_CONNECTED 3
#define WL_IDLE_STATUS 0
#define WL_NO_SSID_AVAIL 1
#define WL_SCAN_COMPLETED 2
#define WL_CONNECT_FAILED 4
#define WL_CONNECTION_LOST 5
#define WL_DISCONNECTED 6
#define WL_NO_SHIELD 255
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
inline int64_t esp_timer_get_time() { return static_cast<int64_t>(fakeMs)*1000; }
inline uint32_t esp_random() { static uint32_t n=0;return ++n; }
inline int esp_reset_reason() { return 1; }
inline void pinMode(int, int) {}
inline void digitalWrite(int pin, int value) { pins[pin] = value; }
inline int digitalRead(int pin) { return pins[pin]; }
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
  std::deque<char> input;
  int available() { return static_cast<int>(input.size()); }
  int read() { if (input.empty()) return -1; int c=input.front(); input.pop_front(); return c; }
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
using WiFiEvent_t = int;
constexpr WiFiEvent_t ARDUINO_EVENT_WIFI_STA_DISCONNECTED = 5;
constexpr WiFiEvent_t ARDUINO_EVENT_WIFI_SCAN_DONE = 1;
constexpr WiFiEvent_t ARDUINO_EVENT_WIFI_STA_CONNECTED = 4;
constexpr WiFiEvent_t ARDUINO_EVENT_WIFI_STA_GOT_IP = 7;
constexpr WiFiEvent_t ARDUINO_EVENT_WIFI_STA_LOST_IP = 9;
struct WiFiEventInfo_t {
  struct { uint8_t reason; } wifi_sta_disconnected;
  struct { uint32_t status;uint8_t number,scan_id; } wifi_scan_done;
  struct { uint8_t bssid[6];uint8_t channel;int authmode; } wifi_sta_connected;
};
enum wifi_auth_mode_t { WIFI_AUTH_OPEN, WIFI_AUTH_WEP, WIFI_AUTH_WPA_PSK, WIFI_AUTH_WPA2_PSK,
  WIFI_AUTH_WPA_WPA2_PSK, WIFI_AUTH_WPA2_ENTERPRISE, WIFI_AUTH_WPA3_PSK, WIFI_AUTH_WPA2_WPA3_PSK };
struct wifi_ap_record_t {
  uint8_t bssid[6]{};
  uint8_t ssid[33]{};
  uint8_t primary=11;
  int8_t rssi=-55;
  wifi_auth_mode_t authmode=WIFI_AUTH_WPA2_PSK;
};
constexpr int WIFI_SCAN_RUNNING=-1, WIFI_SCAN_FAILED=-2;
using esp_err_t=int;
constexpr esp_err_t ESP_OK=0;
enum wifi_country_policy_t { WIFI_COUNTRY_POLICY_AUTO, WIFI_COUNTRY_POLICY_MANUAL };
struct wifi_country_t { char cc[3]={'C','N',0};uint8_t schan=1,nchan=13;int8_t max_tx_power=20;wifi_country_policy_t policy=WIFI_COUNTRY_POLICY_AUTO; };
inline wifi_country_t fakeCountry{};
inline esp_err_t fakeCountryResult=ESP_OK;
inline esp_err_t esp_wifi_get_country(wifi_country_t* country) { *country=fakeCountry;return fakeCountryResult; }
inline int scanStopCalls=0;
inline esp_err_t esp_wifi_scan_stop() { ++scanStopCalls;return 0; }
inline const char* esp_err_to_name(esp_err_t error) { return error==ESP_OK?"ESP_OK":"TEST_ERROR"; }
struct FakeScanResult { int16_t result; std::vector<wifi_ap_record_t> records; };
struct FakeScanParameters { bool passive;uint32_t dwell;uint8_t channel; };
struct WiFiFake {
  int state = 0;
  int beginCalls = 0;
  int pinnedBeginCalls=0,lastBeginChannel=0;
  uint8_t lastBeginBssid[6]={};
  const char* lastBeginPassword=nullptr;
  bool modeResult = true;
  int scanCalls=0, scanDeleteCalls=0;
  int16_t scanResult=0;
  uint32_t driverScanStatus=0;
  bool emitScanDone=true;
  std::vector<wifi_ap_record_t> accessPoints;
  std::deque<FakeScanResult> scanResults;
  std::vector<FakeScanParameters> scanParameters;
  std::vector<std::string> operations;
  void (*eventCallback)(WiFiEvent_t,WiFiEventInfo_t) = nullptr;
  int status() { return state; }
  bool mode(int) { operations.emplace_back("mode");return modeResult; }
  int begin(const char* ssid, const char* password) { assert(strcmp(ssid,WIFI_SSID_TEST)==0 && password);lastBeginPassword=password;operations.emplace_back("begin"); ++beginCalls; return state; }
  int begin(const char* ssid,const char* password,int channel,const uint8_t* bssid,bool connect) {
    assert(connect && bssid);++pinnedBeginCalls;lastBeginChannel=channel;memcpy(lastBeginBssid,bssid,6);return begin(ssid,password);
  }
  static constexpr char WIFI_SSID_TEST[] = "BENCH_TEST_AP";
  void onEvent(void (*callback)(WiFiEvent_t,WiFiEventInfo_t)) { eventCallback=callback; }
  struct IP { std::string toString() { return "10.0.0.2"; } };
  IP localIP() { return {}; }
  int RSSI() { return -55; }
  std::string macAddress() { return "02:00:00:00:00:01"; }
  int16_t scanNetworks(bool async, bool hidden, bool passive=false,uint32_t dwell=300,uint8_t channel=0) {
    assert(!async && hidden);operations.emplace_back("scan");++scanCalls;
    scanParameters.push_back({passive,dwell,channel});
    if(!scanResults.empty()) {auto next=scanResults.front();scanResults.pop_front();scanResult=next.result;accessPoints=next.records;}
    if(scanResult>=0 && eventCallback && emitScanDone) {
      WiFiEventInfo_t info{};info.wifi_scan_done={driverScanStatus,static_cast<uint8_t>(scanResult),static_cast<uint8_t>(scanCalls)};
      eventCallback(ARDUINO_EVENT_WIFI_SCAN_DONE,info);
    }
    return scanResult;
  }
  int16_t scanComplete() { return scanResult==WIFI_SCAN_RUNNING?WIFI_SCAN_FAILED:scanResult; }
  void* getScanInfoByIndex(int i) { return static_cast<size_t>(i)<accessPoints.size()?&accessPoints[i]:nullptr; }
  void scanDelete() { ++scanDeleteCalls;accessPoints.clear(); }
};
inline WiFiFake WiFi;
struct WiFiClient {};
struct WiFiClientSecure:WiFiClient{const char* ca=nullptr;int handshake=0;void setCACert(const char* value){ca=value;}void setHandshakeTimeout(unsigned value){handshake=value;}};
struct PubSubClient {
  bool online = false, publishResult = true;
  bool connectResult = false, subscribeResult = true, bufferResult = true;
  int stateCode = -1, connectCalls = 0, subscribeCalls = 0, publishCalls = 0;
  bool authenticatedConnect = false;
  std::string lastPayload, lastTopic;
  explicit PubSubClient(WiFiClient&) {}
  bool connected() { return online; }
  bool connect(const char*) { ++connectCalls; online=connectResult; if(online)stateCode=0; return online; }
  bool connect(const char* id, const char* user, const char* password) { assert(user && password);authenticatedConnect=true;return connect(id); }
  int state() { return stateCode; }
  void setServer(const char*, int) {}
  bool setBufferSize(int) { return bufferResult; }
  void setSocketTimeout(int) {}
  void setKeepAlive(int) {}
  void setCallback(void (*)(char*,uint8_t*,unsigned int)) {}
  bool subscribe(const char*,int) { ++subscribeCalls; return subscribeResult; }
  void loop() {}
  bool publish(const char* topic, const char* payload, bool retained) {
    assert(!retained); ++publishCalls; lastPayload = payload; lastTopic = topic; return publishResult;
  }
};
struct Preferences {
  uint32_t storedBoot = 0;
  uint64_t storedLifetime = 0;
  bool openOk = true, writeOk = true;
  bool begin(const char*, bool) { return openOk; }
  uint32_t getUInt(const char*, uint32_t) { return storedBoot; }
  uint64_t getULong64(const char*,uint64_t) {return storedLifetime;}
  size_t putULong64(const char*,uint64_t value) {if(!writeOk)return 0;storedLifetime=value;return sizeof(uint64_t);}
  size_t putUInt(const char*, uint32_t value) {
    if (!writeOk) return 0;
    storedBoot = value; return sizeof(uint32_t);
  }
  void end() {}
};
struct FakeQueue { std::vector<unsigned char> data; size_t size; bool occupied = false; };
using QueueHandle_t = FakeQueue*;
inline int queueCreateCalls=0, failQueueCreateCall=0;
inline int taskCreateCalls=0, taskCreateResult=pdPASS;
inline QueueHandle_t xQueueCreate(int count, size_t size) {
  if (++queueCreateCalls==failQueueCreateCall) return nullptr;
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
inline int xTaskCreatePinnedToCore(void (*)(void*), const char*, int, void*, int, void*, int) { ++taskCreateCalls;return taskCreateResult; }
inline void vTaskDelay(unsigned) {}
inline void vTaskDelete(void*) {}
inline unsigned uxTaskGetStackHighWaterMark(void*) { return 1024; }
// Synthetic network identity only. The optional pin uses a locally administered (02:...) address.
constexpr char WIFI_SSID[] = "BENCH_TEST_AP";
#ifndef AGAPAY_HOST_NO_WIFI_PIN
#define AGAPAY_WIFI_PIN_BSSID 0x02,0x00,0x5E,0x10,0x20,0x30
#define AGAPAY_WIFI_PIN_CHANNEL 11
#endif
constexpr char WIFI_PASSWORD[] = "HOST_WIFI_PASSWORD";
constexpr char MQTT_HOST[] = "TEST_ONLY";
#if AGAPAY_RELEASE_BUILD
constexpr int MQTT_PORT=8883;
constexpr char MQTT_ROOT_CA[]="-----BEGIN CERTIFICATE-----" "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX";
#else
constexpr int MQTT_PORT = 1883;
#endif
constexpr char MQTT_USERNAME[] = "STATION_001";
constexpr char MQTT_PASSWORD[] = "HOST_FAKE_PASSWORD_ONLY_NOT_A_REAL_SECRET";
// Synthetic host-only credential; no real station or broker uses this value.
#ifdef AGAPAY_HOST_UNPROVISIONED
constexpr char STATION_INGEST_TOKEN[] = "";
#else
constexpr char STATION_INGEST_TOKEN[] = "agi_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopq";
#endif
