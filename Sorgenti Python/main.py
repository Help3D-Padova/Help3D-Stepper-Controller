import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer

from ui import MainWindowUI
from serial_manager import SerialManager


class Controller(MainWindowUI):
    def __init__(self):
        super().__init__()

        self.serial = SerialManager()

        # stato motore
        self.running = False

        # Parametri come Arduino
        self.FULL_STEPS_PER_REV = 200
        self.STEP_S_LIMIT = 5000.0
        self.minRPM = 5.0
        self.microstep = 16
        self.max_rpm = 0

        # Telemetria
        self.telemetry_x = []
        self.telemetry_y = []
        self.telemetry_time = 0.0
        self.telemetry_started = False

        # Command buffer
        self.cmd_buffer = []
        self.cmd_timer = QTimer()
        self.cmd_timer.timeout.connect(self.flush_cmd_buffer)
        self.cmd_timer.start(10)

        # GUI init
        self.populate_ports()

        self.accel_plot.clear()

        # Bindings GUI
        self.connect_btn.clicked.connect(self.handle_connect_button)
        self.microstep_select.currentIndexChanged.connect(self.update_microstepping)
        self.profile_select.currentIndexChanged.connect(self.update_profile)
        self.start_btn.clicked.connect(self.gui_start_clicked)
        self.stop_btn.clicked.connect(self.gui_stop_clicked)
        self.left_btn.clicked.connect(lambda: self.send_cmd("DIR:CW"))
        self.right_btn.clicked.connect(lambda: self.send_cmd("DIR:CCW"))
        self.speed_slider.valueChanged.connect(self.update_speed)

        self.update_max_rpm()

        # Timer telemetria
        self.telemetry_timer = QTimer()
        self.telemetry_timer.timeout.connect(self.read_serial)
        self.telemetry_timer.start(20)

        # focus tastiera
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

    # ---------------------------------------------------------
    # FLASH
    # ---------------------------------------------------------
    def flash(self, btn):
        btn.setStyleSheet("background-color: yellow; color: black;")
        QTimer.singleShot(120, lambda: btn.setStyleSheet(""))

    # ---------------------------------------------------------
    # COMMAND BUFFER
    # ---------------------------------------------------------
    def send_cmd(self, cmd: str):
        self.cmd_buffer.append(cmd)

    def flush_cmd_buffer(self):
        if not self.serial.ser or not getattr(self.serial.ser, "is_open", False):
            self.cmd_buffer.clear()
            return

        if not self.cmd_buffer:
            return

        cmd = self.cmd_buffer.pop(0)
        self.serial.send(cmd)

    # ---------------------------------------------------------
    # CONNECT / DISCONNECT
    # ---------------------------------------------------------
    def populate_ports(self):
        ports = self.serial.list_ports()
        self.port_select.clear()
        self.port_select.addItems(ports if ports else ["Nessuna porta trovata"])

    def handle_connect_button(self):
        # ============ DISCONNECT ============
        if self.serial.ser and getattr(self.serial.ser, "is_open", False):

            # STOP immediato
            try:
                self.serial.ser.write(b"STOP\n")
                self.serial.ser.flush()
            except:
                pass

            # chiudi seriale
            try:
                self.serial.ser.close()
            except:
                pass

            self.serial.ser = None

            # reset GUI
            self.running = False
            self.speed_slider.setValue(0)
            self.telemetry_started = False
            self.accel_plot.clear()

            self.connect_btn.setText("Connetti")
            self.status_label.setText("Disconnected")
            return

        # ============= CONNECT =============
        port = self.port_select.currentText()
        ok, msg = self.serial.connect(port)
        self.status_label.setText(msg)

        if ok:
            self.connect_btn.setText("Disconnetti")
            self.telemetry_started = False
            self.accel_plot.clear()

            self.running = False
            self.speed_slider.setValue(0)

            self.send_cmd("STOP")
            self.send_cmd(f"MICROSTEP:{self.microstep}")
            self.send_cmd(f"SET_PROFILE:{self.profile_select.currentIndex() + 1}")

        self.setFocus()

    # ---------------------------------------------------------
    # MICROSTEPPING
    # ---------------------------------------------------------
    def update_microstepping(self):
        # nuovo microstep scelto
        new_micro = int(self.microstep_select.currentText())

        # se non cambia nulla, esci
        if new_micro == self.microstep:
            return

        # se il motore sta girando -> auto STOP di sicurezza
        if self.running:
            self.send_cmd("STOP")
            self.running = False
            self.speed_slider.setValue(0)

        # aggiorna valore interno e manda a Arduino
        self.microstep = new_micro
        self.send_cmd(f"MICROSTEP:{self.microstep}")

        # ricalcola i limiti RPM
        self.update_max_rpm()

    def update_max_rpm(self):
        steps_per_rev = self.FULL_STEPS_PER_REV * self.microstep
        max_rpm = (self.STEP_S_LIMIT / steps_per_rev) * 60.0
        max_rpm = max(5.0 * round(max_rpm / 5.0), self.minRPM)

        self.max_rpm = int(max_rpm)
        self.max_label.setText(f"Max RPM: {self.max_rpm}")
        self.speed_slider.setMaximum(self.max_rpm)

        # clamp dello slider se è fuori dal nuovo range
        if self.speed_slider.value() > self.max_rpm:
            self.speed_slider.setValue(self.max_rpm)

    def update_profile(self, index: int):
        self.send_cmd(f"SET_PROFILE:{index + 1}")

    # ---------------------------------------------------------
    # START / STOP
    # ---------------------------------------------------------
    def gui_start_clicked(self):
        self.running = True
        self.send_cmd("START")
        self.send_cmd(f"SET_SPEED:{self.speed_slider.value()}")
        self.flash(self.start_btn)

    def gui_stop_clicked(self):
        self.running = False
        self.send_cmd("STOP")
        self.flash(self.stop_btn)

    # ---------------------------------------------------------
    # SPEED
    # ---------------------------------------------------------
    def update_speed(self, value: int):
        if value > self.max_rpm:
            value = self.max_rpm
            self.speed_slider.setValue(value)

        self.speed_label.setText(f"Speed: {value} RPM")

        if self.running:
            self.send_cmd(f"SET_SPEED:{value}")

    # ---------------------------------------------------------
    # TELEMETRIA
    # ---------------------------------------------------------
    def read_serial(self):
        line = self.serial.read_line()
        if not line:
            return

        if line.startswith("CURRENT:"):
            try:
                rpm = float(line.split(":")[1])
            except:
                return

            self.update_telemetry(rpm)

    def update_telemetry(self, rpm: float):
        if not self.telemetry_started:
            self.telemetry_started = True
            self.telemetry_x.clear()
            self.telemetry_y.clear()
            self.telemetry_time = 0.0
            self.accel_plot.clear()

        self.telemetry_time += 0.02
        self.telemetry_x.append(self.telemetry_time)
        self.telemetry_y.append(rpm)

        # ultimi 15 secondi
        while self.telemetry_x and (self.telemetry_time - self.telemetry_x[0] > 15):
            self.telemetry_x.pop(0)
            self.telemetry_y.pop(0)

        # curva reale
        self.accel_plot.clear()
        self.accel_plot.plot(
            self.telemetry_x,
            self.telemetry_y,
            pen={'width': 3}
        )

    # ---------------------------------------------------------
    # KEYBOARD
    # ---------------------------------------------------------
    def keyPressEvent(self, event):
        key = event.key()

        # Barra spaziatrice → RUN/STOP
        if key == Qt.Key.Key_Space:
            self.running = not self.running

            if self.running:
                self.send_cmd("START")
                self.send_cmd(f"SET_SPEED:{self.speed_slider.value()}")
                self.flash(self.start_btn)
            else:
                self.send_cmd("STOP")
                self.flash(self.stop_btn)
            return

        if key == Qt.Key.Key_Up:
            rpm = min(self.speed_slider.value() + 5, self.max_rpm)
            self.speed_slider.setValue(rpm)
            return

        if key == Qt.Key.Key_Down:
            rpm = max(self.speed_slider.value() - 5, 0)
            self.speed_slider.setValue(rpm)
            return

        if key == Qt.Key.Key_Right:
            self.send_cmd("DIR:CCW")
            self.flash(self.right_btn)
            return

        if key == Qt.Key.Key_Left:
            self.send_cmd("DIR:CW")
            self.flash(self.left_btn)
            return


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Controller()
    window.show()

    # SAFE STOP on app exit
    def stop_motor_on_exit():
        if window.serial.ser and getattr(window.serial.ser, "is_open", False):
            try:
                window.serial.ser.write(b"STOP\n")
                window.serial.ser.flush()
            except:
                pass
            try:
                window.serial.ser.close()
            except:
                pass

    app.aboutToQuit.connect(stop_motor_on_exit)

    sys.exit(app.exec())
