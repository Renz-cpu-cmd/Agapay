// Compile the actual firmware against host fakes and the actual ArduinoJson library.
#include "../src/main.cpp"
#include <iostream>
#include <limits>

void expectNear(float actual, float expected) { assert(fabs(actual - expected) < 0.01F); }
// Depth points inside each tier, derived from the configured geometry (150 cm bench, 65 cm rig, ...).
constexpr float DEPTH_NORMAL = THRESHOLD_ADVISORY_CM * 0.5F;
constexpr float DEPTH_ADVISORY = (THRESHOLD_ADVISORY_CM + THRESHOLD_WARNING_CM) * 0.5F;
constexpr float DEPTH_WARNING = (THRESHOLD_WARNING_CM + THRESHOLD_EVACUATE_CM) * 0.5F;
constexpr float DEPTH_EVACUATE = THRESHOLD_EVACUATE_CM + (SENSOR_HEIGHT_CM - MIN_DISTANCE_CM - THRESHOLD_EVACUATE_CM) * 0.5F;
static_assert(SENSOR_HEIGHT_CM - DEPTH_EVACUATE > MIN_DISTANCE_CM, "Evacuate test point must stay in sensor range");
unsigned long echoForDistance(float cm) { return static_cast<unsigned long>(lround(cm / 0.01715F)); }
// Matching sensor distances for setMedian(); DIST_EVACUATE is exactly the critical boundary.
constexpr float DIST_NORMAL = SENSOR_HEIGHT_CM - DEPTH_NORMAL;
constexpr float DIST_ADVISORY = SENSOR_HEIGHT_CM - DEPTH_ADVISORY;
constexpr float DIST_WARNING = SENSOR_HEIGHT_CM - DEPTH_WARNING;
constexpr float DIST_EVACUATE = SENSOR_HEIGHT_CM - THRESHOLD_EVACUATE_CM;

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

// Synthetic identities only (host_stubs.h): SSID "BENCH_TEST_AP" (13 bytes) and, unless
// AGAPAY_HOST_NO_WIFI_PIN, a locally administered pin BSSID 02:00:5E:10:20:30 on channel 11.
const char* pinSeen(bool found) { return !WIFI_PIN_CONFIGURED ? "BSSID=NOT PINNED" : found ? "BSSID=FOUND" : "BSSID=NOT SEEN"; }
std::string summary(const char* label,bool ssid,bool bssid,bool pair) {
  return std::string("[WIFI SCAN ")+label+"] Configured network: SSID="+(ssid?"FOUND":"NOT SEEN")+" "+pinSeen(bssid)+
      " same_AP="+(!WIFI_PIN_CONFIGURED?"n/a":pair?"FOUND":"NOT SEEN");
}
bool noNetworkIdentifiersLogged() {
  return !logged("BENCH_TEST_AP") && !logged("bench_test_ap") && !logged("NEIGHBOR_PRIVATE") && !logged("RENAMED_NETWORK") &&
      !logged("02:00:5E") && !logged("hex=[") && !logged("escaped=");
}

void testWiFiDiscovery() {
  fakeMs=90000;WiFi.state=WL_DISCONNECTED;WiFi.operations.clear();
  auto pinned=accessPoint("BENCH_TEST_AP");
  memcpy(pinned.bssid,WIFI_PIN_BSSID,6);
  if (!WIFI_PIN_CONFIGURED) pinned.bssid[5]=0x30;  // same synthetic address; nothing is pinned in this build
  auto neighbor=accessPoint("NEIGHBOR_PRIVATE");neighbor.primary=1;
  WiFi.scanResults={{4,{neighbor,pinned,accessPoint("BENCH_TEST_AP "),accessPoint("")}},
      {2,{accessPoint("bench_test_ap"),accessPoint("NEIGHBOR_PRIVATE")}}, {1,{pinned}}};
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
  assert(logged(WIFI_PIN_CONFIGURED
      ? "[WIFI SCAN FULL] Configured network record: SSID_match=1 BSSID_match=1 RSSI=-55 dBm channel=11 auth=3 (WPA2_PSK)"
      : "[WIFI SCAN FULL] Configured network record: SSID_match=1 BSSID_match=n/a RSSI=-55 dBm channel=11 auth=3 (WPA2_PSK)"));
  assert(logged(summary("FULL",true,true,true).c_str()));
  // Near misses are diagnosable without printing the name (the 2026-10-13 trailing-space case).
  assert(logged("[WIFI SSID FULL] AP #3 near match: DIFFERS ONLY BY TRAILING WHITESPACE; never adopted"));
  assert(logged("[WIFI SSID CH11-ACTIVE] AP #1 near match: DIFFERS ONLY BY LETTER CASE; never adopted"));
  assert(logged(summary("CH11-ACTIVE",false,false,false).c_str()));
  assert(logged(summary("CH11-PASSIVE",true,true,true).c_str()));
  assert(logged("completion_events=1 driver_status=0 (0=success; nonzero=failure)"));
  assert(logged(WIFI_PIN_CONFIGURED ? "Pinned BSSID diagnostic=eligible" : "Pinned BSSID diagnostic=not configured (normal association)"));
  assert(noNetworkIdentifiersLogged());
  discoverWiFiOnce(true);assert(WiFi.scanCalls==3); // Never repeat this boot's sequence.
  maintainWiFiNonBlocking(fakeMs);assert(WiFi.operations.back()=="begin");
  assert(WiFi.scanCalls==3 && rainPreferences.storedLifetime==persisted);

  // Individual scan outcomes: empty scans differ from failure/pending.
  serialLines.clear();WiFi.scanResult=0;
  runWiFiDiscoveryScan("EMPTY",false,600,11);
  assert(logged("result=0") && logged("Networks detected: 0") && logged(summary("EMPTY",false,false,false).c_str()));
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
  WiFi.accessPoints[257]=accessPoint("BENCH_TEST_AP",-65);
  runWiFiDiscoveryScan("LARGE",false,300,0);
  assert(logged(summary("LARGE",true,false,false).c_str()) && noNetworkIdentifiersLogged());
  // SSID and BSSID found in different records must not be reported as a pair.
  serialLines.clear();WiFi.scanResult=2;
  auto renamed=pinned;snprintf(reinterpret_cast<char*>(renamed.ssid),sizeof(renamed.ssid),"%s","RENAMED_NETWORK");
  WiFi.accessPoints={accessPoint("BENCH_TEST_AP"),renamed};
  runWiFiDiscoveryScan("SPLIT",true,1000,11);
  assert(logged(summary("SPLIT",true,WIFI_PIN_CONFIGURED,false).c_str()) && noNetworkIdentifiersLogged());
  if (WIFI_PIN_CONFIGURED) assert(logged("[WIFI SSID SPLIT] pinned AP: returned_len=15 configured_len=13 classification=DIFFERENT SSID BYTES"));
  // Wrapper can expose counts without exposing a failed/partial driver event.
  serialLines.clear();WiFi.scanResult=1;WiFi.accessPoints={neighbor};WiFi.driverScanStatus=1;
  runWiFiDiscoveryScan("PARTIAL",false,600,11);
  assert(logged("driver_status=1") && logged("Results may be partial; absent targets are inconclusive"));
  WiFi.driverScanStatus=0;WiFi.emitScanDone=false;serialLines.clear();WiFi.scanResult=0;
  runWiFiDiscoveryScan("NO-EVENT",false,600,11);
  assert(logged("driver completion event not observed within 100 ms; completion status unknown"));
  WiFi.emitScanDone=true;
  // Report existing region without broadening a range excluding the discovery channel.
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
  setMedian(DIST_EVACUATE);expectPins(LOW,LOW,HIGH,LOW);
  assert(rainPreferences.storedLifetime==persisted && !logged("HOST_FAKE_PASSWORD"));
  WiFi.beginCalls=0;wifiAttempted=false;lastWifiStatus=-1;
  wifiPinEligible=false;wifiPinSsidMismatch=false;wifiPinnedAttempt=false;
  std::cerr << "PASS (" << (WIFI_PIN_CONFIGURED?"pinned":"no pin") << "): full then channel-11 active/passive before begin, explicit dwell, anonymous channel/RSSI, country bounds/errors, SSID/BSSID/pair matching without printing names or BSSIDs, near-match classification, empty/error cleanup, once per boot, GPIO/NVS preservation\n";
}

void testSsidIdentityAndPinnedConnection() {
  // Comparison rules (names are compared, never printed).
  const auto exact=accessPoint("BENCH_TEST_AP"),trailing=accessPoint("BENCH_TEST_AP "),lower=accessPoint("bench_test_ap"),
      longer=accessPoint("BENCH_TEST_APX");
  wifi_ap_record_t zero{};
  assert(compareToConfiguredSsid(exact.ssid)==SsidComparison::Exact);
  assert(compareToConfiguredSsid(trailing.ssid)==SsidComparison::TrailingWhitespaceOnly);
  assert(compareToConfiguredSsid(lower.ssid)==SsidComparison::CaseOnly);
  assert(compareToConfiguredSsid(longer.ssid)==SsidComparison::Different);
  assert(compareToConfiguredSsid(zero.ssid)==SsidComparison::Empty);
  auto tailOnly=zero;tailOnly.ssid[1]='X';
  assert(compareToConfiguredSsid(tailOnly.ssid)==SsidComparison::Different);  // leading NUL with a nonzero tail is not "hidden"
#ifndef AGAPAY_HOST_NO_WIFI_PIN
  serialLines.clear();wifiPinEligible=false;wifiPinSsidMismatch=false;
  auto hidden=accessPoint("");memcpy(hidden.bssid,WIFI_PIN_BSSID,6);
  inspectPinnedSsid("HIDDEN",hidden,true);
  assert(logged("[WIFI SSID HIDDEN] pinned AP: returned_len=0 configured_len=13 classification=EMPTY/HIDDEN FIELD"));
  assert(wifiPinEligible && !wifiPinSsidMismatch);
  fakeMs=300000;WiFi.state=WL_DISCONNECTED;lastWifiAttemptMs=fakeMs-WIFI_RETRY_MS;
  const int calls=WiFi.beginCalls,pinnedCalls=WiFi.pinnedBeginCalls;
  maintainWiFiNonBlocking(fakeMs);
  assert(WiFi.pinnedBeginCalls==pinnedCalls+1 && WiFi.lastBeginChannel==11);
  assert(memcmp(WiFi.lastBeginBssid,WIFI_PIN_BSSID,6)==0 && WiFi.lastBeginPassword==WIFI_PASSWORD);
  assert(logged("Pinned attempt: configured SSID/password unchanged, channel=11, BSSID from local settings, grace_ms=30000"));
  maintainWiFiNonBlocking(fakeMs+29999);assert(WiFi.beginCalls==calls+1);
  maintainWiFiNonBlocking(fakeMs+30000);assert(WiFi.beginCalls==calls+2);
  WiFiEventInfo_t link{};memcpy(link.wifi_sta_connected.bssid,WIFI_PIN_BSSID,6);
  link.wifi_sta_connected.channel=11;link.wifi_sta_connected.authmode=WIFI_AUTH_WPA2_PSK;
  const auto beforeCallback=serialLines.size();
  wifiDiagnosticEvent(ARDUINO_EVENT_WIFI_STA_CONNECTED,link);
  wifiDiagnosticEvent(ARDUINO_EVENT_WIFI_STA_GOT_IP,{});
  assert(serialLines.size()==beforeCallback);
  WiFi.state=WL_CONNECTED;maintainWiFiNonBlocking(fakeMs+30001);
  assert(logged("[WIFI ASSOC] Link established auth_mode=3 channel=11 pinned_bssid=match"));
  assert(logged("[WIFI DHCP] GOT_IP: 10.0.0.2"));
  wifiDiagnosticEvent(ARDUINO_EVENT_WIFI_STA_LOST_IP,{});maintainWiFiNonBlocking(fakeMs+30002);
  assert(logged("[WIFI DHCP] LOST_IP"));
  // A visible different name at the pinned BSSID must never be adopted/pinned.
  serialLines.clear();auto changed=accessPoint("BENCH_TEST_AP ");memcpy(changed.bssid,hidden.bssid,6);
  inspectPinnedSsid("CHANGED",changed,true);
  assert(logged("classification=DIFFERS ONLY BY TRAILING WHITESPACE") && wifiPinSsidMismatch);
  const int pinnedBefore=WiFi.pinnedBeginCalls;beginWiFiAssociation();
  assert(!wifiPinnedAttempt && WiFi.pinnedBeginCalls==pinnedBefore && WiFi.lastBeginPassword==WIFI_PASSWORD);
  inspectPinnedSsid("LATER-HIDDEN",hidden,true);assert(wifiPinSsidMismatch); // later blank cannot override mismatch
  // Hostile bytes are classified, never echoed.
  serialLines.clear();auto bytes=hidden;const uint8_t hostile[]={0x22,0x5C,0x0A,0x1B,0xFF,0};
  memcpy(bytes.ssid,hostile,sizeof(hostile));inspectPinnedSsid("ESCAPED",bytes,true);
  assert(logged("returned_len=5 configured_len=13 classification=DIFFERENT SSID BYTES") && !logged("\\x0A") && !logged("hex="));
  // Maximum-length SSIDs and nonzero tail behind a leading NUL remain bounded.
  auto maximum=hidden;memset(maximum.ssid,'X',32);maximum.ssid[32]=0;
  inspectPinnedSsid("MAX",maximum,true);assert(boundedSsidLength(maximum.ssid)==32 && logged("returned_len=32"));
  wifiPinEligible=false;wifiPinSsidMismatch=false;
  auto tail=hidden;tail.ssid[1]='X';inspectPinnedSsid("TAIL",tail,true);
  assert(wifiPinSsidMismatch && !wifiPinEligible);
  wifiPinEligible=false;wifiPinSsidMismatch=false;
  inspectPinnedSsid("FAILED-SCAN",hidden,false);assert(!wifiPinEligible);
  auto otherChannel=hidden;otherChannel.primary=6;
  inspectPinnedSsid("OTHER-CHANNEL",otherChannel,true);assert(!wifiPinEligible);  // must be on the pinned channel
  assert(!logged("HOST_WIFI_PASSWORD") && !logged("HOST_FAKE_PASSWORD") && noNetworkIdentifiersLogged());
#else
  // Without local pin settings nothing is ever pinned: plain association only.
  serialLines.clear();wifiPinEligible=true;wifiPinSsidMismatch=false;
  fakeMs=300000;WiFi.state=WL_DISCONNECTED;lastWifiAttemptMs=fakeMs-WIFI_RETRY_MS;
  const int pinnedCalls=WiFi.pinnedBeginCalls,calls=WiFi.beginCalls;
  maintainWiFiNonBlocking(fakeMs);
  assert(WiFi.pinnedBeginCalls==pinnedCalls && WiFi.beginCalls==calls+1 && !wifiPinnedAttempt && WiFi.lastBeginPassword==WIFI_PASSWORD);
  assert(!isPinnedBssid(accessPoint("BENCH_TEST_AP").bssid));
  WiFiEventInfo_t link{};link.wifi_sta_connected.channel=11;link.wifi_sta_connected.authmode=WIFI_AUTH_WPA2_PSK;
  wifiDiagnosticEvent(ARDUINO_EVENT_WIFI_STA_CONNECTED,link);
  WiFi.state=WL_CONNECTED;maintainWiFiNonBlocking(fakeMs+1);
  assert(logged("[WIFI ASSOC] Link established auth_mode=3 channel=11 pinned_bssid=not-configured"));
  assert(!logged("HOST_WIFI_PASSWORD") && noNetworkIdentifiersLogged());
#endif
  wifiPinEligible=false;wifiPinSsidMismatch=false;wifiPinnedAttempt=false;
  WiFi.state=WL_DISCONNECTED;
  std::cerr << "PASS (" << (WIFI_PIN_CONFIGURED?"pinned":"no pin") << "): SSID comparison classes, hidden/exact/near-match/mismatch rules, pinned BSSID/channel only from local settings with unchanged password, 30s association grace, link/DHCP outcomes, no names/BSSIDs/secrets logged\n";
}

void testNetworkDiagnostics() {
  fakeMs=100000;
  WiFi.state=WL_DISCONNECTED;mqttClient.online=false;
  initializeNetwork();
  assert(WiFi.eventCallback==wifiDiagnosticEvent && mqttBufferReady);
  assert(logged("STA initialization: OK"));
  maintainWiFiNonBlocking(fakeMs);
  assert(WiFi.beginCalls==1 && logged("Connecting to configured SSID (len=13)") && !logged("BENCH_TEST_AP"));
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
  setMedian(DIST_EVACUATE);expectPins(LOW,LOW,HIGH,LOW);
  assert(!logged("HOST_FAKE_PASSWORD"));
  std::cerr << "PASS: Wi-Fi/MQTT gates, 10s/5s retries and wrap, framework event reasons/rate limits, authenticated CONNACK failures, subscription retry, bounded rain write failure and independent GPIO\n";
}
void testLocalAlertDiagnostics() {
  localBenchAlerts=false;localOutputTestActive=false;Serial.input.clear();
  localCommandLength=0;localCommandOverflow=false;
  const auto lifetime=rainLifetimeTips,persisted=rainPreferences.storedLifetime,sequence=sequenceNo;
  float distance,depth;
  // The actual integer-pulse acquisition crosses critical one echo step either side of the
  // configured boundary; the old 120/100/20 geometry is rejected by configuration validation.
  const unsigned long criticalEcho=static_cast<unsigned long>(floorf(DIST_EVACUATE/0.01715F));
  echoes={criticalEcho+1,criticalEcho,1166};
  assert(readDistanceOnce(distance) && calculateWaterDepth(distance,depth) && classifyAlert(depth)==AlertTier::WARNING);
  assert(readDistanceOnce(distance) && calculateWaterDepth(distance,depth) && classifyAlert(depth)==AlertTier::EVACUATE);
  assert(!readDistanceOnce(distance) && blindZoneSeen);
  blindZoneSeen=false;
  printLocalAlertStatus();assert(SENSOR_HEIGHT_CM-THRESHOLD_EVACUATE_CM > MIN_DISTANCE_CM+RANGE_MARGIN_CM+SENSOR_UNCERTAINTY_CM);
  setMedian(DIST_WARNING);expectPins(LOW,HIGH,LOW,HIGH);
  handleLocalAlertCommand("ALERT DEMO ON",1000);
  assert(localBenchAlerts && currentTier==AlertTier::WARNING);
  setMedian(25);expectPins(LOW,LOW,HIGH,LOW);expectNear(latestSample.waterDepthCm,SENSOR_HEIGHT_CM-25);
  assert(latestSample.benchProfile);
  assert(classifyBenchAlert(60)==AlertTier::ADVISORY);
  assert(classifyBenchAlert(35)==AlertTier::WARNING);
  assert(classifyBenchAlert(25.01F)==AlertTier::WARNING);
  setMedian(19); // out of sensor range never becomes a valid critical reading
  assert(!latestSample.sensorValid);expectPins(LOW,HIGH,HIGH,LOW);
  setMedian(DIST_WARNING);handleLocalAlertCommand("ALERT DEMO OFF",1001);
  assert(latestSample.benchProfile); // Acquired before the mode change; queue metadata is immutable.
  assert(!localBenchAlerts);expectPins(LOW,HIGH,LOW,HIGH);

  setMedian(DIST_NORMAL);
  assert(!latestSample.benchProfile);
  handleLocalAlertCommand("ALERT TEST",2000);expectPins(HIGH,LOW,LOW,HIGH);
  setMedian(DIST_ADVISORY); // acquisition continues, but temporary GPIO test stays green
  assert(currentTier==AlertTier::ADVISORY);expectPins(HIGH,LOW,LOW,HIGH);
  handleLocalAlertCommand("ALERT TEST",2100);assert(localOutputTestStartMs==2000);
  serviceLocalAlertDiagnostics(3000);expectPins(LOW,HIGH,LOW,HIGH);
  serviceLocalAlertDiagnostics(4000);expectPins(LOW,LOW,HIGH,LOW);
  assert(latestSample.sensorValid);expectNear(latestSample.waterDepthCm,DEPTH_ADVISORY);
  serviceLocalAlertDiagnostics(5000);expectPins(LOW,HIGH,LOW,HIGH);
  assert(!localOutputTestActive && currentTier==AlertTier::ADVISORY);

  handleLocalAlertCommand("ALERT TEST",6000);setMedian(DIST_EVACUATE);
  assert(!localOutputTestActive);expectPins(LOW,LOW,HIGH,LOW);
  handleLocalAlertCommand("ALERT TEST",6001);assert(!localOutputTestActive);
  setMedian(DIST_NORMAL);handleLocalAlertCommand("ALERT TEST",7000);
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


// 65 cm cardboard exercise positions (revision 2). Only meaningful for that geometry.
void testCardboardExercisePositions() {
  if (SENSOR_HEIGHT_CM != 65.0F || THRESHOLD_EVACUATE_CM != 35.0F) return;
  localBenchAlerts=false;localOutputTestActive=false;
  struct Position { float distance; AlertTier tier; } positions[] = {
    {65.0F, AlertTier::NORMAL}, {45.0F, AlertTier::ADVISORY}, {35.0F, AlertTier::WARNING}, {30.0F, AlertTier::EVACUATE}};
  for (const auto& p : positions) {
    setMedian(p.distance);
    assert(latestSample.sensorValid && currentTier==p.tier);
    expectNear(latestSample.waterDepthCm, SENSOR_HEIGHT_CM-p.distance);
  }
  // The sensor read about 1.3 cm short at 65 cm; EVACUATE still holds at 30 cm with that offset.
  setMedian(30.0F-1.3F);assert(latestSample.sensorValid && currentTier==AlertTier::EVACUATE);
  // A closer target stays a valid EVACUATE reading (the 38 cm limit constrains the threshold, not readings).
  setMedian(25.0F);assert(latestSample.sensorValid && currentTier==AlertTier::EVACUATE);
  std::cerr<<"PASS: 65 cm exercise positions 65/45/35/30 cm read NORMAL/ADVISORY/WARNING/EVACUATE\n";
}

void testAcquisitionGeometryAndFaultPolicy() {
  localBenchAlerts=false;localOutputTestActive=false;sensorFaultActive=false;
  uint32_t now=400000;
  for (float depth : {DEPTH_NORMAL,DEPTH_ADVISORY,DEPTH_WARNING,DEPTH_EVACUATE}) {
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
  localBenchAlerts=false;setMedian(SENSOR_HEIGHT_CM-DEPTH_ADVISORY);
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
  assert(calculateWaterDepth(SENSOR_HEIGHT_CM-12.7F, value)); expectNear(value, 12.7F);
  assert(calculateWaterDepth(SENSOR_HEIGHT_CM, value)); expectNear(value, 0);
  assert(!calculateWaterDepth(SENSOR_HEIGHT_CM+1, value) && isnan(value));
  assert(!calculateWaterDepth(19, value));
  assert(!calculateWaterDepth(451, value));
  assert(!calculateWaterDepth(NAN, value));
  assert(!calculateWaterDepth(std::numeric_limits<float>::infinity(), value));

  assert(classifyAlert(THRESHOLD_ADVISORY_CM-0.01F) == AlertTier::NORMAL);
  assert(classifyAlert(THRESHOLD_ADVISORY_CM) == AlertTier::ADVISORY);
  assert(classifyAlert(THRESHOLD_WARNING_CM) == AlertTier::WARNING);
  assert(classifyAlert(THRESHOLD_EVACUATE_CM) == AlertTier::EVACUATE);
  // Wi-Fi and MQTT stay disconnected throughout all local GPIO checks.
  assert(!mqttClient.connected() && WiFi.status() != WL_CONNECTED);
  setMedian(SENSOR_HEIGHT_CM-DEPTH_NORMAL); expectPins(HIGH, LOW, LOW, HIGH);
  setMedian(SENSOR_HEIGHT_CM-DEPTH_ADVISORY); expectPins(LOW, HIGH, LOW, HIGH);
  setMedian(SENSOR_HEIGHT_CM-DEPTH_WARNING); expectPins(LOW, HIGH, LOW, HIGH);
  setMedian(SENSOR_HEIGHT_CM-THRESHOLD_EVACUATE_CM); expectPins(LOW, LOW, HIGH, LOW);
  validSamples = 2; finishSensorSample();
  assert(!latestSample.sensorValid && isnan(latestSample.waterDepthCm));
  assert(currentTier == AlertTier::EVACUATE); expectPins(LOW, HIGH, HIGH, LOW);
  setMedian(SENSOR_HEIGHT_CM+1); // valid raw range but impossible negative depth
  assert(!latestSample.sensorValid && currentTier == AlertTier::EVACUATE);
  expectPins(LOW, HIGH, HIGH, LOW);

  // Burst scheduler: five probes, including invalid outliers, once per second.
  sampling = false; lastSensorMs = 0;
  const unsigned long inRange = echoForDistance(SENSOR_HEIGHT_CM-10.0F);
  echoes = {inRange, 0, 29000, inRange, inRange};
  sampleSensors(999); assert(echoes.size() == 5);
  sampleSensors(1000); assert(echoes.size() == 4);
  sampleSensors(1001); assert(echoes.size() == 4);
  for (uint32_t t = 1060; t <= 1240; t += 60) sampleSensors(t);
  assert(!sampling && latestSample.sensorValid); expectNear(latestSample.waterDepthCm, SENSOR_HEIGHT_CM-inRange*0.01715F);
  sampleSensors(1500); assert(!sampling);
  sampling = false; lastSensorMs = UINT32_MAX - 500;
  echoes = {0, 0, 0, 0, 0};
  sampleSensors(499); assert(sampling); // millis wrap
  for (uint32_t t = 559; t <= 739; t += 60) sampleSensors(t);
  assert(!latestSample.sensorValid);

  rainTipCount = 0; rainTipSeen = false;
  expectNear(snapshotRainfallInterval(), 0);
  fakeUs = 1; rainTipISR(); // first tip need not wait for debounce after boot
  fakeUs = RAIN_DEBOUNCE_US; rainTipISR(); // debounce - 1 us: bounce ignored
  fakeUs = 82001; rainTipISR(); // A8 regression: second closure 82 ms after a tip is not a new tip
  expectNear(snapshotRainfallInterval(), 0.70F);
  fakeUs = RAIN_DEBOUNCE_US + 1; rainTipISR();
  fakeUs = 2 * RAIN_DEBOUNCE_US + 1; rainTipISR();
  expectNear(snapshotRainfallInterval(), 1.40F);
  expectNear(snapshotRainfallInterval(), 0);
  fakeUs = 3 * RAIN_DEBOUNCE_US + 1; rainTipISR();
  fakeUs = 4 * RAIN_DEBOUNCE_US + 1;
  afterUnlock = rainTipISR; // a new tip immediately AFTER copy/reset
  expectNear(snapshotRainfallInterval(), 0.70F);
  expectNear(snapshotRainfallInterval(), 0.70F); // not lost or double counted
  rainTipSeen = true; lastRainInterruptUs = UINT32_MAX - 20000;
  fakeUs = RAIN_DEBOUNCE_US - 20000; rainTipISR(); // micros wrap: elapsed is debounce + 1 us
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
  rainPreferences.writeOk=false;fakeMs=70000;fakeUs+=RAIN_DEBOUNCE_US;rainTipISR();updateRainState(fakeMs);
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
  testCardboardExercisePositions();
  testDepthHistory();
  vQueueDelete(reportQueue);
  vQueueDelete(rainQueue);
  const int taskCalls=taskCreateCalls;
  failQueueCreateCall=queueCreateCalls+2;setup(); // rain queue allocation failure
  assert(reportQueue==nullptr && rainQueue==nullptr && taskCreateCalls==taskCalls+1);
  assert(logged("rain_queue=FAILED task=unavailable"));
  taskCreateResult=0;setup(); // network task allocation failure
  assert(reportQueue==nullptr && rainQueue==nullptr && taskCreateCalls==taskCalls+3);
  setMedian(DIST_EVACUATE);expectPins(LOW,LOW,HIGH,LOW);
  std::cerr << "PASS: rain queue/task allocation failures are diagnosed and preserve local sensing\n";
}
