#pragma once

#include <stdbool.h>
#include <stddef.h>

typedef struct {
    bool connected;
    bool setup_mode;
    char ssid[33];
    char ip[16];
    int rssi;
} wifi_status_t;

typedef struct {
    char ssid[33];
    int rssi;
    char security[12];
} wifi_network_t;

void wifi_manager_init(void);
void wifi_manager_get_status(wifi_status_t *status);
size_t wifi_manager_scan(wifi_network_t *networks, size_t capacity);
bool wifi_manager_connect(const char *ssid, const char *password);
void wifi_manager_forget(void);
