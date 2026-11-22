/*
 * ============================================================================
 * VenueGuard Smart Crowd Management System - IoT NodeMCU ESP8266 Firmware
 * Component: Ultrasonic Turnstile Counter & Real-Time Telemetry Monitor
 * ============================================================================
 * Hardware Bill of Materials:
 *  - ESP8266 NodeMCU V2/V3 (CP2102 or CH340)
 *  - HC-SR04 Ultrasonic Distance Sensor (or HC-SR04P 3.3V compatible)
 *  - 1k Ohm & 2k Ohm Resistors (Voltage divider for 5V HC-SR04 Echo to 3.3V D6)
 *  - Active Buzzer (5V / 3.3V)
 *  - RGB LED (Common Cathode) or 3x Discrete LEDs (Green, Yellow, Red)
 *  - 3x 220 Ohm Resistors for LEDs
 *  - Breadboard & Jumper Wires
 * 
 * Pin Mapping:
 *  - D5 (GPIO 14) -> HC-SR04 TRIG Pin
 *  - D6 (GPIO 12) -> HC-SR04 ECHO Pin (via voltage divider)
 *  - D1 (GPIO 5)  -> Green Status LED (Normal entry)
 *  - D2 (GPIO 4)  -> Red Status LED / Warning LED
 *  - D8 (GPIO 15) -> Active Piezo Buzzer (Emergency & High Alert)
 * ============================================================================
 */

#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>

// --- Network & Server Credentials ---
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Backend API Endpoint & Secret
const char* SERVER_URL    = "http://192.168.1.100:5000/api/hardware/telemetry";
const char* DEVICE_KEY    = "vg-device-secure-key-2026"; // Matches HARDWARE_DEVICE_KEY
const char* GATE_ID       = "main_gate";                 // Designated gate identity

// --- Pin Definitions ---
const int PIN_TRIG   = 14; // D5
const int PIN_ECHO   = 12; // D6
const int PIN_LED_G  = 5;  // D1
const int PIN_LED_R  = 4;  // D2
const int PIN_BUZZER = 15; // D8

// --- Detection Parameters ---
const int DETECTION_THRESHOLD_CM = 75; // Trigger when visitor passes within 75cm
const unsigned long DEBOUNCE_MS  = 1200; // Minimum interval between headcount events

// --- State Variables ---
unsigned long lastTriggerTime = 0;
bool isEmergency = false;
int currentOccupancy = 0;

long measureDistanceCm() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);

  long duration = pulseIn(PIN_ECHO, HIGH, 30000); // 30ms timeout (~5m max)
  if (duration == 0) return 999; // Out of range / timeout
  return duration * 0.034 / 2;
}

void triggerLocalBeep(int count, int durationMs) {
  for (int i = 0; i < count; i++) {
    digitalWrite(PIN_BUZZER, HIGH);
    delay(durationMs);
    digitalWrite(PIN_BUZZER, LOW);
    if (i < count - 1) delay(durationMs);
  }
}

void sendTelemetry(const char* actionType, int delta) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WIFI] Disconnected! Cannot send telemetry.");
    return;
  }

  WiFiClient client;
  HTTPClient http;

  Serial.printf("[HTTP] Connecting to %s ...\n", SERVER_URL);
  if (http.begin(client, SERVER_URL)) {
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-Device-Key", DEVICE_KEY);

    // Build JSON payload
    StaticJsonDocument<200> doc;
    doc["gate_id"] = GATE_ID;
    doc["action_type"] = actionType;
    doc["count_delta"] = delta;

    String requestBody;
    serializeJson(doc, requestBody);

    int httpCode = http.POST(requestBody);

    if (httpCode == HTTP_CODE_OK || httpCode == 201) {
      String response = http.getString();
      Serial.printf("[HTTP] Response: %s\n", response.c_str());

      StaticJsonDocument<300> resDoc;
      DeserializationError error = deserializeJson(resDoc, response);

      if (!error) {
        isEmergency = resDoc["emergency"] | false;
        currentOccupancy = resDoc["current_occupancy"] | 0;
        const char* status = resDoc["status"] | "NORMAL";

        // Handle Alert Statuses
        if (isEmergency) {
          Serial.println("[CRITICAL] EMERGENCY BROADCAST RECEIVED!");
          digitalWrite(PIN_LED_R, HIGH);
          digitalWrite(PIN_LED_G, LOW);
          triggerLocalBeep(3, 200);
        } else if (strcmp(status, "FULL") == 0 || strcmp(status, "HIGH") == 0) {
          digitalWrite(PIN_LED_R, HIGH);
          digitalWrite(PIN_LED_G, LOW);
        } else {
          digitalWrite(PIN_LED_R, LOW);
          digitalWrite(PIN_LED_G, HIGH);
        }
      }
    } else {
      Serial.printf("[HTTP] Failed, error code: %d\n", httpCode);
    }
    http.end();
  } else {
    Serial.println("[HTTP] Unable to connect to host");
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n--- VenueGuard IoT Smart Turnstile Initializing ---");

  // Configure GPIOs
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  pinMode(PIN_LED_G, OUTPUT);
  pinMode(PIN_LED_R, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);

  digitalWrite(PIN_TRIG, LOW);
  digitalWrite(PIN_LED_G, LOW);
  digitalWrite(PIN_LED_R, LOW);
  digitalWrite(PIN_BUZZER, LOW);

  // Self-test beep
  triggerLocalBeep(1, 100);

  // Connect to Wi-Fi
  Serial.printf("Connecting to Wi-Fi SSID: %s\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 25) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WIFI] Connected successfully!");
    Serial.print("[WIFI] Node IP Address: ");
    Serial.println(WiFi.localIP());
    digitalWrite(PIN_LED_G, HIGH);
  } else {
    Serial.println("\n[WIFI] Failed to connect. Running in offline fallback mode.");
    digitalWrite(PIN_LED_R, HIGH);
  }
}

void loop() {
  unsigned long now = millis();

  // Continuous distance detection
  long distance = measureDistanceCm();

  if (distance > 0 && distance <= DETECTION_THRESHOLD_CM) {
    if (now - lastTriggerTime > DEBOUNCE_MS) {
      lastTriggerTime = now;
      Serial.printf("[SENSOR] Visitor entry detected at %ld cm\n", distance);

      // Local visual & auditory feedback
      digitalWrite(PIN_LED_G, LOW);
      digitalWrite(PIN_BUZZER, HIGH);
      delay(40);
      digitalWrite(PIN_BUZZER, LOW);
      digitalWrite(PIN_LED_G, HIGH);

      // Transmit Entry Event to VenueGuard Central Backend
      sendTelemetry("entry", 1);
    }
  }

  delay(60); // 16 Hz sampling rate
}

