/*
 * WiMotion Node 2: Active Access Point (CSI Receiver)
 * Captures raw CSI from incoming WiFi frames, formats packets as CSI_DATA,
 * and streams to PC over USB-UART at 921600 baud.
 * Target: ESP32-WROOM-32 on ESP-IDF v4.3 / v4.4
 */
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "driver/uart.h"

#define WIFI_SSID      "WiMotion_AP"
#define WIFI_PASS      "wimotion123"
#define WIFI_CHANNEL   6
#define UART_BAUD_RATE 921600

static const char *TAG = "WiMotion_RX";

static void _wifi_csi_cb(void *ctx, wifi_csi_info_t *data) {
    if (!data || !data->buf) return;
    wifi_pkt_rx_ctrl_t rx_ctrl = data->rx_ctrl;

    // Buffer for fast UART printing
    static char out_buf[1024];
    int offset = snprintf(out_buf, sizeof(out_buf),
        "CSI_DATA,AP,%02X:%02X:%02X:%02X:%02X:%02X,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%u,%d,%d,%d,%d,%d,%d,[",
        data->mac[0], data->mac[1], data->mac[2], data->mac[3], data->mac[4], data->mac[5],
        rx_ctrl.rssi,
        rx_ctrl.rate,
        rx_ctrl.sig_mode,
        rx_ctrl.mcs,
        rx_ctrl.cwb,
        rx_ctrl.smoothing,
        rx_ctrl.not_sounding,
        rx_ctrl.aggregation,
        rx_ctrl.stbc,
        rx_ctrl.fec_coding,
        rx_ctrl.sgi,
        rx_ctrl.noise_floor,
        rx_ctrl.ampdu_cnt,
        rx_ctrl.channel,
        rx_ctrl.secondary_channel,
        (unsigned int)rx_ctrl.timestamp,
        rx_ctrl.ant,
        rx_ctrl.sig_len,
        rx_ctrl.rx_state,
        data->len,
        data->first_word_invalid,
        data->len
    );

    int8_t *csi_raw = (int8_t *)data->buf;
    for (int i = 0; i < data->len && offset < (int)(sizeof(out_buf) - 8); i++) {
        offset += snprintf(out_buf + offset, sizeof(out_buf) - offset, i == 0 ? "%d" : " %d", csi_raw[i]);
    }
    snprintf(out_buf + offset, sizeof(out_buf) - offset, "]\n");

    uart_write_bytes(UART_NUM_0, out_buf, strlen(out_buf));
}

void app_main(void) {
    ESP_ERROR_CHECK(nvs_flash_init());

    // Configure UART0 for high-speed 921600 baud streaming
    uart_config_t uart_config = {
        .baud_rate = UART_BAUD_RATE,
        .data_bits = UART_DATA_8_BITS,
        .parity    = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE
    };
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_0, &uart_config));

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_ap();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    wifi_config_t wifi_config = {
        .ap = {
            .ssid = WIFI_SSID,
            .ssid_len = strlen(WIFI_SSID),
            .channel = WIFI_CHANNEL,
            .password = WIFI_PASS,
            .max_connection = 4,
            .authmode = WIFI_AUTH_WPA2_PSK
        },
    };
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &wifi_config));

    // Enable CSI callback
    wifi_csi_config_t csi_config = {
        .lltf_en           = 1,
        .htltf_en          = 1,
        .stbc_htltf2_en    = 1,
        .ltf_merge_en      = 1,
        .channel_filter_en = 0,
        .manu_scale        = 0,
        .shift             = 0,
    };
    ESP_ERROR_CHECK(esp_wifi_set_csi_config(&csi_config));
    ESP_ERROR_CHECK(esp_wifi_set_csi_rx_cb(_wifi_csi_cb, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_csi(1));

    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_LOGI(TAG, "WiMotion CSI AP Initialized on Channel %d (Baud: %d)", WIFI_CHANNEL, UART_BAUD_RATE);
}
