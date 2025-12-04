from PyQt6.QtWidgets import (
    QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QComboBox
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
import pyqtgraph as pg


class MainWindowUI(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("HELP3D Stepper Motor Control")
        self.setMinimumWidth(600)

        layout = QVBoxLayout()

        # LOGO
        self.logo_label = QLabel()
        pix = QPixmap("logo.png")
        if not pix.isNull():
            pix = pix.scaledToWidth(220, Qt.TransformationMode.SmoothTransformation)
            self.logo_label.setPixmap(pix)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.logo_label)

        # PORTA SERIALE
        layout.addWidget(QLabel("Porta seriale:"))
        self.port_select = QComboBox()
        layout.addWidget(self.port_select)

        self.connect_btn = QPushButton("Connetti")
        layout.addWidget(self.connect_btn)

        self.status_label = QLabel("Disconnected")
        layout.addWidget(self.status_label)

        # MICROSTEPPING
        layout.addWidget(QLabel("Microstepping:"))
        self.microstep_select = QComboBox()
        self.microstep_select.addItems(["1", "2", "4", "8", "16", "32", "64"])
        self.microstep_select.setCurrentText("16")
        layout.addWidget(self.microstep_select)

        # PROFILO ACCELERAZIONE
        layout.addWidget(QLabel("Profilo accelerazione:"))
        self.profile_select = QComboBox()
        self.profile_select.addItems([
            "1 - Soft (50 RPM/s)",
            "2 - Medio (150 RPM/s)",
            "3 - Aggressivo (400 RPM/s)"
        ])
        self.profile_select.setCurrentIndex(1)
        layout.addWidget(self.profile_select)

        # MAX RPM
        self.max_label = QLabel("Max RPM: -")
        layout.addWidget(self.max_label)

        # Start/Stop
        cmd_row = QHBoxLayout()
        self.start_btn = QPushButton("START")
        self.stop_btn = QPushButton("STOP")
        cmd_row.addWidget(self.start_btn)
        cmd_row.addWidget(self.stop_btn)
        layout.addLayout(cmd_row)

        # Direzione
        dir_row = QHBoxLayout()
        self.left_btn = QPushButton("← CCW")
        self.right_btn = QPushButton("CW →")
        dir_row.addWidget(self.left_btn)
        dir_row.addWidget(self.right_btn)
        layout.addLayout(dir_row)

        # SLIDER VELOCITÀ
        self.speed_label = QLabel("Speed: 0 RPM")
        layout.addWidget(self.speed_label)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setMinimum(0)
        self.speed_slider.setMaximum(2000)
        layout.addWidget(self.speed_slider)

        # GRAFICO
        self.accel_plot = pg.PlotWidget()
        self.accel_plot.setLabel("bottom", "Tempo", units="s")
        self.accel_plot.setLabel("left", "RPM")
        self.accel_plot.showGrid(x=True, y=True, alpha=0.3)
        layout.addWidget(self.accel_plot)

        self.setLayout(layout)
