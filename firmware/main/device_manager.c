#include "device_manager.h"

#include "driver/gpio.h"
#include "esp_err.h"
#include "esp_timer.h"
#include "led_strip.h"

#define LED_GPIO GPIO_NUM_38
#define BUTTON_GPIO GPIO_NUM_0

static led_strip_handle_t led_strip;

void device_manager_init(void)
{
    led_strip_config_t strip_config = {.strip_gpio_num = LED_GPIO, .max_leds = 1};
    led_strip_rmt_config_t rmt_config = {.resolution_hz = 10 * 1000 * 1000, .flags.with_dma = false};
    ESP_ERROR_CHECK(led_strip_new_rmt_device(&strip_config, &rmt_config, &led_strip));
    ESP_ERROR_CHECK(led_strip_clear(led_strip));
    gpio_config_t button_config = {
        .pin_bit_mask = 1ULL << BUTTON_GPIO,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&button_config));
}

void device_manager_set_led(bool on)
{
    if (on) {
        ESP_ERROR_CHECK(led_strip_set_pixel(led_strip, 0, 20, 20, 20));
        ESP_ERROR_CHECK(led_strip_refresh(led_strip));
    } else {
        ESP_ERROR_CHECK(led_strip_clear(led_strip));
    }
}

bool device_manager_button_pressed(void)
{
    return gpio_get_level(BUTTON_GPIO) == 0;
}

unsigned long device_manager_uptime_seconds(void)
{
    return (unsigned long)(esp_timer_get_time() / 1000000);
}
