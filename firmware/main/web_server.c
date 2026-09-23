#include "web_server.h"

#include <stdio.h>
#include <string.h>

#include "backend_client.h"
#include "device_manager.h"
#include "esp_http_server.h"
#include "esp_system.h"
#include "wifi_manager.h"

static const char PORTAL[] =
"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
"<title>FabAI</title><style>body{margin:0;background:#f3f5f7;color:#18212b;font:15px Arial,sans-serif}.app{max-width:800px;margin:auto;padding:24px}header{border-bottom:2px solid #159a9c;padding-bottom:18px}h1{margin:0;font-size:32px}header p{margin:6px 0 0;color:#53616e}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-top:20px}.section{border-top:1px solid #cbd5dc;padding:16px 0}h2{font-size:13px;letter-spacing:0;margin:0 0 13px;color:#35505b}.row{display:flex;justify-content:space-between;gap:12px;padding:6px 0}.muted{color:#61707b}.good{color:#087e5b;font-weight:bold}.bad{color:#a23b28;font-weight:bold}button{background:#087e8b;border:0;border-radius:5px;color:#fff;cursor:pointer;font-weight:bold;padding:10px 14px}button.secondary{background:#455866}input{width:100%;padding:10px;border:1px solid #aab7bf;border-radius:4px}label{display:block;margin:10px 0 4px}#networks button{display:block;width:100%;margin:5px 0;text-align:left;background:#fff;color:#18212b;border:1px solid #cbd5dc}@media(max-width:620px){.app{padding:16px}.grid{grid-template-columns:1fr}}</style></head><body><main class='app'>"
"<header><h1>FabAI</h1><p>SUTD Fabrication Lab Assistant</p></header><div class='grid'>"
"<section class='section'><h2>DEVICE</h2><div class='row'><span>Status</span><span id='device'>Loading</span></div><div class='row'><span>Device</span><span>FabAI-01</span></div><div class='row'><span>Firmware</span><span>0.1.0</span></div><div class='row'><span>Uptime</span><span id='uptime'>-</span></div></section>"
"<section class='section'><h2>NETWORK</h2><div class='row'><span>Wi-Fi</span><span id='wifi'>-</span></div><div class='row'><span>SSID</span><span id='ssid'>-</span></div><div class='row'><span>IP</span><span id='ip'>-</span></div><button onclick='scan()'>Scan Wi-Fi</button><div id='networks'></div><label>Network name</label><input id='newssid' autocomplete='off'><label>Password</label><input id='password' type='password' autocomplete='new-password'><button onclick='connect()'>Save and Connect</button> <button class='secondary' onclick='forget()'>Forget Wi-Fi</button></section>"
"<section class='section'><h2>AI BACKEND</h2><div class='row'><span>Status</span><span id='backend'>Offline</span></div><label>Backend URL</label><input id='backendUrl' placeholder='http://192.168.x.x:8000'><button onclick='saveBackend()'>Save Backend</button></section>"
"<section class='section'><h2>HARDWARE</h2><div class='row'><span>RGB LED</span><span>GPIO 38</span></div><div class='row'><span>BOOT Button</span><span id='button'>Released</span></div><button onclick=\"api('/api/led/on')\">LED On</button> <button class='secondary' onclick=\"api('/api/led/off')\">LED Off</button></section></div><section class='section'><button class='secondary' onclick=\"api('/api/restart')\">Restart Device</button> <span class='muted' id='note'></span></section></main>"
"<script>const note=t=>document.querySelector('#note').textContent=t;async function api(u,o={method:'POST'}){let r=await fetch(u,o);note=r.ok?'Saved':'Request failed';setTimeout(refresh,400)}async function refresh(){let s=await fetch('/api/status').then(r=>r.json());let e=id=>document.querySelector(id);e('#device').textContent='Online';e('#device').className='good';e('#uptime').textContent=Math.floor(s.uptime/3600).toString().padStart(2,'0')+':'+Math.floor(s.uptime%3600/60).toString().padStart(2,'0')+':'+(s.uptime%60).toString().padStart(2,'0');e('#wifi').textContent=s.wifi.connected?'Connected':(s.wifi.setup?'Setup mode':'Offline');e('#wifi').className=s.wifi.connected?'good':'bad';e('#ssid').textContent=s.wifi.ssid||'-';e('#ip').textContent=s.wifi.ip||'192.168.4.1';e('#backend').textContent=s.backend.online?'Connected':'Offline';e('#backend').className=s.backend.online?'good':'bad';e('#backendUrl').value=document.activeElement===e('#backendUrl')?e('#backendUrl').value:s.backend.url;e('#button').textContent=s.button?'Pressed':'Released'}async function scan(){note='Scanning...';let n=await fetch('/api/wifi/scan').then(r=>r.json());let box=document.querySelector('#networks');box.innerHTML='';n.networks.forEach(x=>{let b=document.createElement('button');b.textContent=x.ssid+' '+x.rssi+' dBm '+x.security;b.onclick=()=>document.querySelector('#newssid').value=x.ssid;box.appendChild(b)});note='Select a network'}function form(path,values){return api(path,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(values)})}function connect(){form('/api/wifi/connect',{ssid:newssid.value,password:password.value});password.value=''}function forget(){api('/api/wifi/forget')}function saveBackend(){form('/api/backend',{url:backendUrl.value})}refresh();setInterval(refresh,3000)</script></body></html>";

static esp_err_t send_json(httpd_req_t *req, const char *json)
{
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Cache-Control", "no-store");
    return httpd_resp_sendstr(req, json);
}

static esp_err_t root_handler(httpd_req_t *req)
{
    httpd_resp_set_type(req, "text/html");
    return httpd_resp_send(req, PORTAL, HTTPD_RESP_USE_STRLEN);
}

static esp_err_t status_handler(httpd_req_t *req)
{
    wifi_status_t wifi;
    char backend[128];
    char json[512];
    wifi_manager_get_status(&wifi);
    backend_client_get_url(backend, sizeof(backend));
    snprintf(json, sizeof(json), "{\"uptime\":%lu,\"button\":%s,\"wifi\":{\"connected\":%s,\"setup\":%s,\"ssid\":\"%s\",\"ip\":\"%s\",\"rssi\":%d},\"backend\":{\"online\":%s,\"url\":\"%s\"}}",
             device_manager_uptime_seconds(), device_manager_button_pressed() ? "true" : "false",
             wifi.connected ? "true" : "false", wifi.setup_mode ? "true" : "false", wifi.ssid, wifi.ip, wifi.rssi,
             backend_client_is_online() ? "true" : "false", backend);
    return send_json(req, json);
}

static esp_err_t scan_handler(httpd_req_t *req)
{
    wifi_network_t networks[12];
    size_t count = wifi_manager_scan(networks, 12);
    char json[1600] = "{\"networks\":[";
    for (size_t i = 0; i < count; ++i) {
        char entry[128];
        snprintf(entry, sizeof(entry), "%s{\"ssid\":\"%s\",\"rssi\":%d,\"security\":\"%s\"}", i ? "," : "", networks[i].ssid, networks[i].rssi, networks[i].security);
        strlcat(json, entry, sizeof(json));
    }
    strlcat(json, "]}", sizeof(json));
    return send_json(req, json);
}

static bool read_form(httpd_req_t *req, char *body, size_t body_size)
{
    if (req->content_len <= 0 || req->content_len >= body_size) return false;
    int received = httpd_req_recv(req, body, req->content_len);
    if (received <= 0) return false;
    body[received] = '\0';
    return true;
}

static esp_err_t connect_handler(httpd_req_t *req)
{
    char body[180] = {0}, ssid[33] = {0}, password[65] = {0};
    bool ok = read_form(req, body, sizeof(body)) && httpd_query_key_value(body, "ssid", ssid, sizeof(ssid)) == ESP_OK && httpd_query_key_value(body, "password", password, sizeof(password)) == ESP_OK && wifi_manager_connect(ssid, password);
    return send_json(req, ok ? "{\"ok\":true}" : "{\"ok\":false}");
}

static esp_err_t backend_handler(httpd_req_t *req)
{
    char body[180] = {0}, url[128] = {0};
    bool ok = read_form(req, body, sizeof(body)) && httpd_query_key_value(body, "url", url, sizeof(url)) == ESP_OK && backend_client_set_url(url);
    return send_json(req, ok ? "{\"ok\":true}" : "{\"ok\":false}");
}

static esp_err_t action_handler(httpd_req_t *req)
{
    const char *path = req->uri;
    if (strcmp(path, "/api/led/on") == 0) device_manager_set_led(true);
    else if (strcmp(path, "/api/led/off") == 0) device_manager_set_led(false);
    else if (strcmp(path, "/api/wifi/forget") == 0) wifi_manager_forget();
    else if (strcmp(path, "/api/restart") == 0) esp_restart();
    return send_json(req, "{\"ok\":true}");
}

void web_server_start(void)
{
    httpd_handle_t server = NULL;
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.max_uri_handlers = 9;
    ESP_ERROR_CHECK(httpd_start(&server, &config));
    const httpd_uri_t routes[] = {
        {.uri = "/", .method = HTTP_GET, .handler = root_handler},
        {.uri = "/api/status", .method = HTTP_GET, .handler = status_handler},
        {.uri = "/api/wifi/scan", .method = HTTP_GET, .handler = scan_handler},
        {.uri = "/api/wifi/connect", .method = HTTP_POST, .handler = connect_handler},
        {.uri = "/api/backend", .method = HTTP_POST, .handler = backend_handler},
        {.uri = "/api/wifi/forget", .method = HTTP_POST, .handler = action_handler},
        {.uri = "/api/led/on", .method = HTTP_POST, .handler = action_handler},
        {.uri = "/api/led/off", .method = HTTP_POST, .handler = action_handler},
        {.uri = "/api/restart", .method = HTTP_POST, .handler = action_handler},
    };
    for (size_t i = 0; i < sizeof(routes) / sizeof(routes[0]); ++i) ESP_ERROR_CHECK(httpd_register_uri_handler(server, &routes[i]));
}
