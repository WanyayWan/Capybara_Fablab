#pragma once

#include <stdbool.h>

void device_manager_init(void);
void device_manager_set_led(bool on);
bool device_manager_button_pressed(void);
unsigned long device_manager_uptime_seconds(void);
