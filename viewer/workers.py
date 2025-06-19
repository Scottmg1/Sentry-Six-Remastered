import os
import re
import subprocess
import traceback
from PyQt6.QtCore import QObject, pyqtSignal

from . import utils

class ExportWorker(QObject):
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)
    progress_value = pyqtSignal(int)  # New signal for the percentage value (0-100)

    def __init__(self, ffmpeg_cmd, duration_s, parent=None):
        super().__init__(parent)
        self.ffmpeg_cmd = ffmpeg_cmd
        self.duration_s = duration_s  # Total duration of the clip in seconds
        self._is_running = True
        self.proc = None

    def run(self):
        # Regex to find the time string in FFmpeg's output, e.g., "time=00:00:12.34"
        time_pattern = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")
        
        try:
            if utils.DEBUG_UI:
                print(f"--- Starting Export ---\nFFmpeg Command:\n{' '.join(self.ffmpeg_cmd)}\n-----------------------")
            
            self.progress.emit("Exporting clip... (0%)")
            
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
                
                match = time_pattern.search(line)
                if match and self.duration_s > 0:
                    hours = int(match.group(1))
                    minutes = int(match.group(2))
                    seconds = int(match.group(3))
                    hundredths = int(match.group(4))
                    
                    current_progress_s = (hours * 3600) + (minutes * 60) + seconds + (hundredths / 100)
                    percentage = int((current_progress_s / self.duration_s) * 100)
                    
                    # Clamp percentage between 0 and 100
                    percentage = max(0, min(100, percentage))

                    self.progress_value.emit(percentage)
                    self.progress.emit(f"Exporting... ({percentage}%)")

                if utils.DEBUG_UI:
                    print(f"[FFMPEG]: {line.strip()}")
            
            self.proc.wait()

            if not self._is_running:
                self.finished.emit(False, "Export was cancelled by the user.")
            elif self.proc.returncode == 0:
                # Ensure the progress bar completes on success
                self.progress_value.emit(100)
                self.progress.emit("Finalizing...")
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