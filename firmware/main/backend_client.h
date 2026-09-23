#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef enum {
    BACKEND_EVENT_TALK_PRESSED,
    BACKEND_EVENT_TALK_RELEASED,
    BACKEND_EVENT_HELP_REQUESTED,
} backend_event_t;

void backend_client_init(void);
bool backend_client_is_online(void);
void backend_client_get_url(char *url, size_t url_size);
bool backend_client_set_url(const char *url);

// Queues an event for the sender task; never blocks. held_ms is used by TALK_RELEASED.
// Returns false if the queue is full.
bool backend_client_send_event(backend_event_t event, uint32_t held_ms);
