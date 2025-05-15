from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QGridLayout, QHBoxLayout, QInputDialog, QMessageBox, QSlider, QComboBox, QRadioButton, QButtonGroup, QApplication
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QUrl, QTimer, QEvent
from PyQt6.QtGui import QKeyEvent
import os
import subprocess
import traceback
import tempfile

# TeslaCamViewer provides a PyQt6-based GUI to view and export TeslaCam multi-camera footage.
class TeslaCamViewer(QWidget):
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
        self.temp_dir = None
        super().__init__()
        self.setWindowTitle("TeslaCam 6-Camera Viewer")
        self.setGeometry(100, 100, 1200, 800)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.layout = QVBoxLayout()

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
        self.scrubber = QSlider(Qt.Orientation.Horizontal)  # Timeline scrubber  # Used to scrub through video timeline
        self.scrubber.setRange(0, 1000)
        self.scrubber.sliderMoved.connect(self.seek_all)
        self.slider_layout.addWidget(self.time_label)
        self.slider_layout.addWidget(self.scrubber)
        self.layout.addLayout(self.slider_layout)

        self.setLayout(self.layout)

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
            cam_keywords = ["front", "left_repeater", "right_repeater", "back", "left_pillar", "right_pillar"]
            grouped = {kw: [] for kw in cam_keywords}

            for file in files:
                for cam in cam_keywords:
                    if cam in file and file.endswith(".mp4"):
                        grouped[cam].append(os.path.join(folder, file))

            self.temp_dir = tempfile.mkdtemp()

            for i, cam in enumerate(cam_keywords):
                if grouped[cam]:
                    txt_path = os.path.join(self.temp_dir, f"{cam}_list.txt")
                    output_path = os.path.join(self.temp_dir, f"{cam}_combined.mp4")
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

