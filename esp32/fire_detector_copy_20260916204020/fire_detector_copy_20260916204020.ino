#include "esp_camera.h"
#include <DHT.h>
#include <PubSubClient.h>
#include <WebServer.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include "soc/soc.h"           // สำหรับแก้ปัญหา Brownout detector triggered
#include "soc/rtc_cntl_reg.h"  // สำหรับแก้ปัญหา Brownout detector triggered

// =====================================================
// WIFI CONFIGURATION (HOME WIFI)
// =====================================================

const char *WIFI_SSID = "CS";
const char *WIFI_PASSWORD = "CS888888";

// =====================================================
// SERVER CONFIG (HTTP API & MQTT)
// =====================================================

const char *SERVER_HOST = "192.168.1.135";
const int HTTP_PORT = 5001;
const char *HTTP_API_URL = "http://172.20.10.2:5001/api/sensor";

const char *MQTT_SERVER = "192.168.1.135";
const int MQTT_PORT = 1883;
const char *MQTT_TOPIC = "firemonitor/sensor";

WiFiClient espClient;
PubSubClient mqttClient(espClient);

// =====================================================
// ROOM
// =====================================================

const char *ROOM_NAME = "warehouse";

// =====================================================
// DHT11
// =====================================================

#define DHT_PIN 13
#define DHT_TYPE DHT11

DHT dht(DHT_PIN, DHT_TYPE);

// =====================================================
// MQ DIGITAL OUTPUT
// =====================================================

#define MQ_PIN 14

// MQ DO ส่วนใหญ่เป็น Active LOW
// LOW  = ตรวจพบก๊าซ
// HIGH = ปกติ

#define MQ_GAS_STATE LOW

#define MQ_WARMUP_TIME 30000

unsigned long mqStartTime = 0;

// =====================================================
// TEMPERATURE
// =====================================================

#define TEMP_TRIGGER 29.5

// =====================================================
// CAMERA - AI THINKER ESP32-CAM
// =====================================================

#define PWDN_GPIO_NUM 32
#define RESET_GPIO_NUM -1

#define XCLK_GPIO_NUM 0
#define SIOD_GPIO_NUM 26
#define SIOC_GPIO_NUM 27

#define Y9_GPIO_NUM 35
#define Y8_GPIO_NUM 34
#define Y7_GPIO_NUM 39
#define Y6_GPIO_NUM 36
#define Y5_GPIO_NUM 21
#define Y4_GPIO_NUM 19
#define Y3_GPIO_NUM 18
#define Y2_GPIO_NUM 5

#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM 23
#define PCLK_GPIO_NUM 22

// =====================================================
// WEB SERVER
// =====================================================

WebServer server(80);

// =====================================================
// CAMERA STATE
// =====================================================

bool cameraOK = false;
bool cameraEnabled = false;
bool streamEnabled = false;
bool cameraTrigger = false;

// =====================================================
// SENSOR STATE
// =====================================================

float temperature = 0.0;
float humidity = 0.0;

// สำหรับ DO จะมีเพียง 0 / 1
int gasRaw = HIGH;

float gasPercent = 0.0;

bool gasDetected = false;

float risk = 0.0;

bool abnormalCondition = false;
bool previousAbnormalCondition = false;

// =====================================================
// TIMER
// =====================================================

unsigned long lastSensorRead = 0;
unsigned long lastMQTT = 0;

const unsigned long SENSOR_INTERVAL = 2000;
const unsigned long MQTT_INTERVAL = 1000;

// =====================================================
// CAMERA ACTIVE CHECK
// =====================================================

bool isCameraActiveRequired() { return abnormalCondition || cameraEnabled; }

// =====================================================
// READ MQ DIGITAL
// =====================================================

int readMQ() { return digitalRead(MQ_PIN); }

// =====================================================
// MQ WARMUP
// =====================================================

bool mqWarmingUp() { return (millis() - mqStartTime) < MQ_WARMUP_TIME; }

// =====================================================
// CONNECT WIFI
// =====================================================

void connectWiFi() {

  Serial.println();
  Serial.println("================================");
  Serial.println("Connecting WiFi...");
  Serial.println("================================");

  WiFi.mode(WIFI_OFF);
  delay(100);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.setSleep(false); // Disables Modem Sleep to prevent WebServer latency spikes and connection drops
  WiFi.setTxPower(WIFI_POWER_15dBm); // 15dBm reduces current spikes on FTDI / weak 5V power sources
  delay(300);

  Serial.print("[INFO] Connecting to WiFi SSID: ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int retry = 0;
  int wifiAttempts = 1;

  while (WiFi.status() != WL_CONNECTED) {

    delay(500);
    Serial.print(".");
    retry++;

    if (retry > 40) { // Retry begin after 20 seconds
      Serial.println();
      wl_status_t status = WiFi.status();
      Serial.print("[WARN] WiFi status code: ");
      Serial.print(status);
      if (status == WL_NO_SSID_AVAIL) {
        Serial.println(" (SSID not found - check 2.4GHz network)");
      } else if (status == WL_CONNECT_FAILED) {
        Serial.println(" (Connect failed - check password)");
      } else if (status == WL_DISCONNECTED) {
        Serial.println(" (Disconnected)");
      } else {
        Serial.println();
      }

      if (wifiAttempts < 3) {
        wifiAttempts++;
        Serial.printf("[RETRY] Re-attempting WiFi.begin (%d/3)...\n", wifiAttempts);
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
        retry = 0;
      } else {
        Serial.println("[ERROR] WiFi connection failed after 3 attempts. Restarting ESP32...");
        delay(1000);
        ESP.restart();
      }
    }
  }

  Serial.println();
  Serial.println("[OK] WiFi Connected!");

  Serial.print("ESP32-CAM IP: ");
  Serial.println(WiFi.localIP());

  Serial.print("Stream: http://");
  Serial.print(WiFi.localIP());
  Serial.println("/stream");
}

// =====================================================
// CAMERA INIT
// =====================================================

void initCamera() {

  if (cameraOK) {
    return;
  }

  Serial.println();
  Serial.println("================================");
  Serial.println("Initializing Camera...");
  Serial.println("================================");

  camera_config_t config;

  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;

  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;

  config.pin_xclk = XCLK_GPIO_NUM;

  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;

  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;

  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;

  config.xclk_freq_hz = 20000000;

  config.pixel_format = PIXFORMAT_JPEG;

#if defined(CAMERA_GRAB_LATEST)
  config.grab_mode = CAMERA_GRAB_LATEST;
#endif

  if (psramFound()) {
    Serial.println("[OK] PSRAM detected");
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 12;
    config.fb_count = 2;
    config.fb_location = CAMERA_FB_IN_PSRAM;
  } else {
    Serial.println("[WARN] PSRAM not detected");
    config.frame_size = FRAMESIZE_CIF;
    config.jpeg_quality = 14;
    config.fb_count = 1;
    config.fb_location = CAMERA_FB_IN_DRAM;
  }

  esp_err_t err = esp_camera_init(&config);

  if (err != ESP_OK) {

    Serial.print("[ERROR] Camera init failed: 0x");
    Serial.println(err, HEX);

    cameraOK = false;

    return;
  }

  cameraOK = true;

  sensor_t *sensor = esp_camera_sensor_get();

  if (sensor != nullptr) {
    if (psramFound()) {
      sensor->set_framesize(sensor, FRAMESIZE_VGA);
    } else {
      sensor->set_framesize(sensor, FRAMESIZE_CIF);
    }
  }

  Serial.println("[OK] Camera initialized");
}

// =====================================================
// CAMERA DEINIT (Turn OFF Camera)
// =====================================================

void deinitCamera() {

  if (!cameraOK) {
    return;
  }

  Serial.println();
  Serial.println("================================");
  Serial.println("Deinitializing Camera...");
  Serial.println("================================");

  esp_err_t err = esp_camera_deinit();

  if (err == ESP_OK) {
    Serial.println("[OK] Camera deinitialized (Powered OFF)");
  } else {
    Serial.print("[WARN] Camera deinit warning: 0x");
    Serial.println(err, HEX);
  }

  cameraOK = false;
  cameraEnabled = false;
  streamEnabled = false;
}

// =====================================================
// READ SENSORS
// =====================================================

void readSensors() {

  // =================================================
  // DHT11
  // =================================================

  float newTemperature = dht.readTemperature();

  float newHumidity = dht.readHumidity();

  if (!isnan(newTemperature)) {

    temperature = newTemperature;

  } else {

    Serial.println("[ERROR] DHT11 temperature read failed");
  }

  if (!isnan(newHumidity)) {

    humidity = newHumidity;

  } else {

    Serial.println("[ERROR] DHT11 humidity read failed");
  }

  // =================================================
  // MQ DO
  // =================================================

  gasRaw = readMQ();

  // DO ไม่มีค่า 0-4095
  // มีแค่ LOW / HIGH

  if (gasRaw == LOW) {

    gasPercent = 100.0;

  } else {

    gasPercent = 0.0;
  }

  // =================================================
  // MQ WARMUP
  // =================================================

  if (mqWarmingUp()) {

    gasDetected = false;

  } else {

    gasDetected = (gasRaw == MQ_GAS_STATE);
  }

  // =================================================
  // RISK
  // =================================================

  risk = 0.0;

  if (temperature < 29.5) {

    risk = 0;

  } else if (temperature < 31.0) {

    risk = 20;

  } else if (temperature < 32.0) {

    risk = 30;

  } else if (temperature < 33.0) {

    risk = 40;

  } else if (temperature < 34.0) {

    risk = 50;

  } else {

    risk = 60;
  }

  // =================================================
  // GAS RISK
  // =================================================

  if (gasDetected) {

    risk += 40;
  }

  if (risk > 100) {

    risk = 100;
  }

  // =================================================
  // ABNORMAL
  // =================================================

  abnormalCondition = (temperature >= TEMP_TRIGGER) || gasDetected;

  // =================================================
  // CAMERA TRIGGER
  // =================================================

  if (abnormalCondition && !previousAbnormalCondition) {

    cameraTrigger = true;

    Serial.println();
    Serial.println("================================");

    Serial.println("[ALERT] ABNORMAL CONDITION");

    Serial.println("[ALERT] CAMERA TRIGGERED");

    Serial.println("================================");
  }

  // =================================================
  // CAMERA LAZY INIT / IMMEDIATE DEINIT BASED ON SENSORS
  // =================================================

  if (abnormalCondition) {

    if (!cameraOK) {

      Serial.println();
      Serial.println("[ALERT] Sensor Anomaly Detected! Initializing Camera...");

      initCamera();
    }

    cameraEnabled = cameraOK;

  } else {

    if (cameraOK && !streamEnabled) {

      Serial.println();
      Serial.println(
          "[OK] Conditions Normal. Immediately Deinitializing Camera...");

      deinitCamera();
    }

    cameraEnabled = false;
    cameraTrigger = false;
  }

  previousAbnormalCondition = abnormalCondition;

  // =================================================
  // SERIAL
  // =================================================

  Serial.println();
  Serial.println("========== SENSOR ==========");

  Serial.print("Temperature: ");

  Serial.print(temperature, 2);

  Serial.println(" C");

  Serial.print("Humidity: ");

  Serial.print(humidity, 2);

  Serial.println(" %");

  Serial.print("MQ DO: ");

  Serial.println(gasRaw == LOW ? "LOW" : "HIGH");

  Serial.print("Gas: ");

  Serial.print(gasPercent, 0);

  Serial.println(" %");

  Serial.print("Gas Detected: ");

  Serial.println(gasDetected ? "YES" : "NO");

  Serial.print("Risk: ");

  Serial.print(risk, 2);

  Serial.println(" %");

  Serial.print("Camera: ");

  Serial.println(cameraEnabled ? "ON" : "OFF");

  Serial.print("Abnormal: ");

  Serial.println(abnormalCondition ? "YES" : "NO");

  Serial.println("============================");
}

// =====================================================
// MQTT CONNECT
// =====================================================

unsigned long lastMQTTRetry = 0;
const unsigned long MQTT_RETRY_INTERVAL = 5000;

void reconnectMQTT() {
  if (mqttClient.connected()) {
    return;
  }

  unsigned long now = millis();
  if (now - lastMQTTRetry < MQTT_RETRY_INTERVAL) {
    return; // Prevent blocking stream thread with frequent reconnect attempts
  }
  lastMQTTRetry = now;

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WARNING] WiFi not connected. Attempting WiFi reconnect...");
    connectWiFi();
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("[ERROR] WiFi connection failed. Skipping MQTT connect.");
      return;
    }
  }

  Serial.println();
  Serial.print("Connecting MQTT to ");
  Serial.print(MQTT_SERVER);
  Serial.print(":");
  Serial.println(MQTT_PORT);

  String clientID = "ESP32-CAM-" + String((uint32_t)ESP.getEfuseMac(), HEX);

  if (mqttClient.connect(clientID.c_str())) {
    Serial.println("[OK] MQTT Connected");
  } else {
    int state = mqttClient.state();
    Serial.print("[ERROR] MQTT failed, rc=");
    Serial.print(state);
    if (state == -2) {
      Serial.println(" (MQTT_CONNECT_FAILED: Cannot reach MQTT Broker IP/Port)");
    } else if (state == -4) {
      Serial.println(" (MQTT_CONNECTION_TIMEOUT)");
    } else if (state == 5) {
      Serial.println(" (MQTT_CONNECT_UNAUTHORIZED)");
    } else {
      Serial.println();
    }
  }
}

// =====================================================
// PUBLISH SENSOR DATA (HTTP POST & MQTT)
// =====================================================

void sendHTTPData(const String &payload) {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(HTTP_API_URL);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(3000);

    int httpCode = http.POST(payload);
    if (httpCode > 0) {
      Serial.printf("[OK] HTTP POST sent to Server (Code %d)\n", httpCode);
    } else {
      Serial.printf("[WARN] HTTP POST failed: %s\n", http.errorToString(httpCode).c_str());
    }
    http.end();
  }
}

void publishSensorData() {

  String payload = "{";

  payload += "\"room\":\"";
  payload += ROOM_NAME;
  payload += "\",";

  payload += "\"ip\":\"";
  payload += WiFi.localIP().toString();
  payload += "\",";

  payload += "\"temperature\":";
  payload += String(temperature, 2);

  payload += ",";

  payload += "\"humidity\":";
  payload += String(humidity, 2);

  payload += ",";

  payload += "\"gasRaw\":";
  payload += String(gasRaw);

  payload += ",";

  payload += "\"gas\":";
  payload += String(gasPercent, 2);

  payload += ",";

  payload += "\"gasDetected\":";
  payload += gasDetected ? "true" : "false";

  payload += ",";

  payload += "\"risk\":";
  payload += String(risk, 2);

  payload += ",";

  payload += "\"camera\":";
  payload += cameraEnabled ? "true" : "false";

  payload += ",";

  payload += "\"cameraTrigger\":";
  payload += cameraTrigger ? "true" : "false";

  payload += ",";

  payload += "\"abnormal\":";
  payload += abnormalCondition ? "true" : "false";

  payload += "}";

  // 1. Send via HTTP POST directly to Dashboard Backend (only when not streaming to avoid network stall)
  if (!streamEnabled) {
    sendHTTPData(payload);
  }

  // 2. Send via MQTT if connected
  if (mqttClient.connected()) {
    mqttClient.publish(MQTT_TOPIC, payload.c_str());
  }

  Serial.println("Published Payload:");
  Serial.println(payload);

  cameraTrigger = false;
}

// =====================================================
// CAMERA STATUS
// =====================================================

void handleCameraStatus() {

  String json = "{";

  json += "\"cameraOK\":";
  json += cameraOK ? "true" : "false";

  json += ",";

  json += "\"cameraEnabled\":";
  json += cameraEnabled ? "true" : "false";

  json += ",";

  json += "\"streamEnabled\":";
  json += streamEnabled ? "true" : "false";

  json += ",";

  json += "\"temperature\":";
  json += String(temperature, 2);

  json += ",";

  json += "\"humidity\":";
  json += String(humidity, 2);

  json += ",";

  json += "\"gasRaw\":";
  json += String(gasRaw);

  json += ",";

  json += "\"gas\":";
  json += String(gasPercent, 2);

  json += ",";

  json += "\"gasDetected\":";
  json += gasDetected ? "true" : "false";

  json += ",";

  json += "\"risk\":";
  json += String(risk, 2);

  json += ",";

  json += "\"abnormal\":";
  json += abnormalCondition ? "true" : "false";

  json += "}";

  server.send(200, "application/json", json);
}

// =====================================================
// CAMERA ON
// =====================================================

void handleCameraOn() {

  if (!cameraOK) {
    initCamera();
  }

  cameraEnabled = cameraOK;

  server.send(200, "text/plain", cameraOK ? "Camera ON" : "Camera Init Failed");
}

// =====================================================
// CAMERA OFF
// =====================================================

void handleCameraOff() {

  deinitCamera();

  server.send(200, "text/plain", "Camera OFF");
}

// =====================================================
// STREAM
// =====================================================

void handleStream() {

  if (!isCameraActiveRequired()) {

    server.send(403, "text/plain", "Camera stream disabled - condition normal");

    return;
  }

  if (!cameraOK) {
    initCamera();
  }

  if (!cameraOK) {

    server.send(500, "text/plain", "Camera not available");

    return;
  }

  WiFiClient client = server.client();

  if (!client) {

    return;
  }

  streamEnabled = true;
  cameraEnabled = true;

  Serial.println();

  Serial.println("================================");

  Serial.println("STREAM STARTED");

  Serial.println("================================");

  client.print("HTTP/1.1 200 OK\r\n"
               "Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
               "Cache-Control: no-cache\r\n"
               "Pragma: no-cache\r\n"
               "Access-Control-Allow-Origin: *\r\n"
               "Connection: close\r\n"
               "\r\n");

  while (client.connected() && isCameraActiveRequired()) {

    // =================================================
    // MQTT
    // =================================================

    if (!mqttClient.connected()) {

      reconnectMQTT();
    }

    mqttClient.loop();

    // =================================================
    // SENSOR
    // =================================================

    unsigned long now = millis();

    if (now - lastSensorRead >= SENSOR_INTERVAL) {

      lastSensorRead = now;

      readSensors();
    }

    // =================================================
    // MQTT PUBLISH
    // =================================================

    if (now - lastMQTT >= MQTT_INTERVAL) {

      lastMQTT = now;

      publishSensorData();
    }

    // =================================================
    // CAMERA
    // =================================================

    camera_fb_t *fb = esp_camera_fb_get();

    if (!fb) {
      Serial.println("[ERROR] Camera capture failed");
      delay(10);
      continue;
    }

    client.print("--frame\r\n"
                 "Content-Type: image/jpeg\r\n"
                 "Content-Length: ");

    client.print(fb->len);

    client.print("\r\n\r\n");

    client.write(fb->buf, fb->len);

    client.print("\r\n");

    esp_camera_fb_return(fb);

    if (!client.connected()) {
      Serial.println("[INFO] Stream client disconnected");
      break;
    }

    delay(1);
  }

  streamEnabled = false;

  if (!abnormalCondition) {

    if (cameraOK) {
      deinitCamera();
    }

    Serial.println("[OK] Condition normal - camera deinitialized immediately");
  }

  Serial.println("STREAM ENDED");
}

// =====================================================
// ROOT
// =====================================================

void handleRoot() {

  String html = "";

  html += "<!DOCTYPE html>";
  html += "<html>";
  html += "<head>";

  html += "<meta charset='UTF-8'>";

  html += "<meta name='viewport' ";
  html += "content='width=device-width,initial-scale=1'>";

  html += "<title>AI Fire Detector</title>";

  html += "</head>";

  html += "<body>";

  html += "<h1>AI Fire Detector</h1>";

  html += "<hr>";

  html += "<h2>Sensor</h2>";

  html += "<p>Temperature: ";
  html += String(temperature, 2);

  html += " °C</p>";

  html += "<p>Humidity: ";
  html += String(humidity, 2);

  html += " %</p>";

  html += "<p>MQ DO: ";

  html += gasRaw == LOW ? "LOW" : "HIGH";

  html += "</p>";

  html += "<p>Gas Detected: ";

  html += gasDetected ? "YES" : "NO";

  html += "</p>";

  html += "<p>Risk: ";

  html += String(risk, 2);

  html += " %</p>";

  html += "<p>Abnormal: ";

  html += abnormalCondition ? "YES" : "NO";

  html += "</p>";

  html += "<hr>";

  html += "<h2>Camera</h2>";

  if (cameraOK && abnormalCondition) {

    html += "<img src='/stream' ";
    html += "style='width:100%;max-width:640px;'>";

  } else {

    html += "<p>Camera in <b>STANDBY</b> (Waiting for MQ sensor or DHT11 "
            "anomaly detection).</p>";
  }

  html += "</body>";
  html += "</html>";

  server.send(200, "text/html", html);
}

// =====================================================
// WEB SERVER
// =====================================================

void startWebServer() {

  server.on("/", HTTP_GET, handleRoot);

  server.on("/camera/status", HTTP_GET, handleCameraStatus);

  server.on("/camera/on", HTTP_GET, handleCameraOn);

  server.on("/camera/off", HTTP_GET, handleCameraOff);

  server.on("/stream", HTTP_GET, handleStream);

  server.begin();

  Serial.println("🌐 WebServer started");
}

// =====================================================
// SENSOR + MQTT BACKGROUND
// =====================================================

void processSensorsAndMQTT() {

  if (!mqttClient.connected()) {

    reconnectMQTT();
  }

  mqttClient.loop();

  unsigned long now = millis();

  if (now - lastSensorRead >= SENSOR_INTERVAL) {

    lastSensorRead = now;

    readSensors();
  }

  if (now - lastMQTT >= MQTT_INTERVAL) {

    lastMQTT = now;

    publishSensorData();
  }
}

// =====================================================
// SETUP
// =====================================================

void setup() {

  // ปิดการทำงานของ Brownout detector ป้องกัน ESP32 รีสตาร์ทเนื่องจากแรงดันไฟตกชั่วขณะช่วงเปิด WiFi
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  Serial.begin(115200);

  delay(1000);

  Serial.println();
  Serial.println();

  Serial.println("======================================");

  Serial.println("🔥 AI FIRE DETECTOR - ESP32-CAM");

  Serial.println("======================================");

  // =================================================
  // DHT
  // =================================================

  dht.begin();

  Serial.println("[OK] DHT11 initialized");

  // =================================================
  // MQ DO
  // =================================================

  pinMode(MQ_PIN, INPUT);

  mqStartTime = millis();

  Serial.println("[OK] MQ DO initialized");

  Serial.println("MQ DO GPIO: 14");

  Serial.println("DO LOW = Gas detected");

  Serial.println("MQ warmup: 30 seconds");

  // =================================================
  // WIFI
  // =================================================

  connectWiFi();

  // =================================================
  // MQTT
  // =================================================

  mqttClient.setBufferSize(512); // Essential for large JSON payloads
  mqttClient.setKeepAlive(15);
  mqttClient.setSocketTimeout(3);
  mqttClient.setServer(MQTT_SERVER, MQTT_PORT);

  reconnectMQTT();

  // =================================================
  // CAMERA (LAZY INIT - Standby until MQ / DHT11 triggers)
  // =================================================

  Serial.println("Camera in STANDBY (Will initialize only when MQ or DHT11 "
                 "detects anomaly)");

  // =================================================
  // SENSOR INITIAL READ
  // =================================================

  readSensors();

  // =================================================
  // INITIAL MQTT
  // =================================================

  publishSensorData();

  // =================================================
  // WEB SERVER
  // =================================================

  startWebServer();

  Serial.println();

  Serial.println("======================================");

  Serial.print("ESP32-CAM: http://");

  Serial.println(WiFi.localIP());

  Serial.print("Stream: http://");

  Serial.print(WiFi.localIP());

  Serial.println("/stream");

  Serial.println("MQTT Topic: firemonitor/sensor");

  Serial.println("======================================");
}

// =====================================================
// LOOP
// =====================================================

void loop() {

  server.handleClient();

  processSensorsAndMQTT();

  delay(5);
}