// ============================================================
// AGAPAY COMPLETE HARDWARE INTEGRATION TEST
// ESP32 + Ultrasonic + Rain Gauge + LEDs + Buzzer
//
// IMPORTANT:
// Distance thresholds below are BENCH TEST thresholds only.
// They are NOT final calibrated flood thresholds.
// ============================================================


// ======================= PIN DEFINITIONS =====================

#define TRIG_PIN     5
#define ECHO_PIN     18

#define RAIN_PIN     4

#define BUZZER_PIN   25

#define LED_GREEN    26
#define LED_YELLOW   27
#define LED_RED      14


// ======================= BUZZER LOGIC ========================
// MH-FMD module is LOW-level triggered.

#define BUZZER_ON    LOW
#define BUZZER_OFF   HIGH


// ======================== RAIN GAUGE =========================

volatile unsigned long rainTipCount = 0;
volatile unsigned long lastRainInterruptUs = 0;

const unsigned long RAIN_DEBOUNCE_US = 50000;   // 50 ms

const float MM_PER_TIP = 0.70;


// ================= TEMPORARY BENCH THRESHOLDS ================
//
// As water/object moves CLOSER to sensor,
// measured distance becomes SMALLER.
//
// THESE ARE NOT FINAL AGAPAY FLOOD THRESHOLDS.

const float ADVISORY_DISTANCE_CM = 60.0;
const float WARNING_DISTANCE_CM  = 35.0;
const float EVACUATE_DISTANCE_CM = 25.0;


// ========================= ALERT TIERS ========================

enum AlertTier {
  NORMAL,
  ADVISORY,
  WARNING,
  EVACUATE
};


// ======================= RAIN INTERRUPT =======================

void IRAM_ATTR rainTipISR() {

  unsigned long nowUs = micros();

  if (nowUs - lastRainInterruptUs > RAIN_DEBOUNCE_US) {

    rainTipCount++;

    lastRainInterruptUs = nowUs;
  }
}


// ====================== ULTRASONIC READING ====================

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

  if (distanceCm < 20.0 || distanceCm > 450.0) {
    return false;
  }

  return true;
}


// ======================== MEDIAN FILTER =======================

bool measureDistance(float &distanceCm) {

  float readings[5];

  int validCount = 0;

  for (int i = 0; i < 5; i++) {

    float reading;

    if (readDistanceOnce(reading)) {

      readings[validCount] = reading;

      validCount++;
    }

    delay(20);
  }


  if (validCount < 3) {

    return false;
  }


  // Sort valid readings

  for (int i = 0; i < validCount - 1; i++) {

    for (int j = i + 1; j < validCount; j++) {

      if (readings[j] < readings[i]) {

        float temp = readings[i];

        readings[i] = readings[j];

        readings[j] = temp;
      }
    }
  }


  // Median value

  distanceCm =
      readings[validCount / 2];

  return true;
}


// ======================= ALERT CLASSIFIER =====================

AlertTier classifyAlert(float distanceCm) {

  if (distanceCm <= EVACUATE_DISTANCE_CM) {

    return EVACUATE;
  }

  if (distanceCm <= WARNING_DISTANCE_CM) {

    return WARNING;
  }

  if (distanceCm <= ADVISORY_DISTANCE_CM) {

    return ADVISORY;
  }

  return NORMAL;
}


// ======================== ALERT OUTPUT ========================

void applyAlert(AlertTier tier) {

  // First turn everything OFF

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

      // For now WARNING also uses yellow.
      // Later we can implement blinking behavior.

      digitalWrite(LED_YELLOW, HIGH);

      break;


    case EVACUATE:

      digitalWrite(LED_RED, HIGH);

      digitalWrite(BUZZER_PIN, BUZZER_ON);

      break;
  }
}


// ========================== TIER TEXT =========================

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


// ============================= SETUP ==========================

void setup() {

  Serial.begin(115200);


  // Ultrasonic

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);


  // Rain gauge

  pinMode(RAIN_PIN, INPUT_PULLUP);

  attachInterrupt(
    digitalPinToInterrupt(RAIN_PIN),
    rainTipISR,
    FALLING
  );


  // LEDs

  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_RED, OUTPUT);


  // Buzzer

  pinMode(BUZZER_PIN, OUTPUT);


  // Initial safe state

  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_YELLOW, LOW);
  digitalWrite(LED_RED, LOW);

  digitalWrite(BUZZER_PIN, BUZZER_OFF);


  Serial.println();
  Serial.println("============================================");
  Serial.println("       AGAPAY SENSOR NODE TEST");
  Serial.println("============================================");
  Serial.println("Ultrasonic : GPIO 5 / GPIO 18");
  Serial.println("Rain Gauge : GPIO 4");
  Serial.println("Green LED  : GPIO 26");
  Serial.println("Yellow LED : GPIO 27");
  Serial.println("Red LED    : GPIO 14");
  Serial.println("Buzzer     : GPIO 25");
  Serial.println("Rain Gauge : 0.70 mm/tip");
  Serial.println("--------------------------------------------");
  Serial.println("BENCH TEST MODE - NOT FINAL FLOOD THRESHOLDS");
  Serial.println("============================================");
}


// ============================= LOOP ===========================

void loop() {

  float distanceCm = 0;

  bool ultrasonicValid =
      measureDistance(distanceCm);


  // Safely copy interrupt counter

  noInterrupts();

  unsigned long tips =
      rainTipCount;

  interrupts();


  float rainfallMm =
      tips * MM_PER_TIP;


  Serial.println();
  Serial.println("--------------------------------------------");


  // ================= ULTRASONIC =================

  if (ultrasonicValid) {

    AlertTier tier =
        classifyAlert(distanceCm);

    applyAlert(tier);


    Serial.print("Distance : ");
    Serial.print(distanceCm, 1);
    Serial.println(" cm");


    Serial.print("Status   : ");
    Serial.println(tierName(tier));
  }

  else {

    // Keep buzzer OFF for this bench test
    // and show invalid sensor condition.

    digitalWrite(LED_GREEN, LOW);
    digitalWrite(LED_YELLOW, LOW);
    digitalWrite(LED_RED, LOW);

    digitalWrite(BUZZER_PIN, BUZZER_OFF);


    Serial.println("Distance : INVALID");
    Serial.println("Status   : SENSOR ERROR");
  }


  // ================= RAINFALL ====================

  Serial.print("Rain Tips: ");
  Serial.println(tips);

  Serial.print("Rainfall : ");
  Serial.print(rainfallMm, 2);
  Serial.println(" mm");


  delay(1000);
}