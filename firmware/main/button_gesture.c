#include "button_gesture.h"

// Rules are in docs/build-plan.md section 6. Durations use unsigned subtraction, so
// they stay correct when the millisecond counter wraps.

#define TAP_MAX_MS 350        // a press shorter than this is a tap
#define DOUBLE_GAP_MAX_MS 400 // second press within this long after a tap's release is HELP

void gesture_init(gesture_t *g)
{
    *g = (gesture_t){0};
}

static gesture_event_t on_press(gesture_t *g, uint32_t now_ms)
{
    bool is_double = g->last_was_tap && (uint32_t)(now_ms - g->release_ms) <= DOUBLE_GAP_MAX_MS;
    g->pressed = true;
    g->press_ms = now_ms;
    g->last_was_tap = false;
    if (is_double) {
        g->in_help_press = true;
        return GESTURE_HELP;
    }
    g->talking = true;
    return GESTURE_TALK_START;
}

static gesture_event_t on_release(gesture_t *g, uint32_t now_ms, uint32_t *held_ms_out)
{
    uint32_t held_ms = now_ms - g->press_ms;
    g->pressed = false;
    g->release_ms = now_ms;
    if (g->in_help_press) {
        // The HELP press never counts as a tap, so a third tap starts a new gesture.
        g->in_help_press = false;
        return GESTURE_NONE;
    }
    g->talking = false;
    g->last_was_tap = held_ms < TAP_MAX_MS;
    if (held_ms_out) *held_ms_out = held_ms;
    return GESTURE_TALK_END;
}

gesture_event_t gesture_on_edge(gesture_t *g, bool pressed, uint32_t now_ms, uint32_t *held_ms_out)
{
    if (pressed == g->pressed) return GESTURE_NONE; // repeated edge (or release with no press)
    return pressed ? on_press(g, now_ms) : on_release(g, now_ms, held_ms_out);
}
