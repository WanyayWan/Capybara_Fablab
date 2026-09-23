// Host unit tests for button_gesture.c (docs/test-plan.md, firmware host tests).
// Build and run: make -C firmware/test

#include <stdio.h>

#include "button_gesture.h"

// TODO F1: down 0, up 2000 -> TALK_START, TALK_END(held 2000)
// TODO F2: down 0, up 100, down 300, up 400 -> TALK_START, TALK_END(100), HELP, NONE
// TODO F3: down 0, up 100, down 700, up 2700 -> TALK_START, TALK_END, TALK_START, TALK_END
// TODO F4: down 0, up 500, down 700 -> third edge is TALK_START (first press was not a tap)
// TODO F5: triple tap within 400 ms gaps -> TALK_START, TALK_END, HELP, NONE, TALK_START, TALK_END
// TODO F6: up with no prior down -> NONE
// TODO F7: timer wrap (now_ms near UINT32_MAX) -> same as F2

int main(void)
{
    gesture_t g;
    gesture_init(&g);
    printf("0 tests run (Phase 0 skeleton)\n");
    return 0;
}
