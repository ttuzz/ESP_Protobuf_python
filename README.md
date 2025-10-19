![demo](assets/preview.gif)

# ESP8266 Protobuf Serial Communication

## Overview
- This project demonstrates Protobuf-based serial communication between a PyQt5 GUI and ESP8266 (PlatformIO + Arduino). Messages are encoded/decoded on the ESP side using Nanopb, with a simple frame format (0xAA 0x55 + 16-bit length + payload).

## How it works
- The GUI (PC) sends partial updates (e.g., sensor temperature). The ESP merges/overwrites incoming data into its own `device_state` object and sends both immediate responses and periodic status messages. This ensures the GUI always receives the latest state.

## Quick Start
1. Place the `assests/preview.gif` file in an `assests` folder at the project root. The GIF will be automatically displayed at the top of the README.
2. Check serial port settings in `platformio.ini` with `upload_port` and `monitor_speed` (default: COM6, 115200).
3. For Python GUI:
   - Run `py_scripts/gui.py` (install dependencies first if needed: `pip install -r requirements.txt` or `pip install pyqt5 protobuf pyserial` in a virtual environment).
4. For Firmware:
   - Compile and upload to ESP using PlatformIO: `platformio run --target upload` from project root (you can also use VSCode PlatformIO tasks).
5. In the serial monitor (COM6), you can see both framed protobuf stream and debug messages (USB Serial).

## Notes
- If `assests/preview.gif` doesn't exist, you may see an empty image link at the top of the README; add the GIF as `assests/preview.gif` or update the file path in the README.
- `proto` files and nanopb generation are supported via `py_scripts/proto.bat`; `protoc` and `protoc-gen-nanopb.exe` should be available in Windows environment.

## Support
- If you need more help, copy and send relevant log lines from serial output; I can help with decode/merge steps.
