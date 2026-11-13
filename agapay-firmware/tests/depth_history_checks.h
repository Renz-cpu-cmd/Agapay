// Exercises the actual journal, filesystem adapter and network/ACK path.
void testDepthHistory() {
  fakeDepthFiles.clear();
  DepthStorage storage;assert(storage.begin());
  DepthJournal<DepthStorage> journal(storage);journal.restore();
  assert(journal.pending()==0);
  assert(journal.append("{\"original\":true}",1,42,100));
  DepthRecord first{};assert(journal.oldest(first));
  DepthJournal<DepthStorage> rebooted(storage);rebooted.restore();
  DepthRecord restored{};assert(rebooted.oldest(restored));
  assert(restored.boot==42 && restored.sequence==100 && restored.config==1);
  assert(strcmp(restored.json,"{\"original\":true}")==0);
  // A torn/uncommitted temp write does not replace the last committed slot.
  fakeDepthFiles["/agapay-depth/pending.tmp"]={1,2,3};
  DepthJournal<DepthStorage> interrupted(storage);interrupted.restore();
  assert(interrupted.oldest(restored) && restored.sequence==100);
  assert(interrupted.acknowledge(restored) && interrupted.pending()==0);
  assert(!interrupted.acknowledge(restored));
  fakeDepthFiles.clear();DepthJournal<DepthStorage> bounded(storage);bounded.restore();
  for (unsigned i=0;i<DEPTH_HISTORY_SLOTS+1;++i)
    assert(bounded.append("{\"history\":true}",1,43,101+i));
  assert(bounded.pending()==DEPTH_HISTORY_SLOTS && bounded.evicted==1);
  assert(!bounded.acknowledge(first)); // Wrapped slot is protected from old ACKs.
  assert(bounded.oldest(restored));
  fakeDepthWriteFailure=true;assert(!bounded.append("{}",1,43,999));fakeDepthWriteFailure=false;
  fakeDepthRenameFailure=true;assert(!bounded.append("{}",1,43,999));fakeDepthRenameFailure=false;
  assert(bounded.writeFailures==2 && bounded.pending()==DEPTH_HISTORY_SLOTS && bounded.evicted==1);
  fakeDepthRemoveFailure=true;assert(!bounded.acknowledge(restored));fakeDepthRemoveFailure=false;
  assert(bounded.pending()==DEPTH_HISTORY_SLOTS);
  const unsigned slot=(restored.serial-1)%DEPTH_HISTORY_SLOTS;
  char path[48];storage.path(slot,path,sizeof(path));fakeDepthFiles[path][100]^=0x80;
  DepthJournal<DepthStorage> damaged(storage);damaged.restore();
  assert(damaged.corrupt==1 && damaged.pending()==DEPTH_HISTORY_SLOTS-1);

  // Actual firmware observation serialization stays immutable through replay.
  fakeDepthFiles.clear();DepthJournal<DepthStorage> fresh(storage);fresh.restore();
  TelemetryReport report{};report.bootSequence=5001;report.sequence=123456;
  report.sample.sensorValid=true;report.sample.waterDepthCm=105;
  report.sample.uptimeMs=123456000;report.sample.measuredAtMs=fakeUtcMs;
  JsonDocument document;buildDepthObservation(document.to<JsonObject>(),report);
  char observation[1100];serializeJson(document,observation,sizeof(observation));
  assert(fresh.append(observation,AGAPAY_CONFIG_VERSION,report.bootSequence,report.sequence));
  assert(fresh.oldest(restored));
  xQueueOverwrite(depthReplayQueue,&restored);
  mqttClient.online=true;depthAckSubscribed=false;fakeMs+=1000;
  const auto beforePublish=mqttClient.publishCalls;
  deliverDepthHistory(fakeMs);
  assert(mqttClient.publishCalls==beforePublish+1 && depthInFlightReady);
  JsonDocument sent;assert(!deserializeJson(sent,mqttClient.lastPayload));
  assert(strcmp(sent["delivery_mode"],"backfill")==0);
  assert(sent["telemetry"]["water_depth_cm"].as<float>()==105);
  assert(sent["telemetry"]["sequence_no"].as<uint64_t>()==123456);
  assert(mqttClient.lastPayload.find("agapay-depth")==std::string::npos);
  xQueueOverwrite(depthReplayQueue,&restored);deliverDepthHistory(fakeMs+500);
  assert(mqttClient.publishCalls==beforePublish+1); // Bounded replay budget.
  char topic[100];snprintf(topic,sizeof(topic),"agapay/stations/%s/telemetry-ack",STATION_ID);
  JsonDocument ack;ack["station_id"]=STATION_ID;ack["boot_id"]="STATION_001-5001";
  ack["telemetry"].set(document);
  ack["sequence_no"]=123455;ack["config_version"]=AGAPAY_CONFIG_VERSION;ack["persisted"]=true;
  char body[1536];size_t size=serializeJson(ack,body,sizeof(body));
  depthAcknowledgement(topic,reinterpret_cast<uint8_t*>(body),size);
  assert(depthInFlightReady && !uxQueueMessagesWaiting(depthAckQueue));
  ack["sequence_no"]=123456;ack["telemetry"]["water_depth_cm"]=106;
  size=serializeJson(ack,body,sizeof(body));
  depthAcknowledgement(topic,reinterpret_cast<uint8_t*>(body),size);
  assert(depthInFlightReady && !uxQueueMessagesWaiting(depthAckQueue));
  ack["telemetry"]["water_depth_cm"]=105;size=serializeJson(ack,body,sizeof(body));
  depthAcknowledgement(topic,reinterpret_cast<uint8_t*>(body),size);
  assert(!depthInFlightReady && xQueueReceive(depthAckQueue,&restored,0)==pdTRUE);
  assert(fresh.acknowledge(restored) && fresh.pending()==0);
  mqttClient.online=false;setMedian(DIST_EVACUATE);expectPins(LOW,LOW,HIGH,LOW);
  std::cerr << "PASS: depth outage/reboot restore, immutable JSON, bounded capacity/replay, CRC/torn-write recovery, exact ACK removal, wrapped-slot protection and local GPIO responsiveness\n";
}
