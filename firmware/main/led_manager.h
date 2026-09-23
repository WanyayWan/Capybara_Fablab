#pragma once

// Owns the RGB LED (GPIO38) and renders the backend's `led` values at 20 Hz:
// off, blue, yellow, green, red_pulse, purple, red_flash, offline, white (debug).

void led_manager_init(void);
void led_manager_set(const char *led);
