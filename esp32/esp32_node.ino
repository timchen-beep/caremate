// 作用：ESP32 传感器节点：读 LD2410C 雷达并上报 presence，收告警按语义表点灯/蜂鸣（不含业务判断）
/*
 * CareMate · ESP32 传感器节点（雷达 LD2410C + 灯/蜂鸣器）
 *
 * 分工：ESP32 只做「读传感器 → 发 MQTT」和「收 MQTT → 点灯」，不含任何业务判断。
 *      所有判断在服务端；ESP32 掉线不影响提醒。
 *
 * 接线（ESP32-S3 / ESP32 DevKit 均可）
 *   LD2410C  TX → GPIO16 (RX2)      LD2410C  RX → GPIO17 (TX2)      VCC 5V, GND 共地
 *   LED 正极 → GPIO4（串 220Ω）     蜂鸣器 → GPIO5（有源蜂鸣器，3.3V）
 *
 * 依赖库（Arduino IDE）：PubSubClient、ArduinoJson
 * 配置：改下面的 WIFI_SSID / WIFI_PASS / MQTT_HOST（树莓派或香橙派的局域网 IP）
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ---------------- 要改的四个值
const char* WIFI_SSID = "你的WiFi";
const char* WIFI_PASS = "你的密码";
const char* MQTT_HOST = "192.168.1.50";   // 树莓派 / 香橙派
const int   MQTT_PORT = 1883;
const char* ELDER_ID  = "u-elder";

// ---------------- 引脚
const int PIN_RADAR_RX = 16;
const int PIN_RADAR_TX = 17;
const int PIN_LED      = 4;
const int PIN_BUZZER   = 5;

WiFiClient net;
PubSubClient mqtt(net);
unsigned long lastPresence = 0;
bool lastState = false;

const char* TOPIC_PRESENCE = "home/sensor/presence";
char topicAlarm[64];
char topicReminder[64];

// 灯语义表（与报告 R4-4 一致）：绿=已完成 黄=待确认 红=未确认 蓝闪=呼救
void setLed(int r, int g, int b) {
  // 单色 LED 时只按亮度区分；三色 LED 用 RGB 值
  analogWrite(PIN_LED, (r + g + b) / 3);
}

void onMessage(char* topic, byte* payload, unsigned int len) {
  StaticJsonDocument<512> doc;
  if (deserializeJson(doc, payload, len)) return;
  const char* kind = doc["kind"] | "";
  if (strstr(topic, "/alarm/")) {
    if (strcmp(kind, "sos") == 0) {                 // 呼救：红灯 + 长鸣
      setLed(255, 0, 0);
      digitalWrite(PIN_BUZZER, HIGH); delay(1500); digitalWrite(PIN_BUZZER, LOW);
    } else {                                        // 其它告警：黄灯短鸣
      setLed(255, 180, 0);
      digitalWrite(PIN_BUZZER, HIGH); delay(200); digitalWrite(PIN_BUZZER, LOW);
    }
    return;
  }
  if (strstr(topic, "/reminder/")) {
    const char* state = doc["state"] | "";
    if (strcmp(state, "confirmed") == 0)      setLed(0, 255, 0);
    else if (strcmp(state, "notified") == 0)  setLed(255, 180, 0);
    else if (strcmp(state, "missed") == 0)    setLed(255, 0, 0);
  }
}

void reconnect() {
  while (!mqtt.connected()) {
    String cid = String("esp32-") + ELDER_ID;
    if (mqtt.connect(cid.c_str())) {
      mqtt.subscribe(topicAlarm);
      mqtt.subscribe(topicReminder);
      Serial.println("[mqtt] 已连上并订阅");
    } else {
      delay(2000);
    }
  }
}

void publishPresence(bool present) {
  StaticJsonDocument<192> doc;
  doc["elder_id"] = ELDER_ID;
  doc["present"] = present;
  doc["source"] = "ld2410c";
  doc["ts"] = millis();
  char buf[192];
  serializeJson(doc, buf, sizeof(buf));
  mqtt.publish(TOPIC_PRESENCE, buf);
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  Serial2.begin(256000, SERIAL_8N1, PIN_RADAR_RX, PIN_RADAR_TX);  // LD2410C 默认 256000

  snprintf(topicAlarm, sizeof(topicAlarm), "home/alarm/%s", ELDER_ID);
  snprintf(topicReminder, sizeof(topicReminder), "home/reminder/%s/state", ELDER_ID);

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.printf("\n[wifi] %s\n", WiFi.localIP().toString().c_str());

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMessage);
  mqtt.setBufferSize(512);
}

void loop() {
  if (!mqtt.connected()) reconnect();
  mqtt.loop();

  // LD2410C：有字节就认为有人（完整帧解析见官方协议；演示用「有数据=有人」足够）
  bool present = Serial2.available() > 0;
  while (Serial2.available()) Serial2.read();

  // 状态变化才发，避免刷屏；另外每 60 秒发一次心跳
  unsigned long now = millis();
  if (present != lastState || now - lastPresence > 60000) {
    publishPresence(present);
    lastState = present;
    lastPresence = now;
    Serial.printf("[radar] %s\n", present ? "有人" : "没人");
  }
  delay(200);
}
