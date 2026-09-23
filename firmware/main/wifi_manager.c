#include "wifi_manager.h"

#include <string.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "storage_manager.h"

#define CONNECTED_BIT BIT0
#define SETUP_AP_SSID "FabAI-Setup"
#define MAX_RETRIES 3

static const char *TAG = "wifi";
static EventGroupHandle_t wifi_events;
static esp_netif_t *sta_netif;
static wifi_status_t status;
static int retries;

static void start_setup_ap(void)
{
    wifi_config_t ap_config = {
        .ap = {
            .ssid = SETUP_AP_SSID,
            .ssid_len = strlen(SETUP_AP_SSID),
            .channel = 1,
            .max_connection = 4,
            .authmode = WIFI_AUTH_OPEN,
        },
    };
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_APSTA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &ap_config));
    status.setup_mode = true;
    ESP_LOGI(TAG, "Setup access point active: %s", SETUP_AP_SSID);
}

static void event_handler(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        status.connected = false;
        xEventGroupClearBits(wifi_events, CONNECTED_BIT);
        if (retries++ < MAX_RETRIES && status.ssid[0]) {
            esp_wifi_connect();
        } else {
            start_setup_ap();
        }
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = data;
        esp_ip4addr_ntoa(&event->ip_info.ip, status.ip, sizeof(status.ip));
        status.connected = true;
        status.setup_mode = false;
        retries = 0;
        xEventGroupSetBits(wifi_events, CONNECTED_BIT);
        ESP_LOGI(TAG, "Connected to %s, IP %s", status.ssid, status.ip);
    }
}

void wifi_manager_init(void)
{
    wifi_events = xEventGroupCreate();
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    sta_netif = esp_netif_create_default_wifi_sta();
    esp_netif_create_default_wifi_ap();
    wifi_init_config_t config = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&config));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &event_handler, NULL, NULL));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &event_handler, NULL, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));

    char password[65] = {0};
    if (storage_manager_load_wifi(status.ssid, sizeof(status.ssid), password, sizeof(password))) {
        wifi_config_t sta_config = {0};
        strlcpy((char *)sta_config.sta.ssid, status.ssid, sizeof(sta_config.sta.ssid));
        strlcpy((char *)sta_config.sta.password, password, sizeof(sta_config.sta.password));
        ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
        ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &sta_config));
    } else {
        ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_APSTA));
        status.setup_mode = true;
    }
    ESP_ERROR_CHECK(esp_wifi_start());
    if (status.setup_mode) start_setup_ap();
}

void wifi_manager_get_status(wifi_status_t *out)
{
    *out = status;
    if (status.connected) {
        wifi_ap_record_t ap;
        if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) out->rssi = ap.rssi;
    }
}

static const char *security_name(wifi_auth_mode_t auth)
{
    if (auth == WIFI_AUTH_OPEN) return "Open";
    if (auth == WIFI_AUTH_WEP) return "WEP";
    if (auth == WIFI_AUTH_WPA_PSK) return "WPA";
    if (auth == WIFI_AUTH_WPA2_PSK) return "WPA2";
    return "WPA2/3";
}

size_t wifi_manager_scan(wifi_network_t *networks, size_t capacity)
{
    wifi_scan_config_t scan_config = {0};
    if (esp_wifi_scan_start(&scan_config, true) != ESP_OK) return 0;
    wifi_ap_record_t records[16];
    uint16_t count = capacity > 16 ? 16 : capacity;
    if (esp_wifi_scan_get_ap_records(&count, records) != ESP_OK) return 0;
    for (uint16_t i = 0; i < count; ++i) {
        strlcpy(networks[i].ssid, (char *)records[i].ssid, sizeof(networks[i].ssid));
        networks[i].rssi = records[i].rssi;
        strlcpy(networks[i].security, security_name(records[i].authmode), sizeof(networks[i].security));
    }
    return count;
}

bool wifi_manager_connect(const char *ssid, const char *password)
{
    if (!ssid || !ssid[0] || strlen(ssid) > 32 || strlen(password) > 63) return false;
    wifi_config_t config = {0};
    strlcpy((char *)config.sta.ssid, ssid, sizeof(config.sta.ssid));
    strlcpy((char *)config.sta.password, password, sizeof(config.sta.password));
    storage_manager_save_wifi(ssid, password);
    strlcpy(status.ssid, ssid, sizeof(status.ssid));
    status.ip[0] = '\0';
    retries = 0;
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_APSTA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &config));
    esp_wifi_disconnect();
    return esp_wifi_connect() == ESP_OK;
}

void wifi_manager_forget(void)
{
    storage_manager_forget_wifi();
    status.ssid[0] = '\0';
    status.ip[0] = '\0';
    status.connected = false;
    retries = MAX_RETRIES;
    esp_wifi_disconnect();
    start_setup_ap();
}
