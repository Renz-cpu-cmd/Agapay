// Compile the actual firmware against host fakes and the actual ArduinoJson library.
#include "../src/main.cpp"
#include <iostream>
#include <limits>

void expectNear(float actual, float expected) { assert(fabs(actual - expected) < 0.01F); }
void setMedian(float distance) {
  validSamples = 5;
  for (int i = 0; i < 5; ++i) distanceSamples[i] = distance;
  finishSensorSample();
}
void expectPins(int green, int yellow, int red, int buzzer) {
  assert(pins[LED_GREEN] == green && pins[LED_YELLOW] == yellow);
  assert(pins[LED_RED] == red && pins[BUZZER_PIN] == buzzer);
}
int main() {
  setup();
  assert(currentTier == AlertTier::UNKNOWN);
  expectPins(LOW, LOW, LOW, HIGH);
  validSamples = 0; finishSensorSample();
  assert(!latestSample.sensorValid && currentTier == AlertTier::UNKNOWN);
  expectPins(LOW, LOW, LOW, HIGH);

  float value;
  echoes = {0, 100, 29000, 5831};
  assert(!readDistanceOnce(value) && isnan(value)); // timeout
  assert(!readDistanceOnce(value)); // too close
  assert(!readDistanceOnce(value)); // too far
  assert(readDistanceOnce(value)); expectNear(value, 100.00165F);
  float samples[] = {80, 30, 50, 40, 60};
  assert(measureDistanceMedian(samples, 5, value)); expectNear(value, 50);
  float four[] = {20, 60, 40, 80};
  assert(measureDistanceMedian(four, 4, value)); expectNear(value, 60);
  assert(measureDistanceMedian(four, 3, value)); expectNear(value, 40);
  assert(!measureDistanceMedian(four, 2, value) && isnan(value));
  assert(calculateWaterDepth(77.3F, value)); expectNear(value, 42.7F);
  assert(calculateWaterDepth(120, value)); expectNear(value, 0);
  assert(!calculateWaterDepth(121, value) && isnan(value));
  assert(!calculateWaterDepth(19, value));
  assert(!calculateWaterDepth(451, value));
  assert(!calculateWaterDepth(NAN, value));
  assert(!calculateWaterDepth(std::numeric_limits<float>::infinity(), value));

  assert(classifyAlert(59.99F) == AlertTier::NORMAL);
  assert(classifyAlert(60) == AlertTier::ADVISORY);
  assert(classifyAlert(85) == AlertTier::WARNING);
  assert(classifyAlert(100) == AlertTier::EVACUATE);
  // Wi-Fi and MQTT stay disconnected throughout all local GPIO checks.
  assert(!mqttClient.connected() && WiFi.status() != WL_CONNECTED);
  setMedian(100); expectPins(HIGH, LOW, LOW, HIGH);
  setMedian(60); expectPins(LOW, HIGH, LOW, HIGH);
  setMedian(35); expectPins(LOW, HIGH, LOW, HIGH);
  setMedian(20); expectPins(LOW, LOW, HIGH, LOW);
  validSamples = 2; finishSensorSample();
  assert(!latestSample.sensorValid && isnan(latestSample.waterDepthCm));
  assert(currentTier == AlertTier::EVACUATE); expectPins(LOW, LOW, HIGH, LOW);
  setMedian(121); // valid raw range but impossible negative depth
  assert(!latestSample.sensorValid && currentTier == AlertTier::EVACUATE);
  expectPins(LOW, LOW, HIGH, LOW);

  // Burst scheduler: five probes, including invalid outliers, once per second.
  sampling = false; lastSensorMs = 0;
  echoes = {5831, 0, 100, 5831, 5831};
  sampleSensors(999); assert(echoes.size() == 5);
  sampleSensors(1000); assert(echoes.size() == 4);
  sampleSensors(1001); assert(echoes.size() == 4);
  for (uint32_t t = 1060; t <= 1240; t += 60) sampleSensors(t);
  assert(!sampling && latestSample.sensorValid); expectNear(latestSample.waterDepthCm, 20);
  sampleSensors(1500); assert(!sampling);
  sampling = false; lastSensorMs = UINT32_MAX - 500;
  echoes = {0, 0, 0, 0, 0};
  sampleSensors(499); assert(sampling); // millis wrap
  for (uint32_t t = 559; t <= 739; t += 60) sampleSensors(t);
  assert(!latestSample.sensorValid);

  rainTipCount = 0; rainTipSeen = false;
  expectNear(snapshotRainfallInterval(), 0);
  fakeUs = 1; rainTipISR(); // first tip need not wait for debounce after boot
  fakeUs = 50000; rainTipISR(); // 49999 us: bounce ignored
  expectNear(snapshotRainfallInterval(), 0.70F);
  fakeUs = 50001; rainTipISR();
  fakeUs = 100001; rainTipISR();
  expectNear(snapshotRainfallInterval(), 1.40F);
  expectNear(snapshotRainfallInterval(), 0);
  fakeUs = 150001; rainTipISR();
  fakeUs = 200001;
  afterUnlock = rainTipISR; // a new tip immediately AFTER copy/reset
  expectNear(snapshotRainfallInterval(), 0.70F);
  expectNear(snapshotRainfallInterval(), 0.70F); // not lost or double counted
  rainTipSeen = true; lastRainInterruptUs = UINT32_MAX - 20000;
  fakeUs = 30000; rainTipISR(); // micros wrap
  expectNear(snapshotRainfallInterval(), 0.70F);

  uint64_t seq;
  assert(nextSequenceNumber(seq) && seq == 1000001);
  assert(nextSequenceNumber(seq) && seq == 1000002);
  sequenceReady = reserveSequenceBlock(); // simulated ordinary reboot
  assert(nextSequenceNumber(seq) && seq == 2000001);
  sequenceNo = sequenceLimit;
  assert(nextSequenceNumber(seq) && seq == 3000001); // exhausted block
  preferences.writeOk = false; sequenceNo = sequenceLimit;
  assert(!nextSequenceNumber(seq) && !sequenceReady);
  preferences.writeOk = true; preferences.openOk = false;
  assert(!reserveSequenceBlock());
  preferences.openOk = true; preferences.storedBoot = UINT32_MAX;
  assert(!reserveSequenceBlock());
  preferences.storedBoot = 5000; sequenceReady = reserveSequenceBlock();
  assert(nextSequenceNumber(seq) && seq == 5001000001ULL); // no 32-bit truncation

  // Actual loop snapshots rain into separate windows even with MQTT offline.
  sampling = false; lastSensorMs = 10000; lastPublishMs = 0;
  fakeMs = 10000; rainTipCount = 2; loop();
  TelemetryReport report;
  assert(xQueueReceive(reportQueue, &report, 0) == pdTRUE);
  expectNear(report.rainfallMm, 1.40F);
  fakeMs = 20000; loop();
  assert(xQueueReceive(reportQueue, &report, 0) == pdTRUE);
  expectNear(report.rainfallMm, 0);
  fakeMs = 30000; rainTipCount = 1; loop();
  fakeMs = 40000; rainTipCount = 2; loop();
  assert(xQueueReceive(reportQueue, &report, 0) == pdTRUE);
  assert(report.uptimeMs == 40000); expectNear(report.rainfallMm, 1.40F);

  fakeMs = 50000; rainTipCount = 2000; loop();
  assert(!uxQueueMessagesWaiting(reportQueue)); // impossible interval is rejected, not clamped
  expectNear(snapshotRainfallInterval(), 0);

  // Actual delivery gate: offline and stale windows are dropped, never merged.
  report.uptimeMs = fakeMs;
  xQueueOverwrite(reportQueue, &report);
  deliverLatestReport();
  assert(mqttClient.lastPayload.empty() && !uxQueueMessagesWaiting(reportQueue));
  mqttClient.online = true;
  report.uptimeMs = fakeMs - PUBLISH_INTERVAL_MS;
  xQueueOverwrite(reportQueue, &report);
  deliverLatestReport();
  assert(mqttClient.lastPayload.empty());
  report.uptimeMs = fakeMs;
  xQueueOverwrite(reportQueue, &report);
  deliverLatestReport();
  assert(!mqttClient.lastPayload.empty());
  // Emit real firmware JSON for Python validation against BOTH shared contracts.
  mqttClient.online = true;
  for (bool valid : {true, false}) {
    for (float rain : {0.0F, 0.70F, 1.40F}) {
      report.sample = {valid ? 42.7F : NAN, valid};
      report.rainfallMm = rain;
      assert(nextSequenceNumber(report.sequence));
      report.uptimeMs = 40000;
      publishTelemetry(report);
      assert(mqttClient.lastTopic == "agapay/stations/STATION_001/telemetry");
      std::cout << mqttClient.lastPayload << '\n';
    }
  }
  mqttClient.publishResult = false;
  publishTelemetry(report);
  assert(serialLines.back().find("FAILED; interval dropped") != std::string::npos);
  std::cerr << "PASS: acquisition/filtering/depth, scheduling/wrap, offline GPIO/fail-safe, ISR intervals/debounce, sequences/NVS, queue windows, actual JSON\n";
  vQueueDelete(reportQueue);
}
