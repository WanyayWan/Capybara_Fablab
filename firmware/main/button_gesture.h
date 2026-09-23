#pragma once

// Pure button-gesture logic (hold-to-talk and double-press for staff).
// No ESP-IDF includes, so it can be unit-tested on the host with gcc.

#include <stdbool.h>
#include <stdint.h>

typedef enum {
    GESTURE_NONE,
    GESTURE_TALK_START,
    GESTURE_TALK_END,
    GESTURE_HELP,
} gesture_event_t;

typedef struct {
    bool pressed;
    bool talking;
    bool in_help_press;
    bool last_was_tap;
    uint32_t press_ms;
    uint32_t release_ms;
} gesture_t;

void gesture_init(gesture_t *g);

// Feed one debounced edge. Returns the resulting event; for GESTURE_TALK_END,
// writes the hold duration to *held_ms_out (if not NULL).
gesture_event_t gesture_on_edge(gesture_t *g, bool pressed, uint32_t now_ms, uint32_t *held_ms_out);
