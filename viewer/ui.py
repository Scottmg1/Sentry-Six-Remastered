from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QGridLayout, QHBoxLayout, QInputDialog, QMessageBox, QSlider, QComboBox, QRadioButton, QButtonGroup
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QUrl, QTimer, QEvent
from PyQt6.QtGui import QKeyEvent
import os
import subprocess
import traceback
import tempfile

class TeslaCamViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TeslaCam 6-Camera Viewer")
        self.setGeometry(100, 100, 1200, 800)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.layout = QVBoxLayout()

        # Folder selection and export clip on same row
        folder_export_layout = QHBoxLayout()
        self.select_folder_btn = QPushButton("Select TeslaCam Folder")
        self.export_btn = QPushButton("Export Clip")
        self.select_folder_btn.clicked.connect(self.select_folder)
        self.export_btn.clicked.connect(self.export_clip)
        folder_export_layout.addWidget(self.select_folder_btn)
        folder_export_layout.addWidget(self.export_btn)
        self.layout.addLayout(folder_export_layout)

        # Layout selector
        layout_selector_layout = QHBoxLayout()
        layout_selector_label = QLabel("View Layout:")
        self.layout_selector = QComboBox()
        self.layout_selector.addItems(["All Cameras (3x2)", "Front & Back (2x2)", "Repeaters (1x2)", "Pillars (1x2)", "Single View (1x1)"])
        self.layout_selector.currentIndexChanged.connect(self.update_layout)
        layout_selector_layout.addWidget(layout_selector_label)
        layout_selector_layout.addWidget(self.layout_selector)
        self.layout.addLayout(layout_selector_layout)

        # Video grid layout
        self.video_grid = QGridLayout()
        self.players = []
        self.video_widgets = []
        self.sources = [None] * 6

        for _ in range(6):
            video_widget = QVideoWidget()
            player = QMediaPlayer()
            player.setVideoOutput(video_widget)
            player.setAudioOutput(QAudioOutput())
            self.players.append(player)
            self.video_widgets.append(video_widget)

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
        cam_labels = ["Front", "Back", "Left Repeater", "Right Repeater", "Left Pillar", "Right Pillar"]
        for label in cam_labels:
            btn = QRadioButton(label)
            btn.toggled.connect(self.update_layout)
            self.single_view_group.addButton(btn)
            self.single_view_buttons.append(btn)
            self.single_view_layout.addWidget(btn)
        self.single_view_buttons[0].setChecked(True)

        self.single_view_container = QWidget()
        self.single_view_container.setLayout(self.single_view_layout)
        self.single_view_container.hide()
        control_layout.addWidget(self.single_view_container)

        control_layout.addStretch()
        self.layout.addLayout(control_layout)

        # Time label + scrubber
        self.slider_layout = QHBoxLayout()
        self.time_label = QLabel("00:00 / 00:00")
        self.scrubber = QSlider(Qt.Orientation.Horizontal)
        self.scrubber.setRange(0, 1000)
        self.scrubber.sliderMoved.connect(self.seek_all)
        self.slider_layout.addWidget(self.time_label)
        self.slider_layout.addWidget(self.scrubber)
        self.layout.addLayout(self.slider_layout)

        self.setLayout(self.layout)

        self.sync_timer = QTimer()
        self.sync_timer.timeout.connect(self.sync_playback)
        self.sync_timer.start(1000)

        self.slider_timer = QTimer()
        self.slider_timer.timeout.connect(self.update_slider)
        self.slider_timer.start(500)

        self.update_layout()

    def update_layout(self):
        for i in reversed(range(self.video_grid.count())):
            widget = self.video_grid.itemAt(i).widget()
            if widget:
                self.video_grid.removeWidget(widget)
                widget.setParent(None)

        mode = self.layout_selector.currentText()
        if hasattr(self, 'single_view_container'):
            self.single_view_container.setVisible(mode == "Single View (1x1)")

        if mode == "All Cameras (3x2)":
            self.video_grid.addWidget(self.video_widgets[4], 0, 0)
            self.video_grid.addWidget(self.video_widgets[0], 0, 1)
            self.video_grid.addWidget(self.video_widgets[5], 0, 2)
            self.video_grid.addWidget(self.video_widgets[1], 1, 0)
            self.video_grid.addWidget(self.video_widgets[3], 1, 1)
            self.video_grid.addWidget(self.video_widgets[2], 1, 2)
        elif mode == "Front & Back (2x2)":
            self.video_grid.addWidget(self.video_widgets[0], 0, 0)
            self.video_grid.addWidget(self.video_widgets[3], 0, 1)
        elif mode == "Repeaters (1x2)":
            self.video_grid.addWidget(self.video_widgets[1], 0, 0)
            self.video_grid.addWidget(self.video_widgets[2], 0, 1)
        elif mode == "Pillars (1x2)":
            self.video_grid.addWidget(self.video_widgets[4], 0, 0)
            self.video_grid.addWidget(self.video_widgets[5], 0, 1)
        elif mode == "Single View (1x1)":
            index = self.single_view_buttons.index(next(btn for btn in self.single_view_buttons if btn.isChecked()))
            self.video_grid.addWidget(self.video_widgets[index], 0, 0)

    def format_time(self, ms):
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
                    self.scrubber.setMaximum(duration)
                    self.scrubber.setValue(position)
                    self.time_label.setText(f"{self.format_time(position)} / {self.format_time(duration)}")
                    break

    def seek_all(self, value):
        for player in self.players:
            if player.source():
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

    def select_folder(self):
        try:
            folder = QFileDialog.getExistingDirectory(self, "Select TeslaCam Folder")
            if not folder:
                return

            files = sorted(os.listdir(folder))
            cam_keywords = ["front", "left_repeater", "right_repeater", "back", "left_bpillar", "right_bpillar"]
            grouped = {kw: [] for kw in cam_keywords}

            for file in files:
                for cam in cam_keywords:
                    if cam in file and file.endswith(".mp4"):
                        grouped[cam].append(os.path.join(folder, file))

            temp_dir = tempfile.mkdtemp()

            for i, cam in enumerate(cam_keywords):
                if grouped[cam]:
                    txt_path = os.path.join(temp_dir, f"{cam}_list.txt")
                    output_path = os.path.join(temp_dir, f"{cam}_combined.mp4")
                    with open(txt_path, 'w') as f:
                        for clip in grouped[cam]:
                            f.write(f"file '{clip.replace('\\', '/')}\n")
                    subprocess.run([
                        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                        "-i", txt_path, "-c", "copy", output_path
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.players[i].setSource(QUrl.fromLocalFile(output_path))
                    self.sources[i] = output_path
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to load videos:\n{e}")

    def export_clip(self):
        try:
            start_ms, ok1 = QInputDialog.getInt(self, "Start Time", "Enter start time (seconds):", min=0)
            duration_ms, ok2 = QInputDialog.getInt(self, "Duration", "Enter duration (seconds):", min=1)
            if not (ok1 and ok2):
                return

            output_folder = QFileDialog.getExistingDirectory(self, "Select Export Destination")
            if not output_folder:
                return

            for i, source in enumerate(self.sources):
                if not source:
                    continue
                base_name = os.path.basename(source)
                out_file = os.path.join(output_folder, f"clip_{i}_{base_name}")
                cmd = [
                    "ffmpeg",
                    "-ss", str(start_ms),
                    "-i", source,
                    "-t", str(duration_ms),
                    "-c", "copy",
                    out_file
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            QMessageBox.information(self, "Export Complete", "Clip export finished for all available cameras.")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Export Error", f"An error occurred during export:\n{e}")

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Space:
            any_playing = any(p.playbackState() == QMediaPlayer.PlaybackState.PlayingState for p in self.players)
            if any_playing:
                self.pause_all()
            else:
                self.play_all()
        elif event.key() == Qt.Key.Key_Right:
            self.frame_forward()
        elif event.key() == Qt.Key.Key_Left:
            self.frame_back()
        else:
            super().keyPressEvent(event)