import os
import subprocess
import traceback
from PyQt6.QtCore import QObject, pyqtSignal

from . import utils

class ExportWorker(QObject):
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)

    def __init__(self, ffmpeg_cmd, parent=None):
        super().__init__(parent)
        self.ffmpeg_cmd = ffmpeg_cmd
        self._is_running = True
        self.proc = None

    def run(self):
        try:
            if utils.DEBUG_UI:
                print(f"--- Starting Export ---\nFFmpeg Command:\n{' '.join(self.ffmpeg_cmd)}\n-----------------------")
            
            self.progress.emit("Exporting clip... This may take a while.")
            
            creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            self.proc = subprocess.Popen(
                self.ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                creationflags=creation_flags
            )

            for line in self.proc.stdout:
                if not self._is_running:
                    self.proc.terminate()
                    break
                if utils.DEBUG_UI:
                    print(f"[FFMPEG]: {line.strip()}")
            
            self.proc.wait()

            if not self._is_running:
                self.finished.emit(False, "Export was cancelled by the user.")
            elif self.proc.returncode == 0:
                self.finished.emit(True, "Export completed successfully!")
            else:
                self.finished.emit(False, f"Export failed with return code {self.proc.returncode}.")
        
        except Exception as e:
            self.finished.emit(False, f"An exception occurred during export: {e}\n{traceback.format_exc()}")
        
        finally:
            self._is_running = False

    def stop(self):
        self._is_running = False
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()