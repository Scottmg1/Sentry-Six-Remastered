import os
import json
import time
import traceback
import tempfile
import math
import re
import subprocess
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog,
                             QGridLayout, QHBoxLayout, QMessageBox, QComboBox, 
                             QRadioButton, QApplication, QCheckBox, QProgressDialog, 
                             QDialog, QDialogButtonBox)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt6.QtCore import Qt, QUrl, QTimer, QSettings, QThread
from PyQt6.QtGui import QPixmap, QAction, QKeySequence

from . import utils
from . import widgets
from . import workers


class WelcomeDialog(QDialog):
    """Simple first-time welcome dialog prompting for TeslaCam folder."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Sentry-Six")
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("It looks like this is your first time running Sentry-Six.\nPlease choose your TeslaCam clips folder to get started."))
        self.choose_btn = QPushButton("Select Clips Folder")
        layout.addWidget(self.choose_btn)
        self.dont_show_cb = QCheckBox("Don't show this again")
        layout.addWidget(self.dont_show_cb)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.choose_btn.clicked.connect(self._choose_folder)
        self.selected_folder = None

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select TeslaCam Folder")
        if folder:
            self.selected_folder = folder

class TeslaCamViewer(QWidget):
    def __init__(self, show_welcome: bool = True):
        super().__init__()
        self.settings = QSettings()
        self.camera_name_to_index = {"front":0, "left_repeater":1, "right_repeater":2, "back":3, "left_pillar":4, "right_pillar":5}
        self.camera_index_to_name = {v: k for k, v in self.camera_name_to_index.items()}

        self.daily_clip_collections = [[] for _ in range(6)]
        self.export_start_ms, self.export_end_ms = None, None
        self.root_clips_path = None
        self.first_timestamp_of_day = None
        self.is_daily_view_active = False
        self.go_to_time_dialog_instance = None
        self.event_tooltip = widgets.EventToolTip(self)
        self.tooltip_timer = QTimer(self)
        self.tooltip_timer.setSingleShot(True)
        self.export_thread, self.export_worker = None, None
        self.files_to_cleanup_after_export = []
        self.last_text_update_time = 0
        self.playback_state = utils.PlaybackState(clip_indices=[-1]*6, segment_start_ms=0)
        self.was_playing_before_scrub = False

        self.setWindowTitle("TeslaCam Viewer")
        self.setMinimumSize(1280, 720)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(8)
        self.layout.setContentsMargins(8, 8, 8, 8)

        self._create_top_controls()
        self._create_video_grid()
        self._create_players_and_items()
        self._create_playback_controls()
        self._create_scrubber()
        self._create_actions_and_shortcuts()

        self.setLayout(self.layout)
        
        self.position_update_timer = QTimer(self); self.position_update_timer.setInterval(300)
        self.position_update_timer.timeout.connect(self.update_slider_and_time_display)
        
        self.load_settings()

        # First-time onboarding dialog
        if show_welcome:
            self._maybe_show_welcome_dialog()
        self.update_layout()


    def _maybe_show_welcome_dialog(self):
        if self.root_clips_path is not None and self.settings.value("welcome_seen", False, type=bool):
            return
        dlg = WelcomeDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if dlg.selected_folder:
                self._apply_root_folder(dlg.selected_folder)
            if dlg.dont_show_cb.isChecked() or dlg.selected_folder:
                self.settings.setValue("welcome_seen", True)
        else:
            if dlg.dont_show_cb.isChecked():
                self.settings.setValue("welcome_seen", True)

    def _create_top_controls(self):
        top_controls_layout = QHBoxLayout()
        self.select_folder_btn = QPushButton("📂 Select Clips"); self.select_folder_btn.clicked.connect(self.select_root_folder)
        self.go_to_time_btn = QPushButton("⏰ Go to Time"); self.go_to_time_btn.clicked.connect(self.show_go_to_time_dialog)
        self.reset_layout_btn = QPushButton("🔄 Reset Layout"); self.reset_layout_btn.clicked.connect(self.reset_to_default_layout)
        
        self.date_selector = QComboBox(); self.date_selector.setEnabled(False)
        self.date_selector.currentIndexChanged.connect(self.handle_date_selection_change)

        top_controls_layout.addWidget(self.select_folder_btn)
        top_controls_layout.addWidget(self.go_to_time_btn)
        top_controls_layout.addWidget(self.reset_layout_btn)
        top_controls_layout.addSpacing(15)
        top_controls_layout.addWidget(QLabel("Date:"))
        top_controls_layout.addWidget(self.date_selector)
        top_controls_layout.addSpacing(25)
        
        self.camera_visibility_checkboxes, self.checkbox_info = [], [
            ("LP", "Left Pillar", self.camera_name_to_index["left_pillar"]),("F", "Front", self.camera_name_to_index["front"]),
            ("RP", "Right Pillar", self.camera_name_to_index["right_pillar"]),("LR", "Left Repeater", self.camera_name_to_index["left_repeater"]),
            ("B", "Back", self.camera_name_to_index["back"]),("RR", "Right Repeater", self.camera_name_to_index["right_repeater"]),
        ]
        for abbr, full_name, _ in self.checkbox_info:
            cb = QCheckBox(abbr); cb.setToolTip(full_name); cb.setChecked(True)
            cb.toggled.connect(self.update_layout_from_visibility_change)
            self.camera_visibility_checkboxes.append(cb); top_controls_layout.addWidget(cb)
        
        top_controls_layout.addStretch(1)
        self.layout.addLayout(top_controls_layout)

    def _create_video_grid(self):
        self.video_grid_widget = QWidget(self)
        self.video_grid = QGridLayout(self.video_grid_widget)
        self.video_grid.setSpacing(3)
        self.layout.addWidget(self.video_grid_widget, 1)

    def _create_players_and_items(self):
        self.players_a, self.players_b = [], []
        self.video_player_item_widgets = []
        self.video_items_a, self.video_items_b = [], []
        self.active_player_set = 'a'

        for i in range(6):
            player_a = QMediaPlayer(); player_a.setAudioOutput(QAudioOutput())
            player_a.mediaStatusChanged.connect(lambda s, p=player_a, idx=i: self.handle_media_status_changed(s, p, idx))
            player_b = QMediaPlayer(); player_b.setAudioOutput(QAudioOutput())
            player_b.mediaStatusChanged.connect(lambda s, p=player_b, idx=i: self.handle_media_status_changed(s, p, idx))
            self.players_a.append(player_a); self.players_b.append(player_b)

            self.video_items_a.append(QGraphicsVideoItem())
            self.video_items_b.append(QGraphicsVideoItem())
            
            self.players_a[i].setVideoOutput(self.video_items_a[i])
            self.players_b[i].setVideoOutput(self.video_items_b[i])

            widget = widgets.VideoPlayerItemWidget(i, self)
            widget.set_video_item(self.video_items_a[i])
            self.video_player_item_widgets.append(widget)

    def _create_playback_controls(self):
        control_layout = QHBoxLayout(); control_layout.setSpacing(8); control_layout.addStretch()
        
        self.skip_bwd_15_btn = QPushButton("« 15s"); self.skip_bwd_15_btn.clicked.connect(lambda: self.seek_all_global(self.scrubber.value() - 15000))
        self.frame_back_btn = QPushButton("⏪ FR"); self.frame_back_btn.clicked.connect(lambda: self.frame_action(-33))
        self.play_btn = QPushButton("▶️ Play"); self.play_btn.clicked.connect(self.toggle_play_pause_all)
        self.frame_forward_btn = QPushButton("FR ⏩"); self.frame_forward_btn.clicked.connect(lambda: self.frame_action(33))
        self.skip_fwd_15_btn = QPushButton("15s »"); self.skip_fwd_15_btn.clicked.connect(lambda: self.seek_all_global(self.scrubber.value() + 15000))
        
        for btn in [self.skip_bwd_15_btn, self.frame_back_btn, self.play_btn, self.frame_forward_btn, self.skip_fwd_15_btn]:
            control_layout.addWidget(btn)
        
        control_layout.addSpacing(20)
        self.mark_start_btn = QPushButton("Set Start"); self.mark_start_btn.clicked.connect(self.mark_start_time)
        self.start_time_label = QLabel("Start: --:--"); 
        self.mark_end_btn = QPushButton("Set End"); self.mark_end_btn.clicked.connect(self.mark_end_time)
        self.end_time_label = QLabel("End: --:--")
        self.export_btn = QPushButton("Export Clip"); self.export_btn.clicked.connect(self.show_export_dialog)
        
        for w in [self.mark_start_btn, self.start_time_label, self.mark_end_btn, self.end_time_label, self.export_btn]:
            control_layout.addWidget(w)
            
        control_layout.addSpacing(20)
        self.speed_selector = QComboBox()
        self.playback_rates = {"0.25x":0.25, "0.5x":0.5, "1x":1.0, "1.5x":1.5, "2x":2.0, "4x":4.0}
        self.speed_selector.addItems(self.playback_rates.keys())
        self.speed_selector.currentTextChanged.connect(self.set_playback_speed)
        control_layout.addWidget(QLabel("Speed:"))
        control_layout.addWidget(self.speed_selector)
        
        control_layout.addStretch()
        self.layout.addLayout(control_layout)
        
    def _create_scrubber(self):
        self.slider_layout = QHBoxLayout()
        self.time_label = QLabel("MM/DD/YYYY hh:mm:ss (Clip: 00:00 / 00:00)")
        self.scrubber = widgets.ExportScrubber(Qt.Orientation.Horizontal)
        self.scrubber.setRange(0, 1000)
        self.scrubber.sliderMoved.connect(self.seek_all_global)
        self.scrubber.sliderPressed.connect(self._handle_scrubber_press)
        self.scrubber.sliderReleased.connect(self.handle_scrubber_release)
        self.scrubber.export_marker_moved.connect(self.handle_marker_drag)
        self.scrubber.event_marker_clicked.connect(self.handle_event_click)
        self.scrubber.event_marker_hovered.connect(self.handle_event_hover)
        self.scrubber.drag_started.connect(self._handle_scrubber_press)
        self.scrubber.drag_finished.connect(self.handle_scrubber_release)
        
        self.slider_layout.addWidget(self.time_label)
        self.slider_layout.addWidget(self.scrubber, 1)
        self.layout.addLayout(self.slider_layout)

    def _create_actions_and_shortcuts(self):
        # Play/Pause Action
        play_pause_action = QAction("Play/Pause", self)
        play_pause_action.setShortcut(QKeySequence(Qt.Key.Key_Space))
        play_pause_action.triggered.connect(self.toggle_play_pause_all)
        self.addAction(play_pause_action)

        # Frame Back Action
        frame_back_action = QAction("Frame Back", self)
        frame_back_action.setShortcut(QKeySequence(Qt.Key.Key_Left))
        frame_back_action.triggered.connect(lambda: self.frame_action(-33))
        self.addAction(frame_back_action)

        # Frame Forward Action
        frame_forward_action = QAction("Frame Forward", self)
        frame_forward_action.setShortcut(QKeySequence(Qt.Key.Key_Right))
        frame_forward_action.triggered.connect(lambda: self.frame_action(33))
        self.addAction(frame_forward_action)

        # Mark Start Action
        mark_start_action = QAction("Mark Start", self)
        mark_start_action.setShortcut(QKeySequence(Qt.Key.Key_M))
        mark_start_action.triggered.connect(self.mark_start_time)
        self.addAction(mark_start_action)

        # Mark End Action
        mark_end_action = QAction("Mark End", self)
        mark_end_action.setShortcut(QKeySequence(Qt.Key.Key_N))
        mark_end_action.triggered.connect(self.mark_end_time)
        self.addAction(mark_end_action)

        # Export Action
        export_action = QAction("Export", self)
        export_action.setShortcut(QKeySequence(Qt.Key.Key_E))
        export_action.triggered.connect(self.show_export_dialog)
        self.addAction(export_action)

    def get_active_players(self): return self.players_a if self.active_player_set == 'a' else self.players_b
    def get_inactive_players(self): return self.players_b if self.active_player_set == 'a' else self.players_a
    def get_active_video_items(self): return self.video_items_a if self.active_player_set == 'a' else self.video_items_b
        
    def reset_to_default_layout(self):
        for checkbox in self.camera_visibility_checkboxes:
            checkbox.blockSignals(True); checkbox.setChecked(True); checkbox.blockSignals(False)
        self.update_layout_from_visibility_change()

    def update_layout_from_visibility_change(self):
        self.ordered_visible_player_indices = [self.checkbox_info[i][2] for i, cb in enumerate(self.camera_visibility_checkboxes) if cb.isChecked()]
        self.update_layout(); self.save_settings()

    def load_settings(self):
        geom = self.settings.value("windowGeometry"); self.restoreGeometry(geom) if geom else self.setGeometry(50, 50, 1600, 950)
        self.speed_selector.setCurrentText(self.settings.value("lastSpeedText", "1x", type=str))
        vis_states = self.settings.value("cameraVisibility");
        if vis_states and len(vis_states) == len(self.camera_visibility_checkboxes):
            for i, cb in enumerate(self.camera_visibility_checkboxes): cb.setChecked(vis_states[i] == 'true')
        self.update_layout_from_visibility_change()
        last_folder = self.settings.value("lastRootFolder", "", type=str)
        if last_folder and os.path.isdir(last_folder):
            self.root_clips_path = last_folder; self.repopulate_date_selector_from_path(last_folder); self.date_selector.setCurrentIndex(-1)
        if not self.is_daily_view_active: self.clear_all_players()

    def save_settings(self):
        self.settings.setValue("windowGeometry", self.saveGeometry()); self.settings.setValue("lastRootFolder", self.root_clips_path or "")
        self.settings.setValue("lastSpeedText", self.speed_selector.currentText()); self.settings.setValue("cameraVisibility", [str(cb.isChecked()).lower() for cb in self.camera_visibility_checkboxes])

    def closeEvent(self, event): 
        self.save_settings()
        if self.export_thread and self.export_thread.isRunning():
            self.export_worker.stop(); self.export_thread.quit(); self.export_thread.wait()
        for p_set in [self.players_a, self.players_b]:
            for p in p_set: p.setSource(QUrl())
        super().closeEvent(event)

    def load_selected_date_videos(self):
        selected_date_str = self.date_selector.currentData()
        if not self.root_clips_path or not selected_date_str: return
        self.clear_all_players(); self.is_daily_view_active = True
        raw_files = {cam_idx: [] for cam_idx in range(6)}; all_ts = []; events = []
        try:
            potential_folders = [p for p in [os.path.join(self.root_clips_path, d) for d in os.listdir(self.root_clips_path)] if os.path.isdir(p) and os.path.basename(p).startswith(selected_date_str)]
            if not potential_folders:
                QMessageBox.warning(self, "No Data", f"No folders found for {selected_date_str}"); self.clear_all_players(); return
            
            for folder in potential_folders:
                for filename in os.listdir(folder):
                    m = utils.filename_pattern.match(filename)
                    if m:
                        try:
                            ts = datetime.strptime(f"{m.group(1)} {m.group(2).replace('-',':')}", "%Y-%m-%d %H:%M:%S")
                            cam_idx = self.camera_name_to_index[m.group(3)]; raw_files[cam_idx].append((os.path.join(folder, filename), ts)); all_ts.append(ts)
                        except (ValueError, KeyError): pass
                    elif filename == "event.json":
                        try:
                            with open(os.path.join(folder, filename), 'r') as f: data = json.load(f)
                            data['timestamp_dt'] = datetime.fromisoformat(data['timestamp']); data['folder_path'] = folder; events.append(data)
                        except (json.JSONDecodeError, KeyError, ValueError): pass

            if not all_ts:
                QMessageBox.warning(self, "No Videos", f"No valid video files found for {selected_date_str}."); self.clear_all_players(); return
            
            self.first_timestamp_of_day, last_ts = min(all_ts), max(all_ts)
            last_clip_path = next((f[0] for files in raw_files.values() for f in files if f[1] == last_ts), None)
            total_duration = int((last_ts - self.first_timestamp_of_day).total_seconds() * 1000) + utils.get_video_duration_ms(last_clip_path)
            self.scrubber.setRange(0, total_duration)
            
            for evt in events: evt['ms_in_timeline'] = (evt['timestamp_dt'] - self.first_timestamp_of_day).total_seconds() * 1000
            self.scrubber.set_events(events)

            for i in range(6):
                raw_files[i].sort(key=lambda x: x[1]); self.daily_clip_collections[i] = [f[0] for f in raw_files[i]]

            self._load_and_set_segment(0)
            self.update_layout()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading date videos: {e}"); traceback.print_exc(); self.clear_all_players()

    def handle_date_selection_change(self):
        if self.date_selector.currentIndex() >= 0: self.load_selected_date_videos()
        else: self.clear_all_players()

    def _apply_root_folder(self, folder):
        """Set root clips folder and refresh date selector."""
        if folder and os.path.isdir(folder):
            self.root_clips_path = folder
            self.clear_all_players()
            if not self.repopulate_date_selector_from_path(folder):
                QMessageBox.information(self, "No Dates", "No date folders found.")
            else:
                self.date_selector.setCurrentIndex(-1)

    def select_root_folder(self): 
        folder = QFileDialog.getExistingDirectory(self, "Select Clips Root", self.root_clips_path or os.path.expanduser("~"))
        self._apply_root_folder(folder)

    def repopulate_date_selector_from_path(self, folder_path):
        self.date_selector.blockSignals(True); self.date_selector.clear(); self.date_selector.setEnabled(False)
        date_folder_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2})")
        dates = sorted({m.group(1) for item in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, item)) and (m := date_folder_pattern.match(item))}, reverse=True)
        for date_str in dates:
            display_text = datetime.strptime(date_str, "%Y-%m-%d").strftime("%m/%d/%Y")
            self.date_selector.addItem(display_text, date_str)
        if dates: self.date_selector.setEnabled(True)
        self.date_selector.blockSignals(False); return bool(dates)

    def generate_and_set_thumbnail(self, video_path, timestamp_seconds):
        if not utils.FFMPEG_FOUND or not self.go_to_time_dialog_instance: return
        
        temp_fd, temp_file_path = tempfile.mkstemp(suffix=".jpg"); os.close(temp_fd)
        try:
            cmd = [utils.FFMPEG_PATH, "-y", "-ss", str(timestamp_seconds), "-i", video_path, "-vframes", "1", "-vf", "scale=192:-1", "-q:v", "3", temp_file_path]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            
            pixmap = QPixmap(temp_file_path) if os.path.exists(temp_file_path) else QPixmap()
            if self.go_to_time_dialog_instance: self.go_to_time_dialog_instance.set_thumbnail(pixmap)
            
        except Exception:
            if self.go_to_time_dialog_instance: self.go_to_time_dialog_instance.set_thumbnail(QPixmap())
        finally:
            if os.path.exists(temp_file_path):
                try: os.remove(temp_file_path)
                except OSError: pass
            
    def show_go_to_time_dialog(self):
        if not self.is_daily_view_active:
            QMessageBox.warning(self, "Action Required", "Please load a date before using 'Go to Time'."); return
        current_date_display = self.date_selector.currentText()
        current_date_data = self.date_selector.currentData()
        self.go_to_time_dialog_instance = widgets.GoToTimeDialog(self, current_date_display, self.first_timestamp_of_day, self.daily_clip_collections, self.camera_name_to_index["front"])
        self.go_to_time_dialog_instance.request_thumbnail.connect(self.generate_and_set_thumbnail)
        if self.go_to_time_dialog_instance.exec():
            time_str = self.go_to_time_dialog_instance.get_time_string().strip()
            if not time_str: return
            try: target_dt = datetime.strptime(f"{current_date_data} {time_str}", "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError): QMessageBox.warning(self,"Invalid Time","Please use HH:MM:SS format."); return
            if self.first_timestamp_of_day:
                global_ms = (target_dt - self.first_timestamp_of_day).total_seconds()*1000
                if 0 <= global_ms <= self.scrubber.maximum(): self.seek_all_global(int(global_ms))
                else: QMessageBox.information(self,"Out of Range","The specified time is outside the range of the current day's clips.")
        self.go_to_time_dialog_instance = None
    
    def toggle_play_pause_all(self):
        if not self.is_daily_view_active: return
        if any(p.playbackState() == QMediaPlayer.PlaybackState.PlayingState for p in self.get_active_players()): self.pause_all()
        else: self.play_all()

    def play_all(self): 
        self.play_btn.setText("⏸️ Pause"); rate = self.playback_rates.get(self.speed_selector.currentText(), 1.0)
        any_playing = False
        for i, p in enumerate(self.get_active_players()):
            if i in self.ordered_visible_player_indices and p.source() and p.source().isValid():
                p.setPlaybackRate(rate); p.play(); any_playing = True
        if any_playing: self.position_update_timer.start()

    def pause_all(self): 
        self.play_btn.setText("▶️ Play"); [p.pause() for p in self.get_active_players()]; self.position_update_timer.stop(); self.update_slider_and_time_display()
    
    def frame_action(self, offset_ms): 
        if not self.is_daily_view_active: return
        self.pause_all(); [p.setPosition(p.position() + offset_ms) for p in self.get_active_players() if p.source() and p.source().isValid()]; self.update_slider_and_time_display()

    def _handle_scrubber_press(self):
        if not self.is_daily_view_active: return
        self.was_playing_before_scrub = self.play_btn.text() == "⏸️ Pause"
        self.pause_all()

    def handle_scrubber_release(self):
        self.seek_all_global(self.scrubber.value())
        if self.was_playing_before_scrub:
            self.play_all()
        self.was_playing_before_scrub = False

    def seek_all_global(self, global_ms):
        if not self.is_daily_view_active or not self.first_timestamp_of_day: return
        
        target_dt = self.first_timestamp_of_day + timedelta(milliseconds=max(0, global_ms))
        front_clips = self.daily_clip_collections[self.camera_name_to_index["front"]]
        if not front_clips: return
        
        target_seg_idx = -1
        for i, p in enumerate(front_clips):
            m = utils.filename_pattern.match(os.path.basename(p))
            if m:
                s_dt = datetime.strptime(f"{m.group(1)} {m.group(2).replace('-' , ':')}", "%Y-%m-%d %H:%M:%S")
                if s_dt <= target_dt < s_dt + timedelta(seconds=60):
                    target_seg_idx = i; break
        if target_seg_idx == -1 and target_dt >= self.first_timestamp_of_day: target_seg_idx = len(front_clips) - 1
        if target_seg_idx == -1: return
        
        m = utils.filename_pattern.match(os.path.basename(front_clips[target_seg_idx])); s_dt = datetime.strptime(f"{m.group(1)} {m.group(2).replace('-' , ':')}", "%Y-%m-%d %H:%M:%S")
        pos_in_seg_ms = int((target_dt - s_dt).total_seconds() * 1000)
        
        if target_seg_idx != self.playback_state.clip_indices[0]:
            self._load_and_set_segment(target_seg_idx, pos_in_seg_ms)
        else:
            for p in self.get_active_players(): p.setPosition(pos_in_seg_ms)
        
        self.update_slider_and_time_display()

    def mark_start_time(self):
        if not self.is_daily_view_active: return
        self.export_start_ms = self.scrubber.value()
        if self.export_end_ms is not None and self.export_start_ms >= self.export_end_ms:
            self.export_end_ms = self.export_start_ms + 1000 
        self.update_export_ui()

    def mark_end_time(self):
        if not self.is_daily_view_active: return
        self.export_end_ms = self.scrubber.value()
        if self.export_start_ms is not None and self.export_end_ms <= self.export_start_ms:
            self.export_start_ms = self.export_end_ms - 1000
        self.update_export_ui()

    def handle_marker_drag(self, marker_type, value):
        if marker_type == 'start': self.export_start_ms = value
        elif marker_type == 'end': self.export_end_ms = value
        self.update_export_ui(); self.seek_all_global(value)

    def handle_event_click(self, event_data):
        seek_ms = event_data['ms_in_timeline']
        if 'sentry' in event_data['reason'] or 'user_interaction' in event_data['reason']:
            seek_ms -= 10000 
        self.seek_all_global(max(0, seek_ms))
        self.play_all()

    def handle_event_hover(self, event_data, global_pos):
        self.tooltip_timer.stop()
        try: self.tooltip_timer.timeout.disconnect()
        except TypeError: pass 
        
        if event_data:
            self.tooltip_timer.timeout.connect(lambda evt=event_data, pos=global_pos: self.show_event_tooltip(evt, pos))
            self.tooltip_timer.start(500)
        else: self.event_tooltip.hide()

    def show_event_tooltip(self, event_data, global_pos):
        self.event_tooltip.move(global_pos.x() - self.event_tooltip.width() // 2, global_pos.y() - self.event_tooltip.height() - 20)
        self.event_tooltip.show()
        
        thumb_path = os.path.join(event_data['folder_path'], 'thumb.png')
        pixmap = QPixmap(thumb_path) if os.path.exists(thumb_path) else QPixmap()
        self.event_tooltip.update_content(event_data['reason'], pixmap)

    def update_export_ui(self):
        self.start_time_label.setText(f"Start: {utils.format_time(self.export_start_ms)}")
        self.end_time_label.setText(f"End: {utils.format_time(self.export_end_ms)}")
        self.scrubber.set_export_range(self.export_start_ms, self.export_end_ms)

    def show_export_dialog(self):
        if not all([utils.FFMPEG_FOUND, self.is_daily_view_active, self.export_start_ms is not None, self.export_end_ms is not None]):
            QMessageBox.warning(self, "Export Error", "Please load clips and set both a start and end time before exporting."); return
        dialog = QDialog(self); dialog.setWindowTitle("Export Options"); layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Select export quality:")); full_res_rb = QRadioButton("Full Resolution"); mobile_rb = QRadioButton("Mobile Friendly - 1080p")
        full_res_rb.setChecked(True); layout.addWidget(full_res_rb); layout.addWidget(mobile_rb)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        if dialog.exec():
            output_path, _ = QFileDialog.getSaveFileName(self, "Save Exported Clip", f"{self.date_selector.currentData()}_clip.mp4", "MP4 Videos (*.mp4)")
            if output_path: self.start_export(output_path, mobile_rb.isChecked())

    def start_export(self, output_path, is_mobile):
        self.pause_all()
        result = self._build_ffmpeg_command(output_path, is_mobile)
        if not result:
            QMessageBox.critical(self, "Export Failed", "Could not generate FFmpeg command. No visible cameras or clips found for the selected range."); return
        
        ffmpeg_cmd, self.files_to_cleanup_after_export = result
        self.progress_dialog = QProgressDialog("Preparing export...", "Cancel", 0, 0, self); self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal); self.progress_dialog.setWindowTitle("Exporting"); self.progress_dialog.show()
        
        self.export_worker = workers.ExportWorker(ffmpeg_cmd); self.export_thread = QThread(); self.export_worker.moveToThread(self.export_thread)
        self.export_thread.started.connect(self.export_worker.run); self.export_worker.finished.connect(self.on_export_finished)
        self.export_worker.progress.connect(self.progress_dialog.setLabelText); self.progress_dialog.canceled.connect(self.export_worker.stop)
        self.export_thread.start()

    def on_export_finished(self, success, message):
        self.progress_dialog.close()
        if self.export_thread: self.export_thread.quit(); self.export_thread.wait()
        if success: QMessageBox.information(self, "Export Complete", message)
        else: QMessageBox.critical(self, "Export Failed", message)
        for path in self.files_to_cleanup_after_export:
            try: os.remove(path)
            except OSError as e: print(f"Error removing temp file {path}: {e}")
        self.files_to_cleanup_after_export.clear()
        self.export_thread, self.export_worker = None, None

    def _build_ffmpeg_command(self, output_path, is_mobile):
        start_dt = self.first_timestamp_of_day + timedelta(milliseconds=self.export_start_ms)
        duration = (self.export_end_ms - self.export_start_ms) / 1000.0
        
        inputs, temp_files = [], []
        front_cam_idx = self.camera_name_to_index["front"]
        
        for p_idx in self.ordered_visible_player_indices:
            if not self.daily_clip_collections[p_idx]: continue
            clips_in_range = [(p, s_dt) for p in self.daily_clip_collections[p_idx] if (m:=utils.filename_pattern.match(os.path.basename(p))) and (s_dt:=datetime.strptime(f"{m.group(1)} {m.group(2).replace('-' , ':')}", "%Y-%m-%d %H:%M:%S")) < start_dt + timedelta(seconds=duration) and s_dt + timedelta(seconds=60) > start_dt]
            if not clips_in_range: continue
            
            fd, path = tempfile.mkstemp(suffix=".txt", text=True); temp_files.append(path)
            with os.fdopen(fd, 'w') as f:
                [f.write(f"file '{os.path.abspath(p)}'\n") for p, _ in clips_in_range]
            inputs.append({"p_idx": p_idx, "path": path, "offset": max(0, (start_dt - clips_in_range[0][1]).total_seconds())})

        if not inputs: return None

        cmd = [utils.FFMPEG_PATH, "-y"]
        initial_filters = []
        stream_maps = []
        
        for i, stream_data in enumerate(inputs):
            cmd.extend(["-f", "concat", "-safe", "0", "-ss", str(stream_data["offset"]), "-i", stream_data["path"]])
            is_front = stream_data["p_idx"] == front_cam_idx
            scale_filter = ",scale=1448:938" if is_front else ""
            initial_filters.append(f"[{i}:v]setpts=PTS-STARTPTS{scale_filter}[v{i}]")
            stream_maps.append(f"[v{i}]")
        
        main_processing_chain = []
        num_streams = len(inputs)
        last_output_tag = "[v0]"

        if num_streams > 1:
            cols = 2 if num_streams in [2, 4] else 3
            w, h = (1448, 938)
            layout = '|'.join([f"{c*w}_{r*h}" for i in range(num_streams) for r, c in [divmod(i, cols)]])
            main_processing_chain.append(f"{''.join(stream_maps)}xstack=inputs={num_streams}:layout={layout}")
            last_output_tag = ""
        else:
            w, h, cols = 1448, 938, 1

        start_time_unix = start_dt.timestamp()
        basetime_us = int(start_time_unix * 1_000_000)

        drawtext_filter = (
            "drawtext="
            "font='Arial':"
            f"expansion=strftime:basetime={basetime_us}:"
            "text='%m/%d/%Y %I\\:%M\\:%S %p':"
            "fontcolor=white:fontsize=36:box=1:boxcolor=black@0.4:boxborderw=5:"
            "x=(w-text_w)/2:y=h-th-10"
        )
        main_processing_chain.append(f"{last_output_tag}{drawtext_filter}")

        if is_mobile:
            total_width = w * cols
            total_height = h * math.ceil(num_streams / cols)
            mobile_width = int(1080 * (total_width / total_height)) // 2 * 2
            main_processing_chain.append(f"scale={mobile_width}:1080")
        
        # Chain all main processing filters together with commas
        chained_processing = ",".join(main_processing_chain)
        
        # Add the final output tag to the end of the chain
        final_video_stream = "[final_v]"
        chained_processing += final_video_stream

        # Join the initial setup chains and the main chain with a semicolon
        full_filter_complex = ";".join(initial_filters + [chained_processing])
        
        cmd.extend(["-filter_complex", full_filter_complex, "-map", final_video_stream])
        
        audio_stream_idx = next((i for i, data in enumerate(inputs) if data["p_idx"] == front_cam_idx), -1)
        if audio_stream_idx != -1: cmd.extend(["-map", f"{audio_stream_idx}:a?"])
        
        v_codec = ["-c:v", "libx264", "-preset", "fast", "-crf", "23"] if is_mobile else ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]
        cmd.extend(["-t", str(duration), *v_codec, "-c:a", "aac", "-b:a", "128k", output_path])
        return cmd, temp_files
    
    def set_playback_speed(self, speed_text):
        rate = self.playback_rates.get(speed_text,1.0)
        for p_set in [self.players_a, self.players_b]:
            for p in p_set: p.setPlaybackRate(rate)

    def update_slider_and_time_display(self):
        try:
            if not self.is_daily_view_active or not self.first_timestamp_of_day: return
            
            ref_player = self.get_active_players()[self.camera_name_to_index["front"]]
            if not (ref_player.source() and ref_player.source().isValid()):
                ref_player = next((p for i, p in enumerate(self.get_active_players()) if p.source() and p.source().isValid()), None)

            if not ref_player:
                if self.play_btn.text() != "▶️ Play":
                     if self.scrubber.value() < self.scrubber.maximum(): self.scrubber.setValue(self.scrubber.maximum())
                     self.pause_all()
                return

            current_pos = ref_player.position()
            global_position = min(self.playback_state.segment_start_ms + current_pos, self.scrubber.maximum())
            
            if not self.scrubber.isSliderDown(): 
                self.scrubber.blockSignals(True); self.scrubber.setValue(global_position); self.scrubber.blockSignals(False)
            
            current_time = time.time()
            if current_time - self.last_text_update_time > 1 or self.play_btn.text() == "▶️ Play":
                clip_duration = ref_player.duration()
                global_time = self.first_timestamp_of_day + timedelta(milliseconds=global_position)
                self.time_label.setText(f"{global_time.strftime('%m/%d/%Y %I:%M:%S %p')} (Clip: {utils.format_time(current_pos)} / {utils.format_time(clip_duration if clip_duration > 0 else 0)})")
                self.last_text_update_time = current_time
        
        except Exception as e:
            if utils.DEBUG_UI: print(f"Error in update_slider_and_time_display: {e}"); traceback.print_exc()
    
    def clear_all_players(self): 
        self.position_update_timer.stop()
        for p_set in [self.players_a, self.players_b]:
            for p in p_set: p.stop(); p.setSource(QUrl())
        self.playback_state = utils.PlaybackState(clip_indices=[-1]*6, segment_start_ms=0)
        self.is_daily_view_active=False
        self.time_label.setText("MM/DD/YYYY HH:MM:SS (Clip: 00:00 / 00:00)")
        self.scrubber.setValue(0); self.scrubber.setMaximum(1000)
        self.play_btn.setText("▶️ Play"); self.speed_selector.setCurrentText("1x") 
        self.export_start_ms = None; self.export_end_ms = None
        self.scrubber.set_events([]); self.update_export_ui()

    def _load_and_set_segment(self, segment_index, position_ms=0):
        self.active_player_set = 'a'
        active_players = self.get_active_players()
        
        front_clips = self.daily_clip_collections[self.camera_name_to_index["front"]]
        m = utils.filename_pattern.match(os.path.basename(front_clips[segment_index]))
        s_dt = datetime.strptime(f"{m.group(1)} {m.group(2).replace('-' , ':')}", "%Y-%m-%d %H:%M:%S")
        self.playback_state = utils.PlaybackState(clip_indices=[segment_index]*6, segment_start_ms=int((s_dt - self.first_timestamp_of_day).total_seconds() * 1000))

        for i in range(6):
            self._load_next_clip_for_player_set(active_players, i)
            active_players[i].setPosition(position_ms)
        
        self._preload_next_segment()

    def _preload_next_segment(self):
        if not self.is_daily_view_active: return
        next_segment_index = self.playback_state.clip_indices[0] + 1
        front_cam_idx = self.camera_name_to_index["front"]
        if next_segment_index >= len(self.daily_clip_collections[front_cam_idx]): return
        
        inactive_players = self.get_inactive_players()
        if inactive_players[front_cam_idx].source().isValid():
            path = inactive_players[front_cam_idx].source().path()
            if os.path.basename(path) == os.path.basename(self.daily_clip_collections[front_cam_idx][next_segment_index]):
                return
        
        if utils.DEBUG_UI: print(f"--- Preloading segment {next_segment_index} ---")
        for i in range(6):
            self._load_next_clip_for_player_set(inactive_players, i, next_segment_index)

    def _load_next_clip_for_player_set(self, player_set, player_index, force_index=None):
        idx_to_load = force_index if force_index is not None else self.playback_state.clip_indices[player_index]
        clips = self.daily_clip_collections[player_index]
        if 0 <= idx_to_load < len(clips):
            player_set[player_index].setSource(QUrl.fromLocalFile(clips[idx_to_load]))
        else: player_set[player_index].setSource(QUrl())
            
    def handle_media_status_changed(self, status, player_instance, player_index):
        front_idx = self.camera_name_to_index["front"]

        if status == QMediaPlayer.MediaStatus.EndOfMedia and player_instance.source() and player_instance.source().isValid():
            if player_index == front_idx and player_instance in self.get_active_players():
                self._swap_player_sets()
        
        elif status == QMediaPlayer.MediaStatus.LoadedMedia: 
            self.video_player_item_widgets[player_index].fit_video_to_view()

    def _swap_player_sets(self):
        if utils.DEBUG_UI: print(f"--- Swapping player sets. New active set: {'b' if self.active_player_set == 'a' else 'a'} ---")
        was_playing = self.play_btn.text() == "⏸️ Pause"
        [p.stop() for p in self.get_active_players()]
        
        self.active_player_set = 'b' if self.active_player_set == 'a' else 'a'
        active_players = self.get_active_players()
        active_video_items = self.get_active_video_items()
        
        next_segment_index = self.playback_state.clip_indices[0] + 1
        front_cam_idx = self.camera_name_to_index["front"]
        
        if next_segment_index >= len(self.daily_clip_collections[front_cam_idx]):
            self.pause_all(); return
        
        self.playback_state.clip_indices = [next_segment_index] * 6
        
        front_clips = self.daily_clip_collections[front_cam_idx]
        m = utils.filename_pattern.match(os.path.basename(front_clips[next_segment_index]))
        s_dt = datetime.strptime(f"{m.group(1)} {m.group(2).replace('-' , ':')}", "%Y-%m-%d %H:%M:%S")
        self.playback_state.segment_start_ms = int((s_dt - self.first_timestamp_of_day).total_seconds() * 1000)

        for i in range(6):
            self.video_player_item_widgets[i].set_video_item(active_video_items[i])
            active_players[i].setPosition(0)
        
        if active_players[front_cam_idx].mediaStatus() == QMediaPlayer.MediaStatus.InvalidMedia:
            if utils.DEBUG_UI: print(f"--- Segment {next_segment_index} is invalid, skipping. ---")
            QTimer.singleShot(0, self._swap_player_sets)
            return

        if was_playing: self.play_all()
        self._preload_next_segment()

    def update_layout(self):
        while self.video_grid.count():
            item = self.video_grid.takeAt(0)
            if item and item.widget(): 
                item.widget().setParent(None); item.widget().hide()
        
        num_visible = len(self.ordered_visible_player_indices)
        if num_visible == 0: self.video_grid.update(); return 

        cols = 1 if num_visible == 1 else 2 if num_visible in [2, 4] else 3
        
        current_col, current_row = 0, 0
        for p_idx in self.ordered_visible_player_indices:
            widget = self.video_player_item_widgets[p_idx]; widget.setVisible(True); widget.reset_view() 
            self.video_grid.addWidget(widget, current_row, current_col)
            
            active_video_item = self.get_active_video_items()[p_idx]
            widget.set_video_item(active_video_item)

            current_col += 1
            if current_col >= cols: current_col = 0; current_row += 1

        for hidden_idx in (set(range(6)) - set(self.ordered_visible_player_indices)):
            self.video_player_item_widgets[hidden_idx].setVisible(False)
        
        self.video_grid_widget.update()