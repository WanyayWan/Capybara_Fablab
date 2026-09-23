// Host unit tests for button_gesture.c (docs/test-plan.md, firmware host tests).
// Build and run: make -C firmware/test

#include <stdio.h>

#include "button_gesture.h"

typedef struct {
    bool pressed;
    uint32_t at_ms;
} edge_t;

typedef struct {
    gesture_event_t event;
    uint32_t held_ms;  // checked only for GESTURE_TALK_END
} expect_t;

static int failures;

static const char *event_name(gesture_event_t e)
{
    switch (e) {
    case GESTURE_NONE: return "NONE";
    case GESTURE_TALK_START: return "TALK_START";
    case GESTURE_TALK_END: return "TALK_END";
    case GESTURE_HELP: return "HELP";
    }
    return "?";
}

static void run(const char *name, const edge_t *edges, const expect_t *expected, int count)
{
    gesture_t g;
    gesture_init(&g);
    bool ok = true;
    for (int i = 0; i < count; ++i) {
        uint32_t held = 0xDEADBEEF;
        gesture_event_t got = gesture_on_edge(&g, edges[i].pressed, edges[i].at_ms, &held);
        if (got != expected[i].event) {
            printf("FAIL %s edge %d: got %s, want %s\n", name, i, event_name(got), event_name(expected[i].event));
            ok = false;
        } else if (got == GESTURE_TALK_END && held != expected[i].held_ms) {
            printf("FAIL %s edge %d: held %lu, want %lu\n", name, i, (unsigned long)held,
                   (unsigned long)expected[i].held_ms);
            ok = false;
        }
    }
    if (ok) printf("ok   %s\n", name);
    else ++failures;
}

#define RUN(name, edges, expected) run(name, edges, expected, (int)(sizeof(edges) / sizeof(edges[0])))

static void f1_hold_to_talk(void)
{
    const edge_t edges[] = {{true, 0}, {false, 2000}};
    const expect_t want[] = {{GESTURE_TALK_START, 0}, {GESTURE_TALK_END, 2000}};
    RUN("F1 hold to talk", edges, want);
}

static void f2_double_press(void)
{
    const edge_t edges[] = {{true, 0}, {false, 100}, {true, 300}, {false, 400}};
    const expect_t want[] = {{GESTURE_TALK_START, 0}, {GESTURE_TALK_END, 100}, {GESTURE_HELP, 0}, {GESTURE_NONE, 0}};
    RUN("F2 double press", edges, want);
}

static void f3_gap_too_long(void)
{
    const edge_t edges[] = {{true, 0}, {false, 100}, {true, 700}, {false, 2700}};
    const expect_t want[] = {
        {GESTURE_TALK_START, 0}, {GESTURE_TALK_END, 100}, {GESTURE_TALK_START, 0}, {GESTURE_TALK_END, 2000}};
    RUN("F3 gap too long", edges, want);
}

static void f4_first_press_not_tap(void)
{
    const edge_t edges[] = {{true, 0}, {false, 500}, {true, 700}};
    const expect_t want[] = {{GESTURE_TALK_START, 0}, {GESTURE_TALK_END, 500}, {GESTURE_TALK_START, 0}};
    RUN("F4 first press not a tap", edges, want);
}

static void f5_triple_tap(void)
{
    const edge_t edges[] = {{true, 0}, {false, 100}, {true, 300}, {false, 400}, {true, 600}, {false, 700}};
    const expect_t want[] = {{GESTURE_TALK_START, 0}, {GESTURE_TALK_END, 100}, {GESTURE_HELP, 0},
                             {GESTURE_NONE, 0},       {GESTURE_TALK_START, 0}, {GESTURE_TALK_END, 100}};
    RUN("F5 triple tap", edges, want);
}

static void f6_release_without_press(void)
{
    const edge_t edges[] = {{false, 50}};
    const expect_t want[] = {{GESTURE_NONE, 0}};
    RUN("F6 release without press", edges, want);
}

static void f7_timer_wrap(void)
{
    const uint32_t t0 = UINT32_MAX - 150;  // wraps between the first release and the second press
    const edge_t edges[] = {{true, t0}, {false, t0 + 100}, {true, t0 + 300}, {false, t0 + 400}};
    const expect_t want[] = {{GESTURE_TALK_START, 0}, {GESTURE_TALK_END, 100}, {GESTURE_HELP, 0}, {GESTURE_NONE, 0}};
    RUN("F7 timer wrap", edges, want);
}

int main(void)
{
    f1_hold_to_talk();
    f2_double_press();
    f3_gap_too_long();
    f4_first_press_not_tap();
    f5_triple_tap();
    f6_release_without_press();
    f7_timer_wrap();
    if (failures) {
        printf("%d of 7 tests FAILED\n", failures);
        return 1;
    }
    printf("7 tests passed\n");
    return 0;
}
