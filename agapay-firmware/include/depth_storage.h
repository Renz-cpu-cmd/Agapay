#pragma once
#include <LittleFS.h>
// Dedicated names only. Never format the partition or touch other application files.
struct DepthStorage {
  void path(unsigned slot,char* target,size_t length) {
    snprintf(target,length,"/agapay-depth/%03u.bin",slot);
  }
  bool begin() {return LittleFS.begin(false) && (LittleFS.exists("/agapay-depth") || LittleFS.mkdir("/agapay-depth"));}
  bool exists(unsigned slot) {char name[48];path(slot,name,sizeof(name));return LittleFS.exists(name);}
  bool read(unsigned slot,void* data,size_t length) {
    char name[48];path(slot,name,sizeof(name));auto file=LittleFS.open(name,"r");
    if (!file || file.size()!=length) return false;
    const bool ok=file.read(static_cast<uint8_t*>(data),length)==length;file.close();return ok;
  }
  bool write(unsigned slot,const void* data,size_t length) {
    char name[48];path(slot,name,sizeof(name));
    // LittleFS copy-on-write + rename preserves the previous committed slot if
    // power fails before replacement. A leftover temp file is never ingested.
    auto file=LittleFS.open("/agapay-depth/pending.tmp","w");
    if (!file) return false;
    const bool ok=file.write(static_cast<const uint8_t*>(data),length)==length;
    file.flush();file.close();
    return ok && LittleFS.rename("/agapay-depth/pending.tmp",name);
  }
  bool remove(unsigned slot) {char name[48];path(slot,name,sizeof(name));return LittleFS.remove(name);}
};
