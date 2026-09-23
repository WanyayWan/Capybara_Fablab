#pragma once

#include <stdbool.h>
#include <stddef.h>

void backend_client_init(void);
bool backend_client_is_online(void);
void backend_client_get_url(char *url, size_t url_size);
bool backend_client_set_url(const char *url);
void backend_client_send_button_event(void);
