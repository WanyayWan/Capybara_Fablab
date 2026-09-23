#include "button_gesture.h"

// Phase 0 stub. Rules are in docs/build-plan.md section 6.

void gesture_init(gesture_t *g)
{
    (void)g;
}

gesture_event_t gesture_on_edge(gesture_t *g, bool pressed, uint32_t now_ms, uint32_t *held_ms_out)
{
    (void)g;
    (void)pressed;
    (void)now_ms;
    (void)held_ms_out;
    return GESTURE_NONE;
}
