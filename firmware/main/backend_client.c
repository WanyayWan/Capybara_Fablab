#include "backend_client.h"

#include <stdio.h>
#include <string.h>

#include "device_manager.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "led_manager.h"
#include "storage_manager.h"
#include "wifi_manager.h"

// Event queue + sender task, state poll task, 15 s heartbeat (build-plan section 6, 9.9).
// Each task keeps one keep-alive esp_http_client; a handle is never shared between tasks.

#define URL_MAX 128
#define EVENT_QUEUE_LEN 8
#define POLL_PERIOD_MS 400
#define POLL_TIMEOUT_MS 1000
#define EVENT_TIMEOUT_MS 2000
#define OFFLINE_AFTER_FAILS 3
#define HEARTBEAT_PERIOD_MS 15000

typedef struct {
    backend_event_t event;
    uint32_t held_ms;
} queued_event_t;

typedef struct {
    esp_http_client_handle_t client;
    unsigned url_gen;
    int timeout_ms;
    char *resp;
    size_t resp_size;
    size_t resp_len;
} conn_t;

static const char *TAG = "backend";
static portMUX_TYPE url_lock = portMUX_INITIALIZER_UNLOCKED;
static char backend_url[URL_MAX];
static unsigned url_gen = 1; // bumped on every URL change so tasks rebuild their client
static volatile bool backend_online;
static QueueHandle_t event_queue;

static unsigned snapshot_url(char *out)
{
    taskENTER_CRITICAL(&url_lock);
    strlcpy(out, backend_url, URL_MAX);
    unsigned gen = url_gen;
    taskEXIT_CRITICAL(&url_lock);
    return gen;
}

static bool network_ready(void)
{
    wifi_status_t wifi;
    wifi_manager_get_status(&wifi);
    return wifi.connected;
}

static esp_err_t on_http_event(esp_http_client_event_t *evt)
{
    conn_t *c = evt->user_data;
    if (evt->event_id == HTTP_EVENT_ON_DATA && c->resp && c->resp_len + 1 < c->resp_size) {
        size_t n = (size_t)evt->data_len;
        if (n > c->resp_size - 1 - c->resp_len) n = c->resp_size - 1 - c->resp_len;
        memcpy(c->resp + c->resp_len, evt->data, n);
        c->resp_len += n;
        c->resp[c->resp_len] = '\0';
    }
    return ESP_OK;
}

static void conn_drop(conn_t *c)
{
    if (c->client) esp_http_client_cleanup(c->client);
    c->client = NULL;
}

// GET when body is NULL, else POST JSON. Reuses the connection; drops it on any error so the
// next call reconnects. resp (optional) receives the body, truncated to resp_size - 1.
static bool conn_request(conn_t *c, const char *path, const char *body, char *resp, size_t resp_size)
{
    char base[URL_MAX];
    char url[URL_MAX + 64];
    unsigned gen = snapshot_url(base);
    if (!base[0]) return false;
    snprintf(url, sizeof(url), "%s%s", base, path);
    if (c->client && c->url_gen != gen) conn_drop(c);
    if (!c->client) {
        esp_http_client_config_t config = {
            .url = url,
            .timeout_ms = c->timeout_ms,
            .keep_alive_enable = true,
            .event_handler = on_http_event,
            .user_data = c,
        };
        c->client = esp_http_client_init(&config);
        if (!c->client) return false;
        c->url_gen = gen;
        if (body) {
            esp_http_client_set_method(c->client, HTTP_METHOD_POST);
            esp_http_client_set_header(c->client, "Content-Type", "application/json");
        }
    }
    esp_http_client_set_url(c->client, url);
    if (body) esp_http_client_set_post_field(c->client, body, (int)strlen(body));
    c->resp = resp;
    c->resp_size = resp_size;
    c->resp_len = 0;
    if (resp && resp_size) resp[0] = '\0';
    esp_err_t err = esp_http_client_perform(c->client);
    int code = esp_http_client_get_status_code(c->client);
    c->resp = NULL;
    if (err != ESP_OK) {
        conn_drop(c);
        return false;
    }
    return code >= 200 && code < 300;
}

// Extracts the "led" string from {"activity": ..., "help": ..., "led": "..."}.
static bool parse_led(const char *json, char *led, size_t led_size)
{
    const char *p = strstr(json, "\"led\"");
    if (!p || !(p = strchr(p + 5, ':')) || !(p = strchr(p, '"'))) return false;
    const char *end = strchr(++p, '"');
    if (!end || end == p || (size_t)(end - p) >= led_size) return false;
    memcpy(led, p, end - p);
    led[end - p] = '\0';
    return true;
}

static void poll_task(void *arg)
{
    (void)arg;
    conn_t conn = {.timeout_ms = POLL_TIMEOUT_MS};
    char resp[160];
    char led[16];
    int fails = 0;
    TickType_t wake = xTaskGetTickCount();
    while (true) {
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(POLL_PERIOD_MS));
        bool ok = network_ready() &&
                  conn_request(&conn, "/api/device/state?device_id=" DEVICE_ID, NULL, resp, sizeof(resp)) &&
                  parse_led(resp, led, sizeof(led));
        if (ok) {
            if (fails >= OFFLINE_AFTER_FAILS) ESP_LOGI(TAG, "backend online");
            fails = 0;
            backend_online = true;
            led_manager_set(led);
        } else if (fails < OFFLINE_AFTER_FAILS && ++fails == OFFLINE_AFTER_FAILS) {
            // Set once on the transition, so a debug "white" is not overwritten while offline.
            ESP_LOGW(TAG, "backend offline");
            backend_online = false;
            led_manager_set("offline");
        }
        if (!ok) wake = xTaskGetTickCount(); // don't burst to catch up after a slow timeout
    }
}

static const char *event_name(backend_event_t event)
{
    switch (event) {
    case BACKEND_EVENT_TALK_PRESSED: return "talk_pressed";
    case BACKEND_EVENT_TALK_RELEASED: return "talk_released";
    case BACKEND_EVENT_HELP_REQUESTED: return "help_requested";
    }
    return "unknown";
}

static void send_queued(conn_t *conn, const queued_event_t *ev)
{
    char body[128];
    if (ev->event == BACKEND_EVENT_TALK_RELEASED) {
        snprintf(body, sizeof(body), "{\"device_id\":\"" DEVICE_ID "\",\"event\":\"%s\",\"held_ms\":%lu}",
                 event_name(ev->event), (unsigned long)ev->held_ms);
    } else {
        snprintf(body, sizeof(body), "{\"device_id\":\"" DEVICE_ID "\",\"event\":\"%s\"}", event_name(ev->event));
    }
    bool ok = network_ready() && conn_request(conn, "/api/device/event", body, NULL, 0);
    if (!ok) ESP_LOGW(TAG, "event %s not delivered", event_name(ev->event));
}

static void sender_task(void *arg)
{
    (void)arg;
    static const char ID_BODY[] = "{\"device_id\":\"" DEVICE_ID "\"}";
    conn_t conn = {.timeout_ms = EVENT_TIMEOUT_MS};
    unsigned registered_gen = 0;
    TickType_t last_heartbeat = xTaskGetTickCount();
    while (true) {
        queued_event_t ev;
        if (xQueueReceive(event_queue, &ev, pdMS_TO_TICKS(1000)) == pdTRUE) send_queued(&conn, &ev);
        // Housekeeping after events, so a button press never waits behind it.
        char base[URL_MAX];
        unsigned gen = snapshot_url(base);
        if (!base[0] || !network_ready()) continue;
        if (registered_gen != gen && conn_request(&conn, "/api/device/register", ID_BODY, NULL, 0)) {
            ESP_LOGI(TAG, "registered with %s", base);
            registered_gen = gen;
        }
        if (xTaskGetTickCount() - last_heartbeat >= pdMS_TO_TICKS(HEARTBEAT_PERIOD_MS)) {
            last_heartbeat = xTaskGetTickCount();
            conn_request(&conn, "/api/device/heartbeat", ID_BODY, NULL, 0);
        }
    }
}

void backend_client_init(void)
{
    storage_manager_load_backend_url(backend_url, sizeof(backend_url));
    event_queue = xQueueCreate(EVENT_QUEUE_LEN, sizeof(queued_event_t));
    xTaskCreate(sender_task, "backend_send", 4096, NULL, 4, NULL);
    xTaskCreate(poll_task, "backend_poll", 4096, NULL, 4, NULL);
}

bool backend_client_is_online(void) { return backend_online; }

void backend_client_get_url(char *url, size_t url_size)
{
    char copy[URL_MAX];
    snapshot_url(copy);
    strlcpy(url, copy, url_size);
}

bool backend_client_set_url(const char *url)
{
    if (!url || strlen(url) >= URL_MAX || (url[0] && strncmp(url, "http://", 7) != 0)) return false;
    char clean[URL_MAX];
    strlcpy(clean, url, sizeof(clean));
    size_t len = strlen(clean);
    while (len > 7 && clean[len - 1] == '/') clean[--len] = '\0'; // paths are appended with a leading '/'
    taskENTER_CRITICAL(&url_lock);
    strlcpy(backend_url, clean, sizeof(backend_url));
    ++url_gen;
    taskEXIT_CRITICAL(&url_lock);
    storage_manager_save_backend_url(clean);
    backend_online = false;
    return true;
}

bool backend_client_send_event(backend_event_t event, uint32_t held_ms)
{
    queued_event_t ev = {.event = event, .held_ms = held_ms};
    if (event_queue && xQueueSend(event_queue, &ev, 0) == pdTRUE) return true;
    ESP_LOGW(TAG, "event queue full, dropped %s", event_name(event));
    return false;
}
