# main.py
import sys
from PyQt6.QtWidgets import QApplication
from viewer.ui import TeslaCamViewer

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QWidget {
            background-color: #1e1e1e;
            color: #ffffff;
            font-family: Arial;
            font-size: 12pt;
        }
        QPushButton {
            background-color: #3a3a3a;
            color: white;
            border: 1px solid #5c5c5c;
            padding: 5px 10px;
        }
        QPushButton:hover {
            background-color: #505050;
        }
        QSlider::groove:horizontal {
            background: #3a3a3a;
            height: 10px;
        }
        QSlider::handle:horizontal {
            background: #a0a0a0;
            width: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }
    """)
    viewer = TeslaCamViewer()
    viewer.show()
    sys.exit(app.exec())
