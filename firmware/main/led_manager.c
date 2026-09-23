#include "led_manager.h"

#include <math.h>
#include <stdint.h>
#include <string.h>

#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "led_strip.h"

// Patterns are in docs/build-plan.md section 2 (LED table).

#define LED_GPIO 38
#define MAX_LEVEL 40      // brightness cap (of 255)
#define FRAME_MS 50       // 20 Hz render
#define PULSE_PERIOD_MS 2000
#define FLASH_ON_MS 150
#define FLASH_OFF_MS 150
#define FLASH_COUNT 3
#define OFFLINE_PERIOD_MS 2000
#define OFFLINE_ON_MS 150
#define OFFLINE_LEVEL 8

typedef enum {
    LED_OFF,
    LED_BLUE,
    LED_YELLOW,
    LED_GREEN,
    LED_RED_PULSE,
    LED_PURPLE,
    LED_RED_FLASH,
    LED_OFFLINE,
    LED_WHITE,
} led_mode_t;

typedef struct {
    uint8_t r, g, b;
} rgb_t;

static const struct {
    const char *name;
    led_mode_t mode;
} MODES[] = {
    {"off", LED_OFF},         {"blue", LED_BLUE},           {"yellow", LED_YELLOW},
    {"green", LED_GREEN},     {"red_pulse", LED_RED_PULSE}, {"purple", LED_PURPLE},
    {"red_flash", LED_RED_FLASH}, {"offline", LED_OFFLINE}, {"white", LED_WHITE},
};

static const char *TAG = "led";
static led_strip_handle_t strip;
static portMUX_TYPE lock = portMUX_INITIALIZER_UNLOCKED;
static led_mode_t mode = LED_OFF;
static TickType_t mode_since;

static rgb_t render(led_mode_t m, uint32_t elapsed_ms)
{
    switch (m) {
    case LED_BLUE: return (rgb_t){0, 0, MAX_LEVEL};
    case LED_YELLOW: return (rgb_t){MAX_LEVEL, 28, 0};
    case LED_GREEN: return (rgb_t){0, MAX_LEVEL, 0};
    case LED_PURPLE: return (rgb_t){28, 0, MAX_LEVEL};
    case LED_WHITE: return (rgb_t){16, 16, 16};
    case LED_RED_PULSE: {
        float phase = (float)(elapsed_ms % PULSE_PERIOD_MS) / PULSE_PERIOD_MS;
        float level = 0.5f - 0.5f * cosf(2.0f * (float)M_PI * phase); // 0 -> 1 -> 0
        return (rgb_t){(uint8_t)(2 + level * (MAX_LEVEL - 2)), 0, 0};
    }
    case LED_RED_FLASH: {
        bool on = elapsed_ms < FLASH_COUNT * (FLASH_ON_MS + FLASH_OFF_MS) &&
                  elapsed_ms % (FLASH_ON_MS + FLASH_OFF_MS) < FLASH_ON_MS;
        return (rgb_t){on ? MAX_LEVEL : 0, 0, 0};
    }
    case LED_OFFLINE:
        return (rgb_t){elapsed_ms % OFFLINE_PERIOD_MS < OFFLINE_ON_MS ? OFFLINE_LEVEL : 0, 0, 0};
    case LED_OFF:
    default: return (rgb_t){0, 0, 0};
    }
}

static void led_task(void *arg)
{
    (void)arg;
    rgb_t shown = {1, 1, 1}; // forces the first frame to be written
    TickType_t wake = xTaskGetTickCount();
    while (true) {
        taskENTER_CRITICAL(&lock);
        led_mode_t m = mode;
        TickType_t since = mode_since;
        taskEXIT_CRITICAL(&lock);
        rgb_t c = render(m, pdTICKS_TO_MS(xTaskGetTickCount() - since));
        if (memcmp(&c, &shown, sizeof(c)) != 0) {
            esp_err_t err = (c.r | c.g | c.b) ? led_strip_set_pixel(strip, 0, c.r, c.g, c.b) : ESP_OK;
            if (err == ESP_OK) err = (c.r | c.g | c.b) ? led_strip_refresh(strip) : led_strip_clear(strip);
            if (err == ESP_OK) shown = c;
            else ESP_LOGW(TAG, "LED write failed: %s", esp_err_to_name(err));
        }
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(FRAME_MS));
    }
}

void led_manager_init(void)
{
    led_strip_config_t strip_config = {.strip_gpio_num = LED_GPIO, .max_leds = 1};
    led_strip_rmt_config_t rmt_config = {.resolution_hz = 10 * 1000 * 1000, .flags.with_dma = false};
    ESP_ERROR_CHECK(led_strip_new_rmt_device(&strip_config, &rmt_config, &strip));
    ESP_ERROR_CHECK(led_strip_clear(strip));
    mode_since = xTaskGetTickCount();
    xTaskCreate(led_task, "led_task", 3072, NULL, 3, NULL);
}

void led_manager_set(const char *led)
{
    for (size_t i = 0; led && i < sizeof(MODES) / sizeof(MODES[0]); ++i) {
        if (strcmp(led, MODES[i].name) != 0) continue;
        taskENTER_CRITICAL(&lock);
        if (mode != MODES[i].mode) { // same value again keeps the pattern's phase (poll repeats it)
            mode = MODES[i].mode;
            mode_since = xTaskGetTickCount();
        }
        taskEXIT_CRITICAL(&lock);
        return;
    }
    ESP_LOGW(TAG, "unknown led value: %s", led ? led : "(null)");
}
