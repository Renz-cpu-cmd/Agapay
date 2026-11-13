// HISTORICAL BENCH SKETCH: use agapay-firmware/src/main.cpp for official telemetry.
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ============================================================
// AGAPAY HARDWARE + WIFI + MQTT DEVELOPMENT TEST
//
// IMPORTANT:
// - Current distance thresholds are BENCH TEST values.
// - distance_cm is NOT yet calibrated water depth.
// - Public MQTT broker is DEVELOPMENT ONLY.
// ============================================================


// ========================== WIFI ==============================

// Credentials shared with the canonical firmware; never commit secrets.h.
#include "../agapay-firmware/include/secrets.h"


// ========================== MQTT ==============================

const char* MQTT_SERVER = "broker.hivemq.com";
// MQTT_PORT comes from the local secrets.h.

WiFiClient espClient;
PubSubClient mqttClient(espClient);

char mqttClientId[64];
char mqttTopic[128];


// =========================== PINS =============================

#define TRIG_PIN    5
#define ECHO_PIN    18

#define RAIN_PIN    4

#define BUZZER_PIN  25

#define LED_GREEN   26
#define LED_YELLOW  27
#define LED_RED     14


// ======================= BUZZER LOGIC =========================
// Your buzzer module is LOW-triggered.

#define BUZZER_ON   LOW
#define BUZZER_OFF  HIGH


// ======================== RAIN GAUGE ==========================

volatile unsigned long rainTipCount = 0;
volatile unsigned long lastRainInterruptUs = 0;

const unsigned long RAIN_DEBOUNCE_US = 50000;

const float MM_PER_TIP = 0.70;


// ==================== BENCH TEST THRESHOLDS ===================
// NOT final flood thresholds.

const float ADVISORY_DISTANCE_CM = 60.0;
const float WARNING_DISTANCE_CM  = 35.0;
const float EVACUATE_DISTANCE_CM = 25.0;


// ========================== TIMERS ============================

unsigned long lastSensorMs = 0;
unsigned long lastPublishMs = 0;

unsigned long lastWifiAttemptMs = 0;
unsigned long lastMqttAttemptMs = 0;

const unsigned long SENSOR_INTERVAL_MS = 1000;
const unsigned long PUBLISH_INTERVAL_MS = 5000;

const unsigned long WIFI_RETRY_MS = 10000;
const unsigned long MQTT_RETRY_MS = 5000;


// ======================== SENSOR STATE ========================

float latestDistanceCm = 0.0;
bool ultrasonicValid = false;

unsigned long sequenceNo = 0;


// ========================= ALERT TIER ==========================

enum AlertTier {
  NORMAL,
  ADVISORY,
  WARNING,
  EVACUATE
};

AlertTier currentTier = NORMAL;


// ============================================================
// RAIN GAUGE INTERRUPT
// ============================================================

void IRAM_ATTR rainTipISR() {

  unsigned long nowUs = micros();

  if (nowUs - lastRainInterruptUs > RAIN_DEBOUNCE_US) {

    rainTipCount++;

    lastRainInterruptUs = nowUs;
  }
}


// ============================================================
// ULTRASONIC
// ============================================================

bool readDistanceOnce(float &distanceCm) {

  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);

  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);

  digitalWrite(TRIG_PIN, LOW);

  unsigned long duration =
      pulseIn(ECHO_PIN, HIGH, 30000);

  if (duration == 0) {
    return false;
  }

  distanceCm =
      (duration * 0.0343f) / 2.0f;

  if (distanceCm < 20.0f ||
      distanceCm > 450.0f) {

    return false;
  }

  return true;
}


// ============================================================
// MEDIAN OF 5
// ============================================================

bool measureDistance(float &distanceCm) {

  float samples[5];

  int valid = 0;

  for (int i = 0; i < 5; i++) {

    float reading;

    if (readDistanceOnce(reading)) {

      samples[valid++] = reading;
    }

    delay(20);
  }


  if (valid < 3) {
    return false;
  }


  for (int i = 0; i < valid - 1; i++) {

    for (int j = i + 1; j < valid; j++) {

      if (samples[j] < samples[i]) {

        float temp = samples[i];

        samples[i] = samples[j];

        samples[j] = temp;
      }
    }
  }


  distanceCm = samples[valid / 2];

  return true;
}


// ============================================================
// ALERT CLASSIFICATION
// ============================================================

AlertTier classifyAlert(float distanceCm) {

  if (distanceCm <= EVACUATE_DISTANCE_CM)
    return EVACUATE;

  if (distanceCm <= WARNING_DISTANCE_CM)
    return WARNING;

  if (distanceCm <= ADVISORY_DISTANCE_CM)
    return ADVISORY;

  return NORMAL;
}


// ============================================================
// LOCAL ALERT OUTPUT
// ============================================================

void applyAlert(AlertTier tier) {

  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_YELLOW, LOW);
  digitalWrite(LED_RED, LOW);

  digitalWrite(BUZZER_PIN, BUZZER_OFF);


  switch (tier) {

    case NORMAL:

      digitalWrite(LED_GREEN, HIGH);

      break;


    case ADVISORY:

      digitalWrite(LED_YELLOW, HIGH);

      break;


    case WARNING:

      digitalWrite(LED_YELLOW, HIGH);

      break;


    case EVACUATE:

      digitalWrite(LED_RED, HIGH);

      digitalWrite(BUZZER_PIN, BUZZER_ON);

      break;
  }
}


const char* tierName(AlertTier tier) {

  switch (tier) {

    case NORMAL:
      return "NORMAL";

    case ADVISORY:
      return "ADVISORY";

    case WARNING:
      return "WARNING";

    case EVACUATE:
      return "EVACUATE";

    default:
      return "UNKNOWN";
  }
}


// ============================================================
// WIFI - NON-BLOCKING
// ============================================================

void maintainWiFi(unsigned long now) {

  if (WiFi.status() == WL_CONNECTED) {
    return;
  }


  if (now - lastWifiAttemptMs < WIFI_RETRY_MS) {
    return;
  }


  lastWifiAttemptMs = now;

  Serial.println();
  Serial.println("[WIFI] Attempting connection...");

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}


// ============================================================
// MQTT - NON-BLOCKING RETRY
// ============================================================

void maintainMQTT(unsigned long now) {

  if (WiFi.status() != WL_CONNECTED) {
    return;
  }


  if (mqttClient.connected()) {
    return;
  }


  if (now - lastMqttAttemptMs < MQTT_RETRY_MS) {
    return;
  }


  lastMqttAttemptMs = now;

  Serial.println("[MQTT] Attempting connection...");


  if (mqttClient.connect(mqttClientId)) {

    Serial.println("[MQTT] CONNECTED");

    Serial.print("[MQTT] Topic: ");
    Serial.println(mqttTopic);
  }

  else {

    Serial.print("[MQTT] Failed. State = ");
    Serial.println(mqttClient.state());
  }
}


// ============================================================
// MQTT TELEMETRY
// ============================================================

void publishTelemetry() {

  if (!mqttClient.connected()) {
    return;
  }


  noInterrupts();

  unsigned long tips = rainTipCount;

  interrupts();


  float rainfallTotalMm =
      tips * MM_PER_TIP;


  JsonDocument doc;


  doc["station_id"] = "STATION_001";

  doc["sequence_no"] = ++sequenceNo;

  doc["sensor_quality"] =
      ultrasonicValid ? "valid" : "invalid";


  // IMPORTANT:
  // This is still raw distance, NOT calibrated water depth.

  if (ultrasonicValid) {

    doc["distance_cm"] =
        latestDistanceCm;
  }

  else {

    doc["distance_cm"] = nullptr;
  }


  doc["rain_tip_total"] = tips;

  doc["rainfall_total_mm"] =
      rainfallTotalMm;

  doc["bench_alert_tier"] =
      tierName(currentTier);

  doc["device_uptime_ms"] =
      millis();

  doc["firmware_version"] =
      "0.2.0-hardware-mqtt-test";


  char payload[512];

  serializeJson(
    doc,
    payload,
    sizeof(payload)
  );


  bool published =
      mqttClient.publish(
        mqttTopic,
        payload
      );


  if (published) {

    Serial.println();
    Serial.println("[MQTT] PUBLISHED:");

    Serial.println(payload);
  }

  else {

    Serial.println(
      "[MQTT] Publish failed"
    );
  }
}


// ============================================================
// SETUP
// ============================================================

void setup() {

  Serial.begin(115200);


  // ---------------- ULTRASONIC ----------------

  pinMode(TRIG_PIN, OUTPUT);

  pinMode(ECHO_PIN, INPUT);


  // ---------------- RAIN ----------------

  pinMode(RAIN_PIN, INPUT_PULLUP);

  attachInterrupt(
    digitalPinToInterrupt(RAIN_PIN),
    rainTipISR,
    FALLING
  );


  // ---------------- LEDs ----------------

  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_RED, OUTPUT);


  // ---------------- BUZZER ----------------

  pinMode(BUZZER_PIN, OUTPUT);


  // Start in NORMAL local state.

  applyAlert(NORMAL);


  // ---------------- DEVICE ID ----------------

  uint32_t chip =
      (uint32_t)(ESP.getEfuseMac() & 0xFFFFFFFF);


  snprintf(
    mqttClientId,
    sizeof(mqttClientId),
    "AGAPAY_STATION_001_%08X",
    chip
  );


  snprintf(
    mqttTopic,
    sizeof(mqttTopic),
    "agapay/dev/ucu/STATION_001/%08X/telemetry",
    chip
  );


  // ---------------- MQTT ----------------

  mqttClient.setServer(
    MQTT_SERVER,
    MQTT_PORT
  );

  // Avoid very long network blocking.

  mqttClient.setSocketTimeout(2);

  mqttClient.setKeepAlive(15);


  // ---------------- WIFI ----------------

  WiFi.mode(WIFI_STA);

  WiFi.begin(
    WIFI_SSID,
    WIFI_PASSWORD
  );


  Serial.println();
  Serial.println("==============================================");
  Serial.println("      AGAPAY HARDWARE + MQTT TEST");
  Serial.println("==============================================");

  Serial.print("MQTT Client ID : ");
  Serial.println(mqttClientId);

  Serial.print("MQTT Topic     : ");
  Serial.println(mqttTopic);

  Serial.println("----------------------------------------------");
  Serial.println("LOCAL ALERTS WORK EVEN WITHOUT NETWORK");
  Serial.println("DISTANCE = BENCH TEST ONLY");
  Serial.println("==============================================");
}


// ============================================================
// LOOP
// ============================================================

void loop() {

  unsigned long now = millis();


  // ==========================================================
  // SENSOR + LOCAL ALERT LOOP
  // ==========================================================

  if (now - lastSensorMs >= SENSOR_INTERVAL_MS) {

    lastSensorMs = now;


    float distanceCm;


    ultrasonicValid =
        measureDistance(distanceCm);


    if (ultrasonicValid) {

      latestDistanceCm =
          distanceCm;


      currentTier =
          classifyAlert(
            latestDistanceCm
          );


      // IMPORTANT:
      // Local output happens independently of WiFi/MQTT.

      applyAlert(currentTier);
    }

    else {

      // Do NOT manufacture NORMAL when sensor fails.
      // Retain previous local alert state.

      Serial.println(
        "[SENSOR] INVALID - retaining previous alert state"
      );
    }


    noInterrupts();

    unsigned long tips =
        rainTipCount;

    interrupts();


    float rainfall =
        tips * MM_PER_TIP;


    Serial.println();
    Serial.println("----------------------------------------------");


    if (ultrasonicValid) {

      Serial.print("Distance : ");

      Serial.print(
        latestDistanceCm,
        1
      );

      Serial.println(" cm");
    }

    else {

      Serial.println(
        "Distance : INVALID"
      );
    }


    Serial.print("Status   : ");
    Serial.println(
      tierName(currentTier)
    );


    Serial.print("Rain Tips: ");
    Serial.println(tips);


    Serial.print("Rainfall : ");

    Serial.print(
      rainfall,
      2
    );

    Serial.println(" mm");


    if (WiFi.status() ==
        WL_CONNECTED) {

      Serial.print("WiFi     : CONNECTED | ");

      Serial.println(
        WiFi.localIP()
      );
    }

    else {

      Serial.println(
        "WiFi     : DISCONNECTED"
      );
    }


    Serial.print("MQTT     : ");

    Serial.println(
      mqttClient.connected()
      ? "CONNECTED"
      : "DISCONNECTED"
    );
  }


  // ==========================================================
  // NETWORK MAINTENANCE
  // ==========================================================

  maintainWiFi(now);

  maintainMQTT(now);


  if (mqttClient.connected()) {

    mqttClient.loop();
  }


  // ==========================================================
  // MQTT PUBLISH
  // ==========================================================

  if (now - lastPublishMs >= PUBLISH_INTERVAL_MS) {

    lastPublishMs = now;

    publishTelemetry();
  }
}
