#include <stdio.h>
#include <string.h>

#include "backend_client.h"
#include "device_manager.h"
#include "esp_chip_info.h"
#include "esp_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "storage_manager.h"
#include "web_server.h"
#include "wifi_manager.h"

#define SERIAL_BUF_LEN 64

static void send_ready_banner(void)
{
    esp_chip_info_t chip;
    uint32_t flash_size = 0;
    esp_chip_info(&chip);
    esp_flash_get_size(NULL, &flash_size);
    puts("FABAI_READY");
    puts("DEVICE_ID=fabai-01");
    printf("CHIP_REVISION=%d.%d\n", chip.revision / 100, chip.revision % 100);
    printf("FLASH_SIZE_MB=%lu\n", (unsigned long)(flash_size / (1024 * 1024)));
    puts("LED_GPIO=38");
    puts("BUTTON_GPIO=0");
    puts("PORTAL_AP=http://192.168.4.1");
    fflush(stdout);
}

static void button_task(void *arg)
{
    bool previous = device_manager_button_pressed();
    TickType_t changed_at = xTaskGetTickCount();
    while (true) {
        bool pressed = device_manager_button_pressed();
        TickType_t now = xTaskGetTickCount();
        if (pressed != previous && now - changed_at >= pdMS_TO_TICKS(50)) {
            previous = pressed;
            changed_at = now;
            if (pressed) {
                puts("BUTTON_PRESSED");
                fflush(stdout);
                device_manager_set_led(true);
                backend_client_send_button_event();
                vTaskDelay(pdMS_TO_TICKS(150));
                device_manager_set_led(false);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

static void handle_command(char *line)
{
    line[strcspn(line, "\r\n")] = '\0';
    if (strcmp(line, "LED_ON") == 0) {
        device_manager_set_led(true);
        puts("LED_ON_OK");
    } else if (strcmp(line, "LED_OFF") == 0) {
        device_manager_set_led(false);
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
