"""
Timeline Manager for Sentry-Six.

Handles timeline operations including seeking, time calculations, and timeline state management.
"""

import os
import re
from typing import List, Optional, Callable
from datetime import datetime, timedelta

from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer
from PyQt6.QtWidgets import QWidget, QMessageBox

from .. import utils
from ..state import AppState, TimelineData
from .. import workers


class TimelineManager(QObject):
    """Manages timeline operations and seeking functionality."""
    
    # Signals
    timeline_loaded = pyqtSignal(TimelineData)
    timeline_cleared = pyqtSignal()
    seek_requested = pyqtSignal(int)  # global_ms
    
    def __init__(self, parent: QWidget, app_state: AppState, camera_map: dict):
        super().__init__(parent)
        self._parent = parent
        self.app_state = app_state
        self.camera_map = camera_map
        
        # Thread management
        self.clip_loader_thread: Optional[QThread] = None
        self.clip_loader_worker: Optional[workers.ClipLoaderWorker] = None
        
        # Callbacks
        self.on_timeline_loaded: Optional[Callable] = None
        self.on_loading_state_changed: Optional[Callable] = None
    
    def set_callbacks(self, on_timeline_loaded: Callable, on_loading_state_changed: Callable):
        """Set callback functions for timeline events."""
        self.on_timeline_loaded = on_timeline_loaded
        self.on_loading_state_changed = on_loading_state_changed
    
    def load_date(self, selected_date_str: str):
        """Load clips for a specific date."""
        if not self.app_state.root_clips_path:
            return
        
        self.clear_timeline()
        self._set_loading_state(True)
        
        self.clip_loader_worker = workers.ClipLoaderWorker(
            self.app_state.root_clips_path,
            selected_date_str,
            self.camera_map
        )
        self.clip_loader_thread = QThread()
        self.clip_loader_worker.moveToThread(self.clip_loader_thread)
        
        self.clip_loader_thread.started.connect(self.clip_loader_worker.run)
        self.clip_loader_worker.finished.connect(self._on_clips_loaded)
        self.clip_loader_thread.finished.connect(self.clip_loader_thread.deleteLater)
        self.clip_loader_worker.finished.connect(self.clip_loader_worker.deleteLater)
        
        self.clip_loader_thread.start()
    
    def _on_clips_loaded(self, data: TimelineData):
        """Handle loaded timeline data."""
        self._set_loading_state(False)
        
        if data.error:
            QMessageBox.warning(self._parent, "Could Not Load Date", data.error)
            return
        
        if data.first_timestamp_of_day is None:
            QMessageBox.warning(self._parent, "No Videos", "No valid video files found.")
            return
        
        # Update app state
        self.app_state.is_daily_view_active = True
        self.app_state.first_timestamp_of_day = data.first_timestamp_of_day
        self.app_state.daily_clip_collections = data.daily_clip_collections
        
        # Emit signals
        self.timeline_loaded.emit(data)
        
        # Call callback if set
        if self.on_timeline_loaded:
            self.on_timeline_loaded(data)
    
    def clear_timeline(self):
        """Clear the current timeline and stop any loading operations."""
        if self.clip_loader_thread and self.clip_loader_thread.isRunning() and self.clip_loader_worker:
            self.clip_loader_worker.stop()
            self.clip_loader_thread.quit()
            self.clip_loader_thread.wait()
        
        self.clip_loader_thread = None
        self.clip_loader_worker = None
        
        # Reset app state
        root_path = self.app_state.root_clips_path
        self.app_state = AppState()
        self.app_state.root_clips_path = root_path
        
        self.timeline_cleared.emit()
    
    def _set_loading_state(self, is_loading: bool):
        """Set the loading state and notify callbacks."""
        if self.on_loading_state_changed:
            self.on_loading_state_changed(is_loading)
    
    def seek_to_global_time(self, global_ms: int, restore_play_state: bool = False):
        """Seek to a specific global time in the timeline."""
        if not self.app_state.is_daily_view_active or not self.app_state.first_timestamp_of_day:
            return
        
        self.seek_requested.emit(global_ms)
    
    def preview_at_global_time(self, global_ms: int):
        """Preview at a specific global time without affecting main timeline."""
        if not self.app_state.is_daily_view_active or not self.app_state.first_timestamp_of_day:
            return
        
        target_dt = self.app_state.first_timestamp_of_day + timedelta(milliseconds=max(0, global_ms))
        front_clips = self.app_state.daily_clip_collections[self.camera_map["front"]]
        
        if not front_clips:
            return
        
        # Find target segment
        target_seg_idx = -1
        for i, clip_path in enumerate(front_clips):
            m = utils.filename_pattern.match(os.path.basename(clip_path))
            if m:
                clip_start_dt = datetime.strptime(f"{m.group(1)} {m.group(2).replace('-', ':')}", "%Y-%m-%d %H:%M:%S")
                if clip_start_dt <= target_dt:
                    target_seg_idx = i
                else:
                    break
        
        if target_seg_idx == -1:
            return
        
        # Calculate position within segment
        m = utils.filename_pattern.match(os.path.basename(front_clips[target_seg_idx]))
        if m:
            s_dt = datetime.strptime(f"{m.group(1)} {m.group(2).replace('-', ':')}", "%Y-%m-%d %H:%M:%S")
            pos_in_seg_ms = int((target_dt - s_dt).total_seconds() * 1000)
            
            # Emit signal for video player manager to handle
            self.seek_requested.emit(global_ms)
    
    def get_segment_for_time(self, global_ms: int) -> tuple[int, int]:
        """Get segment index and position within segment for a global time."""
        if not self.app_state.is_daily_view_active or not self.app_state.first_timestamp_of_day:
            return -1, 0
        
        target_dt = self.app_state.first_timestamp_of_day + timedelta(milliseconds=max(0, global_ms))
        front_clips = self.app_state.daily_clip_collections[self.camera_map["front"]]
        
        if not front_clips:
            return -1, 0
        
        # Find target segment
        target_seg_idx = -1
        for i, clip_path in enumerate(front_clips):
            m = utils.filename_pattern.match(os.path.basename(clip_path))
            if m:
                clip_start_dt = datetime.strptime(f"{m.group(1)} {m.group(2).replace('-', ':')}", "%Y-%m-%d %H:%M:%S")
                if clip_start_dt <= target_dt:
                    target_seg_idx = i
                else:
                    break
        
        if target_seg_idx == -1:
            return -1, 0
        
        # Calculate position within segment
        m = utils.filename_pattern.match(os.path.basename(front_clips[target_seg_idx]))
        if m:
            s_dt = datetime.strptime(f"{m.group(1)} {m.group(2).replace('-', ':')}", "%Y-%m-%d %H:%M:%S")
            pos_in_seg_ms = int((target_dt - s_dt).total_seconds() * 1000)
            return target_seg_idx, pos_in_seg_ms
        
        return target_seg_idx, 0
    
    def get_global_time_for_segment(self, segment_index: int, position_ms: int = 0) -> int:
        """Get global time for a specific segment and position."""
        if not self.app_state.is_daily_view_active or not self.app_state.first_timestamp_of_day:
            return 0
        
        front_clips = self.app_state.daily_clip_collections[self.camera_map["front"]]
        if not (0 <= segment_index < len(front_clips)):
            return 0
        
        m = utils.filename_pattern.match(os.path.basename(front_clips[segment_index]))
        if m:
            s_dt = datetime.strptime(f"{m.group(1)} {m.group(2).replace('-', ':')}", "%Y-%m-%d %H:%M:%S")
            segment_start_ms = int((s_dt - self.app_state.first_timestamp_of_day).total_seconds() * 1000)
            return segment_start_ms + position_ms
        
        return 0
    
    def get_timeline_duration(self) -> int:
        """Get the total duration of the current timeline in milliseconds."""
        if not self.app_state.is_daily_view_active:
            return 0
        
        return self.app_state.playback_state.segment_start_ms if hasattr(self.app_state, 'playback_state') else 0
    
    def get_events(self) -> List[dict]:
        """Get events for the current timeline."""
        if not self.app_state.is_daily_view_active:
            return []
        
        # This would need to be stored in the app state
        return []
    
    def cleanup(self):
        """Clean up resources before shutdown."""
        self.clear_timeline() 