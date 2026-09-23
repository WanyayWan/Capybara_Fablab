#pragma once

#include <stdbool.h>
#include <stddef.h>

void storage_manager_init(void);
bool storage_manager_load_wifi(char *ssid, size_t ssid_size, char *password, size_t password_size);
void storage_manager_save_wifi(const char *ssid, const char *password);
void storage_manager_forget_wifi(void);
void storage_manager_load_backend_url(char *url, size_t url_size);
void storage_manager_save_backend_url(const char *url);
