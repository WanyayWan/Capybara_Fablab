#include <stdio.h>
#include <string.h>

#include "backend_client.h"
#include "button_gesture.h"
#include "device_manager.h"
#include "esp_chip_info.h"
#include "esp_flash.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "led_manager.h"
#include "storage_manager.h"
#include "web_server.h"
#include "wifi_manager.h"

#define SERIAL_BUF_LEN 64
#define DEBOUNCE_MS 50

static void send_ready_banner(void)
{
    esp_chip_info_t chip;
    uint32_t flash_size = 0;
    esp_chip_info(&chip);
    esp_flash_get_size(NULL, &flash_size);
    puts("FABAI_READY");
    puts("DEVICE_ID=" DEVICE_ID);
    printf("CHIP_REVISION=%d.%d\n", chip.revision / 100, chip.revision % 100);
    printf("FLASH_SIZE_MB=%lu\n", (unsigned long)(flash_size / (1024 * 1024)));
    puts("LED_GPIO=38");
    puts("BUTTON_GPIO=0");
    puts("PORTAL_AP=http://192.168.4.1");
    fflush(stdout);
}

static uint32_t now_ms(void)
{
    return (uint32_t)(esp_timer_get_time() / 1000); // wraps after ~49 days; gestures handle it
}

static void handle_gesture(gesture_event_t event, uint32_t held_ms)
{
    switch (event) {
    case GESTURE_TALK_START:
        led_manager_set("blue"); // local feedback before the next state poll
        backend_client_send_event(BACKEND_EVENT_TALK_PRESSED, 0);
        puts("EVENT=talk_pressed");
        break;
    case GESTURE_TALK_END:
        backend_client_send_event(BACKEND_EVENT_TALK_RELEASED, held_ms);
        printf("EVENT=talk_released HELD_MS=%lu\n", (unsigned long)held_ms);
        break;
    case GESTURE_HELP:
        backend_client_send_event(BACKEND_EVENT_HELP_REQUESTED, 0);
        puts("EVENT=help_requested");
        break;
    case GESTURE_NONE:
        return;
    }
    fflush(stdout);
}

static void button_task(void *arg)
{
    (void)arg;
    gesture_t gesture;
    gesture_init(&gesture);
    bool previous = device_manager_button_pressed();
    uint32_t changed_at = now_ms();
    while (true) {
        bool pressed = device_manager_button_pressed();
        uint32_t now = now_ms();
        if (pressed != previous && now - changed_at >= DEBOUNCE_MS) {
            previous = pressed;
            changed_at = now;
            uint32_t held_ms = 0;
            handle_gesture(gesture_on_edge(&gesture, pressed, now, &held_ms), held_ms);
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

static void handle_command(char *line)
{
    line[strcspn(line, "\r\n")] = '\0';
    if (strcmp(line, "LED_ON") == 0) {
        led_manager_set("white");
        puts("LED_ON_OK");
    } else if (strcmp(line, "LED_OFF") == 0) {
        led_manager_set("off");
        puts("LED_OFF_OK");
    } else if (line[0]) {
        printf("UNKNOWN_COMMAND=%s\n", line);
    }
    fflush(stdout);
}

void app_main(void)
{
    storage_manager_init();
    device_manager_init();
    led_manager_init();
    wifi_manager_init();
    web_server_start();
    backend_client_init();
    send_ready_banner();
    xTaskCreate(button_task, "button_task", 3072, NULL, 5, NULL);

    char buffer[SERIAL_BUF_LEN];
    while (true) {
        if (fgets(buffer, sizeof(buffer), stdin)) {
            handle_command(buffer);
        } else {
            clearerr(stdin);
            vTaskDelay(pdMS_TO_TICKS(10));
        }
    }
}
