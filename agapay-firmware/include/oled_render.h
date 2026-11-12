// AGAPAY SH1106 128x64 page renderer (U8g2 C API; identical on the ESP32 and the host preview).
#pragma once
#include "oled_model.h"
#if defined(ARDUINO)
#include <U8g2lib.h>
#else
#include "u8g2.h"
#endif

// Draws one complete frame into the U8g2 buffer (caller sends it). Never blocks.
void oledRender(u8g2_t* u8g2, const oled::Inputs& in);
