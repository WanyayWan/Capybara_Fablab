#include "backend_client.h"

#include <stdio.h>
#include <string.h>

#include "esp_http_client.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "storage_manager.h"
#include "wifi_manager.h"

#define DEVICE_ID "fabai-01"

static char backend_url[128];
static bool backend_online;

static bool request(const char *path, const char *body)
{
    if (!backend_url[0]) return false;
    char url[192];
    snprintf(url, sizeof(url), "%s%s", backend_url, path);
    esp_http_client_config_t config = {.url = url, .timeout_ms = 2000};
    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (body) {
        esp_http_client_set_method(client, HTTP_METHOD_POST);
        esp_http_client_set_header(client, "Content-Type", "application/json");
        esp_http_client_set_post_field(client, body, strlen(body));
    }
    esp_err_t err = esp_http_client_perform(client);
    int code = esp_http_client_get_status_code(client);
    esp_http_client_cleanup(client);
    return err == ESP_OK && code >= 200 && code < 300;
}

static void backend_task(void *arg)
{
    while (true) {
        wifi_status_t wifi;
        wifi_manager_get_status(&wifi);
        backend_online = wifi.connected && request("/health", NULL);
        if (backend_online) {
            request("/api/device/heartbeat", "{\"device_id\":\"fabai-01\"}");
        }
        vTaskDelay(pdMS_TO_TICKS(15000));
    }
}

void backend_client_init(void)
{
    storage_manager_load_backend_url(backend_url, sizeof(backend_url));
    xTaskCreate(backend_task, "backend_task", 4096, NULL, 4, NULL);
}

bool backend_client_is_online(void) { return backend_online; }

void backend_client_get_url(char *url, size_t url_size) { strlcpy(url, backend_url, url_size); }

bool backend_client_set_url(const char *url)
{
    if (!url || strlen(url) >= sizeof(backend_url) || (url[0] && strncmp(url, "http://", 7) != 0)) return false;
    strlcpy(backend_url, url, sizeof(backend_url));
    storage_manager_save_backend_url(backend_url);
    backend_online = false;
    return true;
}

void backend_client_send_button_event(void)
{
    if (backend_online) request("/api/device/event", "{\"device_id\":\"fabai-01\",\"event\":\"talk_button_pressed\"}");
}
