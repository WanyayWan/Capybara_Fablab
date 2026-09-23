#include "device_manager.h"

#include "driver/gpio.h"
#include "esp_err.h"
#include "esp_timer.h"

#define BUTTON_GPIO GPIO_NUM_0

void device_manager_init(void)
{
    gpio_config_t button_config = {
        .pin_bit_mask = 1ULL << BUTTON_GPIO,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&button_config));
}

bool device_manager_button_pressed(void)
{
    return gpio_get_level(BUTTON_GPIO) == 0;
}

unsigned long device_manager_uptime_seconds(void)
{
    return (unsigned long)(esp_timer_get_time() / 1000000);
}
