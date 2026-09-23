#include "storage_manager.h"

#include "esp_err.h"
#include "nvs.h"
#include "nvs_flash.h"

#define NVS_NAMESPACE "fabai"

void storage_manager_init(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
}

static bool load_pair(const char *first_key, char *first, size_t first_size,
                      const char *second_key, char *second, size_t second_size)
{
    nvs_handle_t handle;
    if (nvs_open(NVS_NAMESPACE, NVS_READONLY, &handle) != ESP_OK) return false;
    size_t first_len = first_size;
    size_t second_len = second_size;
    esp_err_t first_err = nvs_get_str(handle, first_key, first, &first_len);
    esp_err_t second_err = nvs_get_str(handle, second_key, second, &second_len);
    nvs_close(handle);
    return first_err == ESP_OK && second_err == ESP_OK && first[0] != '\0';
}

bool storage_manager_load_wifi(char *ssid, size_t ssid_size, char *password, size_t password_size)
{
    return load_pair("wifi_ssid", ssid, ssid_size, "wifi_pass", password, password_size);
}

void storage_manager_save_wifi(const char *ssid, const char *password)
{
    nvs_handle_t handle;
    ESP_ERROR_CHECK(nvs_open(NVS_NAMESPACE, NVS_READWRITE, &handle));
    ESP_ERROR_CHECK(nvs_set_str(handle, "wifi_ssid", ssid));
    ESP_ERROR_CHECK(nvs_set_str(handle, "wifi_pass", password));
    ESP_ERROR_CHECK(nvs_commit(handle));
    nvs_close(handle);
}

void storage_manager_forget_wifi(void)
{
    nvs_handle_t handle;
    ESP_ERROR_CHECK(nvs_open(NVS_NAMESPACE, NVS_READWRITE, &handle));
    esp_err_t ssid_err = nvs_erase_key(handle, "wifi_ssid");
    esp_err_t pass_err = nvs_erase_key(handle, "wifi_pass");
    if (ssid_err != ESP_OK && ssid_err != ESP_ERR_NVS_NOT_FOUND) ESP_ERROR_CHECK(ssid_err);
    if (pass_err != ESP_OK && pass_err != ESP_ERR_NVS_NOT_FOUND) ESP_ERROR_CHECK(pass_err);
    ESP_ERROR_CHECK(nvs_commit(handle));
    nvs_close(handle);
}

void storage_manager_load_backend_url(char *url, size_t url_size)
{
    nvs_handle_t handle;
    size_t len = url_size;
    if (nvs_open(NVS_NAMESPACE, NVS_READONLY, &handle) == ESP_OK) {
        if (nvs_get_str(handle, "backend_url", url, &len) == ESP_OK) {
            nvs_close(handle);
            return;
        }
        nvs_close(handle);
    }
    url[0] = '\0';
}

void storage_manager_save_backend_url(const char *url)
{
    nvs_handle_t handle;
    ESP_ERROR_CHECK(nvs_open(NVS_NAMESPACE, NVS_READWRITE, &handle));
    ESP_ERROR_CHECK(nvs_set_str(handle, "backend_url", url));
    ESP_ERROR_CHECK(nvs_commit(handle));
    nvs_close(handle);
}
