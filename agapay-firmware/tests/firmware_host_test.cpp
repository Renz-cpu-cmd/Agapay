// Compile the actual firmware against host fakes and the actual ArduinoJson library.
#include "../src/main.cpp"
#include <iostream>
#include <limits>

void expectNear(float actual, float expected) { assert(fabs(actual - expected) < 0.01F); }
void setMedian(float distance) {
  blindZoneSeen=false;
  validSamples = 5;
  for (int i = 0; i < 5; ++i) distanceSamples[i] = distance;
  finishSensorSample();
}
void expectPins(int green, int yellow, int red, int buzzer) {
  assert(pins[LED_GREEN] == green && pins[LED_YELLOW] == yellow);
  assert(pins[LED_RED] == red && pins[BUZZER_PIN] == buzzer);
}
bool logged(const char* text) {
  for (const auto& line : serialLines) if (line.find(text)!=std::string::npos) return true;
  return false;
}

wifi_ap_record_t accessPoint(const char* ssid, int rssi=-55) {
  wifi_ap_record_t ap{};
  snprintf(reinterpret_cast<char*>(ap.ssid),sizeof(ap.ssid),"%s",ssid);
  ap.rssi=static_cast<int8_t>(rssi);ap.primary=11;ap.authmode=WIFI_AUTH_WPA2_PSK;
  ap.bssid[0]=0x02;ap.bssid[5]=0xAB;
  return ap;
}

void testWiFiDiscovery() {
  fakeMs=90000;WiFi.state=WL_DISCONNECTED;WiFi.operations.clear();
  auto upstairs=accessPoint("Upstairs");
  memcpy(upstairs.bssid,WIFI_DISCOVERY_TARGETS[0].bssid,6);
  auto hiddenHotspot=accessPoint("NEIGHBOR_PRIVATE");
  memcpy(hiddenHotspot.bssid,WIFI_DISCOVERY_TARGETS[1].bssid,6);
  auto neighbor=accessPoint("NEIGHBOR_PRIVATE");neighbor.primary=1;
  WiFi.scanResults={{4,{neighbor,upstairs,accessPoint("pangit"),accessPoint("")}},
      {2,{hiddenHotspot,accessPoint("NEIGHBOR_PRIVATE")}}, {1,{upstairs}}};
  const auto persisted=rainPreferences.storedLifetime;
  initializeNetwork();
  assert(WiFi.operations==std::vector<std::string>({"mode","scan","scan","scan"}));
  assert(WiFi.beginCalls==0 && WiFi.scanCalls==3 && WiFi.scanDeleteCalls==3);
  assert(!WiFi.scanParameters[0].passive && WiFi.scanParameters[0].dwell==300 && WiFi.scanParameters[0].channel==0);
  assert(!WiFi.scanParameters[1].passive && WiFi.scanParameters[1].dwell==600 && WiFi.scanParameters[1].channel==11);
  assert(WiFi.scanParameters[2].passive && WiFi.scanParameters[2].dwell==1000 && WiFi.scanParameters[2].channel==11);
  assert(logged("Networks detected: 4") && logged("ESP32 STA MAC: 02:00:00:00:00:01"));
  assert(logged("country=CN start_channel=1 channel_count=13 last_channel=13 policy=0 (AUTO) channel11_in_range=1"));
  assert(logged("[WIFI SCAN FULL] AP #1 channel=1 RSSI=-55 dBm"));
  assert(logged("[WIFI SCAN FULL] Channel 11 APs visible=3 missing_records=0"));
  assert(logged("Known Upstairs: SSID_match=1 BSSID_match=1 RSSI=-55 dBm channel=11 auth=3 (WPA2_PSK) BSSID=00:16:78:A2:55:F0"));
  assert(logged("[WIFI SCAN FULL] Upstairs: SSID=FOUND BSSID=FOUND same_AP=FOUND"));
  assert(logged("[WIFI SCAN CH11-ACTIVE] pangit: SSID=NOT SEEN BSSID=FOUND same_AP=NOT SEEN"));
  assert(logged("[WIFI SCAN CH11-PASSIVE] Upstairs: SSID=FOUND BSSID=FOUND same_AP=FOUND"));
  assert(logged("completion_events=1 driver_status=0 (0=success; nonzero=failure)"));
  assert(!logged("NEIGHBOR_PRIVATE"));
  discoverWiFiOnce(true);assert(WiFi.scanCalls==3); // Never repeat this boot's sequence.
  maintainWiFiNonBlocking(fakeMs);assert(WiFi.operations.back()=="begin");
  assert(WiFi.scanCalls==3 && rainPreferences.storedLifetime==persisted);

  // Individual scan outcomes: empty scans differ from failure/pending.
  serialLines.clear();WiFi.scanResult=0;
  runWiFiDiscoveryScan("EMPTY",false,600,11);
  assert(logged("result=0") && logged("Networks detected: 0") && logged("Upstairs: SSID=NOT SEEN BSSID=NOT SEEN same_AP=NOT SEEN"));
  assert(logged("Channel 11 APs visible=0"));
  assert(scanStopCalls==0);
  for (int16_t result : {static_cast<int16_t>(WIFI_SCAN_FAILED),static_cast<int16_t>(WIFI_SCAN_RUNNING)}) {
    serialLines.clear();WiFi.scanResult=result;
    const int stopped=scanStopCalls;runWiFiDiscoveryScan("ERROR",false,300,0);
    assert(scanStopCalls==stopped+1 && logged("discovery unknown (not a zero-network result)"));
    assert(!logged("Networks detected: 0") && !logged("NOT SEEN"));
    assert(logged("cleanup_scan_state="));
  }
  // A target beyond index 255 must still be found (no uint8_t truncation).
  serialLines.clear();WiFi.scanResult=258;
  WiFi.accessPoints.assign(258,accessPoint("NEIGHBOR_PRIVATE"));
  WiFi.accessPoints[257]=accessPoint("Upstairs",-65);
  runWiFiDiscoveryScan("LARGE",false,300,0);
  assert(logged("Upstairs: SSID=FOUND BSSID=NOT SEEN same_AP=NOT SEEN") && !logged("NEIGHBOR_PRIVATE"));
  // SSID and BSSID found in different records must not be reported as a pair.
  serialLines.clear();WiFi.scanResult=2;
  auto renamed=upstairs;snprintf(reinterpret_cast<char*>(renamed.ssid),sizeof(renamed.ssid),"%s","RENAMED_UPSTAIRS");
  WiFi.accessPoints={accessPoint("Upstairs"),renamed};
  runWiFiDiscoveryScan("SPLIT",true,1000,11);
  assert(logged("Upstairs: SSID=FOUND BSSID=FOUND same_AP=NOT SEEN") && !logged("NEIGHBOR_PRIVATE"));
  assert(logged("escaped=\"RENAMED_UPSTAIRS\"")); // explicitly requested known-BSSID bytes
  // Wrapper can expose counts without exposing a failed/partial driver event.
  serialLines.clear();WiFi.scanResult=1;WiFi.accessPoints={neighbor};WiFi.driverScanStatus=1;
  runWiFiDiscoveryScan("PARTIAL",false,600,11);
  assert(logged("driver_status=1") && logged("Results may be partial; absent targets are inconclusive"));
  WiFi.driverScanStatus=0;WiFi.emitScanDone=false;serialLines.clear();WiFi.scanResult=0;
  runWiFiDiscoveryScan("NO-EVENT",false,600,11);
  assert(logged("driver completion event not observed within 100 ms; completion status unknown"));
  WiFi.emitScanDone=true;
  // Report existing region without broadening a range excluding channel 11.
  serialLines.clear();wifiDiscoveryDone=false;WiFi.scanResult=0;
  fakeCountry.nchan=10;fakeCountry.policy=WIFI_COUNTRY_POLICY_MANUAL;
  const int beforeRestricted=WiFi.scanCalls;discoverWiFiOnce(true);
  assert(WiFi.scanCalls==beforeRestricted+1 && logged("channel11_in_range=0"));
  assert(logged("Channel 11 scans SKIPPED: outside configured country range"));
  assert(fakeCountry.nchan==10 && fakeCountry.policy==WIFI_COUNTRY_POLICY_MANUAL);
  // A failed country query is reported; driver continues to enforce its range.
  serialLines.clear();wifiDiscoveryDone=false;fakeCountryResult=1;
  const int beforeUnknown=WiFi.scanCalls;discoverWiFiOnce(true);
  assert(logged("get_country=1 (TEST_ERROR)") && WiFi.scanCalls==beforeUnknown+3);
  fakeCountry={};fakeCountryResult=ESP_OK;
  serialLines.clear();wifiDiscoveryDone=false;
  const int scans=WiFi.scanCalls;discoverWiFiOnce(false);
  assert(WiFi.scanCalls==scans && logged("SKIPPED: station initialization failed"));
  // Unavailable network/discovery must not affect physical thresholds/outputs.
  setMedian(50);expectPins(LOW,LOW,HIGH,LOW);
  assert(rainPreferences.storedLifetime==persisted && !logged("HOST_FAKE_PASSWORD"));
  WiFi.beginCalls=0;wifiAttempted=false;lastWifiStatus=-1;
  upstairsPinnedEligible=false;upstairsSsidMismatch=false;upstairsPinnedAttempt=false;
  std::cerr << "PASS: full then channel-11 active/passive before begin, explicit dwell, anonymous channel/RSSI, country bounds/errors, SSID/BSSID/pair matching and privacy, empty/error cleanup, once per boot, GPIO/NVS preservation\n";
}

void testSsidIdentityAndPinnedConnection() {
  assert(isConfiguredUpstairs("Upstairs") && isConfiguredUpstairs("Upstairs "));
  assert(!isConfiguredUpstairs("Upstairs  ") && !isConfiguredUpstairs("Unknown network"));
  serialLines.clear();upstairsPinnedEligible=false;upstairsSsidMismatch=false;
  auto hidden=accessPoint("");memcpy(hidden.bssid,WIFI_DISCOVERY_TARGETS[0].bssid,6);
  inspectUpstairsSsid("HIDDEN",hidden,true);
  assert(logged("returned SSID len=0 hex=[] escaped=\"\""));
  assert(logged("configured WIFI_SSID len=8 hex=[55 70 73 74 61 69 72 73] escaped=\"Upstairs\""));
  assert(logged("classification=EMPTY/HIDDEN FIELD") && upstairsPinnedEligible && !upstairsSsidMismatch);
  fakeMs=300000;WiFi.state=WL_DISCONNECTED;lastWifiAttemptMs=fakeMs-WIFI_RETRY_MS;
  const int calls=WiFi.beginCalls,pinned=WiFi.pinnedBeginCalls;
  maintainWiFiNonBlocking(fakeMs);
  assert(WiFi.pinnedBeginCalls==pinned+1 && WiFi.lastBeginChannel==11);
  assert(memcmp(WiFi.lastBeginBssid,WIFI_DISCOVERY_TARGETS[0].bssid,6)==0 && WiFi.lastBeginPassword==WIFI_PASSWORD);
  maintainWiFiNonBlocking(fakeMs+29999);assert(WiFi.beginCalls==calls+1);
  maintainWiFiNonBlocking(fakeMs+30000);assert(WiFi.beginCalls==calls+2);
  WiFiEventInfo_t link{};memcpy(link.wifi_sta_connected.bssid,WIFI_DISCOVERY_TARGETS[0].bssid,6);
  link.wifi_sta_connected.channel=11;link.wifi_sta_connected.authmode=WIFI_AUTH_WPA2_PSK;
  const auto beforeCallback=serialLines.size();
  wifiDiagnosticEvent(ARDUINO_EVENT_WIFI_STA_CONNECTED,link);
  wifiDiagnosticEvent(ARDUINO_EVENT_WIFI_STA_GOT_IP,{});
  assert(serialLines.size()==beforeCallback);
  WiFi.state=WL_CONNECTED;maintainWiFiNonBlocking(fakeMs+30001);
  assert(logged("[WIFI ASSOC] Link established auth_mode=3 channel=11"));
  assert(logged("[WIFI DHCP] GOT_IP: 10.0.0.2"));
  wifiDiagnosticEvent(ARDUINO_EVENT_WIFI_STA_LOST_IP,{});maintainWiFiNonBlocking(fakeMs+30002);
  assert(logged("[WIFI DHCP] LOST_IP"));
  // A visible different name at the same BSSID must never be adopted/pinned.
  serialLines.clear();auto changed=accessPoint("Upstairs ");memcpy(changed.bssid,hidden.bssid,6);
  inspectUpstairsSsid("CHANGED",changed,true);
  assert(logged("len=9 hex=[55 70 73 74 61 69 72 73 20]") && upstairsSsidMismatch);
  const int pinnedBefore=WiFi.pinnedBeginCalls;beginWiFiAssociation();
  assert(!upstairsPinnedAttempt && WiFi.pinnedBeginCalls==pinnedBefore && WiFi.lastBeginPassword==WIFI_PASSWORD);
  inspectUpstairsSsid("LATER-HIDDEN",hidden,true);assert(upstairsSsidMismatch); // later blank cannot override mismatch
  // Hex and printable diagnostics escape controls, quotes, backslash, high bytes.
  serialLines.clear();auto bytes=hidden;const uint8_t hostile[]={0x22,0x5C,0x0A,0x1B,0xFF,0};
  memcpy(bytes.ssid,hostile,sizeof(hostile));inspectUpstairsSsid("ESCAPED",bytes,true);
  assert(logged("hex=[22 5C 0A 1B FF]") && logged("\\x0A\\x1B\\xFF"));
  // Maximum-length SSIDs and nonzero tail behind a leading NUL remain bounded.
  auto maximum=hidden;memset(maximum.ssid,'X',32);maximum.ssid[32]=0;
  inspectUpstairsSsid("MAX",maximum,true);assert(boundedSsidLength(maximum.ssid)==32);
  upstairsPinnedEligible=false;upstairsSsidMismatch=false;
  auto tail=hidden;tail.ssid[1]='X';inspectUpstairsSsid("TAIL",tail,true);
  assert(upstairsSsidMismatch && !upstairsPinnedEligible);
  upstairsPinnedEligible=false;upstairsSsidMismatch=false;
  inspectUpstairsSsid("FAILED-SCAN",hidden,false);assert(!upstairsPinnedEligible);
  assert(!logged("HOST_WIFI_PASSWORD") && !logged("HOST_FAKE_PASSWORD"));
  upstairsPinnedEligible=false;upstairsSsidMismatch=false;upstairsPinnedAttempt=false;
  WiFi.state=WL_DISCONNECTED;
  std::cerr << "PASS: SSID bounded hex/escaping, hidden/exact/mismatch rules, known BSSID/channel with unchanged password, 30s association grace, link/DHCP outcomes and no secret logging\n";
}

void testNetworkDiagnostics() {
  fakeMs=100000;
  WiFi.state=WL_DISCONNECTED;mqttClient.online=false;
  initializeNetwork();
  assert(WiFi.eventCallback==wifiDiagnosticEvent && mqttBufferReady);
  assert(logged("STA initialization: OK"));
  maintainWiFiNonBlocking(fakeMs);
  assert(WiFi.beginCalls==1 && logged("Connecting to SSID: Upstairs"));
  maintainWiFiNonBlocking(fakeMs+9999);assert(WiFi.beginCalls==1);
  maintainWiFiNonBlocking(fakeMs+10000);assert(WiFi.beginCalls==2);
  const auto beforeEvent=serialLines.size();
  WiFi.eventCallback(ARDUINO_EVENT_WIFI_STA_DISCONNECTED,{{202},{},{}});
  assert(serialLines.size()==beforeEvent); // event task never writes Serial
  maintainWiFiNonBlocking(fakeMs+10001);assert(logged("last_reason=202 (AUTH_FAIL"));
  WiFi.eventCallback(ARDUINO_EVENT_WIFI_STA_DISCONNECTED,{{201},{},{}});
  const auto beforeReason=serialLines.size();
  maintainWiFiNonBlocking(fakeMs+10002);assert(serialLines.size()==beforeReason);
  maintainWiFiNonBlocking(fakeMs+20001);assert(logged("last_reason=201 (NO_AP_FOUND"));
  // Gate MQTT while Wi-Fi is down, then classify a real broker credential refusal.
  maintainMqttNonBlocking(fakeMs);assert(mqttClient.connectCalls==0);
  WiFi.state=WL_CONNECTED;maintainWiFiNonBlocking(fakeMs+20002);
  assert(logged("[WIFI] Connected") && logged("IP: 10.0.0.2 RSSI: -55"));
  fakeMs=125000;mqttClient.stateCode=4;
  maintainMqttNonBlocking(fakeMs);
  assert(mqttClient.connectCalls==1 && mqttClient.authenticatedConnect);
  assert(logged("state=4 (broker refused username/password)"));
  maintainMqttNonBlocking(fakeMs+4999);assert(mqttClient.connectCalls==1);
  mqttClient.connectResult=true;mqttClient.subscribeResult=false;
  fakeMs+=5000;maintainMqttNonBlocking(fakeMs);
  assert(mqttClient.online && mqttClient.subscribeCalls==1 && !rainAckSubscriptionSent);
  assert(logged("Rain-ACK subscribe FAILED"));
  maintainRainAckSubscription(fakeMs+4999);assert(mqttClient.subscribeCalls==1);
  mqttClient.subscribeResult=true;maintainRainAckSubscription(fakeMs+5000);
  assert(mqttClient.subscribeCalls==2 && rainAckSubscriptionSent);
  assert(logged("broker grant unverified until ACK received"));
  mqttClient.online=false;mqttClient.connectResult=false;mqttClient.stateCode=-3;
  maintainMqttNonBlocking(fakeMs+5000);assert(logged("Disconnected state=-3 (TCP connection lost)"));
  // Wrap-safe Wi-Fi and MQTT retry intervals.
  WiFi.state=WL_DISCONNECTED;lastWifiAttemptMs=UINT32_MAX-5000;
  const int wifiAttempts=WiFi.beginCalls;
  maintainWiFiNonBlocking(4998);assert(WiFi.beginCalls==wifiAttempts);
  maintainWiFiNonBlocking(4999);assert(WiFi.beginCalls==wifiAttempts+1);
  WiFi.state=WL_CONNECTED;lastMqttAttemptMs=UINT32_MAX-2500;
  const int mqttAttempts=mqttClient.connectCalls;
  fakeMs=2498;maintainMqttNonBlocking(fakeMs);assert(mqttClient.connectCalls==mqttAttempts);
  fakeMs=2499;mqttClient.stateCode=-2;maintainMqttNonBlocking(fakeMs);assert(mqttClient.connectCalls==mqttAttempts+1);
  assert(logged("state=-2 (TCP connect failed"));
  assert(std::string(mqttStateName(-4)).find("timeout")!=std::string::npos);
  assert(std::string(mqttStateName(5)).find("topic ACL still separate")!=std::string::npos);
  // Failed packet writes have a bounded retry, without losing the cumulative counter.
  mqttClient.online=true;mqttClient.publishResult=false;
  rainPublishAttempted=false;networkRainReady=true;
  networkRainSnapshot={rainBootStartTips+1,1000};lastRainPublishedCount=UINT64_MAX;
  const auto durableCount=rainLifetimeTips;
  fakeMs=200000;publishRainSnapshot(fakeMs);
  const int writes=mqttClient.publishCalls;
  for (uint32_t t=1;t<500;++t) publishRainSnapshot(fakeMs+t);
  assert(mqttClient.publishCalls==writes && rainLifetimeTips==durableCount);
  publishRainSnapshot(fakeMs+500);assert(mqttClient.publishCalls==writes+1);
  mqttClient.publishResult=true;publishRainSnapshot(fakeMs+1000);
  assert(lastRainPublishedCount==networkRainSnapshot.count);
  // Diagnosable initialization failures gate MQTT; sensor GPIO remains available.
  WiFi.modeResult=false;mqttClient.bufferResult=false;
  initializeNetwork();assert(!mqttBufferReady && logged("STA initialization: FAILED"));
  assert(logged("FAILED (MQTT disabled; check memory)"));
  mqttClient.online=false;const int attempts=mqttClient.connectCalls;
  maintainMqttNonBlocking(fakeMs+10000);assert(mqttClient.connectCalls==attempts);
  setMedian(50);expectPins(LOW,LOW,HIGH,LOW);
  assert(!logged("HOST_FAKE_PASSWORD"));
  std::cerr << "PASS: Wi-Fi/MQTT gates, 10s/5s retries and wrap, framework event reasons/rate limits, authenticated CONNACK failures, subscription retry, bounded rain write failure and independent GPIO\n";
}
void testLocalAlertDiagnostics() {
  localBenchAlerts=false;localOutputTestActive=false;Serial.input.clear();
  localCommandLength=0;localCommandOverflow=false;
  const auto lifetime=rainLifetimeTips,persisted=rainPreferences.storedLifetime,sequence=sequenceNo;
  float distance,depth;
  // The actual integer-pulse acquisition crosses critical with 30 cm near-range
  // margin; the old 120/100/20 geometry is rejected by configuration validation.
  echoes={2916,2915,1166};
  assert(readDistanceOnce(distance) && calculateWaterDepth(distance,depth) && classifyAlert(depth)==AlertTier::WARNING);
  assert(readDistanceOnce(distance) && calculateWaterDepth(distance,depth) && classifyAlert(depth)==AlertTier::EVACUATE);
  assert(!readDistanceOnce(distance) && blindZoneSeen);
  blindZoneSeen=false;
  printLocalAlertStatus();assert(SENSOR_HEIGHT_CM-THRESHOLD_EVACUATE_CM > MIN_DISTANCE_CM+RANGE_MARGIN_CM+SENSOR_UNCERTAINTY_CM);
  setMedian(60);expectPins(LOW,HIGH,LOW,HIGH);
  handleLocalAlertCommand("ALERT DEMO ON",1000);
  assert(localBenchAlerts && currentTier==AlertTier::WARNING);
  setMedian(25);expectPins(LOW,LOW,HIGH,LOW);expectNear(latestSample.waterDepthCm,125);
  assert(latestSample.benchProfile);
  assert(classifyBenchAlert(60)==AlertTier::ADVISORY);
  assert(classifyBenchAlert(35)==AlertTier::WARNING);
  assert(classifyBenchAlert(25.01F)==AlertTier::WARNING);
  setMedian(19); // out of sensor range never becomes a valid critical reading
  assert(!latestSample.sensorValid);expectPins(LOW,HIGH,HIGH,LOW);
  setMedian(65);handleLocalAlertCommand("ALERT DEMO OFF",1001);
  assert(latestSample.benchProfile); // Acquired before the mode change; queue metadata is immutable.
  assert(!localBenchAlerts);expectPins(LOW,HIGH,LOW,HIGH);

  setMedian(95);
  assert(!latestSample.benchProfile);
  handleLocalAlertCommand("ALERT TEST",2000);expectPins(HIGH,LOW,LOW,HIGH);
  setMedian(80); // acquisition continues, but temporary GPIO test stays green
  assert(currentTier==AlertTier::ADVISORY);expectPins(HIGH,LOW,LOW,HIGH);
  handleLocalAlertCommand("ALERT TEST",2100);assert(localOutputTestStartMs==2000);
  serviceLocalAlertDiagnostics(3000);expectPins(LOW,HIGH,LOW,HIGH);
  serviceLocalAlertDiagnostics(4000);expectPins(LOW,LOW,HIGH,LOW);
  assert(latestSample.sensorValid);expectNear(latestSample.waterDepthCm,70);
  serviceLocalAlertDiagnostics(5000);expectPins(LOW,HIGH,LOW,HIGH);
  assert(!localOutputTestActive && currentTier==AlertTier::ADVISORY);

  handleLocalAlertCommand("ALERT TEST",6000);setMedian(50);
  assert(!localOutputTestActive);expectPins(LOW,LOW,HIGH,LOW);
  handleLocalAlertCommand("ALERT TEST",6001);assert(!localOutputTestActive);
  setMedian(95);handleLocalAlertCommand("ALERT TEST",7000);
  handleLocalAlertCommand("ALERT STOP",7001);expectPins(HIGH,LOW,LOW,HIGH);
  handleLocalAlertCommand("ALERT TEST",UINT32_MAX-999);
  serviceLocalAlertDiagnostics(0);expectPins(LOW,HIGH,LOW,HIGH);
  serviceLocalAlertDiagnostics(1000);expectPins(LOW,LOW,HIGH,LOW);
  serviceLocalAlertDiagnostics(2000);expectPins(HIGH,LOW,LOW,HIGH);
  assert(!localOutputTestActive);

  // Serial input is bounded, CRLF works, and an oversized line cannot activate.
  const std::string input=std::string(60,'X')+"ALERT DEMO ON\nALERT STATUS\r\n";
  for(char c:input)Serial.input.push_back(c);
  serviceLocalAlertDiagnostics(8000);assert(Serial.input.size()==input.size()-16);
  while(Serial.available())serviceLocalAlertDiagnostics(8000);
  assert(!localBenchAlerts && logged("discarded invalid/oversized input"));
  assert(rainLifetimeTips==lifetime && rainPreferences.storedLifetime==persisted && sequenceNo==sequence);
  std::cerr<<"PASS: real pulse red-boundary regression, opt-in bench GPIOs, unchanged depth/telemetry, 3-second test/restore/critical preemption, wrap and bounded Serial; NVS rain/sequence unchanged\n";
}

void testTelemetryCadence() {
  assert(PUBLISH_INTERVAL_MS==2000);
  TelemetryReport discard{};
  while(xQueueReceive(reportQueue,&discard,0)==pdTRUE) {}
  const uint32_t originalRain=rainTipCount;
  sampling=false;fakeMs=100000;lastSensorMs=fakeMs;lastPublishMs=fakeMs;
  rainTipCount=1;
  fakeMs=101999;loop();
  assert(!uxQueueMessagesWaiting(reportQueue) && rainTipCount==1);
  fakeMs=102000;loop();
  assert(xQueueReceive(reportQueue,&discard,0)==pdTRUE);
  assert(discard.uptimeMs==102000 && rainTipCount==0);
  expectNear(discard.rainfallMm,RAIN_MM_PER_TIP);
  rainTipCount=originalRain;sampling=false;
  std::cerr<<"PASS: 2-second telemetry boundary retains tips before the window and reports them once at the boundary\n";
}

void testAcquisitionGeometryAndFaultPolicy() {
  localBenchAlerts=false;localOutputTestActive=false;sensorFaultActive=false;
  uint32_t now=400000;
  for (float depth : {10.0F,65.0F,90.0F,105.0F}) {
    const auto duration=static_cast<unsigned long>(lround((SENSOR_HEIGHT_CM-depth)/0.01715F));
    sampling=false;lastSensorMs=now-SENSOR_INTERVAL_MS;
    echoes={duration,duration,duration,duration,duration};
    for(uint32_t offset=0;offset<=240;offset+=60)sampleSensors(now+offset);
    assert(latestSample.sensorValid && fabs(latestSample.waterDepthCm-depth)<0.02F);
    assert(currentTier==classifyAlert(depth));
    now+=1000;
  }
  // Even a mixed burst with otherwise valid echoes cannot hide a blind-zone echo.
  sampling=false;lastSensorMs=now-SENSOR_INTERVAL_MS;
  echoes={2624,2624,100,2624,2624};
  for(uint32_t offset=0;offset<=240;offset+=60)sampleSensors(now+offset);
  assert(!latestSample.sensorValid && strcmp(latestSample.sensorFault,"blind_zone")==0 && sensorFaultActive);
  assert(currentTier==AlertTier::EVACUATE);
  serviceSensorFault(0);expectPins(LOW,LOW,HIGH,LOW);
  serviceSensorFault(250);expectPins(LOW,HIGH,HIGH,LOW);
  handleLocalAlertCommand("ALERT TEST",now);assert(!localOutputTestActive);
  setMedian(SENSOR_HEIGHT_CM-10);assert(!sensorFaultActive && latestSample.sensorValid);
  std::cerr<<"PASS: real five-pulse acquisition crosses all unchanged depth tiers with range margin; blind-zone mixed burst signals fault, latches critical offline, blinks and prevents self-test masking\n";
}

#include "depth_history_checks.h"

int main() {
#ifdef AGAPAY_HOST_UNPROVISIONED
  setup();
  assert(!stationCredentialReady());
  mqttClient.online=true;
  const int writes=mqttClient.publishCalls;
  TelemetryReport unprovisioned{};
  unprovisioned.sequence=1;unprovisioned.sample={42.7F,true};
  publishTelemetry(unprovisioned);
  networkRainReady=true;networkRainSnapshot={rainLifetimeTips,0};
  publishRainSnapshot(5000);
  assert(mqttClient.publishCalls==writes);
  localBenchAlerts=false;setMedian(80);
  assert(latestSample.sensorValid && currentTier==AlertTier::ADVISORY);
  assert(logged("network publication withheld, local sensing continues"));
  std::cerr<<"PASS: unprovisioned firmware withholds telemetry/rain publication and preserves local sensing\n";
  return 0;
#endif
  assert(localBenchAlerts==DEFAULT_LOCAL_BENCH_ALERTS);
  localBenchAlerts=false; // Boot profile assertion above; common acquisition checks use depth outputs.
  setup();
  assert(currentTier == AlertTier::UNKNOWN);
  expectPins(LOW, LOW, LOW, HIGH);
  validSamples = 0; finishSensorSample();
  assert(!latestSample.sensorValid && currentTier == AlertTier::UNKNOWN);
  expectPins(LOW, HIGH, LOW, HIGH);

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
  assert(calculateWaterDepth(77.3F, value)); expectNear(value, SENSOR_HEIGHT_CM-77.3F);
  assert(calculateWaterDepth(SENSOR_HEIGHT_CM, value)); expectNear(value, 0);
  assert(!calculateWaterDepth(SENSOR_HEIGHT_CM+1, value) && isnan(value));
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
  setMedian(130); expectPins(HIGH, LOW, LOW, HIGH);
  setMedian(90); expectPins(LOW, HIGH, LOW, HIGH);
  setMedian(65); expectPins(LOW, HIGH, LOW, HIGH);
  setMedian(50); expectPins(LOW, LOW, HIGH, LOW);
  validSamples = 2; finishSensorSample();
  assert(!latestSample.sensorValid && isnan(latestSample.waterDepthCm));
  assert(currentTier == AlertTier::EVACUATE); expectPins(LOW, HIGH, HIGH, LOW);
  setMedian(151); // valid raw range but impossible negative depth
  assert(!latestSample.sensorValid && currentTier == AlertTier::EVACUATE);
  expectPins(LOW, HIGH, HIGH, LOW);

  // Burst scheduler: five probes, including invalid outliers, once per second.
  sampling = false; lastSensorMs = 0;
  echoes = {5831, 0, 29000, 5831, 5831};
  sampleSensors(999); assert(echoes.size() == 5);
  sampleSensors(1000); assert(echoes.size() == 4);
  sampleSensors(1001); assert(echoes.size() == 4);
  for (uint32_t t = 1060; t <= 1240; t += 60) sampleSensors(t);
  assert(!sampling && latestSample.sensorValid); expectNear(latestSample.waterDepthCm, SENSOR_HEIGHT_CM-100);
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
      report.sample.uptimeMs = static_cast<uint64_t>(UINT32_MAX) + 40000ULL;
      report.sample.measuredAtMs = fakeUtcMs;
      report.rainfallMm = rain;
      assert(nextSequenceNumber(report.sequence));
      report.bootSequence = telemetryBootSequence;
      report.uptimeMs = 40000;
      publishTelemetry(report);
      assert(mqttClient.lastTopic == "agapay/stations/STATION_001/telemetry");
      std::cout << mqttClient.lastPayload << '\n';
    }
  }
  mqttClient.publishResult = false;
  publishTelemetry(report);
  assert(serialLines.back().find("FAILED; interval dropped") != std::string::npos);
  assert(!logged(STATION_INGEST_TOKEN));
  // Unsynchronized acquisition time remains null even if publication happens later.
  report.sample.measuredAtMs = 0;
  publishTelemetry(report);
  JsonDocument unsynchronized;
  assert(!deserializeJson(unsynchronized,mqttClient.lastPayload));
  assert(unsynchronized["telemetry"]["measured_at"].isNull());
  // Rain counter survives legacy interval reset/outage and is durably committed before publishing.
  mqttClient.publishResult=true;mqttClient.online=false;
  rainLifetimeTips=rainBootStartTips;rainPersistedTips=rainBootStartTips;
  rainTipSeen=false;fakeMs=60000;fakeUs=60000000;rainTipISR();
  fakeUs+=1000;rainTipISR(); // contact bounce is ignored
  updateRainState(fakeMs);
  assert(rainLifetimeTips==rainBootStartTips+1);
  assert(rainPreferences.storedLifetime==rainBootStartTips+1);
  expectNear(snapshotRainfallInterval(),RAIN_MM_PER_TIP);
  publishRainSnapshot(fakeMs); // offline keeps queued cumulative state
  assert(networkRainReady);
  mqttClient.online=true;publishRainSnapshot(fakeMs);
  assert(mqttClient.lastTopic=="agapay/stations/STATION_001/rain");
  std::cout<<"RAIN "<<mqttClient.lastPayload<<'\n';
  char ackTopic[]="agapay/stations/STATION_001/rain-ack";
  std::string ack=std::string("{\"boot_id\":\"")+rainBootId+"\",\"cumulative_tip_count\":"+std::to_string(rainLifetimeTips)+",\"device_uptime_ms\":60000}";
  rainAcknowledgement(ackTopic,reinterpret_cast<uint8_t*>(ack.data()),ack.size());
  assert(rainAckTips==rainLifetimeTips);
  assert(logged("[RAIN ACK] backend acknowledged"));
  fakeMs=65000;publishRainSnapshot(fakeMs);
  std::cout<<"RAIN "<<mqttClient.lastPayload<<'\n'; // acknowledged repeat has zero increment
  rainPreferences.writeOk=false;fakeMs=70000;fakeUs+=50000;rainTipISR();updateRainState(fakeMs);
  assert(rainPersistenceWarning && rainPersistedTips<rainLifetimeTips);
  rainPreferences.writeOk=true;updateRainState(fakeMs);
  assert(rainPersistedTips==rainLifetimeTips);
  const uint64_t persisted=rainPersistedTips;restoreRainCounter();
  assert(rainBootStartTips==persisted && rainLifetimeTips==persisted); // reboot does not fabricate a tip
  std::cerr << "PASS: acquisition/filtering/depth, scheduling/wrap, offline GPIO/fail-safe, ISR intervals/debounce, sequences/NVS, queue windows, actual JSON\n";
  testWiFiDiscovery();
  testNetworkDiagnostics();
  testSsidIdentityAndPinnedConnection();
#if AGAPAY_RELEASE_BUILD
  handleLocalAlertCommand("ALERT DEMO ON",1000);assert(!localBenchAlerts);
  assert(logged("Exercise overrides disabled"));
  assert(networkClient.ca==MQTT_ROOT_CA && networkClient.handshake==5);
  const auto savedUtc=fakeUtcMs;fakeUtcMs=0;
  mqttClient.online=false;WiFi.state=WL_CONNECTED;mqttBufferReady=true;fakeMs+=10000;
  const auto beforeUnsynced=mqttClient.connectCalls;maintainMqttNonBlocking(fakeMs);
  assert(mqttClient.connectCalls==beforeUnsynced && logged("synchronized UTC"));fakeUtcMs=savedUtc;
#else
  testLocalAlertDiagnostics();
#endif
  testTelemetryCadence();
  testAcquisitionGeometryAndFaultPolicy();
  testDepthHistory();
  vQueueDelete(reportQueue);
  vQueueDelete(rainQueue);
  const int taskCalls=taskCreateCalls;
  failQueueCreateCall=queueCreateCalls+2;setup(); // rain queue allocation failure
  assert(reportQueue==nullptr && rainQueue==nullptr && taskCreateCalls==taskCalls+1);
  assert(logged("rain_queue=FAILED task=unavailable"));
  taskCreateResult=0;setup(); // network task allocation failure
  assert(reportQueue==nullptr && rainQueue==nullptr && taskCreateCalls==taskCalls+3);
  setMedian(50);expectPins(LOW,LOW,HIGH,LOW);
  std::cerr << "PASS: rain queue/task allocation failures are diagnosed and preserve local sensing\n";
}
