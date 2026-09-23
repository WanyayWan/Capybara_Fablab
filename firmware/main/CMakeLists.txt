idf_component_register(SRCS "main.c"
                            "device_manager.c"
                            "storage_manager.c"
                            "wifi_manager.c"
                            "backend_client.c"
                            "web_server.c"
                            "button_gesture.c"
                            "led_manager.c"
                           INCLUDE_DIRS "."
                           REQUIRES esp_driver_gpio
                                    esp_hw_support
                                    espressif__led_strip
                                    freertos
                                    spi_flash
                                    nvs_flash
                                    esp_wifi
                                    esp_event
                                    esp_netif
                                    esp_http_server
                                    esp_http_client
                                    esp_timer)
