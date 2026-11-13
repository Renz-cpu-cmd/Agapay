// AGAPAY SH1106 OLED: pure display decisions (no Arduino/U8g2 dependency; host-tested).
//
// The display is a read-only view of what the firmware already decided. It never
// classifies water itself: the tier shown is the LOCAL tier that drives the LEDs and
// buzzer (direct depth thresholds from the generated station configuration, no
// hysteresis; backend alerts add 2 cm hysteresis and recovery rules of their own).
// An invalid, stale or missing reading is never shown as NORMAL.
#pragma once
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

namespace oled {

// Mirrors AlertTier in src/main.cpp (same order).
enum class Tier : uint8_t { UNKNOWN, NORMAL, ADVISORY, WARNING, EVACUATE };
enum class Reading : uint8_t { WAITING, VALID, STALE, SENSOR_ERROR };

constexpr uint8_t PAGE_COUNT = 6;
constexpr uint32_t PAGE_MS = 5000;
// Sensor cadence is 1 s; five missed cycles means sampling stopped, not "no change".
constexpr uint32_t STALE_AFTER_MS = 5000;

// Advisory forecast received over MQTT (agapay/stations/<id>/forecast). Display-only:
// it never changes the local tier, LEDs, buzzer or the EVACUATE override.
enum class ForecastState : uint8_t { NONE, AVAILABLE, NOT_AVAILABLE, REJECTED };
struct ForecastPoint { uint8_t horizonMin = 0; float depthCm = NAN, lowerCm = NAN, upperCm = NAN; };
struct ForecastView {
  ForecastState state = ForecastState::NONE;
  char status[20] = "";            // server status when NOT_AVAILABLE
  const char* rejected = "";       // static reason when REJECTED
  uint32_t receivedMs = 0;
  uint32_t lifetimeMs = 0;         // AVAILABLE only: numbers vanish after this
  uint8_t count = 0;
  ForecastPoint points[3];
  bool fresh(uint32_t nowMs) const {
    return state == ForecastState::AVAILABLE && static_cast<uint32_t>(nowMs - receivedMs) < lifetimeMs;
  }
};

inline const char* forecastStatusText(const char* status) {
  if (strcmp(status, "not_trained") == 0) return "Model not trained";
  if (strcmp(status, "unavailable") == 0) return "Not published";
  if (strcmp(status, "insufficient_data") == 0) return "Not enough data";
  if (strcmp(status, "stale_data") == 0) return "Input data stale";
  if (strcmp(status, "invalid_data") == 0) return "Input data invalid";
  if (strcmp(status, "service_error") == 0) return "Server error";
  return "Unavailable";
}

struct Inputs {
  uint32_t nowMs = 0;              // uptime (ms) when the frame is drawn
  Tier localTier = Tier::UNKNOWN;  // tier driving LEDs/buzzer; EVACUATE latches across faults
  bool benchProfile = false;       // cardboard demo: tiers from raw distance, not depth
  bool prototypeGeometry = true;   // built from prototype_config.h (unvalidated bench datum)
  bool anySample = false;          // a 5-ping sample has completed since boot
  bool sampleValid = false;        // the latest completed sample was trustworthy
  uint32_t sampleMs = 0;           // uptime of the latest completed sample
  bool everValid = false;
  uint32_t lastValidMs = 0;
  float lastValidDepthCm = NAN;
  float lastValidDistanceCm = NAN;
  const char* sensorFault = "none";  // none | no_echo | blind_zone | out_of_range | insufficient_echoes
  bool outputSelfTest = false;     // serial ALERT TEST in progress (LEDs/buzzer exercised)
  // Rain (durable physical tip counter).
  uint64_t rainLifetimeTips = 0;
  uint64_t rainBootTips = 0;       // lifetime count when this boot started
  bool rainPersistenceOk = true;
  bool rainTipSinceBoot = false;
  uint32_t rainLastTipMs = 0;
  bool rainWindowReady = false;    // a full 60-minute window has been observed
  uint64_t rainTipsLast60Min = 0;
  uint32_t rainWindowMinutesLeft = 60;
  // Configuration actually compiled in (generated from the backend station configuration).
  const char* stationId = "";
  const char* firmwareVersion = "";
  unsigned configRevision = 0;
  float sensorHeightCm = NAN, minDistanceCm = NAN;
  float advisoryCm = NAN, warningCm = NAN, evacuateCm = NAN;              // DEPTH tiers
  float benchAdvisoryCm = NAN, benchWarningCm = NAN, benchRedCm = NAN;    // DEMO distance tiers
  float mmPerTip = NAN;
  ForecastView forecast;           // written by the network task only
  // Network (written by the network task only).
  bool wifiUp = false;
  bool mqttUp = false;
  int16_t rssiDbm = 0;
  char ip[16] = "";
};

inline Reading reading(const Inputs& in) {
  if (!in.anySample) return Reading::WAITING;
  if (static_cast<uint32_t>(in.nowMs - in.sampleMs) > STALE_AFTER_MS) return Reading::STALE;
  return in.sampleValid ? Reading::VALID : Reading::SENSOR_ERROR;
}

// EVACUATE interrupts paging. The firmware keeps red+buzzer latched when a sensor
// fault follows an EVACUATE sample, so the display keeps the emergency screen too.
inline bool emergency(const Inputs& in) { return in.localTier == Tier::EVACUATE; }
inline bool latchedEmergency(const Inputs& in) { return emergency(in) && reading(in) != Reading::VALID; }

inline uint8_t page(const Inputs& in) { return static_cast<uint8_t>((in.nowMs / PAGE_MS) % PAGE_COUNT); }
// 0..1000 progress through the current page, for the footer progress line.
inline uint16_t pageProgress(const Inputs& in) { return static_cast<uint16_t>((in.nowMs % PAGE_MS) * 1000UL / PAGE_MS); }

inline const char* tierName(Tier tier) {
  switch (tier) {
    case Tier::NORMAL: return "NORMAL";
    case Tier::ADVISORY: return "ADVISORY";
    case Tier::WARNING: return "WARNING";
    case Tier::EVACUATE: return "EVACUATE";
    default: return "NO DATA";
  }
}

// What the alert label says. Only a VALID reading may show a measured tier.
inline const char* statusLabel(const Inputs& in) {
  if (latchedEmergency(in)) return "EVACUATE";
  switch (reading(in)) {
    case Reading::VALID: return tierName(in.localTier);
    case Reading::WAITING: return "NO DATA YET";
    case Reading::STALE: return "DATA STALE";
    default: return "SENSOR ERROR";
  }
}

inline const char* guidance(const Inputs& in) {
  if (emergency(in)) return "Follow evacuation orders";
  switch (reading(in)) {
    case Reading::WAITING: return "Measuring, please wait";
    case Reading::STALE: return "Sensor sampling stopped";
    case Reading::SENSOR_ERROR: return "Sensor fault: check unit";
    default: break;
  }
  switch (in.localTier) {
    case Tier::NORMAL: return "Below advisory level";
    case Tier::ADVISORY: return "Water rising - stay alert";
    case Tier::WARNING: return "Prepare to evacuate";
    default: return "Sensor fault: check unit";
  }
}

inline const char* faultText(const char* fault) {
  if (fault == nullptr || strcmp(fault, "none") == 0) return "OK";
  if (strcmp(fault, "no_echo") == 0) return "NO ECHO";
  if (strcmp(fault, "blind_zone") == 0) return "TOO CLOSE";
  if (strcmp(fault, "out_of_range") == 0) return "OUT OF RANGE";
  if (strcmp(fault, "insufficient_echoes") == 0) return "WEAK ECHO";
  return "FAULT";
}

// "2d 03:04:05" or "03:04:05" (hours wrap into days).
inline void formatUptime(uint32_t ms, char* out, size_t size) {
  const uint32_t seconds = ms / 1000;
  const uint32_t days = seconds / 86400;
  const unsigned h = (seconds / 3600) % 24, m = (seconds / 60) % 60, s = seconds % 60;
  if (days) snprintf(out, size, "%lud %02u:%02u:%02u", static_cast<unsigned long>(days), h, m, s);
  else snprintf(out, size, "%02u:%02u:%02u", h, m, s);
}

// "12s", "4m", "3h", "2d" since an uptime stamp.
inline void formatAge(uint32_t nowMs, uint32_t thenMs, char* out, size_t size) {
  const uint32_t s = static_cast<uint32_t>(nowMs - thenMs) / 1000;
  if (s < 60) snprintf(out, size, "%lus", static_cast<unsigned long>(s));
  else if (s < 3600) snprintf(out, size, "%lum", static_cast<unsigned long>(s / 60));
  else if (s < 86400) snprintf(out, size, "%luh", static_cast<unsigned long>(s / 3600));
  else snprintf(out, size, "%lud", static_cast<unsigned long>(s / 86400));
}

// Rolling 60-minute rain total from the durable lifetime counter, sampled once a
// minute. Reported only after a full hour has actually been observed this boot;
// nothing is extrapolated, and no 24 h total is invented.
class RainWindow {
 public:
  static constexpr uint8_t SLOTS = 61;  // 60 one-minute intervals
  void update(uint32_t nowMs, uint64_t lifetimeTips) {
    if (count_ && static_cast<uint32_t>(nowMs - lastMs_) < 60000UL) return;
    lastMs_ = count_ ? lastMs_ + 60000UL : nowMs;
    head_ = static_cast<uint8_t>((head_ + 1) % SLOTS);
    slots_[head_] = lifetimeTips;
    if (count_ < SLOTS) ++count_;
  }
  bool ready() const { return count_ == SLOTS; }
  uint64_t tipsLastHour() const {
    if (!ready()) return 0;
    const uint64_t oldest = slots_[(head_ + 1) % SLOTS];
    return slots_[head_] >= oldest ? slots_[head_] - oldest : 0;
  }
  uint32_t minutesLeft() const { return ready() ? 0 : static_cast<uint32_t>(SLOTS - count_); }

 private:
  uint64_t slots_[SLOTS] = {};
  uint8_t head_ = 0;
  uint8_t count_ = 0;
  uint32_t lastMs_ = 0;
};

}  // namespace oled
