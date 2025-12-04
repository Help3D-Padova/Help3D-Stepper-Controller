import serial
import serial.tools.list_ports

class SerialManager:
    def __init__(self):
        self.ser = None

    def list_ports(self):
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    def connect(self, port):
        try:
            self.ser = serial.Serial(port, 115200, timeout=1)
            return True, f"Connected on {port}"
        except Exception as e:
            return False, f"Connection failed: {e}"

    def send(self, message):
        if self.ser:
            msg = (message + "\n").encode("utf-8")
            self.ser.write(msg)

    def read_line(self):
        if not self.ser:
            return ""
        try:
            return self.ser.readline().decode(errors="ignore").strip()
        except:
            return ""
