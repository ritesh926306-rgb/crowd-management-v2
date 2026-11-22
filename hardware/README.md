# VenueGuard IoT Hardware Integration Guide
## ESP8266 Ultrasonic Crowd Monitor & Turnstile Telemetry

This hardware module provides automated real-time headcount telemetry for VenueGuard access gates and entry turnstiles.

---

### 1. Bill of Materials (BOM)

| Component | Quantity | Purpose |
| :--- | :--- | :--- |
| **NodeMCU ESP8266** (V2 or V3) | 1 | Microcontroller with Wi-Fi stack |
| **HC-SR04** Ultrasonic Sensor | 1 | Contactless distance sensing |
| **Active 5V Piezo Buzzer** | 1 | Entry confirmation & emergency audio alarm |
| **Green 5mm LED** | 1 | Normal / operational status indicator |
| **Red 5mm LED** | 1 | Warning / Capacity full / Emergency indicator |
| **Resistor 1kΩ** | 1 | Voltage divider upper leg (HC-SR04 Echo) |
| **Resistor 2kΩ** | 1 | Voltage divider lower leg (HC-SR04 Echo) |
| **Resistors 220Ω** | 2 | Current limiters for LEDs |
| **Micro-USB Cable & Breadboard**| 1 set | Power & prototyping interconnect |

---

### 2. Pin-to-Pin Wiring Diagram

```
 NodeMCU ESP8266              HC-SR04 / Peripherals
+-----------------+          +-----------------------+
|             VIN | -------- | VCC (5V Power)        |
|             GND | -------- | GND                   |
|        D5 (GPIO14) -------- | TRIG                  |
|        D6 (GPIO12) <--+--- | ECHO (via divider)    |
|                 |     |    +-----------------------+
|                 |    [1kΩ]
|                 |     |
|                 |     +--- ECHO Sensor Output (5V)
|                 |     |
|                 |    [2kΩ]
|                 |     |
|             GND | <---+
|                 |
|         D1 (GPIO5) --- [220Ω] ---> (Anode) Green LED (Cathode) ---> GND
|         D2 (GPIO4) --- [220Ω] ---> (Anode) Red LED   (Cathode) ---> GND
|        D8 (GPIO15) -------------> (Positive) Buzzer (Negative) ---> GND
+-----------------+
```

> [!CAUTION]
> **Voltage Divider Protection**: The HC-SR04 Echo pin outputs 5V TTL logic. ESP8266 GPIO pins are strictly 3.3V rated. You **must** wire the 1kΩ + 2kΩ voltage divider between Echo and GPIO 12 (D6) to scale 5V down to 3.33V (`5V * 2k / (1k + 2k) = 3.33V`).

---

### 3. Firmware Configuration

Open `esp8266_crowd_monitor.ino` in the Arduino IDE:
1. Under **Tools > Board**, select **NodeMCU 1.0 (ESP-12E Module)**.
2. Under **Tools > Manage Libraries**, ensure **ArduinoJson** (v6 or v7) is installed.
3. Update the credentials in `esp8266_crowd_monitor.ino`:
   ```cpp
   const char* WIFI_SSID     = "Your_WiFi_SSID";
   const char* WIFI_PASSWORD = "Your_WiFi_Password";
   const char* SERVER_URL    = "http://YOUR_SERVER_IP:5000/api/hardware/telemetry";
   const char* DEVICE_KEY    = "vg-device-secure-key-2026";
   const char* GATE_ID       = "main_gate";
   ```
4. Flash the sketch to your ESP8266 board via USB.

---

### 4. Telemetry Endpoint Specification

- **Endpoint**: `POST /api/hardware/telemetry`
- **Header**: `X-Device-Key: <HARDWARE_DEVICE_KEY>`
- **Payload**:
  ```json
  {
    "gate_id": "main_gate",
    "action_type": "entry",
    "count_delta": 1
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "action_type": "entry",
    "count_delta": 1,
    "current_occupancy": 142,
    "status": "NORMAL",
    "emergency": false
  }
  ```

If the venue is in an active emergency state or capacity exceeds limit, the API returns `"emergency": true` or `"status": "FULL"`, causing the ESP8266 to flash the red LED and trigger an audible alarm sequence.

