import sys
import os

DEBUG = False # Set to True for detailed logs, False to hide console output

if not DEBUG:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')

from PyQt6.QtWidgets import QApplication
from viewer.ui import TeslaCamViewer

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setOrganizationName("TeslaCamViewerAdvanced") # Ensure these are set
    app.setApplicationName("TeslaCamViewerAdvanced")      # For QSettings

    app.setStyleSheet("""
        QWidget {
            background-color: #282c34;
            color: #abb2bf;
            font-family: Arial, Helvetica, sans-serif;
            font-size: 11pt;
        }
        QPushButton {
            background-color: #3a3f4b;
            color: #e0e0e0;
            border: 1px solid #20232a;
            padding: 7px 12px;
            border-radius: 4px;
            min-height: 22px;
        }
        QPushButton:hover {
            background-color: #4c5260;
            border: 1px solid #3a3f4b;
        }
        QPushButton:pressed {
            background-color: #30353f;
        }
        QSlider::groove:horizontal {
            background: #3a3f4b;
            height: 8px;
            border-radius: 4px;
        }
        QSlider::handle:horizontal {
            background: #61afef;
            width: 16px;
            margin: -4px 0;
            border-radius: 8px;
            border: 1px solid #282c34;
        }
        QComboBox {
            background-color: #3a3f4b;
            border: 1px solid #20232a;
            padding: 4px 8px; 
            border-radius: 4px;
            min-height: 22px;
            min-width: 120px; 
            combobox-popup: 0; 
        }
        QComboBox:focus { border: 1px solid #61afef; }
        QComboBox::drop-down {
            subcontrol-origin: padding; subcontrol-position: top right;
            width: 22px; border-left-width: 1px; border-left-color: #20232a;
            border-left-style: solid; border-top-right-radius: 3px; border-bottom-right-radius: 3px;
        }
        QComboBox::down-arrow { image: none; }
        QComboBox QAbstractItemView {
            background-color: #2c313a; border: 1px solid #20232a; color: #abb2bf;
            selection-background-color: #61afef; selection-color: #282c34; padding: 3px; 
        }
        QLabel { color: #abb2bf; padding: 3px;}
        QRadioButton { spacing: 6px; color: #abb2bf; padding: 2px; }
        QRadioButton::indicator { width: 14px; height: 14px; border-radius: 8px; border: 2px solid #4c5260; }
        QRadioButton::indicator:unchecked { background-color: #282c34; }
        QRadioButton::indicator:checked { background-color: #61afef; border: 2px solid #528bcc; }
        QRadioButton::indicator:checked:hover { border: 2px solid #61afef; }
        QRadioButton::indicator:unchecked:hover { border: 2px solid #61afef; }
        
        /* QGraphicsView styling */
        QGraphicsView {
            background-color: #000000; /* Black background for video area */
            border: 1px solid #1a1d23; /* Subtle border */
        }
        QMenu {
            background-color: #2c313a; border: 1px solid #20232a; color: #abb2bf; padding: 4px;
        }
        QMenu::item { padding: 4px 20px 4px 20px; }
        QMenu::item:selected { background-color: #61afef; color: #282c34; }
        QMenu::indicator { width: 13px; height: 13px; }

        QFileDialog, QInputDialog, QMessageBox { background-color: #282c34; color: #abb2bf; }
        QFileDialog QLabel, QInputDialog QLabel, QMessageBox QLabel, 
        QInputDialog QLineEdit { 
            color: #abb2bf; background-color: #3a3f4b; 
            border: 1px solid #20232a; padding: 4px; border-radius: 3px;
        }
        QFileDialog QPushButton, QInputDialog QPushButton, QMessageBox QPushButton {
            background-color: #3a3f4b; color: #e0e0e0; border: 1px solid #20232a;
            padding: 6px 10px; border-radius: 3px;
        }
        QFileDialog QPushButton:hover, QInputDialog QPushButton:hover, QMessageBox QPushButton:hover {
            background-color: #4c5260;
        }
    """)
    viewer = TeslaCamViewer()
    viewer.show()
    sys.exit(app.exec())
