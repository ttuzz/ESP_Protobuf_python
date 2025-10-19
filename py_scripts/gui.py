#C:\protoc\bin
from PyQt5.QtCore import Qt, QTimer, QSettings
import message_pb2
import sys
import serial
import serial.tools.list_ports
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLineEdit, QLabel, QComboBox
)
from PyQt5.QtCore import Qt

class SerialGUI(QWidget):
    def refresh_ports(self):
        self.port_combo.clear()
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(port.device)

    def create_sensor_object(self, id=None, temperature=None, humidity=None):
        # Build a SensorArray with a single SensorReading.
        # If we have a current_state, use its first reading as base so
        # partial updates don't overwrite fields with proto3 defaults.
        arr = message_pb2.SensorArray()
        base = None
        if hasattr(self, 'current_state') and hasattr(self.current_state, 'readings') and len(self.current_state.readings) > 0:
            base = self.current_state.readings[0]

        rd = arr.readings.add()
        # copy base values if present
        if base is not None:
            try:
                rd.id = base.id
                rd.temperature = base.temperature
                rd.humidity = base.humidity
            except Exception:
                pass

        # override with any provided values
        if id is not None:
            rd.id = id
        if temperature is not None:
            rd.temperature = temperature
        if humidity is not None:
            rd.humidity = humidity
        return arr

    def update_sensor_display(self, arr):
        # Display the first reading if present
        if hasattr(arr, 'readings') and len(arr.readings) > 0:
            r = arr.readings[0]
            text = f"ID: {r.id}\nTemp: {r.temperature}\nHumidity: {r.humidity}"
        else:
            text = "No sensor data"
        self.sensor_label.setText(text)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Seri Haberleşme Kontrol Paneli")
        self.setGeometry(200, 200, 600, 400)
        self.serial = None
        # Load last used port/baud from settings
        self.settings = QSettings("esp8266_protobus", "serial_gui")
        last_port = self.settings.value("port", "")
        last_baud = self.settings.value("baud", "115200")

        # Cihazın son bilinen durumu (GUI'de göstermek için)
        self.current_state = message_pb2.SensorArray()

        # SensorData nesnesi gösterimi (daha üstte ve büyük font)
        self.sensor_label = QLabel()
        self.sensor_label.setStyleSheet("color: #00ff99; background: #111; font-size: 22px; padding: 12px; border: 2px solid #444;")
        self.sensor_label.setAlignment(Qt.AlignCenter)
        self.update_sensor_display(self.current_state)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.sensor_label)  # Sensor label'ı en üstte ekle
        self.setLayout(layout)

        # Seri port seçimi
        port_layout = QHBoxLayout()
        self.port_combo = QComboBox()
        self.refresh_ports()
        if last_port:
            idx = self.port_combo.findText(last_port)
            if idx != -1:
                self.port_combo.setCurrentIndex(idx)
        port_layout.addWidget(QLabel("Port:"))
        port_layout.addWidget(self.port_combo)
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "115200"])
        idx = self.baud_combo.findText(str(last_baud))
        if idx != -1:
            self.baud_combo.setCurrentIndex(idx)
        port_layout.addWidget(QLabel("Baud:"))
        port_layout.addWidget(self.baud_combo)
        layout.addLayout(port_layout)

        # Bağlantı butonları
        btn_layout = QHBoxLayout()
        self.connect_btn = QPushButton("Bağlan")
        self.disconnect_btn = QPushButton("Bağlantıyı Kes")
        self.disconnect_btn.setEnabled(False)
        btn_layout.addWidget(self.connect_btn)
        btn_layout.addWidget(self.disconnect_btn)
        layout.addLayout(btn_layout)

        # SensorData gönderme alanı (nesne tabanlı)
        send_layout = QHBoxLayout()
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("ID")
        self.temp_input = QLineEdit()
        self.temp_input.setPlaceholderText("Sıcaklık")
        self.hum_input = QLineEdit()
        self.hum_input.setPlaceholderText("Nem")
        self.send_btn = QPushButton("Gönder")
        send_layout.addWidget(QLabel("ID:"))
        send_layout.addWidget(self.id_input)
        send_layout.addWidget(QLabel("Sıcaklık:"))
        send_layout.addWidget(self.temp_input)
        send_layout.addWidget(QLabel("Nem:"))
        send_layout.addWidget(self.hum_input)
        send_layout.addWidget(self.send_btn)
        layout.addLayout(send_layout)

        # Gelen/giden veri alanı
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setStyleSheet("background-color: #222; color: #eee;")
        layout.addWidget(self.text_area)

        # Bağlantı durumu
        self.status_label = QLabel("Durum: Bağlı değil")
        self.status_label.setStyleSheet("color: #ff5555;")
        layout.addWidget(self.status_label)

        # Sinyaller
        self.connect_btn.clicked.connect(self.connect_serial)
        self.disconnect_btn.clicked.connect(self.disconnect_serial)
        self.send_btn.clicked.connect(self.send_data)

        # Timer ile veri okuma
        self.timer = QTimer()
        self.timer.timeout.connect(self.read_serial)

    # RX frame buffer
        self.rx_buf = bytearray()

    def connect_serial(self):
        port = self.port_combo.currentText()
        baud = int(self.baud_combo.currentText())
        try:
            self.serial = serial.Serial(port, baud, timeout=0.05)
            self.status_label.setText("Durum: Bağlandı")
            self.status_label.setStyleSheet("color: #55ff55;")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            self.timer.start(100)
            self.text_area.append(">> Bağlantı açıldı: {} @ {}".format(port, baud))
            # persist last-used selection
            try:
                self.settings.setValue("port", port)
                self.settings.setValue("baud", str(baud))
            except Exception:
                pass
        except Exception as e:
            self.text_area.append(">> Bağlantı hatası: {}".format(e))

    def disconnect_serial(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
            self.text_area.append(">> Bağlantı kapatıldı.")
        self.status_label.setText("Durum: Bağlı değil")
        self.status_label.setStyleSheet("color: #ff5555;")
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.timer.stop()

    def _frame(self, payload: bytes) -> bytes:
        # 0xAA 0x55 + len (LE 16-bit) + payload
        n = len(payload)
        return b"\xAA\x55" + bytes((n & 0xFF, (n >> 8) & 0xFF)) + payload

    def send_data(self):
        if self.serial and self.serial.is_open:
            try:
                # Partial update: sadece dolu alanları gönder
                id_val = self.id_input.text().strip()
                temp_val = self.temp_input.text().strip()
                hum_val = self.hum_input.text().strip()

                id_parsed = int(id_val) if id_val != "" else None
                temp_parsed = float(temp_val) if temp_val != "" else None
                hum_parsed = float(hum_val) if hum_val != "" else None

                obj = self.create_sensor_object(id_parsed, temp_parsed, hum_parsed)
                payload = obj.SerializeToString()
                # Debug: show raw payload hex in GUI log before framing
                try:
                    self.text_area.append("<< Payload hex: " + payload.hex())
                except Exception:
                    self.text_area.append("<< Payload hex: (couldn't hex)")
                framed = self._frame(payload)
                try:
                    self.text_area.append("<< Framed hex: " + framed.hex())
                except Exception:
                    pass
                self.serial.write(framed)

                sent_desc = []
                if id_parsed is not None:
                    sent_desc.append(f"id={id_parsed}")
                if temp_parsed is not None:
                    sent_desc.append(f"temp={temp_parsed}")
                if hum_parsed is not None:
                    sent_desc.append(f"hum={hum_parsed}")
                self.text_area.append("<< Gönderildi: " + ", ".join(sent_desc) if sent_desc else "<< Gönderildi: (boş güncelleme)")
            except Exception as e:
                self.text_area.append(f"<< Gönderim hatası: {e}")
            finally:
                self.id_input.clear()
                self.temp_input.clear()
                self.hum_input.clear()

    def read_serial(self):
        if not (self.serial and self.serial.is_open):
            return
        try:
            data = self.serial.read(self.serial.in_waiting or 1)
            if data:
                self.rx_buf.extend(data)
                try:
                    self.text_area.append(f">> Raw recv bytes: {len(data)} rx_buf_len={len(self.rx_buf)} tail={bytes(self.rx_buf[-32:]).hex()}" )
                except Exception:
                    pass

            # Frame parsing loop
            changed = False
            while True:
                # Find magic header
                idx = self.rx_buf.find(b"\xAA\x55")
                if idx == -1:
                    # No header yet, drop old noise
                    if len(self.rx_buf) > 1024:
                        self.rx_buf.clear()
                    break
                # Drop leading noise
                if idx > 0:
                    del self.rx_buf[:idx]
                if len(self.rx_buf) < 4:
                    break  # Wait for length
                length = self.rx_buf[2] | (self.rx_buf[3] << 8)
                try:
                    self.text_area.append(f">> Found header at idx={idx} length={length} rx_buf_len={len(self.rx_buf)}")
                except Exception:
                    pass
                if len(self.rx_buf) < 4 + length:
                    break  # Wait for full payload
                payload = bytes(self.rx_buf[4:4+length])
                # Remove consumed frame
                del self.rx_buf[:4+length]

                # Parse protobuf payload
                try:
                    # Debug: show received payload hex for comparison with ESP logs
                    try:
                        self.text_area.append(">> Recv payload hex: " + payload.hex())
                    except Exception:
                        pass

                    arr = message_pb2.SensorArray()
                    arr.ParseFromString(payload)
                    self.current_state = arr  # ACK mevcut durum
                    self.update_sensor_display(self.current_state)
                    if len(arr.readings) > 0:
                        r = arr.readings[0]
                        self.text_area.append(f">> ACK: id={r.id}, temp={r.temperature}, hum={r.humidity}")
                    else:
                        self.text_area.append(">> ACK: (empty SensorArray)")
                    changed = True
                except Exception as e:
                    self.text_area.append(f">> Parse hatası: {e}")

            # Optional: throttle UI updates
            if changed:
                pass
        except Exception as e:
            self.text_area.append(f">> Okuma hatası: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = SerialGUI()
    gui.show()
    sys.exit(app.exec_())