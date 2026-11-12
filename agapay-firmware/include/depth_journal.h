#pragma once
// Fixed resource budget. Storage adapter must commit a whole slot atomically.
// Only the journal task touches storage; acquisition never waits for flash/network.
#include <stdint.h>
#include <stddef.h>
#include <string.h>

#ifndef AGAPAY_DEPTH_HISTORY_SLOTS
#define AGAPAY_DEPTH_HISTORY_SLOTS 360
#endif
#ifndef AGAPAY_DEPTH_HISTORY_CADENCE_MS
#define AGAPAY_DEPTH_HISTORY_CADENCE_MS 10000
#endif
constexpr unsigned DEPTH_HISTORY_SLOTS = AGAPAY_DEPTH_HISTORY_SLOTS;
constexpr uint32_t DEPTH_HISTORY_CADENCE_MS = AGAPAY_DEPTH_HISTORY_CADENCE_MS;
static_assert(DEPTH_HISTORY_SLOTS >= 6 && DEPTH_HISTORY_SLOTS <= 1440, "Review flash/history budget");
static_assert(DEPTH_HISTORY_CADENCE_MS >= 10000, "Review flash wear before faster journaling");

struct DepthRecord {
  uint32_t magic;
  uint32_t config;
  uint64_t serial;
  uint64_t sequence;
  uint32_t boot;
  uint16_t length;
  char json[1100]; // Observation only. No ingest or broker secrets on flash.
  uint32_t checksum;
};

inline uint32_t depthChecksum(const DepthRecord& record) {
  uint32_t crc=0xffffffffU;
  const auto* bytes=reinterpret_cast<const unsigned char*>(&record);
  for (size_t i=0;i<offsetof(DepthRecord,checksum);++i) {
    crc^=bytes[i];
    for (unsigned bit=0;bit<8;++bit) crc=(crc>>1)^((crc&1)?0xedb88320U:0);
  }
  return ~crc;
}

template<class Storage> class DepthJournal {
  Storage& storage;
  uint64_t serials[DEPTH_HISTORY_SLOTS]{};
  uint64_t nextSerial=1;
 public:
  uint64_t evicted=0, corrupt=0, writeFailures=0;
  explicit DepthJournal(Storage& target):storage(target) {}
  bool restore() {
    DepthRecord record{};
    for (unsigned slot=0;slot<DEPTH_HISTORY_SLOTS;++slot) {
      if (!storage.exists(slot)) continue;
      if (!read(slot,record)) {++corrupt;continue;}
      serials[slot]=record.serial;
      if (nextSerial<=record.serial) nextSerial=record.serial+1;
    }
    return true;
  }
  bool read(unsigned slot,DepthRecord& record) {
    return storage.read(slot,&record,sizeof(record)) && record.magic==0x44505431U &&
      record.serial>0 && (record.serial-1)%DEPTH_HISTORY_SLOTS==slot &&
      record.length>0 && record.length<sizeof(record.json) && record.json[record.length]==0 &&
      depthChecksum(record)==record.checksum;
  }
  bool append(const char* json,uint32_t config,uint32_t boot,uint64_t sequence) {
    const size_t length=strlen(json);
    if (!length || length>=sizeof(DepthRecord::json)) {++writeFailures;return false;}
    DepthRecord record{};
    record.magic=0x44505431U;record.config=config;record.boot=boot;
    record.sequence=sequence;record.serial=nextSerial;record.length=length;
    memcpy(record.json,json,length+1);record.checksum=depthChecksum(record);
    const unsigned slot=(nextSerial-1)%DEPTH_HISTORY_SLOTS;
    if (!storage.write(slot,&record,sizeof(record))) {++writeFailures;return false;}
    if (serials[slot]) ++evicted;
    serials[slot]=nextSerial++;
    return true;
  }
  bool oldest(DepthRecord& record) {
    unsigned found=DEPTH_HISTORY_SLOTS;
    for (unsigned i=0;i<DEPTH_HISTORY_SLOTS;++i)
      if (serials[i] && (found==DEPTH_HISTORY_SLOTS || serials[i]<serials[found])) found=i;
    if (found==DEPTH_HISTORY_SLOTS) return false;
    if (!read(found,record)) {serials[found]=0;++corrupt;return false;}
    return true;
  }
  bool acknowledge(const DepthRecord& record) {
    const unsigned slot=(record.serial-1)%DEPTH_HISTORY_SLOTS;
    // A delayed ACK may never erase a newer occupant of a wrapped slot.
    if (serials[slot]!=record.serial || !storage.remove(slot)) return false;
    serials[slot]=0;return true;
  }
  unsigned pending() const {
    unsigned total=0;for (auto serial:serials) if (serial) ++total;return total;
  }
};
