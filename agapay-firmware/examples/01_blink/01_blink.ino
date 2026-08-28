// AGAPAY Day 1: ESP32 Blink test
// For a typical ESP32 DevKit V1, the onboard blue LED is connected to GPIO 2.

constexpr int LED_PIN = 2;

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  Serial.println("AGAPAY ESP32 Blink test started");
}

void loop() {
  digitalWrite(LED_PIN, HIGH);
  Serial.println("LED ON");
  delay(1000);

  digitalWrite(LED_PIN, LOW);
  Serial.println("LED OFF");
  delay(1000);
}
