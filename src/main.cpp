#include <Arduino.h>
#include <pb_decode.h>
// Added for encoding ack back to host
#include <pb_encode.h>
#include "message.pb.h"
// We'll use SensorArray on the wire now
// Persistent device state visible to GUI (keeps latest readings)
SensorArray device_state = SensorArray_init_zero;
// Toggle verbose debug prints. Set to true for debugging. Use main Serial so USB monitor sees logs.
bool debug_enabled = true;
// Monotonic message id (increment after each send)
static int32_t message_id = 0;
// RX buffer used by serial/frame processing
static uint8_t rx_buf[512];
static size_t rx_len = 0;
void setup() {
  Serial.begin(115200);    // PC ile iletişim
  // Use main Serial over USB for both framed comms and debug output so user sees logs
  Serial.begin(115200);
  Serial.println("Nanopb Protobuf Test Ready");
  if (debug_enabled) Serial.println("DEBUG: ESP8266 başlatıldı");
  device_state = SensorArray_init_zero;
  // Ensure we have at least one reading so periodic encoding emits data
  device_state.readings_count = 1;
  device_state.readings[0].id = 0;
  device_state.readings[0].temperature = 0.0f;
  device_state.readings[0].humidity = 0.0f;
  // initialize message_id from device_state
  message_id = device_state.readings[0].id;
}

// Read available bytes from Serial into the rx buffer
void readSerialToBuf() {
  int avail = Serial.available();
  if (avail > 0) {
    size_t canRead = (size_t)avail;
    size_t space = sizeof(rx_buf) - rx_len;
    size_t toRead = canRead < space ? canRead : space;
    if (toRead > 0) {
      size_t r = Serial.readBytes(rx_buf + rx_len, toRead);
      rx_len += r;
    }
  }
}

// Find and process one complete framed message in rx_buf. Returns true if a frame was processed.
bool processOneFrame() {
  // need at least header
  if (rx_len < 4) return false;
  size_t idx = 0;
  while (idx + 1 < rx_len && !(rx_buf[idx] == 0xAA && rx_buf[idx+1] == 0x55)) idx++;
  if (!(idx + 1 < rx_len && rx_len >= idx + 4)) {
    if (rx_len > 256) rx_len = 0; // avoid runaway buffer
    return false;
  }

  // drop leading bytes before header
  if (idx > 0) { memmove(rx_buf, rx_buf + idx, rx_len - idx); rx_len -= idx; }
  uint16_t length = rx_buf[2] | (rx_buf[3] << 8);
  if (!(length <= 256 && rx_len >= (size_t)(4 + length))) return false;

  uint8_t payload[256];
  memcpy(payload, rx_buf + 4, length);
  // consume
  memmove(rx_buf, rx_buf + 4 + length, rx_len - (4 + length));
  rx_len -= (4 + length);

  // decode and merge
  pb_istream_t stream = pb_istream_from_buffer(payload, length);
  SensorArray arr = SensorArray_init_zero;
  if (pb_decode(&stream, SensorArray_fields, &arr)) {
    if (debug_enabled) {
      Serial.print("DEBUG: decoded arr.readings_count="); Serial.println((int)arr.readings_count);
    }
    for (size_t i = 0; i < arr.readings_count; i++) {
      SensorReading *r = &arr.readings[i];
        if (debug_enabled) {
        Serial.print("DEBUG: incoming r->id="); Serial.print(r->id);
        Serial.print(" temp="); Serial.print(r->temperature);
        Serial.print(" hum="); Serial.println(r->humidity);
      }
      if (debug_enabled) {
        Serial.print("DEBUG: Reading id="); Serial.print(r->id);
        Serial.print(" temp="); Serial.print(r->temperature);
        Serial.print(" hum="); Serial.println(r->humidity);
      }
      bool merged = false;
      for (size_t j = 0; j < device_state.readings_count; j++) {
        if (device_state.readings[j].id == r->id) {
          device_state.readings[j] = *r;
          merged = true;
          break;
        }
      }
      if (!merged) {
        // Overwrite primary slot so GUI-sent data becomes the canonical device_state[0].
        // This ensures the periodic/send-back payload shows the values the GUI sent.
        device_state.readings[0] = *r;
        device_state.readings_count = 1;
        if (debug_enabled) {
          Serial.print("DEBUG: device_state[0] overwritten id="); Serial.print(device_state.readings[0].id);
          Serial.print(" temp="); Serial.print(device_state.readings[0].temperature);
          Serial.print(" hum="); Serial.println(device_state.readings[0].humidity);
        }
      }
    }
  } else {
    if (debug_enabled) Serial.println("DEBUG: Protobuf decode error for SensorArray");
  }

  // Immediately encode and send the processed device_state back
  uint8_t outbuf[256];
  pb_ostream_t ostream = pb_ostream_from_buffer(outbuf, sizeof(outbuf));
  if (pb_encode(&ostream, SensorArray_fields, &device_state)) {
    uint16_t n = (uint16_t)ostream.bytes_written;
    if (n > 0 && n <= 248) {
      uint8_t frame[4 + 248];
      frame[0] = 0xAA; frame[1] = 0x55;
      frame[2] = (uint8_t)(n & 0xFF);
      frame[3] = (uint8_t)((n >> 8) & 0xFF);
      memcpy(frame + 4, outbuf, n);
      Serial.write(frame, 4 + n);
      Serial.flush();
          // increment message id after sending response and update primary id
          message_id++;
          if (device_state.readings_count > 0) {
            device_state.readings[0].id = message_id;
          }
          if (debug_enabled) {
            Serial.print("DEBUG: response sent, new id="); Serial.println(message_id);
          }
    }
  } else {
    if (debug_enabled) Serial.println("DEBUG: pb_encode failed when sending response");
  }

  return true;
}

// Forward declarations for functions defined below
void printDeviceState();
void sendDeviceStateFrame();

void loop() {
  // read any incoming bytes
  readSerialToBuf();
  // process all complete frames currently available
  while (processOneFrame()) {
    ; // loop until no full frame remains
  }

  // Print device_state every 1 second from a separate function (non-blocking)
  static unsigned long last_print_ms = 0;
  unsigned long now = millis();
  if (now - last_print_ms >= 1000) {
    last_print_ms = now;
    // send device state as framed protobuf so the GUI can update reliably
    sendDeviceStateFrame();
  }
}

// Send current device_state as a framed protobuf message over Serial
void sendDeviceStateFrame() {
  // encode device_state
  uint8_t outbuf[256];
  pb_ostream_t ostream = pb_ostream_from_buffer(outbuf, sizeof(outbuf));
  if (!pb_encode(&ostream, SensorArray_fields, &device_state)) {
    if (debug_enabled) Serial.println("DEBUG: periodic pb_encode failed");
    return;
  }
  uint16_t n = (uint16_t)ostream.bytes_written;
  if (n == 0 || n > 248) {
    if (debug_enabled) {
      Serial.print("DEBUG: periodic encoded size out of range: "); Serial.println(n);
    }
    return;
  }
  uint8_t frame[4 + 248];
  frame[0] = 0xAA; frame[1] = 0x55;
  frame[2] = (uint8_t)(n & 0xFF);
  frame[3] = (uint8_t)((n >> 8) & 0xFF);
  memcpy(frame + 4, outbuf, n);
  Serial.write(frame, 4 + n);
  // don't flush aggressively; let USB stack batch writes
  if (debug_enabled) {
    Serial.print("DEBUG: periodic state sent, bytes="); Serial.print(4 + n);
    if (device_state.readings_count > 0) {
      Serial.print(" id="); Serial.print(device_state.readings[0].id);
      Serial.print(" temp="); Serial.print(device_state.readings[0].temperature);
      Serial.print(" hum="); Serial.println(device_state.readings[0].humidity);
    } else {
      Serial.println();
    }
  }
  // increment message id after periodic send
  message_id++;
  if (device_state.readings_count > 0) {
    device_state.readings[0].id = message_id;
  }
}
