from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QGridLayout, QHBoxLayout, 
                            QInputDialog, QMessageBox, QSlider, QComboBox, QRadioButton, QButtonGroup, QApplication,
                            QListWidget, QListWidgetItem, QDockWidget, QMainWindow, QStyle, QStyleOptionSlider)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QUrl, QTimer, QEvent, QRect, QPoint
from PyQt6.QtGui import QKeyEvent, QPainter, QColor, QPen
import os
import subprocess
import traceback
import tempfile

# TeslaCamViewer provides a PyQt6-based GUI to view and export TeslaCam multi-camera footage.
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
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout(central_widget)
        
        # Store events data
        self.events = []
        self.current_folder = ""
        
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
        self.video_widgets = []  # QVideoWidget instances associated with each player
        self.sources = [None] * 6  # Source file paths for each camera

        # Initialize 6 media players and corresponding video widgets for each camera
        # Create 6 video players and video widgets for the 6 Tesla cameras
        for _ in range(6):
            video_widget = QVideoWidget()
            player = QMediaPlayer()
            player.setVideoOutput(video_widget)
            player.setAudioOutput(QAudioOutput())
            self.players.append(player)
            self.video_widgets.append(video_widget)

        self.video_grid.setRowStretch(0, 1)
        self.video_grid.setRowStretch(1, 1)
        self.video_grid.setColumnStretch(0, 1)
        self.video_grid.setColumnStretch(1, 1)
        self.video_grid.setColumnStretch(2, 1)
        self.layout.addLayout(self.video_grid)

        # Frame-by-frame and playback controls with inline single view selection
        control_layout = QHBoxLayout()
        control_layout.addStretch()

        self.frame_back_btn = QPushButton("⏪ Frame Back")
        self.play_btn = QPushButton("▶️ Play All")
        self.pause_btn = QPushButton("⏸️ Pause All")
        self.frame_forward_btn = QPushButton("⏩ Frame Forward")

        self.frame_back_btn.clicked.connect(self.frame_back)
        self.play_btn.clicked.connect(self.play_all)
        self.pause_btn.clicked.connect(self.pause_all)
        self.frame_forward_btn.clicked.connect(self.frame_forward)

        control_layout.addWidget(self.frame_back_btn)
        control_layout.addWidget(self.play_btn)
        control_layout.addWidget(self.pause_btn)
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

        # Time label + scrubber
        self.slider_layout = QHBoxLayout()
        self.time_label = QLabel("00:00 / 00:00")
        
        # Create custom timeline slider with event indicators
        self.scrubber = TimelineSlider(Qt.Orientation.Horizontal)
        self.scrubber.setRange(0, 1000)
        self.scrubber.sliderMoved.connect(self.seek_all)
        
        # Store event positions (in milliseconds)
        self.event_positions = []
        
        self.slider_layout.addWidget(self.time_label)
        self.slider_layout.addWidget(self.scrubber)
        self.layout.addLayout(self.slider_layout)

        # Layout is already set on central widget

        # Add a button to refresh events
        refresh_btn = QPushButton("🔄 Refresh Events")
        refresh_btn.clicked.connect(lambda: self.scan_for_events(self.current_folder) if self.current_folder else None)
        folder_export_layout.addWidget(refresh_btn)
        
        self.sync_timer = QTimer()  # Keeps videos in sync during playback
        self.sync_timer.timeout.connect(self.sync_playback)
        self.sync_timer.start(1000)

        self.slider_timer = QTimer()  # Updates the UI scrubber position
        self.slider_timer.timeout.connect(self.update_slider)
        self.slider_timer.start(500)

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
            index = self.selected_single_view_index
            for i, widget in enumerate(self.video_widgets):
                if i == index:
                    widget.show()
                    self.video_grid.addWidget(widget, 0, 0, 2, 3)
                else:
                    widget.hide()

    def format_time(self, ms):
        """Format milliseconds as MM:SS"""
        seconds = ms // 1000
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins:02}:{secs:02}"

    def update_slider(self):
        for p in self.players:
            if p.source():
                duration = p.duration()
                if duration > 0:
                    position = p.position()
                    # Only update if the duration has changed significantly
                    if abs(self.scrubber.maximum() - duration) > 1000:  # 1 second threshold
                        self.scrubber.setMaximum(duration)
                    self.scrubber.setValue(position)
                    self.time_label.setText(f"{self.format_time(position)} / {self.format_time(duration)}")
                    break

    def seek_all(self, value):
        # Update the time label immediately for better responsiveness
        self.time_label.setText(f"{self.format_time(value)} / {self.format_time(self.scrubber.maximum())}")
        
        # Only update player position if it's a significant change
        for player in self.players:
            if player.source() and abs(player.position() - value) > 33:  # Only update if change > 33ms
                player.setPosition(value)

    def play_all(self):
        for player in self.players:
            if player.source():
                player.play()

    def pause_all(self):
        for player in self.players:
            if player.source():
                player.pause()

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
        self.events_list.clear()
        self.events = []
        self.event_positions = []  # Reset event positions
        
        for root, _, files in os.walk(folder):
            for file in files:
                if file == "event.json":
                    try:
                        with open(os.path.join(root, file), 'r') as f:
                            event_data = eval(f.read())
                            if 'timestamp' in event_data:
                                self.events.append({
                                    'path': os.path.join(root, file),
                                    'data': event_data
                                })
                    except Exception as e:
                        print(f"Error reading {file}: {e}")
        
        # Sort events by timestamp
        self.events.sort(key=lambda x: x['data'].get('timestamp', ''))
        
        # Add events to the list widget and collect their positions
        for event in self.events:
            event_time = event['data'].get('timestamp', '')
            reason = event['data'].get('reason', 'Unknown Event').replace('_', ' ').title()
            city = event['data'].get('city', 'Unknown Location')
            item_text = f"{event_time} - {reason} - {city}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, event)
            self.events_list.addItem(item)
            
            # Calculate position for the event on the timeline
            try:
                # If we have clip data, calculate the exact position
                if hasattr(self, 'clip_data') and 'front' in self.clip_data and self.clip_data['front']['files']:
                    # Use the first camera as reference for timeline
                    event_pos = self._calculate_event_position(event_time, 'front')
                    if event_pos is not None:
                        self.event_positions.append(event_pos)
            except Exception as e:
                print(f"Error calculating event position: {e}")
        
        # Update the slider with event positions
        if hasattr(self, 'scrubber'):
            self.scrubber.set_event_positions(self.event_positions)
    
    def _calculate_event_position(self, event_time_str, cam):
        """Calculate the position of an event on the timeline in milliseconds"""
        from datetime import datetime
        
        try:
            # Parse the event timestamp
            event_time = datetime.strptime(event_time_str, "%Y-%m-%dT%H:%M:%S")
            
            # Get the list of clips for this camera
            clips = self.clip_data[cam]['files']
            if not clips:
                return None
                
            # Find which clip contains our event
            for i, clip_path in enumerate(clips):
                try:
                    clip_time = datetime.strptime(os.path.basename(clip_path).split('_')[1], "%Y-%m-%d_%H-%M-%S")
                    next_clip_time = None
                    
                    # Get the next clip's time if it exists
                    if i + 1 < len(clips):
                        next_clip_path = clips[i + 1]
                        next_clip_time = datetime.strptime(os.path.basename(next_clip_path).split('_')[1], "%Y-%m-%d_%H-%M-%S")
                    
                    # If this is the last clip or the event is before the next clip
                    if next_clip_time is None or event_time < next_clip_time:
                        # Calculate the position in the timeline
                        clip_start_ms = self.clip_data[cam]['offsets'][i] * 1000  # Convert to ms
                        event_offset = (event_time - clip_time).total_seconds() * 1000  # Convert to ms
                        event_pos = int(clip_start_ms + event_offset)
                        
                        # Ensure the position is within the total duration
                        total_duration = self.clip_data[cam]['offsets'][-1] * 1000
                        return min(event_pos, total_duration - 10000)  # 10 seconds before end if needed
                        
                except (IndexError, ValueError) as e:
                    print(f"Error processing clip {clip_path}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error calculating event position: {e}")
            
        return None
    
    def _on_media_loaded(self, status, player_index, seek_time=0):
        """Callback when media is loaded, seeks to specified time and pauses"""
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            # If seek_time is provided, seek to that position
            if seek_time > 0:
                self.players[player_index].setPosition(seek_time)
            else:
                self.players[player_index].setPosition(0)
            self.players[player_index].pause()
            # Disconnect after first use to avoid multiple connections
            try:
                self.players[player_index].mediaStatusChanged.disconnect()
            except:
                pass
    
    def _update_event_positions(self):
        """Update event positions based on current clip data"""
        if not hasattr(self, 'events') or not hasattr(self, 'clip_data'):
            return
            
        self.event_positions = []
        
        for event in self.events:
            event_time = event['data'].get('timestamp')
            if not event_time:
                continue
                
            # Calculate position for the event on the timeline
            event_pos = self._calculate_event_position(event_time, 'front')  # Use front camera as reference
            if event_pos is not None:
                self.event_positions.append(event_pos)
        
        # Update the slider with new event positions
        if hasattr(self, 'scrubber'):
            self.scrubber.set_event_positions(self.event_positions)


class TimelineSlider(QSlider):
    """Custom slider that displays event markers on the timeline"""
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.event_positions = []
        self.setStyleSheet("""
            QSlider::add-page:horizontal {
                background: #3a3a3a;
                height: 4px;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #505050;
                height: 4px;
                border-radius: 2px;
            }
            QSlider::groove:horizontal {
                background: transparent;
                height: 4px;
            }
            QSlider::handle:horizontal {
                background: #a0a0a0;
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
        """)
    
    def set_event_positions(self, positions):
        """Set the positions of event markers (in milliseconds)"""
        self.event_positions = sorted(positions)
        self.update()
    
    def paintEvent(self, event):
        """Custom paint event to draw event markers"""
        super().paintEvent(event)
        
        if not self.event_positions or self.maximum() <= 0:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get the slider dimensions
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        
        # Calculate the available width for the slider
        available_width = self.width() - self.style()->pixelMetric(QStyle.PixelMetric.PM_SliderLength, opt, self)
        slider_start = self.style()->sliderPositionFromValue(self.minimum(), self.maximum(), self.minimum(), 
                                                           available_width, opt.upsideDown) + 1
        slider_end = self.style()->sliderPositionFromValue(self.minimum(), self.maximum(), self.maximum(), 
                                                         available_width, opt.upsideDown) + 1
        slider_width = slider_end - slider_start
        
        # Draw event markers
        marker_height = 12
        marker_width = 2
        marker_y = (self.height() - marker_height) // 2
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 0, 0, 200))  # Semi-transparent red
        
        for pos in self.event_positions:
            # Calculate the x position of the marker
            x = slider_start + (pos / self.maximum()) * slider_width
            
            # Only draw if the marker is within the visible range
            if slider_start <= x <= slider_end:
                # Draw a small triangle pointing up
                points = [
                    QPoint(x - 3, marker_y + marker_height),  # Bottom left
                    QPoint(x + 3, marker_y + marker_height),  # Bottom right
                    QPoint(x, marker_y)  # Top center
                ]
                painter.drawPolygon(points)
                
                # Draw a vertical line under the triangle
                painter.drawRect(int(x - marker_width//2), marker_y + marker_height - 2, 
                               marker_width, 4)
    
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
        event = item.data(Qt.ItemDataRole.UserRole)
        if not event:
            print("DEBUG: No event data found in the selected item")
            return
        
        from datetime import datetime, timedelta
        from PyQt6.QtCore import QTimer, QUrl
        
        try:
            # Get the event timestamp (assuming it's in the format '2023-01-01T12:00:00')
            event_time_str = event['data']['timestamp']
            event_dir = os.path.dirname(event['path'])
            
            print(f"\n=== DEBUG: Processing event ===")
            print(f"Event time: {event_time_str}")
            print(f"Event directory: {event_dir}")
            print(f"Event data: {event['data']}")
            
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
                    
                    # Play briefly to ensure it loads
                    self.players[cam_idx].play()
                    QTimer.singleShot(100, lambda idx=cam_idx: self.players[idx].pause())
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
    
    def update_timeline(self, time_ms):
        """Update the timeline UI to show current position"""
        # Convert time to seconds for display
        seconds = time_ms / 1000
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        time_str = f"{minutes:02d}:{seconds:02d}"
        
        # Update the time label if it exists
        if hasattr(self, 'time_label'):
            self.time_label.setText(time_str)
        
        # Update the seek bar if it exists
        if hasattr(self, 'seek_bar'):
            # Make sure we don't try to set a value outside the valid range
            value = min(max(0, time_ms), self.total_duration)
            self.seek_bar.setValue(value)
    
    def select_folder(self):
        try:
            folder = QFileDialog.getExistingDirectory(self, "Select TeslaCam Folder")
            if not folder:
                return
                
            self.current_folder = folder
            
            # First scan for events to populate the events list
            self.scan_for_events(folder)

            files = sorted(os.listdir(folder))
            cam_keywords = ["front", "left_repeater", "right_repeater", "back", "left_pillar", "right_pillar"]
            grouped = {kw: [] for kw in cam_keywords}

            for file in files:
                for cam in cam_keywords:
                    if cam in file and file.endswith(".mp4"):
                        grouped[cam].append(os.path.join(folder, file))

            # Process each camera's files
            for cam, files in grouped.items():
                if not files:
                    continue
                    
                # Sort files by timestamp in filename
                files.sort(key=lambda x: os.path.basename(x).split('_')[1])
                
                # Store file information
                self.clip_data[cam]['files'] = files
                self.clip_data[cam]['durations'] = [self.get_clip_duration(f) for f in files]
                
                # Calculate offsets (cumulative durations)
                self.clip_data[cam]['offsets'] = [0]  # Start at 0
                for duration in self.clip_data[cam]['durations'][:-1]:  # All but last duration
                    self.clip_data[cam]['offsets'].append(self.clip_data[cam]['offsets'][-1] + duration)
                
                # Create a temporary combined video for this camera
                if self.temp_dir is None:
                    self.temp_dir = tempfile.mkdtemp(prefix="sentrysix_")
                
                # Create a file list for ffmpeg
                list_path = os.path.join(self.temp_dir, f"{cam}_list.txt")
                with open(list_path, 'w') as f:
                    for file in files:
                        f.write(f"file '{os.path.abspath(file)}'\n")
                
                # Combine videos using ffmpeg
                output_path = os.path.join(self.temp_dir, f"{cam}_combined.mp4")
                if not os.path.exists(output_path):
                    subprocess.run([
                        'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                        '-i', list_path, '-c', 'copy', output_path
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Update the source for this camera
                i = cam_keywords.index(cam)
                self.sources[i] = output_path
                
                # Set the total duration for the timeline
                if cam == "front" and self.clip_data[cam]['durations']:
                    self.total_duration = int(sum(self.clip_data[cam]['durations']) * 1000)  # Convert to ms
                    if hasattr(self, 'scrubber'):
                        self.scrubber.setRange(0, self.total_duration)
                        
            # After loading all clips, update event positions with the new clip data
            self._update_event_positions()
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
                    "-t", str(duration_ms), "-c:v", "libx264", "-preset", "ultrafast", trimmed_path
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
                        "-c:v", "libx264", "-preset", "fast", final_output
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
                    "-filter_complex", scale_filter, "-map", "[v]", final_output
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
                    "-filter_complex", scale_filter, "-map", "[v]", final_output
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
                    "-map", "[v]", top
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print("FFmpeg output (row_top):" + result_top.stderr.decode())
                result_mid = subprocess.run([
                    "ffmpeg", "-y",
                    "-i", inputs[3],
                    "-i", inputs[4],
                    "-i", inputs[5],
                    "-filter_complex",
                    "[0:v]scale=-1:938[a];[1:v]scale=-1:938[b];[2:v]scale=-1:938[c];[a][b][c]hstack=inputs=3[v]",
                    "-map", "[v]", mid
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print("FFmpeg output (row_mid):" + result_mid.stderr.decode())
                 
                

                # Output final based on resolution choice
                if export_mobile:
                    final_output = os.path.join(output_folder, "final_output_mobile.mp4")
                    result_scaled = subprocess.run([
                        "ffmpeg", "-y", "-i", top, "-i", mid,
                        "-filter_complex",
                        "[0:v][1:v]vstack=inputs=2[stack];[stack]scale=1920:-2[v]",
                        "-map", "[v]", final_output
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    print("FFmpeg output (mobile):\n" + result_scaled.stderr.decode())
                    QMessageBox.information(self, "Export Complete", f"Exported mobile-friendly layout to: {final_output}")
                else:
                    result_full = subprocess.run([
                        "ffmpeg", "-y", "-i", top, "-i", mid,
                        "-filter_complex", "[0:v][1:v]vstack=inputs=2[v]", "-map", "[v]", final_output
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

