"""
Export Manager for Sentry-Six.

Handles all export operations including FFmpeg command building, progress tracking,
and export state management.
"""

import os
from typing import List, Optional, Callable, Tuple
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal, QThread
from PyQt6.QtWidgets import QWidget, QMessageBox, QProgressDialog, QFileDialog, QDialog, QVBoxLayout, QLabel, QRadioButton, QDialogButtonBox
from PyQt6.QtCore import Qt

from .. import utils
from ..state import AppState, ExportState
from .. import workers
from ..ffmpeg_builder import FFmpegCommandBuilder


class ExportManager(QObject):
    """Manages video export operations and state."""
    
    # Signals
    export_started = pyqtSignal()
    export_finished = pyqtSignal(bool, str)  # success, message
    export_progress = pyqtSignal(str)  # progress message
    export_progress_value = pyqtSignal(int)  # progress percentage
    
    def __init__(self, parent: QWidget, app_state: AppState, camera_map: dict, ordered_visible_indices: List[int]):
        super().__init__(parent)
        self._parent = parent
        self.app_state = app_state
        self.camera_map = camera_map
        self.ordered_visible_indices = ordered_visible_indices
        
        # Thread management
        self.export_thread: Optional[QThread] = None
        self.export_worker: Optional[workers.ExportWorker] = None
        
        # UI elements
        self.progress_dialog: Optional[QProgressDialog] = None
        
        # State
        self.files_to_cleanup_after_export: List[str] = []
        
        # Callbacks
        self.on_export_finished: Optional[Callable] = None
    
    def set_callbacks(self, on_export_finished: Callable):
        """Set callback functions for export events."""
        self.on_export_finished = on_export_finished
    
    def can_export(self) -> bool:
        """Check if export is possible with current state."""
        return all([
            utils.FFMPEG_FOUND,
            self.app_state.is_daily_view_active,
            self.app_state.export_state.start_ms is not None,
            self.app_state.export_state.end_ms is not None
        ])
    
    def show_export_dialog(self):
        """Show the export options dialog."""
        if not self.can_export():
            QMessageBox.warning(
                self._parent, 
                "Export Error", 
                "Please load clips and set both a start and end time before exporting."
            )
            return
        
        dialog = QDialog(self._parent)
        dialog.setWindowTitle("Export Options")
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel("Select export quality:"))
        full_res_rb = QRadioButton("Full Resolution")
        mobile_rb = QRadioButton("Mobile Friendly - 1080p")
        full_res_rb.setChecked(True)
        
        layout.addWidget(full_res_rb)
        layout.addWidget(mobile_rb)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            output_path, _ = QFileDialog.getSaveFileName(
                self._parent, 
                "Save Exported Clip", 
                f"exported_clip.mp4", 
                "MP4 Videos (*.mp4)"
            )
            if output_path:
                self.start_export(output_path, mobile_rb.isChecked())
    
    def start_export(self, output_path: str, is_mobile: bool):
        """Start the export process."""
        if not self.can_export():
            return
        
        # Build FFmpeg command
        result = self._build_ffmpeg_command(output_path, is_mobile)
        if not result or not result[0] or result[0] is None:
            QMessageBox.critical(
                self._parent, 
                "Export Failed", 
                "Could not generate FFmpeg command. No visible cameras or clips found for the selected range."
            )
            return
        
        ffmpeg_cmd, self.files_to_cleanup_after_export, duration_s = result
        
        # Create progress dialog
        self.progress_dialog = QProgressDialog("Preparing export...", "Cancel", 0, 100, self._parent)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setWindowTitle("Exporting")
        self.progress_dialog.show()
        
        # Create and start export worker
        self.export_worker = workers.ExportWorker(ffmpeg_cmd, duration_s)
        self.export_thread = QThread()
        self.export_worker.moveToThread(self.export_thread)
        
        # Connect signals
        self.export_thread.started.connect(self.export_worker.run)
        self.export_worker.finished.connect(self._on_export_finished)
        self.export_worker.progress.connect(self.progress_dialog.setLabelText)
        self.export_worker.progress_value.connect(self.progress_dialog.setValue)
        self.progress_dialog.canceled.connect(self.export_worker.stop)
        
        # Emit signals
        self.export_started.emit()
        
        # Start export
        self.export_thread.start()
    
    def _build_ffmpeg_command(self, output_path: str, is_mobile: bool) -> Optional[Tuple[Optional[List[str]], List[str], float]]:
        """Build the FFmpeg command for export."""
        builder = FFmpegCommandBuilder(
            app_state=self.app_state,
            ordered_visible_indices=self.ordered_visible_indices,
            camera_map=self.camera_map,
            is_mobile=is_mobile,
            output_path=output_path
        )
        return builder.build()
    
    def _on_export_finished(self, success: bool, message: str):
        """Handle export completion."""
        if success:
            if self.progress_dialog:
                self.progress_dialog.setValue(100)
        
        if self.progress_dialog:
            self.progress_dialog.close()
        
        # Clean up thread
        if self.export_thread:
            self.export_thread.quit()
            self.export_thread.wait()
        
        # Show result message
        if success:
            QMessageBox.information(self._parent, "Export Complete", message)
        else:
            QMessageBox.critical(self._parent, "Export Failed", message)
        
        # Clean up temporary files
        self._cleanup_temp_files()
        
        # Reset state
        self.export_thread = None
        self.export_worker = None
        
        # Emit signals
        self.export_finished.emit(success, message)
        
        # Call callback if set
        if self.on_export_finished:
            self.on_export_finished(success, message)
    
    def _cleanup_temp_files(self):
        """Clean up temporary files created during export."""
        for path in self.files_to_cleanup_after_export:
            try:
                os.remove(path)
            except OSError as e:
                if utils.DEBUG_UI:
                    print(f"Error removing temp file {path}: {e}")
        
        self.files_to_cleanup_after_export.clear()
    
    def set_export_range(self, start_ms: Optional[int], end_ms: Optional[int]):
        """Set the export range."""
        self.app_state.export_state.start_ms = start_ms
        self.app_state.export_state.end_ms = end_ms
    
    def get_export_range(self) -> Tuple[Optional[int], Optional[int]]:
        """Get the current export range."""
        return (
            self.app_state.export_state.start_ms,
            self.app_state.export_state.end_ms
        )
    
    def get_export_duration(self) -> int:
        """Get the duration of the current export range in milliseconds."""
        start_ms = self.app_state.export_state.start_ms
        end_ms = self.app_state.export_state.end_ms
        
        if start_ms is None or end_ms is None:
            return 0
        
        return max(0, end_ms - start_ms)
    
    def cancel_export(self):
        """Cancel the current export operation."""
        if self.export_worker:
            self.export_worker.stop()
        
        if self.progress_dialog:
            self.progress_dialog.close()
    
    def cleanup(self):
        """Clean up resources before shutdown."""
        self.cancel_export()
        self._cleanup_temp_files() 