#pragma once

#include <stdbool.h>

// The one device id (build-plan 9.5): banner, request bodies, state poll, /api/status.
#define DEVICE_ID "fabai-01"

void device_manager_init(void);
bool device_manager_button_pressed(void);
unsigned long device_manager_uptime_seconds(void);
