import sys
import os

# Set to True for detailed logs, False to hide console output
DEBUG = True
# Show first-time welcome dialog (folder picker)
SHOW_WELCOME = True

if not DEBUG:
    # Redirect stdout and stderr to devnull to hide console output on Windows
    # when running from a pythonw.exe interpreter.
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')

from PyQt6.QtWidgets import QApplication
from viewer.ui import TeslaCamViewer
from viewer import utils

def main():
    app = QApplication(sys.argv)
    
    # These must be set for QSettings to work correctly on all platforms
    app.setOrganizationName("TeslaCamViewerAdvanced")
    app.setApplicationName("TeslaCamViewerAdvanced")

    # Create asset files if they don't exist
    utils.setup_assets()
    
    # Load stylesheet from file
    style_path = os.path.join(os.path.dirname(__file__), 'viewer', 'style.qss')
    try:
        with open(style_path, 'r', encoding='utf-8') as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        print(f"Warning: Stylesheet not found at {style_path}")
    except IOError as e:
        print(f"Warning: Could not read stylesheet {style_path}: {e}")

    # Create and show the main window
    viewer = TeslaCamViewer(show_welcome=SHOW_WELCOME)
    viewer.show()
    # Start the application event loop
    sys.exit(app.exec())

if __name__ == '__main__':
    main()