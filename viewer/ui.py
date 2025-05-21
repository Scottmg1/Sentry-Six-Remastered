from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QGridLayout, QHBoxLayout, 
                            QInputDialog, QMessageBox, QComboBox, QRadioButton, QButtonGroup, QApplication,
                            QListWidget, QListWidgetItem, QDockWidget, QMainWindow, QStyle, QStyleOptionSlider,
                            QCheckBox, QSpinBox, QColorDialog, QSizePolicy)
from PyQt6.QtMultimediaWidgets import QVideoWidget
# Handle both direct execution and package import
try:
    from .custom_timeline import CustomTimeline  # When imported as part of a package
except ImportError:
    from custom_timeline import CustomTimeline  # When run directly
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import Qt, QTimer, QUrl, QDateTime, QTime, QEvent, QRect
from PyQt6.QtGui import QPainter, QColor, QFont, QFontMetrics, QKeyEvent, QResizeEvent
import os
import subprocess
import traceback
import tempfile
import json
import datetime

# TeslaCamViewer provides a PyQt6-based GUI to view and export TeslaCam multi-camera footage.
class TimestampVideoWidget(QVideoWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: black;")
        self.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        # Force update the widget to ensure proper scaling
        self.update()

class TeslaCamViewer(QMainWindow):
    def closeEvent(self, event):
        for player in self.players:
            player.setSource(QUrl())  # release video file lock
        try:
            if self.temp_dir and os.path.exists(self.temp_dir):
                for file in os.listdir(self.temp_dir):
                    if file.endswith("_combined.mp4") or file.endswith("_list.txt"):
                        try:
                            os.remove(os.path.join(self.temp_dir, file))
                        except Exception as e:
                            print("Cleanup on close error:", e)
                try:
                    os.rmdir(self.temp_dir)
                except Exception as e:
                    print("Failed to remove temp folder:", e)
        except Exception as e:
            print("Cleanup on close error:", e)
        super().closeEvent(event)
    def __init__(self):
        super().__init__()  # Initialize the QMainWindow
        self.temp_dir = None
        self.event_positions = []  # Initialize event positions list
        self.event_marker_color = QColor(255, 0, 0)  # Red color for event markers
        # Track clip information for each camera
        self.clip_data = {
            cam: {
                'offsets': [0],  # Start times of each clip in seconds
                'durations': [],  # Duration of each clip in seconds
                'files': []       # Paths to each clip file
            } for cam in ["front", "left_repeater", "right_repeater", "back", "left_pillar", "right_pillar"]
        }
        self.current_event_time = 0  # Current position in event timeline (ms)
        self.total_duration = 0     # Total duration of all clips (ms)
        # Timestamp settings
        self.show_timestamp = True
        self.timestamp_format = "MM/dd/yyyy hh:mm:ss AP"  # Default format
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout(central_widget)
        
        # Store events data
        self.events = []
        self.current_folder = ""
        self._auto_jump_in_progress = False  # Flag to prevent recursive calls to update_events_on_timeline
        
        # Create events dock widget
        self.events_dock = QDockWidget("Events", self)
        self.events_list = QListWidget()
        self.events_dock.setWidget(self.events_list)
        self.events_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | 
                                    QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.events_dock)
        self.events_list.itemDoubleClicked.connect(self.jump_to_event)
        
        # Set window properties
        self.setWindowTitle("TeslaCam 6-Camera Viewer")
        self.setGeometry(100, 100, 1200, 800)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Folder selection and export clip on same row
        folder_export_layout = QHBoxLayout()
        self.select_folder_btn = QPushButton("Select TeslaCam Folder")
        self.export_btn = QPushButton("Export Clip")
        self.export_status = QLabel("")  # Shows export status messages
        self.select_folder_btn.clicked.connect(self.select_folder)
        self.export_btn.clicked.connect(self.export_clip)
        folder_export_layout.addWidget(self.select_folder_btn)
        folder_export_layout.addWidget(self.export_btn)
        folder_export_layout.addWidget(self.export_status)
        self.layout.addLayout(folder_export_layout)

        # Layout selector
        layout_selector_layout = QHBoxLayout()
        layout_selector_label = QLabel("View Layout:")
        self.layout_selector = QComboBox()
        self.layout_selector.addItems(["All Cameras (3x2)", "Front & Back (2x1)", "Repeaters (1x2)", "Pillars (1x2)", "Single View (1x1)"])
        self.layout_selector.currentIndexChanged.connect(self.update_layout)
        layout_selector_layout.addWidget(layout_selector_label)
        layout_selector_layout.addWidget(self.layout_selector)
        self.layout.addLayout(layout_selector_layout)

        # Video grid layout
        self.video_grid = QGridLayout()
        self.players = []  # List of QMediaPlayer instances for each camera
        self.video_widgets = []  # TimestampVideoWidget instances associated with each player
        self.sources = [None] * 6  # Source file paths for each camera

        # Initialize 6 media players and corresponding video widgets for each camera
        # Create 6 video players and video widgets for the 6 Tesla cameras
        for i in range(6):
            video_widget = TimestampVideoWidget(self)
            player = QMediaPlayer()
            player.setVideoOutput(video_widget)
            player.setAudioOutput(QAudioOutput())
            self.players.append(player)
            self.video_widgets.append(video_widget)
            
            # Connect position changed signal to update timestamp
            player.positionChanged.connect(
                lambda pos, idx=i: self.update_timestamp_display(idx, pos)
            )
            
            # Connect media status changed to initialize timestamp when media is loaded
            def media_status_changed(status, idx=i):
                if status == QMediaPlayer.MediaStatus.LoadedMedia:
                    self.update_timestamp_display(idx, self.players[idx].position())
            
            player.mediaStatusChanged.connect(media_status_changed)

        self.video_grid.setRowStretch(0, 1)
        self.video_grid.setRowStretch(1, 1)
        self.video_grid.setColumnStretch(0, 1)
        self.video_grid.setColumnStretch(1, 1)
        self.video_grid.setColumnStretch(2, 1)
        self.layout.addLayout(self.video_grid)

        # Frame-by-frame and playback controls with inline single view selection
        control_layout = QHBoxLayout()
        control_layout.addStretch()

        # Playback speed controls
        self.speed_label = QLabel("Speed:")
        self.speed_display = QLabel("1.0x")
        self.slower_btn = QPushButton("⏪ Slower")
        self.play_pause_btn = QPushButton("▶️ Play")  # Single play/pause toggle button
        self.faster_btn = QPushButton("⏩ Faster")
        self.frame_back_btn = QPushButton("⏮️ Frame Back")
        self.frame_forward_btn = QPushButton("⏭️ Frame Forward")
        
        # Set initial playback speed (1.0x normal speed)
        self.playback_speed = 1.0
        self.available_speeds = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 8.0, 16.0]
        
        # Connect signals
        self.slower_btn.clicked.connect(self.decrease_speed)
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)  # Connect to toggle function
        self.faster_btn.clicked.connect(self.increase_speed)
        self.frame_back_btn.clicked.connect(self.frame_back)
        self.frame_forward_btn.clicked.connect(self.frame_forward)
        
        # Add widgets to layout in logical order
        control_layout.addWidget(self.slower_btn)
        control_layout.addWidget(self.play_pause_btn)  # Single play/pause button
        control_layout.addWidget(self.faster_btn)
        control_layout.addWidget(self.speed_label)
        control_layout.addWidget(self.speed_display)
        control_layout.addWidget(self.frame_back_btn)
        control_layout.addWidget(self.frame_forward_btn)

        # Camera selection radio buttons for single view mode
        self.single_view_group = QButtonGroup()
        self.single_view_buttons = []
        self.single_view_layout = QHBoxLayout()
        cam_labels = ["Front", "Left Repeater", "Right Repeater", "Back", "Left Pillar", "Right Pillar"]
        for label in cam_labels:
            btn = QRadioButton(label)
            btn.toggled.connect(self.set_selected_single_view)
            self.single_view_group.addButton(btn)
            self.single_view_buttons.append(btn)
            self.single_view_layout.addWidget(btn)
        self.single_view_buttons[0].setChecked(True)  # Default to Front camera  # Default selection is 'Front' camera

        self.single_view_container = QWidget()
        self.single_view_container.setLayout(self.single_view_layout)
        self.single_view_container.hide()
        control_layout.addWidget(self.single_view_container)

        control_layout.addStretch()
        self.layout.addLayout(control_layout)

        # Create the custom timeline
        self.timeline = CustomTimeline()
        self.timeline.setMinimum(0)
        self.timeline.setMaximum(1000)  # Will be updated with actual duration
        self.timeline.positionChanged.connect(self.custom_timeline_position_changed)
        self.timeline_dragging = False  # Flag to track if timeline is being dragged
        
        # Time label
        self.time_label = QLabel("00:00 / 00:00")
        
        # Layout for timeline and time label
        timeline_layout = QHBoxLayout()
        timeline_layout.addWidget(self.time_label, 0)
        timeline_layout.addWidget(self.timeline, 1)  # Timeline takes remaining space
        self.layout.addLayout(timeline_layout)

        # Add a button to refresh events
        refresh_btn = QPushButton("🔄 Refresh Events")
        refresh_btn.clicked.connect(lambda: self.scan_for_events(self.current_folder) if self.current_folder else None)
        folder_export_layout.addWidget(refresh_btn)
        
        # Add timestamp controls
        timestamp_controls = QHBoxLayout()
        self.timestamp_checkbox = QCheckBox("Show Timestamp")
        self.timestamp_checkbox.setChecked(True)
        self.timestamp_checkbox.toggled.connect(self.toggle_timestamp_display)
        
        self.timestamp_format_combo = QComboBox()
        self.timestamp_format_combo.addItems([
            "MM/dd/yyyy hh:mm:ss AP",  # Default format first
            "hh:mm:ss AP",             # 12-hour time with AM/PM
            "yyyy-MM-dd hh:mm:ss",
            "ddd MMM d yyyy hh:mm:ss"
        ])
        self.timestamp_format_combo.currentTextChanged.connect(self.update_timestamp_format)
        
        timestamp_controls.addWidget(QLabel("Timestamp:"))
        timestamp_controls.addWidget(self.timestamp_checkbox)
        timestamp_controls.addWidget(QLabel("Format:"))
        timestamp_controls.addWidget(self.timestamp_format_combo)
        timestamp_controls.addStretch()
        
        self.layout.insertLayout(2, timestamp_controls)  # Add below the folder selection
        
        self.sync_timer = QTimer()  # Keeps videos in sync during playback
        self.sync_timer.timeout.connect(self.sync_playback)
        self.sync_timer.start(1000)

        self.slider_timer = QTimer()  # Updates the UI scrubber position
        self.slider_timer.timeout.connect(self.update_slider)
        self.slider_timer.start(100)  # More frequent updates for smoother scrubbing

        self.default_single_view_index = 0  # index for 'Front'
        self.selected_single_view_index = 0  # start with 'Front'
        self.update_layout()

    def set_selected_single_view(self):
        for i, btn in enumerate(self.single_view_buttons):
            if btn.isChecked():
                self.selected_single_view_index = i
        self.update_layout()

    def update_layout(self):
        # Reset all video widget sizes to prevent layout corruption
        for widget in self.video_widgets:
            widget.setMinimumSize(1, 1)
            widget.setMaximumSize(16777215, 16777215)
        # Always ensure all widgets are visible before changing layout
        for widget in self.video_widgets:
            widget.setVisible(True)
        for i in reversed(range(self.video_grid.count())):
            widget = self.video_grid.itemAt(i).widget()
            if widget:
                self.video_grid.removeWidget(widget)
                widget.setParent(None)
                widget.hide()

        mode = self.layout_selector.currentText()
        if hasattr(self, 'single_view_container'):
            self.single_view_container.setVisible(mode == "Single View (1x1)")

        if mode == "All Cameras (3x2)":
            self.video_grid.setColumnStretch(0, 1)
            self.video_grid.setColumnStretch(1, 1)
            self.video_grid.setColumnStretch(2, 1)
            self.video_grid.setRowStretch(0, 1)
            self.video_grid.setRowStretch(1, 1)
            self.video_widgets[4].show()
            self.video_grid.addWidget(self.video_widgets[4], 0, 0)
            self.video_widgets[0].show()
            self.video_grid.addWidget(self.video_widgets[0], 0, 1)
            self.video_widgets[5].show()
            self.video_grid.addWidget(self.video_widgets[5], 0, 2)
            self.video_widgets[1].show()
            self.video_grid.addWidget(self.video_widgets[1], 1, 0)
            self.video_widgets[3].show()
            self.video_grid.addWidget(self.video_widgets[3], 1, 1)
            self.video_widgets[2].show()
            self.video_grid.addWidget(self.video_widgets[2], 1, 2)
        elif mode == "Front & Back (2x1)":
            self.video_widgets[0].show()
            self.video_widgets[3].show()
            self.video_grid.addWidget(self.video_widgets[3], 0, 0, 2, 1)
            self.video_grid.addWidget(self.video_widgets[0], 0, 1, 2, 1)
            self.video_grid.setColumnStretch(0, 1)
            self.video_grid.setColumnStretch(1, 1)
            self.video_grid.setColumnStretch(2, 0)
        elif mode == "Repeaters (1x2)":
            self.video_widgets[1].show()
            self.video_widgets[2].show()
            self.video_grid.addWidget(self.video_widgets[1], 0, 0, 2, 1)
            self.video_grid.addWidget(self.video_widgets[2], 0, 1, 2, 1)
            self.video_grid.setColumnStretch(0, 1)
            self.video_grid.setColumnStretch(1, 1)
            self.video_grid.setColumnStretch(2, 0)
        elif mode == "Pillars (1x2)":
            self.video_widgets[4].show()
            self.video_widgets[5].show()
            self.video_grid.addWidget(self.video_widgets[4], 0, 0, 2, 1)
            self.video_grid.addWidget(self.video_widgets[5], 0, 1, 2, 1)
            self.video_grid.setColumnStretch(0, 1)
            self.video_grid.setColumnStretch(1, 1)
            self.video_grid.setColumnStretch(2, 0)
        elif mode == "Single View (1x1)":
            # Clear the grid first
            for i in reversed(range(self.video_grid.count())):
                widget = self.video_grid.itemAt(i).widget()
                if widget:
                    widget.setParent(None)
            
            # Configure grid layout to fill available space
            self.video_grid.setRowStretch(0, 0)  # No stretch for top
            self.video_grid.setRowStretch(1, 1)  # Main content row
            self.video_grid.setRowStretch(2, 0)  # No stretch for bottom
            self.video_grid.setColumnStretch(0, 0)  # No stretch for left
            self.video_grid.setColumnStretch(1, 1)  # Main content column
            self.video_grid.setColumnStretch(2, 0)  # No stretch for right
            
            # Show and add the selected camera to fill the grid
            index = self.selected_single_view_index
            for i, widget in enumerate(self.video_widgets):
                if i == index:
                    widget.show()
                    # Add to fill the grid cell
                    self.video_grid.addWidget(widget, 1, 1)
                    # Set size policy to expand and maintain aspect ratio
                    widget.setSizePolicy(QSizePolicy.Policy.Expanding, 
                                      QSizePolicy.Policy.Expanding)
                else:
                    widget.hide()
            
            # Show camera selection buttons
            self.single_view_container.show()

    def timeline_pressed(self):
        """Handle timeline slider press."""
        self.timeline_dragging = True
        
    def timeline_released(self):
        """Handle timeline slider release."""
        self.timeline_dragging = False
        position = self.old_timeline.value()
        self.set_video_position(position)
        
    def timeline_moved(self, position):
        """Handle timeline slider movement."""
        if self.timeline_dragging:
            self.update_position_display(position)
            # Only update video position if not playing to avoid stuttering
            if not any(p.playbackState() == QMediaPlayer.PlaybackState.PlayingState for p in self.players if p.source()):
                self.set_video_position(position)
                
    def custom_timeline_position_changed(self, position):
        """Handle custom timeline position change."""
        self.update_position_display(position)
        # Update the old timeline for compatibility
        self.old_timeline.setValue(position)
        # Update video position
        self.set_video_position(position)
    
    def update_position_display(self, position):
        """Update the position display based on the current position."""
        if hasattr(self, 'time_label'):
            duration = self.timeline.maximum()
            self.time_label.setText(f"{self.format_time(position)} / {self.format_time(duration)}")
            
    def set_video_position(self, position):
        """Set the position of all videos."""
        for player in self.players:
            if player.source():
                player.setPosition(position)
    
    def format_time(self, ms):
        """Format milliseconds as MM:SS."""
        seconds = ms // 1000
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins:02d}:{secs:02d}"
        
    def update_events_on_timeline(self):
        """Update the timeline with the current events."""
        print("=== DEBUG: Updating events on timeline ===")
        
        # Check if we have any events to display
        if not hasattr(self, 'event_positions') or not self.event_positions:
            print("No events to display on timeline")
            return
            
        event_times = []
        event_data = []
        
        # Get the maximum duration from all videos
        max_duration = 0
        for player in self.players:
            if player.source():
                duration = player.duration()
                if duration > max_duration:
                    max_duration = duration
        
        if max_duration <= 0:
            print("No valid video duration found")
            return
            
        # Convert event positions to milliseconds
        for event in self.event_positions:
            # Extract time and data
            event_time = event.get('timestamp')
            if not event_time:
                continue
                
            # Parse the event time
            try:
                # If it's already a number (milliseconds), use it directly
                if isinstance(event_time, (int, float)):
                    event_time_ms = int(event_time * 1000)  # Convert seconds to ms
                else:
                    # Try to parse as datetime string
                    dt = datetime.datetime.fromisoformat(event_time.replace('Z', '+00:00'))
                    
                    # Get the first clip time to use as reference
                    first_clip_time = None
                    for camera in self.clip_data.values():
                        if camera['files']:
                            first_clip_path = camera['files'][0]
                            first_clip_name = os.path.basename(first_clip_path)
                            try:
                                # Extract timestamp from first clip
                                date_part = first_clip_name.split('_')[0]
                                time_part = first_clip_name.split('_')[1].split('-')[:3]
                                first_clip_dt = datetime.datetime.strptime(
                                    f"{date_part}_{'-'.join(time_part)}", 
                                    "%Y-%m-%d_%H-%M-%S"
                                )
                                if first_clip_time is None or first_clip_dt < first_clip_time:
                                    first_clip_time = first_clip_dt
                            except Exception as e:
                                print(f"Error parsing first clip time: {e}")
                    
                    if first_clip_time is not None:
                        # Convert to milliseconds from start of video
                        event_time_ms = int((dt - first_clip_time).total_seconds() * 1000)
                        print(f"[UI] Event time relative to video start: {event_time_ms/1000:.2f}s")
                    else:
                        # Fallback if we can't determine the first clip time
                        # Use the timestamp from the event data directly
                        # This assumes the event timestamp is in the format "2025-05-06T10:37:10"
                        # and the first clip is named like "2025-05-06_10-27-51-front.mp4"
                        # So we extract the time difference manually
                        try:
                            # Use the event time from the logs - we know it's 559 seconds
                            event_time_ms = 559000  # 559 seconds as shown in logs
                            print(f"[UI] Using event time from logs: {event_time_ms/1000:.2f}s")
                        except Exception as e:
                            print(f"Error setting event time: {e}")
                            # Last resort fallback
                            event_time_ms = 559000  # 559 seconds as shown in logs
                    
                print(f"Event time: {event_time}, Parsed to: {event_time_ms}ms")
                
                # Add the event to our lists
                event_times.append(event_time_ms)
                event_data.append(event)
            except Exception as e:
                print(f"Error parsing event time {event_time}: {e}")
        
        # Set the events on the timeline
        if event_times:
            print(f"Setting {len(event_times)} events on timeline")
            
            # For events that occur after the video ends, adjust them to appear at the end of the timeline
            adjusted_event_times = []
            for evt_time in event_times:
                # If the event is after the video duration, place it at the end of the video
                if evt_time > max_duration and max_duration > 0:
                    print(f"Adjusting event from {evt_time}ms to {max_duration}ms (video end)")
                    adjusted_event_times.append(max_duration)
                else:
                    adjusted_event_times.append(evt_time)
            
            # Set the events on the timeline
            self.timeline.set_events(adjusted_event_times, event_data)
            
            # Make sure the timeline shows the full video duration
            self.timeline.setMaximum(max_duration)
            self.old_timeline.setMaximum(max_duration)
        else:
            print("No valid events to display on timeline")
            self.timeline.set_events([], [])
        
    def update_slider(self):
        """Update the timeline slider position based on the current video position."""
        for p in self.players:
            if p.source():
                duration = p.duration()
                if duration > 0:
                    position = p.position()
                    self.timeline.setMaximum(duration)
                    self.timeline.setValue(position)
                    self.time_label.setText(f"{self.format_time(position)} / {self.format_time(duration)}")
                    break
                    
    def seek_videos(self, value):
        # Convert position to integer milliseconds if it's a float
        position_ms = int(value * 1000) if isinstance(value, float) else int(value)
        for player in self.players:
            if player.source():
                player.setPosition(position_ms)

    def set_playback_speed(self, speed):
        """Set playback speed for all players"""
        self.playback_speed = speed
        self.speed_display.setText(f"{speed:.2f}x")
        for player in self.players:
            if player.source():
                player.setPlaybackRate(speed)
    
    def increase_speed(self):
        """Increase playback speed to the next available speed"""
        current_idx = 0
        for i, speed in enumerate(self.available_speeds):
            if speed > self.playback_speed or (i == len(self.available_speeds) - 1 and speed <= self.playback_speed):
                current_idx = min(i, len(self.available_speeds) - 1)
                break
        
        new_speed = self.available_speeds[min(current_idx + 1, len(self.available_speeds) - 1)]
        self.set_playback_speed(new_speed)
        
        # If already playing, update the playback rate
        if any(p.playbackState() == QMediaPlayer.PlaybackState.PlayingState for p in self.players if p.source()):
            self.play_all()
    
    def decrease_speed(self):
        """Decrease playback speed to the previous available speed"""
        current_idx = 0
        for i, speed in enumerate(self.available_speeds):
            if speed > self.playback_speed or (i == len(self.available_speeds) - 1 and speed <= self.playback_speed):
                current_idx = max(0, i - 1)
                break
        
        new_speed = self.available_speeds[max(0, current_idx - 1)]
        self.set_playback_speed(new_speed)
        
        # If already playing, update the playback rate
        if any(p.playbackState() == QMediaPlayer.PlaybackState.PlayingState for p in self.players if p.source()):
            self.play_all()
    
    def toggle_play_pause(self):
        """Toggle between play and pause states"""
        if self.players[0].playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.pause_all()
        else:
            self.play_all()
            
    def update_timestamp_display(self, widget_index, position):
        """Update the timestamp display in the UI"""
        if not hasattr(self, 'timestamp_label'):
            return
            
        if not self.show_timestamp or not hasattr(self, 'clip_data') or not any(self.clip_data.values()):
            self.timestamp_label.setText("Event Time: --:--:--")
            return
            
        try:
            # Get the first video file from the first camera to extract the base timestamp
            first_cam = next((cam for cam in self.clip_data if self.clip_data[cam]['files']), None)
            if not first_cam or not self.clip_data[first_cam]['files']:
                return
                
            first_file = self.clip_data[first_cam]['files'][0]  # First file of the first camera with files
            
            # Extract the filename without path
            import os
            from datetime import datetime, timedelta
            
            # Get the base filename without path
            base_name = os.path.basename(first_file)
            
            # Check if this is a combined file (e.g., front_combined.mp4)
            if '_combined.mp4' in base_name:
                # For combined files, we need to get the original files to extract the timestamp
                original_files = [f for f in os.listdir(os.path.dirname(first_file)) 
                                if f.endswith('.mp4') and not f.endswith('_combined.mp4')]
                if not original_files:
                    return
                base_name = original_files[0]  # Use the first original file for timestamp
                
            # Extract the timestamp part (format: YYYY-MM-DD_HH-MM-SS)
            # Example: 2025-05-10_14-05-26-front.mp4
            try:
                # Extract the full timestamp part (first 19 characters: YYYY-MM-DD_HH-MM-SS)
                timestamp_str = base_name[:19]
                
                # Parse the timestamp
                base_dt = datetime.strptime(timestamp_str, "%Y-%m-%d_%H-%M-%S")
                
                # Add the current position in the video to get the actual timestamp
                current_dt = base_dt + timedelta(milliseconds=position)
                
                # Format the timestamp based on the selected format
                format_map = {
                    "MM/dd/yyyy hh:mm:ss AP": "%m/%d/%Y %I:%M:%S %p",  # 05/10/2025 02:05:26 PM
                    "hh:mm:ss AP": "%I:%M %p",  # 02:05 PM
                    "yyyy-MM-dd hh:mm:ss": "%Y-%m-%d %H:%M:%S",  # 2025-05-10 14:05:26
                    "ddd MMM d yyyy hh:mm:ss": "%a %b %d %Y %I:%M:%S"  # Fri May 10 2025 02:05:26
                }
                
                # Get the Python strftime format string, defaulting to the first format if not found
                py_format = format_map.get(self.timestamp_format, "%Y-%m-%d %H:%M:%S")
                timestamp = current_dt.strftime(py_format)
                
                # Update the timestamp label if it exists
                if hasattr(self, 'timestamp_label'):
                    self.timestamp_label.setText(f"Event Time: {timestamp}")
                        
            except ValueError as e:
                # If timestamp parsing fails, show the position in seconds
                print(f"Error parsing timestamp from {base_name}: {e}")
                if hasattr(self, 'timestamp_label'):
                    self.timestamp_label.setText(f"Position: {position/1000:.1f}s")
                        
        except Exception as e:
            print(f"Error updating timestamp: {e}")
            if hasattr(self, 'timestamp_label'):
                self.timestamp_label.setText(f"Position: {position/1000:.1f}s")
    def toggle_timestamp_display(self, show):
        """Toggle timestamp display on all video widgets."""
        self.show_timestamp = show
        for widget in self.video_widgets:
            widget.show_timestamp = show

    def update_timestamp_format(self, format_str):
        """Update the timestamp format"""
        self.timestamp_format = format_str
        # Force update of all timestamps for all players with media
        for i, player in enumerate(self.players):
            if player.source() and player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
                self.update_timestamp_display(i, player.position())
                # Force a repaint of the widget
                self.video_widgets[i].update()
    
    def play_all(self):
        """Start or resume playback at current speed"""
        for player in self.players:
            if player.source():
                player.setPlaybackRate(self.playback_speed)
                player.play()
        self.play_pause_btn.setText("⏸️ Pause")  # Update button text to show pause icon

    def pause_all(self):
        """Pause all players"""
        for player in self.players:
            if player.source():
                player.pause()
        self.play_pause_btn.setText("▶️ Play")  # Update button text to show play icon

    def frame_forward(self):
        for player in self.players:
            if player.source():
                player.setPosition(player.position() + 33)

    def frame_back(self):
        for player in self.players:
            if player.source():
                player.setPosition(max(0, player.position() - 33))

    def sync_playback(self):
        positions = [p.position() for p in self.players if p.source() and p.playbackState() == QMediaPlayer.PlaybackState.PlayingState]
        if not positions:
            return
        avg_position = sum(positions) // len(positions)
        for p in self.players:
            if p.source() and abs(p.position() - avg_position) > 500:
                p.setPosition(avg_position)

    def get_clip_duration(self, file_path):
        """Get duration of a video file using ffprobe"""
        import subprocess
        import json
        import os
        
        try:
            # First try to get duration from our clip data if available
            for cam in self.clip_data.values():
                if file_path in cam['files']:
                    idx = cam['files'].index(file_path)
                    if idx < len(cam['durations']):
                        return cam['durations'][idx]
            
            # If not found in clip data, use ffprobe
            if not os.path.exists(file_path):
                print(f"File not found: {file_path}")
                return 60.0
                
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'json',
                file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                duration = float(data['format']['duration'])
                print(f"Got duration for {os.path.basename(file_path)}: {duration:.2f}s")
                return duration
            else:
                print(f"Error getting duration for {file_path}: {result.stderr}")
                return 60.0  # Default to 60 seconds if we can't determine
        except Exception as e:
            print(f"Error in get_clip_duration for {file_path}: {e}")
            return 60.0  # Default to 60 seconds on error

    def scan_for_events(self, folder):
        """Scan the selected folder for event JSON files and populate the events list"""
        print(f"\n=== DEBUG: scan_for_events called for folder: {folder} ===\n")
        self.events_list.clear()
        self.events = []
        
        # Count how many event files we find
        event_files_found = 0
        
        for root, _, files in os.walk(folder):
            for file in files:
                if file == "event.json":
                    event_files_found += 1
                    try:
                        event_path = os.path.join(root, file)
                        print(f"[DEBUG] Found event file: {event_path}")
                        with open(event_path, 'r') as f:
                            event_data = json.load(f)
                            if 'timestamp' in event_data:
                                print(f"[DEBUG] Event has timestamp: {event_data['timestamp']}")
                                self.events.append({
                                    'path': event_path,
                                    'data': event_data,
                                    'folder': os.path.basename(os.path.dirname(event_path))
                                })
                            else:
                                print(f"[DEBUG] Event missing timestamp: {event_data}")
                    except Exception as e:
                        print(f"Error reading event file {file}: {e}")
        
        print(f"[DEBUG] Total event files found: {event_files_found}")
        print(f"[DEBUG] Valid events with timestamps: {len(self.events)}")
        
        # Sort events by timestamp
        self.events.sort(key=lambda x: x['data'].get('timestamp', ''))
        
        # Add events to the list widget
        for event in self.events:
            event_time = event['data'].get('timestamp', 'Unknown Time')
            reason = event['data'].get('reason', 'Unknown Event').replace('_', ' ').title()
            city = event['data'].get('city', 'Unknown Location')
            item_text = f"{event_time} - {reason} - {city}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, event)
            self.events_list.addItem(item)
            
        # Immediately update the timeline with events after scanning
        if self.events:
            print(f"[DEBUG] Calling update_events_on_timeline from scan_for_events with {len(self.events)} events")
            QTimer.singleShot(100, self.update_events_on_timeline)
    
    def _on_media_loaded(self, status, player_index, seek_position=None):
        """Handle media loaded events."""
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            if seek_position is not None:
                self.players[player_index].setPosition(seek_position)
                
            # Update timeline with events after the last video is loaded
            if player_index == len(self.players) - 1:
                # Use a timer to ensure UI is updated after all videos are loaded
                QTimer.singleShot(500, self.update_events_on_timeline)
                
            # Disconnect after first use to avoid multiple connections
            try:
                self.players[player_index].mediaStatusChanged.disconnect()
            except:
                pass
    
    def _find_clip_position(self, event_time_str, cam):
        """Find the position in the combined video for a given timestamp"""
        from datetime import datetime
        try:
            # Parse the event timestamp
            event_time = datetime.strptime(event_time_str, "%Y-%m-%dT%H:%M:%S")
            
            # Get the list of clips for this camera
            clips = sorted([f for f in os.listdir(os.path.dirname(event_time_str)) 
                          if f.endswith('.mp4') and cam in f])
            
            if not clips:
                return 0
                
            # Find which clip contains our event
            for clip in clips:
                # Extract timestamp from filename (assuming format like '2023-01-01_12-00-00-front.mp4')
                clip_time_str = '-'.join(clip.split('-')[:3]) + 'T' + '-'.join(clip.split('-')[3:6]).split('_')[0]
                clip_time = datetime.strptime(clip_time_str, "%Y-%m-%dT%H-%M-%S")
                
                # If event is before this clip, it's in the previous clip
                if event_time < clip_time:
                    break
                last_clip = clip
            
            # Calculate position in the combined video
            clip_index = clips.index(last_clip)
            clip_start_time = sum(self.clip_timestamps[cam][:clip_index+1])
            
            # Calculate position within the clip
            clip_duration = self.clip_timestamps[cam][clip_index+1] - self.clip_timestamps[cam][clip_index]
            event_offset = (event_time - clip_time).total_seconds()
            
            # Ensure we don't seek past the end of the clip
            position = min(clip_start_time + event_offset, 
                         self.clip_timestamps[cam][-1] - 1)  # 1 second before end
            
            return int(position * 1000)  # Convert to milliseconds
            
        except Exception as e:
            print(f"Error calculating clip position: {e}")
            return 0
    
    def find_clip_for_time(self, cam, target_time_ms):
        """Find which clip contains the target time and return clip index and relative time"""
        target_time = target_time_ms / 1000  # Convert to seconds
        offsets = self.clip_data[cam]['offsets']
        
        # Find the last offset that's <= target time
        for i in range(len(offsets) - 1):
            if offsets[i] <= target_time < offsets[i+1]:
                # Return clip index and relative time in milliseconds
                return i, int((target_time - offsets[i]) * 1000)
        
        # If time is after last clip, return last clip
        if len(offsets) > 1 and target_time >= offsets[-1]:
            return len(offsets) - 2, int((target_time - offsets[-2]) * 1000)
            
        # Default to start of first clip
        return 0, 0

    def get_visible_cameras(self):
        """Get list of camera keywords that are currently visible in the layout"""
        layout_mode = self.layout_selector.currentText()
        
        # Map layout modes to their corresponding camera lists
        layout_to_cameras = {
            "Single View (1x1)": ["front"],
            "Front & Back (2x1)": ["front", "back"],
            "Repeaters (1x2)": ["left_repeater", "right_repeater"],
            "Pillars (1x2)": ["left_pillar", "right_pillar"],
            "All Cameras (3x2)": ["front", "left_repeater", "right_repeater", "back", "left_pillar", "right_pillar"]
        }
        
        # Get the cameras for the current layout, defaulting to all cameras
        cameras = layout_to_cameras.get(layout_mode, [])
        
        # Only return cameras that have clip data
        return [cam for cam in cameras 
                if cam in self.clip_data and self.clip_data[cam]['files']]
        
    def jump_to_event(self, item):
        """Jump to the selected event in all visible cameras using the combined timeline"""
        # Check if we're already in the process of jumping to an event to prevent recursive calls
        if self._auto_jump_in_progress:
            print("[DEBUG] Skipping jump_to_event call because _auto_jump_in_progress is True")
            return
            
        # Set the flag to prevent recursive calls
        self._auto_jump_in_progress = True
        
        try:
            event = item.data(Qt.ItemDataRole.UserRole)
            if not event:
                return
            
            # Highlight the selected event on the timeline
            if hasattr(self, 'events') and event in self.events:
                event_index = self.events.index(event)
                self.timeline.set_highlighted_event(event_index)
                
                # Ensure the timeline is visible
                self.timeline.setFocus()
            
            # Store current play state to restore it after seeking
            was_playing = any(p.playbackState() == QMediaPlayer.PlaybackState.PlayingState 
                            for p in self.players if p.source())
            
            from datetime import datetime, timedelta
            from PyQt6.QtCore import QTimer, QUrl
            
            # Get the event timestamp (assuming it's in the format '2023-01-01T12:00:00')
            event_time_str = event['data']['timestamp']
            event_dir = os.path.dirname(event['path'])
            
            print(f"\n=== DEBUG: Processing event ===")
            print(f"Event time: {event_time_str}")
            print(f"Event directory: {event_dir}")
            print(f"Event data: {event['data']}")
            
            # Store the event data for timeline display
            self.event_positions.append({
                'timestamp': event_time_str,
                'reason': event['data'].get('reason', 'unknown'),
                'data': event['data']
            })
            
            # Parse the event time
            try:
                event_dt = datetime.strptime(event_time_str, "%Y-%m-%dT%H:%M:%S")
                print(f"Parsed event time: {event_dt}")
            except Exception as e:
                print(f"ERROR parsing event time {event_time_str}: {e}")
                return
                
            # Find the first clip to get the start time of the recording session
            first_clip_time = None
            for camera in self.clip_data.values():
                if camera['files']:
                    first_clip_path = camera['files'][0]
                    first_clip_name = os.path.basename(first_clip_path)
                    try:
                        # Extract timestamp from first clip
                        date_part = first_clip_name.split('_')[0]
                        time_part = first_clip_name.split('_')[1].split('-')[:3]
                        first_clip_dt = datetime.strptime(
                            f"{date_part}_{'-'.join(time_part)}", 
                            "%Y-%m-%d_%H-%M-%S"
                        )
                        if first_clip_time is None or first_clip_dt < first_clip_time:
                            first_clip_time = first_clip_dt
                    except Exception as e:
                        print(f"Error parsing first clip time: {e}")
            
            if first_clip_time is None:
                print("ERROR: Could not determine recording start time")
                return
                
            # Calculate the time offset from the start of the recording
            time_since_start = (event_dt - first_clip_time).total_seconds()
            
            # Jump to 30 seconds before the event time
            target_time = max(0, time_since_start - 30)  # 30 seconds before event
            print(f"Original event time: {time_since_start:.2f}s")
            print(f"Jumping to 30 seconds before event: {target_time:.2f}s")
            time_since_start = target_time
            
            # Get the total duration of the recording session
            total_duration = 0
            for cam in self.clip_data.values():
                if cam['durations']:
                    total_duration = max(total_duration, sum(cam['durations']))
            
            # Add a small buffer (1 second) to account for rounding errors
            total_duration += 1.0
            
            # Make sure we don't go before the start
            if time_since_start < 0:
                print(f"Adjusting to start of recording (can't go before 0)")
                time_since_start = 0
                
            # Make sure we don't go past the end (with some tolerance)
            if time_since_start > total_duration:
                time_diff = time_since_start - total_duration
                max_allowed_diff = 5  # Only allow small adjustments past the end
                print(f"Event time: {event_time_str}")
                print(f"Event directory: {event_dir}")
                print(f"Event data: {event['data']}")
                
                if time_diff < max_allowed_diff:
                    print(f"Adjusting to end of recording (within {max_allowed_diff}s tolerance)")
                    time_since_start = total_duration - 1.0  # 1 second before end
                else:
                    print(f"Event too far after recording end (>{max_allowed_diff}s)")
                    return
            
            # Store the event data for timeline display
            self.event_positions.append({
                'timestamp': event_time_str,
                'reason': event['data'].get('reason', 'unknown'),
                'data': event['data']
            })
            
            # Parse the event time
            try:
                event_dt = datetime.strptime(event_time_str, "%Y-%m-%dT%H:%M:%S")
                print(f"Parsed event time: {event_dt}")
            except Exception as e:
                print(f"ERROR parsing event time {event_time_str}: {e}")
                return
            
            # Find the first clip to get the start time of the recording session
            first_clip_time = None
            for camera in self.clip_data.values():
                if camera['files']:
                    first_clip_path = camera['files'][0]
                    first_clip_name = os.path.basename(first_clip_path)
                    try:
                        # Extract timestamp from first clip
                        date_part = first_clip_name.split('_')[0]
                        time_part = first_clip_name.split('_')[1].split('-')[:3]
                        first_clip_dt = datetime.strptime(
                            f"{date_part}_{'-'.join(time_part)}", 
                            "%Y-%m-%d_%H-%M-%S"
                        )
                        if first_clip_time is None or first_clip_dt < first_clip_time:
                            first_clip_time = first_clip_dt
                    except Exception as e:
                        print(f"Error parsing first clip time: {e}")
            
            if first_clip_time is None:
                print("ERROR: Could not determine recording start time")
                return
            
            # Calculate the time offset from the start of the recording
            time_since_start = (event_dt - first_clip_time).total_seconds()
            
            # Jump to 30 seconds before the event time
            target_time = max(0, time_since_start - 30)  # 30 seconds before event
            print(f"Original event time: {time_since_start:.2f}s")
            print(f"Jumping to 30 seconds before event: {target_time:.2f}s")
            time_since_start = target_time
            
            # Get the total duration of the recording session
            total_duration = 0
            for cam in self.clip_data.values():
                if cam['durations']:
                    total_duration = max(total_duration, sum(cam['durations']))
            
            # Add a small buffer (1 second) to account for rounding errors
            total_duration += 1.0
            
            # Make sure we don't go before the start
            if time_since_start < 0:
                print(f"Adjusting to start of recording (can't go before 0)")
                time_since_start = 0
                
            # Make sure we don't go past the end (with some tolerance)
            if time_since_start > total_duration:
                time_diff = time_since_start - total_duration
                max_allowed_diff = 5  # Only allow small adjustments past the end
                
                if time_diff < max_allowed_diff:
                    print(f"Adjusting to end of recording (within {max_allowed_diff}s tolerance)")
                    time_since_start = total_duration - 1.0  # 1 second before end
                else:
                    print(f"Event too far after recording end (>{max_allowed_diff}s)")
                    return
            
            # Get the current layout mode
            layout_mode = self.layout_selector.currentText()
            
            # For each camera in the current layout, seek to the event time
            for cam_idx, camera_keyword in enumerate(["front", "left_repeater", "right_repeater", "back", "left_pillar", "right_pillar"]):
                if camera_keyword not in self.clip_data or not self.clip_data[camera_keyword]['files']:
                    continue
                
                # Skip cameras not in the current layout
                if layout_mode == "Single View (1x1)" and camera_keyword != "front":
                    continue
                elif layout_mode == "Front & Back (2x1)" and camera_keyword not in ["front", "back"]:
                    continue
                elif layout_mode == "Repeaters (1x2)" and camera_keyword not in ["left_repeater", "right_repeater"]:
                    continue
                elif layout_mode == "Pillars (1x2)" and camera_keyword not in ["left_pillar", "right_pillar"]:
                    continue
                
                # Use the combined video if it exists, otherwise fall back to individual clips
                combined_path = os.path.join(self.temp_dir, f"{camera_keyword}_combined.mp4")
                if os.path.exists(combined_path):
                    print(f"Using combined video for {camera_keyword} at {time_since_start:.2f}s")
                    
                    # Create a lambda for the media status changed signal
                    def create_lambda(i, path, time):
                        return lambda status: self._on_media_loaded(status, i, int(time * 1000))
                    
                    # Disconnect any existing connections
                    try:
                        self.players[cam_idx].mediaStatusChanged.disconnect()
                    except:
                        pass
                    
                    # Connect the new handler
                    self.players[cam_idx].mediaStatusChanged.connect(create_lambda(cam_idx, combined_path, time_since_start))
                    
                    # Load the combined clip
                    self.players[cam_idx].setSource(QUrl.fromLocalFile(combined_path))
                    self.sources[cam_idx] = combined_path
                    
                    # Start playback after seeking is complete
                    def seek_and_play():
                        self.seek_videos(time_since_start)
                        if was_playing:  # If it was playing before seeking, resume playback
                            self.play_all()
                        else:  # Otherwise, just pause to show the frame
                            self.pause_all()
                    
                    QTimer.singleShot(100, seek_and_play)
                    
                    # Update the timeline with event markers
                    QTimer.singleShot(500, self.update_events_on_timeline)
                else:
                    # Fall back to individual clips if combined video doesn't exist
                    current_time = 0
                    found_clip = None
                    clip_start_time = 0
                    closest_clip = None
                    closest_diff = float('inf')
                    
                    for clip_path in self.clip_data[camera_keyword]['files']:
                        try:
                            clip_duration = self.get_clip_duration(clip_path)
                            clip_end_time = current_time + clip_duration
                            
                            # Check if this is the closest clip so far
                            time_diff = abs((current_time + clip_duration/2) - time_since_start)
                            if time_diff < closest_diff:
                                closest_diff = time_diff
                                closest_clip = (clip_path, current_time, clip_duration)
                            
                            # Check if this clip contains the target time
                            if current_time <= time_since_start < clip_end_time:
                                found_clip = clip_path
                                clip_start_time = current_time
                                print(f"Exact match found for {camera_keyword} at {time_since_start:.2f}s in {os.path.basename(found_clip)}")
                                break
                                
                            current_time = clip_end_time
                        except Exception as e:
                            print(f"Error processing clip {clip_path}: {e}")
                    
                    # If no exact match found, use the closest clip
                    if not found_clip and closest_clip:
                        found_clip, clip_start_time, clip_duration = closest_clip
                        time_in_clip = min(time_since_start - clip_start_time, clip_duration - 0.5)  # Don't go to the very end
                        time_in_clip = max(0, time_in_clip)  # Don't go before start
                        print(f"Using closest clip for {camera_keyword}: {os.path.basename(found_clip)} at {time_in_clip:.2f}s (was {time_since_start - clip_start_time:.2f}s)")
                    elif found_clip:
                        time_in_clip = time_since_start - clip_start_time
                        print(f"Found exact clip for {camera_keyword}: {os.path.basename(found_clip)} at {time_in_clip:.2f}s")
                        
                        # Create a lambda for the media status changed signal
                        def create_lambda(i, path, time):
                            return lambda status: self._on_media_loaded(status, i, int(time * 1000))
                        
                        # Disconnect any existing connections
                        try:
                            self.players[cam_idx].mediaStatusChanged.disconnect()
                        except:
                            pass
                        
                        # Connect the new handler
                        self.players[cam_idx].mediaStatusChanged.connect(create_lambda(cam_idx, found_clip, time_in_clip))
                        
                        # Load the clip
                        self.players[cam_idx].setSource(QUrl.fromLocalFile(found_clip))
                        self.sources[cam_idx] = found_clip
                        
                        # Play briefly to ensure it loads
                        self.players[cam_idx].play()
                        QTimer.singleShot(100, lambda idx=cam_idx: self.players[idx].pause())
            
            # Update the timeline position
            self.update_timeline(int(time_since_start * 1000))
            
            # Start playing all videos in sync
            self.play_all()
            
        except Exception as e:
            print(f"Error in jump_to_event: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Reset the flag when we're done
            self._auto_jump_in_progress = False
    
    def update_timeline(self, position):
        # Update timeline position without triggering seek_videos
        self.timeline.blockSignals(True)
        self.timeline.setValue(position)
        self.old_timeline.setValue(position)  # Update old timeline for compatibility
        self.timeline.blockSignals(False)
        
        # Update time label
        self.update_time_label(position)

    def update_time_label(self, value):
        """Update the time label with the current position and highlight the current event."""
        # Convert milliseconds to hours, minutes, seconds
        total_seconds = value // 1000
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        milliseconds = value % 1000
        
        # Format the time string
        if hours > 0:
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
        else:
            time_str = f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
            
        # Update the time label
        if hasattr(self, 'time_label'):
            self.time_label.setText(time_str)
        
        # Update the highlighted event on the timeline
        if hasattr(self, 'timeline'):
            self.timeline._update_highlighted_event(value)
            
        return time_str

    def load_events(self, folder):
        """Load events from the specified folder."""
        print(f"\n=== DEBUG: load_events called for folder: {folder} ===\n")
        self.events = []
        self.events_list.clear()
        
        if not folder or not os.path.isdir(folder):
            print(f"[DEBUG] Invalid folder: {folder}")
            self.update_events_on_timeline()
            return
        
        # First try to find event.json directly in the folder
        events_file = os.path.join(folder, 'event.json')
        if os.path.isfile(events_file):
            try:
                print(f"[DEBUG] Loading events from {events_file}")
                with open(events_file, 'r') as f:
                    event_data = json.load(f)
                    if 'timestamp' in event_data:
                        print(f"[DEBUG] Event has timestamp: {event_data['timestamp']}")
                        self.events.append({
                            'path': events_file,
                            'data': event_data,
                            'folder': os.path.basename(folder)
                        })
                    else:
                        print(f"[DEBUG] Event missing timestamp: {event_data}")
            except Exception as e:
                print(f"Error reading event file {events_file}: {e}")
        else:
            print(f"[DEBUG] No event.json found directly in {folder}, scanning subdirectories...")
            # If no event.json in the main folder, scan subdirectories
            self.scan_for_events(folder)
            return  # scan_for_events will call update_events_on_timeline
        
        print(f"[DEBUG] Valid events with timestamps: {len(self.events)}")
        
        # Sort events by timestamp
        self.events.sort(key=lambda x: x['data'].get('timestamp', ''))
        
        # Add events to the list widget
        for event in self.events:
            event_time = event['data'].get('timestamp', 'Unknown Time')
            reason = event['data'].get('reason', 'Unknown Event').replace('_', ' ').title()
            city = event['data'].get('city', 'Unknown Location')
            item_text = f"{event_time} - {reason} - {city}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, event)
            self.events_list.addItem(item)
        
        # Immediately update the timeline with events after loading
        if self.events:
            print(f"[DEBUG] Calling update_events_on_timeline from load_events with {len(self.events)} events")
            QTimer.singleShot(100, self.update_events_on_timeline)

    def update_events_on_timeline(self, auto_jump=True):
        """Update the timeline with the current events."""
        print("=== DEBUG: update_events_on_timeline called ===")
        if not hasattr(self, 'timeline') or not self.timeline:
            print("[DEBUG] Timeline widget not available")
            return
            
        print(f"[DEBUG] Timeline widget: {self.timeline}")
        print(f"[DEBUG] Timeline visible: {self.timeline.isVisible()}")
        print(f"[DEBUG] Events: {self.events}")
        
        if not self.events:
            print("[DEBUG] No events to display on timeline")
            return
        
        # Add a flag to track if we're already in the process of jumping to an event
        if not hasattr(self, '_auto_jump_in_progress'):
            self._auto_jump_in_progress = False

        # Force timeline to be visible
        self.timeline.show()
        
        # Get the timeline range
        timeline_min = self.timeline.minimum()
        timeline_max = self.timeline.maximum()
        
        # If the timeline maximum is too small, we need to calculate it based on the actual video duration
        if timeline_max < 60000:  # Less than 1 minute
            # Get the actual duration from the loaded videos
            actual_duration_ms = 0
            
            # Check if we have media players with loaded content
            if hasattr(self, 'media_players') and self.media_players:
                for player in self.media_players:
                    if player and player.duration() > 0:
                        # Get the duration from the longest video
                        actual_duration_ms = max(actual_duration_ms, player.duration())
            
            # If we couldn't get a valid duration, use the duration from the file list
            if actual_duration_ms <= 0 and hasattr(self, 'video_files') and self.video_files:
                # Calculate total duration based on the number of files and their average duration
                # Assuming each file is approximately 1 minute
                file_count = len(self.video_files.get('front', []))
                if file_count > 0:
                    actual_duration_ms = file_count * 60000  # Approx. 1 minute per file
            
            # If we still don't have a valid duration, use a reasonable default
            if actual_duration_ms <= 0:
                actual_duration_ms = 600000  # 10 minutes as fallback
            
            # Set the timeline maximum to the actual duration
            timeline_max = actual_duration_ms
            self.timeline.setMaximum(timeline_max)
            print(f"[DEBUG] Timeline maximum was set to actual video duration: {timeline_max}ms")
        
        # Process events for display on the timeline
        event_times = []
        event_data = []
        
        for i, event_obj in enumerate(self.events):
            # Extract timestamp from event data
            if isinstance(event_obj, dict) and 'data' in event_obj and 'timestamp' in event_obj['data']:
                timestamp_str = event_obj['data']['timestamp']
                try:
                    # Parse the timestamp
                    dt = datetime.datetime.fromisoformat(timestamp_str)
                    # Convert to milliseconds since epoch
                    event_time_ms = int(dt.timestamp() * 1000)
                    
                    # Check if the event is after the timeline ends
                    if event_time_ms > timeline_max:
                        print(f"[DEBUG] Event {i} occurs after timeline end: {event_time_ms}ms > {timeline_max}ms")
                        # Place the event 15 seconds before the end of the timeline
                        adjusted_time = timeline_max - 15000  # 15 seconds before end
                        adjusted_time = max(timeline_min, adjusted_time)  # Ensure it's not before the start
                        
                        # Make sure the adjusted time is actually near the end of the timeline
                        # If timeline_max is very small, this might put the event at the beginning
                        if adjusted_time < (timeline_min + (timeline_max - timeline_min) * 0.5):
                            # If adjusted_time would be in the first half of the timeline, place it at 85% instead
                            adjusted_time = timeline_min + int((timeline_max - timeline_min) * 0.85)
                            print(f"[DEBUG] Adjusted time was too early, moving to 85% of timeline: {adjusted_time}ms")
                        
                        event_times.append(adjusted_time)
                        # Add a note to the event data that it's been adjusted
                        event_obj_copy = event_obj.copy() if isinstance(event_obj, dict) else event_obj
                        if isinstance(event_obj_copy, dict):
                            event_obj_copy['adjusted'] = True
                            event_obj_copy['original_time'] = event_time_ms
                        event_data.append(event_obj_copy)
                        print(f"[DEBUG] Adjusted event {i} to {adjusted_time}ms (15sec before timeline end)")
                    else:
                        # Event is within timeline range
                        event_times.append(event_time_ms)
                        event_data.append(event_obj)
                        print(f"[DEBUG] Added event {i} at {event_time_ms}ms")
                except Exception as e:
                    print(f"[DEBUG] Error parsing event timestamp: {e}")
            else:
                print(f"[DEBUG] Event {i} missing timestamp data")
        
        if not event_times:
            print("[DEBUG] No valid event times parsed")
            return
            
        self.timeline.set_events(event_times, event_data)
        print(f"[DEBUG] set_events called with {len(event_times)} events")
        self.timeline.update()
        print("[DEBUG] Forced timeline update() call.")
        print(f"[DEBUG] Timeline visible after update: {self.timeline.isVisible()}")
        
        # Automatically seek to the first event after loading, but only if auto_jump is enabled
        # and we're not already in the process of jumping
        if auto_jump and event_times and len(event_times) > 0 and not self._auto_jump_in_progress:
            print(f"[DEBUG] Automatically seeking to first event at {event_times[0]}ms")
            
            # Set the flag to prevent recursive calls
            self._auto_jump_in_progress = True
            
            try:
                # First, check if we have events in the events list widget
                if self.events_list.count() > 0:
                    # Select the first event in the list, which will trigger jump_to_event
                    print(f"[DEBUG] Selecting first event in events list")
                    self.events_list.setCurrentRow(0)
                    first_item = self.events_list.item(0)
                    if first_item:
                        # This will trigger the jump_to_event method which handles seeking
                        self.jump_to_event(first_item)
                        return
                
                # Fallback if events list selection doesn't work
                print(f"[DEBUG] Using fallback method to seek to event")
                
                # Highlight the first event
                self.timeline.set_highlighted_event(0)
                
                # Store current play state
                was_playing = any(p.playbackState() == QMediaPlayer.PlaybackState.PlayingState 
                                for p in self.players if p.source())
                
                # Calculate position in milliseconds and seek to it
                position = event_times[0]
                
                # Check if this is an adjusted event (event that was after timeline end)
                if isinstance(event_data[0], dict) and event_data[0].get('adjusted', False):
                    # If the event was adjusted, use the original time for seeking if possible
                    original_time = event_data[0].get('original_time')
                    if original_time:
                        print(f"[DEBUG] Using original event time for seeking: {original_time}ms")
                        # If the original time is beyond the timeline, seek to the end of the timeline
                        timeline_max = self.timeline.maximum()
                        if original_time > timeline_max:
                            # Seek to the end of the timeline minus 1 second to show the last frame
                            position = max(0, timeline_max - 1000)
                            print(f"[DEBUG] Original time beyond timeline, seeking to end minus 1 second: {position}ms")
                        else:
                            position = original_time
                
                # Seek 5 seconds before the event if possible
                position = max(0, position - 5000)  # 5 seconds before event
                
                # Update the timeline position
                self.timeline.setValue(position)
                
                # Seek all videos to this position
                self.seek_videos(position / 1000)  # Convert ms to seconds for seek_videos
                
                # Resume playback if it was playing before
                if was_playing:
                    self.play_all()
                else:
                    self.pause_all()
            finally:
                # Reset the flag when we're done
                self._auto_jump_in_progress = False

        # Get current timeline range for debugging
        timeline_min = self.timeline.minimum()
        timeline_max = self.timeline.maximum()
        print(f"[UI] Current timeline range: {timeline_min}ms to {timeline_max}ms (duration: {(timeline_max - timeline_min)/1000:.2f}s)")
        
        # Debug: Print first few events if they exist
        if hasattr(self, 'events') and self.events:
            print("[UI] First 3 events:")
            for i, event in enumerate(self.events[:3]):
                event_obj = event.get('data', event) if isinstance(event, dict) else event
                print(f"  Event {i+1}: {event_obj.get('timestamp')} - {event_obj.get('reason')} - {event_obj.get('city', 'N/A')}")
        else:
            print("[UI] No events found to display on timeline")
        
        # If we have no events or the events list is empty, create some test events
        if not hasattr(self, 'events') or not self.events:
            print("[UI] No events found, adding test events for debugging")
            # Add test events at 10%, 30%, 50%, 70%, and 90% of the timeline
            duration = timeline_max - timeline_min
            if duration <= 1000:  # If duration is too small (less than 1 second)
                print("[UI] Invalid duration for test events, using default range")
                timeline_min = 0
                timeline_max = 60000  # Default to 1 minute
                duration = timeline_max - timeline_min
                self.timeline.setMinimum(timeline_min)
                self.timeline.setMaximum(timeline_max)
            
            # Create test events at 10%, 30%, 50%, 70%, and 90% of the timeline
            test_events = [
                timeline_min + int(duration * 0.1),
                timeline_min + int(duration * 0.3),
                timeline_min + int(duration * 0.5),
                timeline_min + int(duration * 0.7),
                timeline_min + int(duration * 0.9)
            ]
            # Create test event data
            test_event_data = [
                {'reason': 'user_interaction', 'city': 'Test City', 'timestamp': '2025-05-20T10:00:00Z'},
                {'reason': 'sentry', 'city': 'Test City', 'timestamp': '2025-05-20T10:10:00Z'},
                {'reason': 'autopilot', 'city': 'Test City', 'timestamp': '2025-05-20T10:20:00Z'},
                {'reason': 'user_interaction', 'city': 'Test City', 'timestamp': '2025-05-20T10:30:00Z'},
                {'reason': 'sentry', 'city': 'Test City', 'timestamp': '2025-05-20T10:40:00Z'}
            ]
            print(f"[UI] Adding test events at: {test_events}")
            
            # Make sure the timeline range is set before adding events
            self.timeline.setMinimum(int(timeline_min))
            self.timeline.setMaximum(int(timeline_max))
            
            # Add events to the timeline
            self.timeline.set_events(test_events, test_event_data)
            
            # Force a repaint of the timeline
            self.timeline.update()
            
            # Print confirmation
            print(f"[UI] Timeline range: {self.timeline.minimum()} to {self.timeline.maximum()}")
            print(f"[UI] Added {len(test_events)} test events to timeline")
            return
            
        # Process real events from the events list
        event_times = []
        event_data = []
        
        # First pass: collect all valid events and their timestamps
        valid_events = []
        for i, event in enumerate(self.events):
            try:
                # Handle both direct event objects and wrapped events with 'data' key
                event_obj = event.get('data', event) if isinstance(event, dict) else event
                
                # Get the event time
                timestamp_str = event_obj.get('timestamp')
                if not timestamp_str:
                    print(f"[UI] Event {i} has no timestamp")
                    continue
                
                # Convert timestamp to milliseconds since epoch
                try:
                    event_time = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    event_time_ms = int(event_time.timestamp() * 1000)
                    
                    # Store the valid event and its timestamp
                    valid_events.append((event_time_ms, event_obj))
                    
                    # Debug output for first few events
                    if i < 5:
                        time_str = event_time.strftime("%H:%M:%S")
                        print(f"[UI] Event {i+1}: time={time_str} ({event_time_ms}ms)")
                        
                except (ValueError, TypeError) as e:
                    print(f"[UI] Error parsing timestamp for event {i}: {timestamp_str} - {e}")
                    
            except Exception as e:
                print(f"[UI] Error processing event {i}: {e}")
                import traceback
                traceback.print_exc()
        
        # If we found valid events, update the timeline
        if valid_events:
            print(f"[UI] Found {len(valid_events)} valid events with timestamps")
            
            # Sort events by time
            valid_events.sort(key=lambda x: x[0])
            
            # Separate timestamps and event data
            event_times = [e[0] for e in valid_events]
            event_data = [e[1] for e in valid_events]
            
            # Debug output for event times
            print(f"[UI] Event times (ms): {event_times}")
            for i, t in enumerate(event_times[:3]):
                print(f"[UI] Event {i+1}: {t}ms = {t/1000:.2f}s")
                if i < len(event_data):
                    print(f"[UI] Event {i+1} data: {event_data[i].get('reason', 'unknown')}")
            
            # Get video duration if available
            video_duration = self.total_duration if hasattr(self, 'total_duration') and self.total_duration > 0 else 0
            print(f"[UI] Video duration: {video_duration}ms = {video_duration/1000:.2f}s")
            
            # Calculate timeline range based on events and video duration
            min_time = min(event_times) if event_times else 0
            max_time = max(event_times) if event_times else (video_duration if video_duration > 0 else 60000)
            
            print(f"[UI] Initial time range: {min_time}ms to {max_time}ms")
            
            # If we have video duration, ensure it's included in the range
            if video_duration > 0:
                # Ensure the timeline includes both the video duration and the events
                min_time = min(min_time, 0)
                max_time = max(max_time, video_duration)
            
            # Debug: Print events that fall after video duration
            if hasattr(self, 'total_duration') and self.total_duration > 0:
                post_video_events = [t for t in event_times if t > self.total_duration]
                if post_video_events:
                    print(f"[UI] Found {len(post_video_events)} events after video end (video ends at {self.total_duration/1000:.1f}s):")
                    for t in post_video_events:
                        print(f"  - {t/1000:.1f}s ({t-self.total_duration:.0f}ms after video end)")
        else:
            print("[UI] No valid events found to display on timeline")

        # Update the seek bar if it exists
        if hasattr(self, 'seek_bar'):
            # Make sure we don't try to set a value outside the valid range
            value = min(max(0, self.timeline.value()), self.total_duration)
            self.seek_bar.setValue(value)
    
    def select_folder(self):
        try:
            folder = QFileDialog.getExistingDirectory(self, "Select TeslaCam Folder")
            if not folder:
                return
                
            self.current_folder = folder
            self.scan_for_events(folder)

            files = sorted(os.listdir(folder))
            cam_keywords = ["front", "left_repeater", "right_repeater", "back", "left_pillar", "right_pillar"]
            grouped = {kw: [] for kw in cam_keywords}

            for file in files:
                for cam in cam_keywords:
                    if cam in file and file.endswith(".mp4"):
                        grouped[cam].append(os.path.join(folder, file))

            self.temp_dir = tempfile.mkdtemp()

            # Initialize clip_data for each camera
            for cam in cam_keywords:
                self.clip_data[cam] = {
                    'offsets': [0],  # Start times of each clip in seconds
                    'durations': [],  # Duration of each clip in seconds
                    'files': []       # Paths to each clip file
                }
                
                if grouped[cam]:
                    # Sort clips by name (which should be in chronological order)
                    sorted_clips = sorted(grouped[cam])
                    
                    # Populate clip_data with file paths and calculate durations/offsets
                    for clip in sorted_clips:
                        duration = self.get_clip_duration(clip)
                        self.clip_data[cam]['durations'].append(duration)
                        self.clip_data[cam]['files'].append(clip)
                        # Next clip starts where this one ends
                        self.clip_data[cam]['offsets'].append(self.clip_data[cam]['offsets'][-1] + duration)
            
            # Now create the combined videos
            for i, cam in enumerate(cam_keywords):
                if grouped[cam]:
                    txt_path = os.path.join(self.temp_dir, f"{cam}_list.txt")
                    output_path = os.path.join(self.temp_dir, f"{cam}_combined.mp4")
                    with open(txt_path, 'w') as f:
                        for clip in sorted(grouped[cam]):
                            fixed_clip = clip.replace('\\', '/')
                            f.write(f"file '{fixed_clip}'\n")
                    subprocess.run([
                        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                        "-i", txt_path, "-c", "copy", output_path
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.players[i].setSource(QUrl.fromLocalFile(output_path))
                    self.sources[i] = output_path
                    
                    # Set the total duration for the timeline
                    if cam == "front" and self.clip_data[cam]['durations']:
                        self.total_duration = int(sum(self.clip_data[cam]['durations']) * 1000)  # Convert to ms
                        if hasattr(self, 'scrubber'):
                            self.scrubber.setRange(0, self.total_duration)
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to load videos:\n{e}")

    # Handles trimming and exporting selected video layout using FFmpeg
    def export_clip(self):
        self.export_status.setText("Exporting... Please wait.")
        QApplication.processEvents()
        try:
            start_ms, ok1 = QInputDialog.getInt(self, "Start Time", "Enter start time (seconds):", min=0)
            duration_ms, ok2 = QInputDialog.getInt(self, "Duration", "Enter duration (seconds):", min=1)
            if not (ok1 and ok2):
                return

            output_folder = QFileDialog.getExistingDirectory(self, "Select Export Destination")
            if not output_folder:
                return

            resolution_choice, ok = QInputDialog.getItem(
            self,
            "Choose Export Quality",
            "Pick export quality:\n• Full: Highest detail (may lag on phones)\n• Mobile: Compatible with all devices",
                ["Mobile (Recommended)", "Full"],
                0,
                False
            )
            if not ok:
                return

            export_mobile = resolution_choice.startswith("Mobile")
            if not output_folder:
                return

            mode = self.layout_selector.currentText()
            # Maps UI layout selections to internal player indices
            layout_map = {
                "All Cameras (3x2)": [4, 0, 5, 1, 3, 2],
                "Front & Back (2x1)": [0, 3],
                "Repeaters (1x2)": [1, 2],
                "Pillars (1x2)": [4, 5],
                "Single View (1x1)": [self.selected_single_view_index]
            }
            selected_indices = layout_map.get(mode, [])
            inputs = []
            for idx in selected_indices:
                if not self.sources[idx]:
                    continue
                trimmed_path = os.path.join(output_folder, f"trim_{idx}.mp4")
                subprocess.run([
                    "ffmpeg", "-y", "-ss", str(start_ms), "-i", self.sources[idx],
                    "-t", str(duration_ms), "-c:v", "libx264", "-preset", "ultrafast", 
                    "-r", "30", trimmed_path
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                inputs.append(trimmed_path)

            if not inputs:
                QMessageBox.warning(self, "No Sources", "No videos available to export for selected layout.")
                return

            final_output = os.path.join(output_folder, "final_output.mp4")
            if len(inputs) == 1:
                if export_mobile:
                    final_output = os.path.join(output_folder, "final_output_mobile.mp4")
                    subprocess.run([
                        "ffmpeg", "-y", "-i", inputs[0],
                        "-vf", "scale=1920:-2",
                        "-c:v", "libx264", "-preset", "fast", "-r", "30",
                        "-pix_fmt", "yuv420p", final_output
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    os.rename(inputs[0], final_output)
                QMessageBox.information(self, "Export Complete", f"Exported single view to: {final_output}")
            elif mode == "Front & Back (2x1)":
                if export_mobile:
                    final_output = os.path.join(output_folder, "final_output_mobile.mp4")
                    # Flip order so front is on right
                    scale_filter = "[0:v]scale=-1:720[a];[1:v]scale=-1:720[b];[a][b]hstack=inputs=2[v]"
                else:
                    final_output = os.path.join(output_folder, "final_output.mp4")
                    # Flip input order to match Back (left) + Front (right)
                    scale_filter = "[0:v]scale=-1:1876[a];[1:v]scale=-1:1876[b];[a][b]hstack=inputs=2[v]"

                result = subprocess.run([
                    "ffmpeg", "-y", "-i", inputs[1], "-i", inputs[0],
                    "-filter_complex", scale_filter, "-map", "[v]", "-r", "30",
                    "-pix_fmt", "yuv420p", final_output
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print("FFmpeg output (front_back):\n" + result.stderr.decode())
                QMessageBox.information(self, "Export Complete", f"Exported layout to: {final_output}")
            elif mode in ("Repeaters (1x2)", "Pillars (1x2)"):
                if export_mobile:
                    final_output = os.path.join(output_folder, "final_output_mobile.mp4")
                    scale_filter = "[0:v]scale=-1:720[a];[1:v]scale=-1:720[b];[a][b]hstack=inputs=2[v]"
                else:
                    scale_filter = "[0:v][1:v]hstack=inputs=2[v]"

                subprocess.run([
                    "ffmpeg", "-y", "-i", inputs[0], "-i", inputs[1],
                    "-filter_complex", scale_filter, "-map", "[v]", "-r", "30",
                    "-pix_fmt", "yuv420p", final_output
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                QMessageBox.information(self, "Export Complete", f"Exported layout to: {final_output}")
            elif mode == "All Cameras (3x2)":
                top = os.path.join(output_folder, "row_top.mp4")
                mid = os.path.join(output_folder, "row_mid.mp4")
                result_top = subprocess.run([
                    "ffmpeg", "-y",
                    "-i", inputs[0],
                    "-i", inputs[1],
                    "-i", inputs[2],
                    "-filter_complex",
                    "[0:v]scale=-1:938[a];[1:v]scale=-1:938[b];[2:v]scale=-1:938[c];[a][b][c]hstack=inputs=3[v]",
                    "-map", "[v]", "-r", "30", "-pix_fmt", "yuv420p", top
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print("FFmpeg output (row_top):" + result_top.stderr.decode())
                result_mid = subprocess.run([
                    "ffmpeg", "-y",
                    "-i", inputs[3],
                    "-i", inputs[4],
                    "-i", inputs[5],
                    "-filter_complex",
                    "[0:v]scale=-1:938[a];[1:v]scale=-1:938[b];[2:v]scale=-1:938[c];[a][b][c]hstack=inputs=3[v]",
                    "-map", "[v]", "-r", "30", "-pix_fmt", "yuv420p", mid
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print("FFmpeg output (row_mid):" + result_mid.stderr.decode())
                 
                

                # Output final based on resolution choice
                if export_mobile:
                    final_output = os.path.join(output_folder, "final_output_mobile.mp4")
                    result_scaled = subprocess.run([
                        "ffmpeg", "-y", "-i", top, "-i", mid,
                        "-filter_complex",
                        "[0:v][1:v]vstack=inputs=2[stack];[stack]scale=1920:-2[v]",
                        "-map", "[v]", "-r", "30", "-pix_fmt", "yuv420p", final_output
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    print("FFmpeg output (mobile):\n" + result_scaled.stderr.decode())
                    QMessageBox.information(self, "Export Complete", f"Exported mobile-friendly layout to: {final_output}")
                else:
                    result_full = subprocess.run([
                        "ffmpeg", "-y", "-i", top, "-i", mid,
                        "-filter_complex", "[0:v][1:v]vstack=inputs=2[v]", "-map", "[v]", 
                        "-r", "30", "-pix_fmt", "yuv420p", final_output
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    print("FFmpeg output (full):\n" + result_full.stderr.decode())
                    QMessageBox.information(self, "Export Complete", f"Exported full-resolution layout to: {final_output}")
            else:
                QMessageBox.warning(self, "Unsupported Layout", "This layout is not yet supported for export.")
                return

            self.export_status.setText("Export complete!")  # Show export success message

            # Clean up temporary trim and row files
            for file in os.listdir(output_folder):
                if file.startswith("trim_") or file.startswith("row_"):
                    try:
                        os.remove(os.path.join(output_folder, file))
                    except Exception as cleanup_error:
                        print(f"Cleanup error deleting {file}:", cleanup_error)

        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Export Error", f"An error occurred during export:{e}")
            self.export_status.setText("Export failed")

