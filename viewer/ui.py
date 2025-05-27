from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog,
                             QGridLayout, QHBoxLayout, QInputDialog, QMessageBox,
                             QSlider, QComboBox, QRadioButton, QButtonGroup, QApplication,
                             QLineEdit, QDialog, QMenu, QSizePolicy,
                             QGraphicsView, QGraphicsScene) 
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt6.QtCore import (Qt, QUrl, QTimer, QSettings, QByteArray, QPointF, QRectF, 
                          QSize, pyqtSignal, QMimeData, QPoint) 
from PyQt6.QtGui import (QIcon, QPixmap, QPainter, QMouseEvent, QWheelEvent, QAction, 
                         QDrag, QTransform) 

import os
import traceback
from datetime import datetime, timedelta
import re
import subprocess
import tempfile
import shutil
import math 

try:
    import __main__
    DEBUG_UI = __main__.DEBUG if hasattr(__main__, 'DEBUG') else False
except (ImportError, AttributeError):
    DEBUG_UI = False 

FFMPEG_PATH = "ffmpeg" 
FFMPEG_FOUND = False

def find_ffmpeg():
    global FFMPEG_PATH, FFMPEG_FOUND
    ffmpeg_exe = shutil.which("ffmpeg")
    if ffmpeg_exe: FFMPEG_PATH = ffmpeg_exe; FFMPEG_FOUND = True
    else: FFMPEG_FOUND = False
    if DEBUG_UI: print(f"FFmpeg found: {FFMPEG_FOUND} at {FFMPEG_PATH if FFMPEG_FOUND else 'N/A'}")
    return FFMPEG_FOUND

FFMPEG_FOUND = find_ffmpeg()


class VideoPlayerItemWidget(QGraphicsView):
    def __init__(self, player_index: int, media_player: QMediaPlayer, parent=None):
        super().__init__(parent)
        self.player_index = player_index
        self.media_player = media_player
        self.scene = QGraphicsScene(self)
        self.video_item = QGraphicsVideoItem()
        self.scene.addItem(self.video_item)
        self.setScene(self.scene)
        self.media_player.setVideoOutput(self.video_item)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag) 
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumSize(100,75)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setObjectName(f"VideoPlayerItemWidget_{player_index}")

    def video_native_size(self) -> QSize: return self.video_item.nativeSize()
    def fit_video_to_view(self):
        if self.video_item.nativeSize().isEmpty(): return
        self.fitInView(self.video_item, Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event: QWheelEvent):
        current_scale = self.transform().m11()
        if event.angleDelta().y() > 0: factor = 1.15
        else: factor = 1 / 1.15
        if current_scale * factor > 7.0 and factor > 1.0: factor = 7.0 / current_scale if current_scale > 0 else 7.0
        elif current_scale * factor < 1.0 and factor < 1.0:
            if current_scale <= 1.001: self.setTransform(QTransform()); self.fit_video_to_view(); event.accept(); return
            factor = 1.0 / current_scale if current_scale > 0 else 1.0
        if abs(factor - 1.0) > 0.001 and factor > 0: self.scale(factor, factor)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent): super().mousePressEvent(event) 
    def mouseMoveEvent(self, event: QMouseEvent): super().mouseMoveEvent(event)
    def reset_view(self): self.setTransform(QTransform()); self.fit_video_to_view()
    def resizeEvent(self, event): super().resizeEvent(event); self.fit_video_to_view()


class GoToTimeDialog(QDialog): 
    request_thumbnail = pyqtSignal(str, float) 
    def __init__(self, parent=None, current_date_str="", first_timestamp_of_day=None, daily_clip_collections=None, front_cam_idx=None):
        super().__init__(parent)
        self.setWindowTitle("Go to Timestamp"); self.setMinimumWidth(400)
        self.layout = QVBoxLayout(self)
        self.info_label = QLabel(f"Date: {current_date_str}\nEnter time (HH:MM:SS) or full (YYYY-MM-DD HH:MM:SS)")
        self.layout.addWidget(self.info_label)
        self.time_input = QLineEdit(self); self.time_input.setPlaceholderText("HH:MM:SS or YYYY-MM-DD HH:MM:SS")
        self.time_input.textChanged.connect(self.on_time_input_changed); self.layout.addWidget(self.time_input)
        self.thumbnail_label = QLabel("Enter time to see preview..."); self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setMinimumSize(320, 180); self.thumbnail_label.setStyleSheet("border: 1px solid #444; background-color: #222;")
        self.layout.addWidget(self.thumbnail_label)
        self.buttons_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK"); self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancel"); self.cancel_button.clicked.connect(self.reject)
        self.buttons_layout.addWidget(self.ok_button); self.buttons_layout.addWidget(self.cancel_button)
        self.layout.addLayout(self.buttons_layout)
        if parent: self.setStyleSheet(parent.styleSheet()) 
        self.current_date_str_for_dialog = current_date_str
        self.first_timestamp_of_day_for_thumb = first_timestamp_of_day 
        self.daily_clip_collections_for_thumb = daily_clip_collections; self.front_cam_idx_for_thumb = front_cam_idx
        self.thumbnail_timer = QTimer(self); self.thumbnail_timer.setSingleShot(True); self.thumbnail_timer.timeout.connect(self.trigger_thumbnail_generation)
    def on_time_input_changed(self, text): self.thumbnail_label.setText("Generating preview..."); self.thumbnail_label.setPixmap(QPixmap()); self.thumbnail_timer.start(750) 
    def trigger_thumbnail_generation(self): 
        time_str_input = self.time_input.text().strip()
        if not time_str_input or not FFMPEG_FOUND: self.thumbnail_label.setText("Preview N/A (No input/ffmpeg)"); return
        target_dt_for_thumb = None
        try: target_dt_for_thumb = datetime.strptime(time_str_input, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try: 
                if self.current_date_str_for_dialog and self.current_date_str_for_dialog != "N/A (No date loaded)":
                    date_part = datetime.strptime(self.current_date_str_for_dialog, "%Y-%m-%d").date()
                    target_dt_for_thumb = datetime.combine(date_part, datetime.strptime(time_str_input, "%H:%M:%S").time())
            except ValueError: self.thumbnail_label.setText("Invalid time format for preview"); return
        if target_dt_for_thumb and self.first_timestamp_of_day_for_thumb and \
           self.daily_clip_collections_for_thumb and self.front_cam_idx_for_thumb is not None:
            time_offset_seconds = (target_dt_for_thumb - self.first_timestamp_of_day_for_thumb).total_seconds()
            if time_offset_seconds < 0: self.thumbnail_label.setText("Time before day start"); return
            segment_index = int(time_offset_seconds // 60); offset_in_segment = time_offset_seconds % 60
            front_cam_clips = self.daily_clip_collections_for_thumb[self.front_cam_idx_for_thumb]
            if front_cam_clips and 0 <= segment_index < len(front_cam_clips):
                self.request_thumbnail.emit(front_cam_clips[segment_index], offset_in_segment)
            else: self.thumbnail_label.setText("Time out of range for preview")
        else: self.thumbnail_label.setText("Day context needed for preview")
    def set_thumbnail(self, pixmap:QPixmap):
        if pixmap and not pixmap.isNull(): self.thumbnail_label.setPixmap(pixmap.scaled(self.thumbnail_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else: self.thumbnail_label.setText("Preview failed or N/A")
    def get_time_string(self): return self.time_input.text()


class TeslaCamViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings() 
        self.camera_name_to_index = {"front":0,"left_repeater":1,"right_repeater":2,"back":3,"left_pillar":4,"right_pillar":5}
        # Default visual order: LP, F, RP, LR, B, RR (Player Indices)
        self.default_player_order = [
            self.camera_name_to_index["left_pillar"], self.camera_name_to_index["front"], self.camera_name_to_index["right_pillar"],
            self.camera_name_to_index["left_repeater"], self.camera_name_to_index["back"], self.camera_name_to_index["right_repeater"]
        ]
        self.camera_index_to_name = {v:k for k,v in self.camera_name_to_index.items()}
        self.filename_pattern = re.compile(r"(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})-(front|left_repeater|right_repeater|back|left_pillar|right_pillar)\.mp4")
        
        self.setWindowTitle("TeslaCam Viewer"); self.setMinimumSize(1280,720); self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.layout = QVBoxLayout(self); self.layout.setSpacing(8); self.layout.setContentsMargins(8,8,8,8)

        top_controls_layout = QHBoxLayout()
        self.select_folder_btn = QPushButton("📂 Select Clips"); self.select_folder_btn.clicked.connect(self.select_root_folder)
        top_controls_layout.addWidget(self.select_folder_btn)
        self.go_to_time_btn = QPushButton("⏰ Go to Time"); self.go_to_time_btn.clicked.connect(self.show_go_to_time_dialog)
        top_controls_layout.addWidget(self.go_to_time_btn); 
        
        self.reset_layout_btn = QPushButton("🔄 Reset Layout"); self.reset_layout_btn.clicked.connect(self.reset_to_default_layout)
        top_controls_layout.addWidget(self.reset_layout_btn)
        top_controls_layout.addSpacing(15)

        self.date_selector_label = QLabel("Date:")
        self.date_selector = QComboBox(); self.date_selector.setEnabled(False)
        self.date_selector.currentIndexChanged.connect(self.handle_date_selection_change)
        top_controls_layout.addWidget(self.date_selector_label); top_controls_layout.addWidget(self.date_selector)
        
        self.visible_cameras_button = QPushButton("📺 Visible Cameras")
        self.visible_cameras_menu = QMenu(self)
        self.camera_visibility_actions = [] 
        self.menu_cam_names_ordered = ["Front","Back","Left Repeater","Right Repeater","Left Pillar","Right Pillar"]
        # This maps the MENU item order to player indices.
        self.player_indices_for_menu_actions = [self.camera_name_to_index[name.lower().replace(" ","_")] for name in self.menu_cam_names_ordered]

        for name_in_menu in self.menu_cam_names_ordered:
            action = QAction(name_in_menu,self,checkable=True); action.setChecked(True) 
            action.triggered.connect(self.update_layout_from_visibility_change)
            self.visible_cameras_menu.addAction(action); self.camera_visibility_actions.append(action)
        self.visible_cameras_button.setMenu(self.visible_cameras_menu)
        top_controls_layout.addSpacing(15); top_controls_layout.addWidget(self.visible_cameras_button)
        top_controls_layout.addStretch(1); self.layout.addLayout(top_controls_layout)

        self.video_grid_widget = QWidget(self) 
        self.video_grid = QGridLayout(self.video_grid_widget) 
        self.video_grid.setSpacing(3)
        self.layout.addWidget(self.video_grid_widget, 1)

        self.players = []
        self.video_player_item_widgets = [] 
        self.sources = [None] * 6
        self.ordered_visible_player_indices = list(self.default_player_order) # Initialize with default order

        for i in range(6):
            player = QMediaPlayer(); player.setAudioOutput(QAudioOutput())
            player.mediaStatusChanged.connect(lambda s,p=player,pi=i:self.handle_media_status_changed(s,p,pi))
            self.players.append(player)
            video_item_widget = VideoPlayerItemWidget(i, player, self.video_grid_widget)
            self.video_player_item_widgets.append(video_item_widget)
        
        control_layout = QHBoxLayout(); control_layout.setSpacing(8); control_layout.addStretch()
        self.skip_bwd_15_btn=QPushButton("« 15s"); self.skip_bwd_15_btn.clicked.connect(self.skip_backward_15s)
        self.frame_back_btn=QPushButton("⏪ FR"); self.frame_back_btn.clicked.connect(self.frame_back)
        self.play_btn=QPushButton("▶️ Play"); self.play_btn.clicked.connect(self.toggle_play_pause_all)
        self.frame_forward_btn=QPushButton("FR ⏩"); self.frame_forward_btn.clicked.connect(self.frame_forward)
        self.skip_fwd_15_btn=QPushButton("15s »"); self.skip_fwd_15_btn.clicked.connect(self.skip_forward_15s)
        for btn in [self.skip_bwd_15_btn,self.frame_back_btn,self.play_btn,self.frame_forward_btn,self.skip_fwd_15_btn]: control_layout.addWidget(btn)
        control_layout.addSpacing(20); speed_label=QLabel("Speed:")
        self.speed_selector=QComboBox(); self.playback_rates={"0.25x":0.25,"0.5x":0.5,"1x":1.0,"1.5x":1.5,"2x":2.0,"4x":4.0}
        self.speed_selector.addItems(self.playback_rates.keys()); self.speed_selector.currentTextChanged.connect(self.handle_speed_change)
        control_layout.addWidget(speed_label); control_layout.addWidget(self.speed_selector)
        control_layout.addStretch(); self.layout.addLayout(control_layout)

        self.slider_layout = QHBoxLayout()
        self.time_label = QLabel("YYYY-MM-DD HH:MM:SS (Clip: 00:00 / 00:00)")
        self.scrubber = QSlider(Qt.Orientation.Horizontal)
        self.scrubber.setRange(0,1000); self.scrubber.sliderReleased.connect(self.handle_scrubber_release); self.scrubber.setTracking(True)
        self.slider_layout.addWidget(self.time_label); self.slider_layout.addWidget(self.scrubber,1)
        self.layout.addLayout(self.slider_layout); self.setLayout(self.layout)

        self.sync_timer=QTimer(); self.sync_timer.timeout.connect(self.sync_playback); self.sync_timer.start(1000)
        self.slider_timer=QTimer(); self.slider_timer.timeout.connect(self.update_slider_and_time_display); self.slider_timer.start(200)
        self.daily_clip_collections=[[] for _ in range(6)]; self.current_clip_indices=[-1]*6
        self.root_clips_path=None; self.current_segment_start_datetime=None; self.first_timestamp_of_day=None
        self.is_daily_view_active=False; self.temp_thumbnail_file=None; self.go_to_time_dialog_instance=None
        
        self.load_settings(); self.update_layout()

    def reset_to_default_layout(self):
        if DEBUG_UI: print("Resetting to default layout.")
        # Set all cameras to visible
        for action in self.camera_visibility_actions:
            action.setChecked(True)
        
        # Reset the ordered list to the default order
        self.ordered_visible_player_indices = list(self.default_player_order) # Use a copy
        
        self.update_layout()
        # Save these new default settings
        self.settings.setValue("cameraVisibility", [True] * len(self.camera_visibility_actions))
        self.settings.setValue("orderedVisiblePlayerIndices", self.ordered_visible_player_indices)


    def update_layout_from_visibility_change(self):
        new_ordered_indices = []
        # Iterate through the *menu's defined order* to build the new visible list
        # This ensures that if a user checks "Front", it tries to appear where "Front" would normally be
        # in the default order, if possible, or appends.
        
        # Get a list of player indices that are currently checked in the menu
        player_indices_checked_in_menu = []
        for menu_idx, action in enumerate(self.camera_visibility_actions):
            if action.isChecked():
                player_indices_checked_in_menu.append(self.player_indices_for_menu_actions[menu_idx])

        # Try to maintain the current order for items that are still checked
        for player_idx in self.ordered_visible_player_indices:
            if player_idx in player_indices_checked_in_menu:
                new_ordered_indices.append(player_idx)
        
        # Add any newly checked items that weren't in the previous order
        for player_idx in player_indices_checked_in_menu:
            if player_idx not in new_ordered_indices:
                # Find a logical place to insert or just append
                # For simplicity, append. More complex logic could insert based on default_player_order position.
                new_ordered_indices.append(player_idx)
        
        self.ordered_visible_player_indices = new_ordered_indices
        
        if DEBUG_UI: print(f"Visibility change. New order: {self.ordered_visible_player_indices}")
        self.update_layout()
        self.settings.setValue("cameraVisibility", [act.isChecked() for act in self.camera_visibility_actions])
        self.settings.setValue("orderedVisiblePlayerIndices", self.ordered_visible_player_indices)


    def load_settings(self):
        if DEBUG_UI: print("Loading settings...")
        geom = self.settings.value("windowGeometry")
        if geom and isinstance(geom, QByteArray): self.restoreGeometry(geom)
        else: self.setGeometry(50, 50, 1600, 950)

        last_speed_text = self.settings.value("lastSpeedText", "1x", type=str)
        if last_speed_text in self.playback_rates: self.speed_selector.setCurrentText(last_speed_text)
        self.set_playback_speed(self.speed_selector.currentText())

        raw_visibility_states = self.settings.value("cameraVisibility")
        visibility_loaded_correctly = False
        if raw_visibility_states and isinstance(raw_visibility_states, list) and len(raw_visibility_states) == len(self.camera_visibility_actions):
            converted_states = []
            for state in raw_visibility_states:
                if isinstance(state, str): converted_states.append(state.lower() == 'true')
                elif isinstance(state, int): converted_states.append(bool(state))
                elif isinstance(state, bool): converted_states.append(state)
                else: converted_states.append(True)
            if len(converted_states) == len(self.camera_visibility_actions):
                 for i, action in enumerate(self.camera_visibility_actions): action.setChecked(converted_states[i])
                 visibility_loaded_correctly = True
        if not visibility_loaded_correctly: # Default if no valid setting
            for action in self.camera_visibility_actions: action.setChecked(True)

        # Build current_visible_player_indices based on loaded (or default) QAction states
        current_visible_player_indices = []
        for menu_idx, action in enumerate(self.camera_visibility_actions):
            if action.isChecked():
                current_visible_player_indices.append(self.player_indices_for_menu_actions[menu_idx])
        
        # Load saved order and filter/extend it
        saved_ordered_indices = self.settings.value("orderedVisiblePlayerIndices")
        final_ordered_list = []
        if saved_ordered_indices and isinstance(saved_ordered_indices, list):
            valid_saved_indices = [idx for idx in saved_ordered_indices if isinstance(idx, int) and 0 <= idx < 6]
            # Add items from saved order if they are currently supposed to be visible
            final_ordered_list = [idx for idx in valid_saved_indices if idx in current_visible_player_indices]
        
        # Add any currently visible items that weren't in the loaded (and filtered) saved order
        # This ensures all *checked* cameras appear, maintaining saved order for those that were saved.
        for visible_idx in current_visible_player_indices:
            if visible_idx not in final_ordered_list:
                # Try to insert based on default_player_order, or append
                inserted = False
                for i, default_idx in enumerate(self.default_player_order):
                    if default_idx == visible_idx:
                        # Find appropriate insertion point in final_ordered_list
                        # to maintain relative default order
                        pos_to_insert = 0
                        for existing_idx_in_final in final_ordered_list:
                            if self.default_player_order.index(existing_idx_in_final) < i:
                                pos_to_insert +=1
                            else:
                                break
                        final_ordered_list.insert(pos_to_insert, visible_idx)
                        inserted = True
                        break
                if not inserted: # Fallback: append if not in default order somehow
                    final_ordered_list.append(visible_idx)

        self.ordered_visible_player_indices = final_ordered_list
        if DEBUG_UI: print(f"Loaded ordered_visible_player_indices: {self.ordered_visible_player_indices}")

        last_folder = self.settings.value("lastRootFolder", "", type=str)
        if last_folder and os.path.isdir(last_folder):
            self.root_clips_path = last_folder
            self.repopulate_date_selector_from_path(last_folder) # Populates dates
            self.date_selector.setCurrentIndex(-1) # Ensure no date is auto-selected
            if self.date_selector.count() > 0:
                 if DEBUG_UI: print(f"Dates populated for {last_folder}. User must select a date.")
            elif self.is_daily_view_active : # If was active but folder has no dates now
                self.clear_all_players()
        
        if not self.is_daily_view_active : # If after all loading, no date videos are active
             self.clear_all_players()
             # self.update_layout() # update_layout is called at end of __init__ anyway

    def save_settings(self):
        if DEBUG_UI: print("Saving settings...")
        self.settings.setValue("windowGeometry", self.saveGeometry())
        self.settings.setValue("lastRootFolder", self.root_clips_path if self.root_clips_path else "")
        self.settings.setValue("lastSpeedText", self.speed_selector.currentText())
        self.settings.setValue("cameraVisibility", [act.isChecked() for act in self.camera_visibility_actions])
        self.settings.setValue("orderedVisiblePlayerIndices", self.ordered_visible_player_indices)
        self.settings.remove("lastSelectedDate") 

    def closeEvent(self, event): 
        self.save_settings()
        if self.temp_thumbnail_file and os.path.exists(self.temp_thumbnail_file):
            try: os.remove(self.temp_thumbnail_file)
            except Exception as e: print(f"Error removing temp thumbnail: {e}")
        for player in self.players:
            if player.source() and player.source().isValid(): player.setSource(QUrl())
        super().closeEvent(event)

    def handle_speed_change(self, speed_text): self.set_playback_speed(speed_text)
    def handle_date_selection_change(self):
        if not self.date_selector.isEnabled() and self.date_selector.count() == 0: return
        if self.date_selector.currentIndex() >= 0:
            self.load_selected_date_videos()
        else: 
            self.clear_all_players(); self.update_layout()

    def generate_and_set_thumbnail(self, video_path, timestamp_seconds):
        if not FFMPEG_FOUND:
            if self.go_to_time_dialog_instance: self.go_to_time_dialog_instance.set_thumbnail(QPixmap()); return
        if self.temp_thumbnail_file and os.path.exists(self.temp_thumbnail_file):
            try: os.remove(self.temp_thumbnail_file)
            except: pass 
        temp_fd, self.temp_thumbnail_file = tempfile.mkstemp(suffix=".jpg"); os.close(temp_fd)
        try:
            cmd = [FFMPEG_PATH,"-y","-ss",str(timestamp_seconds),"-i",video_path,"-vframes","1","-vf","scale=320:-1","-q:v","3",self.temp_thumbnail_file]
            if DEBUG_UI: print(f"FFmpeg thumb: {' '.join(cmd)}")
            proc = subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            _, stderr = proc.communicate(timeout=5)
            if proc.returncode==0 and os.path.exists(self.temp_thumbnail_file) and self.go_to_time_dialog_instance:
                self.go_to_time_dialog_instance.set_thumbnail(QPixmap(self.temp_thumbnail_file))
            else:
                if DEBUG_UI and stderr: print(f"FFmpeg thumb err: {stderr.decode(errors='ignore')}")
                if self.go_to_time_dialog_instance: self.go_to_time_dialog_instance.set_thumbnail(QPixmap())
        except subprocess.TimeoutExpired:
            if DEBUG_UI: print("FFmpeg thumb timeout.");
            if self.go_to_time_dialog_instance: self.go_to_time_dialog_instance.set_thumbnail(QPixmap())
            if 'proc' in locals() and hasattr(proc, 'kill') and proc.poll() is None: proc.kill()
        except Exception as e:
            if DEBUG_UI: traceback.print_exc()
            if self.go_to_time_dialog_instance: self.go_to_time_dialog_instance.set_thumbnail(QPixmap())

    def show_go_to_time_dialog(self):
        current_date_loaded = self.date_selector.currentText() if self.date_selector.isEnabled() and self.date_selector.currentIndex() >=0 else "N/A (No date loaded)"
        self.go_to_time_dialog_instance = GoToTimeDialog(self, current_date_loaded, self.first_timestamp_of_day, self.daily_clip_collections, self.camera_name_to_index["front"])
        self.go_to_time_dialog_instance.request_thumbnail.connect(self.generate_and_set_thumbnail)
        if self.go_to_time_dialog_instance.exec():
            time_str_input = self.go_to_time_dialog_instance.get_time_string().strip();
            if not time_str_input: return
            target_dt, parsed_date = None, None
            try: target_dt = datetime.strptime(time_str_input, "%Y-%m-%d %H:%M:%S"); parsed_date = target_dt.strftime("%Y-%m-%d")
            except ValueError:
                if not self.is_daily_view_active or not self.first_timestamp_of_day: QMessageBox.warning(self,"Error","Load day for HH:MM:SS."); return
                try: target_dt = datetime.combine(self.first_timestamp_of_day.date(), datetime.strptime(time_str_input, "%H:%M:%S").time())
                except ValueError: QMessageBox.warning(self,"Invalid Time","Use HH:MM:SS or YYYY-MM-DD HH:MM:SS."); return
            if target_dt:
                if parsed_date and parsed_date != self.date_selector.currentText():
                    if not self.root_clips_path: QMessageBox.warning(self,"Error","No root folder."); return
                    if not os.path.isdir(os.path.join(self.root_clips_path, parsed_date)): QMessageBox.warning(self,"Date Not Found",f"Folder {parsed_date} missing."); return
                    idx = self.date_selector.findText(parsed_date)
                    if idx != -1: self.date_selector.setCurrentIndex(idx); QTimer.singleShot(500,lambda:self.perform_seek_after_date_change(target_dt)); return 
                    else: QMessageBox.warning(self,"Error",f"Cannot switch to {parsed_date}."); return
                if self.first_timestamp_of_day:
                    max_ms = self.scrubber.maximum()
                    day_end_approx = self.first_timestamp_of_day + timedelta(milliseconds=max_ms) if max_ms > 0 else self.first_timestamp_of_day + timedelta(hours=24) # Approximate end
                    if not (self.first_timestamp_of_day <= target_dt <= day_end_approx) : QMessageBox.information(self,"Out of Range","Time outside current day."); return
                    global_ms = (target_dt - self.first_timestamp_of_day).total_seconds()*1000
                    if global_ms >= 0: self.seek_all_global(int(global_ms))
                    else: QMessageBox.warning(self,"Seek Error","Negative seek time.")
                else: QMessageBox.warning(self,"Error","No day loaded.")
        if self.temp_thumbnail_file and os.path.exists(self.temp_thumbnail_file):
            try: os.remove(self.temp_thumbnail_file); self.temp_thumbnail_file = None
            except: pass
        self.go_to_time_dialog_instance = None

    def perform_seek_after_date_change(self, target_datetime_to_seek):
        if self.is_daily_view_active and self.first_timestamp_of_day:
            global_ms = (target_datetime_to_seek - self.first_timestamp_of_day).total_seconds()*1000
            if 0 <= global_ms <= self.scrubber.maximum(): self.seek_all_global(int(global_ms))
            else: 
                QMessageBox.information(self,"Seek Info",f"Time out of range. Seeking to start."); self.seek_all_global(0)
        else: QMessageBox.warning(self,"Load Error","Could not load new date for seek.")

    def set_playback_speed(self, speed_text): 
        rate = self.playback_rates.get(speed_text,1.0)
        for p in self.players: p.setPlaybackRate(rate)

    def handle_scrubber_release(self): 
        if self.is_daily_view_active and self.first_timestamp_of_day: self.seek_all_global(self.scrubber.value())
        elif not self.is_daily_view_active: self.seek_individual_clips(self.scrubber.value())

    def seek_individual_clips(self, position_ms): 
        for p in self.players: 
            if p.source() and p.source().isValid() and p.duration()>0: p.setPosition(max(0,min(position_ms,p.duration())))

    def skip_backward_15s(self): 
        if not self.is_daily_view_active or not self.first_timestamp_of_day: return
        self.seek_all_global(max(0, self.scrubber.value()-15000))

    def skip_forward_15s(self): 
        if not self.is_daily_view_active or not self.first_timestamp_of_day: return
        self.seek_all_global(min(self.scrubber.maximum(), self.scrubber.value()+15000))

    def clear_all_players(self): 
        for p in self.players: p.stop(); p.setSource(QUrl())
        self.sources=[None]*6; self.daily_clip_collections=[[] for _ in range(6)]; self.current_clip_indices=[-1]*6
        self.current_segment_start_datetime=None; self.time_label.setText("YYYY-MM-DD HH:MM:SS (Clip: 00:00 / 00:00)")
        self.scrubber.setValue(0); self.scrubber.setMaximum(1000); self.is_daily_view_active=False
        self.play_btn.setText("▶️ Play"); self.speed_selector.setCurrentText("1x") 
        for p in self.players: p.setPlaybackRate(1.0)
        for container in self.video_player_item_widgets: container.reset_view()

    def repopulate_date_selector_from_path(self, folder_path): 
        self.date_selector.blockSignals(True); self.date_selector.clear(); self.date_selector.setEnabled(False)
        potential_dates = []
        if folder_path and os.path.isdir(folder_path):
            try:
                for item in os.listdir(folder_path):
                    if os.path.isdir(os.path.join(folder_path, item)) and re.match(r"^\d{4}-\d{2}-\d{2}$", item):
                        potential_dates.append(item)
                if potential_dates: self.date_selector.addItems(sorted(potential_dates, reverse=True)); self.date_selector.setEnabled(True)
            except Exception as e:
                if DEBUG_UI: print(f"Error repopulating dates: {e}")
        self.date_selector.blockSignals(False); return self.date_selector.count() > 0

    def select_root_folder(self): 
        initial_dir = self.root_clips_path if self.root_clips_path else os.path.expanduser("~")
        root_folder = QFileDialog.getExistingDirectory(self,"Select RecentClips Root",initial_dir)
        if not root_folder or not os.path.isdir(root_folder): return
        self.root_clips_path=root_folder; self.clear_all_players()
        if not self.repopulate_date_selector_from_path(root_folder):
             QMessageBox.information(self,"No Dates","No date folders found."); self.clear_all_players()
        else: # Dates were found, ensure date selector is blank
            self.date_selector.setCurrentIndex(-1)
        self.update_layout()


    def load_selected_date_videos(self): 
        if not self.root_clips_path or self.date_selector.currentIndex()<0: 
            if DEBUG_UI: print(f"Load videos precondition fail: root={self.root_clips_path}, date_idx={self.date_selector.currentIndex()}")
            return
        selected_date_str = self.date_selector.currentText()
        if not selected_date_str: self.clear_all_players(); return
        if DEBUG_UI: print(f"\n--- Loading Date: {selected_date_str} ---")
        date_folder_path = os.path.join(self.root_clips_path, selected_date_str)
        was_playing = (self.play_btn.text() == "⏸️ Pause")
        for p in self.players: p.stop(); p.setSource(QUrl())
        self.sources=[None]*6; self.daily_clip_collections=[[] for _ in range(6)]; self.current_clip_indices=[-1]*6
        self.current_segment_start_datetime=None; self.first_timestamp_of_day=None
        for container in self.video_player_item_widgets: container.reset_view()
        self.is_daily_view_active=True
        raw_files_by_camera = {name:[] for name in self.camera_name_to_index.keys()}
        try:
            if DEBUG_UI: print(f"Scanning folder: {date_folder_path}")
            for filename in os.listdir(date_folder_path):
                match = self.filename_pattern.match(filename)
                if match:
                    date_f,time_f,cam_type = match.groups()
                    if cam_type in raw_files_by_camera:
                        try:
                            time_f_corrected = time_f.replace('-', ':').replace('_', ':')
                            ts_dt = datetime.strptime(f"{date_f} {time_f_corrected}", "%Y-%m-%d %H:%M:%S")
                            raw_files_by_camera[cam_type].append((ts_dt, os.path.join(date_folder_path, filename)))
                        except ValueError as ve: 
                            if DEBUG_UI: print(f"Date parse error for {filename}: {ve}")
            
            for cam_name, files_with_ts in raw_files_by_camera.items():
                idx = self.camera_name_to_index[cam_name]
                self.daily_clip_collections[idx] = [f[1] for f in sorted(files_with_ts, key=lambda x:x[0])]
                if DEBUG_UI and not files_with_ts: print(f"No files found for camera: {cam_name}")
                elif DEBUG_UI and self.daily_clip_collections[idx]: print(f"Cam {cam_name}: {len(files_with_ts)} files. First: {os.path.basename(self.daily_clip_collections[idx][0])}")

            all_first_ts = []
            for i, cam_clips in enumerate(self.daily_clip_collections):
                if cam_clips:
                    match = self.filename_pattern.match(os.path.basename(cam_clips[0]))
                    if match: 
                        time_f_corrected = match.group(2).replace('-',':').replace('_',':')
                        all_first_ts.append(datetime.strptime(f"{match.group(1)} {time_f_corrected}", "%Y-%m-%d %H:%M:%S"))
                    else: 
                        if DEBUG_UI: print(f"Filename parse error for first clip of cam {i}: {cam_clips[0]}") 
            if not all_first_ts:
                self.is_daily_view_active=False; QMessageBox.information(self,"No Videos",f"No valid video files for {selected_date_str}."); self.clear_all_players(); return
            self.first_timestamp_of_day = min(all_first_ts)
            if DEBUG_UI: print(f"First timestamp of day: {self.first_timestamp_of_day}")
            all_last_ts_ends = []
            for cam_clips in self.daily_clip_collections:
                if cam_clips:
                    match = self.filename_pattern.match(os.path.basename(cam_clips[-1]))
                    if match: 
                        time_f_corrected = match.group(2).replace('-',':').replace('_',':')
                        all_last_ts_ends.append(datetime.strptime(f"{match.group(1)} {time_f_corrected}", "%Y-%m-%d %H:%M:%S") + timedelta(seconds=59, milliseconds=999))
            if all_last_ts_ends: self.scrubber.setRange(0, int(max(60000, (max(all_last_ts_ends) - self.first_timestamp_of_day).total_seconds()*1000)))
            else: self.scrubber.setRange(0,60000)
            if DEBUG_UI: print(f"Scrubber range set to: 0 - {self.scrubber.maximum()}")
            for i in range(6): self.load_next_clip_for_player(i, is_initial_load=True)
            self.update_layout() 
            if was_playing: QTimer.singleShot(300, self.play_all)
        except Exception as e:
            traceback.print_exc(); QMessageBox.critical(self,"Error Loading Date",f"Error: {e}"); self.clear_all_players(); self.is_daily_view_active=False

    def load_next_clip_for_player(self, player_index, is_initial_load=False, target_clip_index_override=None):
        if target_clip_index_override is not None: self.current_clip_indices[player_index] = target_clip_index_override - 1
        self.current_clip_indices[player_index] += 1
        current_idx = self.current_clip_indices[player_index]
        clips_for_player = self.daily_clip_collections[player_index]
        if 0 <= current_idx < len(clips_for_player):
            clip_path = clips_for_player[current_idx]
            if DEBUG_UI: print(f"P{player_index} (idx {current_idx}): Loading {os.path.basename(clip_path)}")
            self.players[player_index].setSource(QUrl.fromLocalFile(clip_path))
            self.sources[player_index] = clip_path
            if player_index == self.camera_name_to_index["front"] or (is_initial_load and not self.current_segment_start_datetime):
                match = self.filename_pattern.match(os.path.basename(clip_path))
                if match:
                    time_f_corr = match.group(2).replace('-',':').replace('_',':')
                    self.current_segment_start_datetime = datetime.strptime(f"{match.group(1)} {time_f_corr}", "%Y-%m-%d %H:%M:%S")
            if not is_initial_load and self.play_btn.text() == "⏸️ Pause": 
                rate = self.playback_rates.get(self.speed_selector.currentText(), 1.0)
                self.players[player_index].setPlaybackRate(rate); self.players[player_index].play()
        else:
            if DEBUG_UI and clips_for_player : print(f"P{player_index}: No more clips (idx {current_idx}/{len(clips_for_player)}).")
            self.players[player_index].setSource(QUrl()); self.sources[player_index] = None

    def handle_media_status_changed(self, status, player_instance, player_index): 
        source_path = player_instance.source().path() if player_instance.source() and player_instance.source().isValid() else "N/A"
        base_name = os.path.basename(source_path) if source_path != "N/A" else "N/A"
        if DEBUG_UI: print(f"P{player_index} ({base_name}): MediaStatus {status}, Error: {player_instance.errorString()}")
        
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self.players[player_index] is player_instance and player_instance.source() and player_instance.source().isValid():
            if DEBUG_UI: print(f"P{player_index}: EndOfMedia.")
            if player_index == self.camera_name_to_index["front"]:
                next_idx = self.current_clip_indices[player_index] + 1
                for i in range(6): self.load_next_clip_for_player(i, target_clip_index_override=next_idx)
            else: self.load_next_clip_for_player(player_index)
        elif status == QMediaPlayer.MediaStatus.LoadedMedia:
            if 0 <= player_index < len(self.video_player_item_widgets):
                self.video_player_item_widgets[player_index].fit_video_to_view()
        elif status in [QMediaPlayer.MediaStatus.InvalidMedia, QMediaPlayer.MediaStatus.NoMedia, 
                        QMediaPlayer.MediaStatus.StalledMedia, QMediaPlayer.MediaStatus.BufferingMedia]:
            if DEBUG_UI: print(f"P{player_index} ({base_name}): Problem status {status}. Error: {player_instance.errorString()}")


    def update_slider_and_time_display(self): 
        if not self.is_daily_view_active: self.time_label.setText("Time: --:-- (Clip: --:--)"); return
        ref_player, ref_player_idx_for_source = None, None
        front_idx = self.camera_name_to_index["front"]
        if self.players[front_idx].source() and self.players[front_idx].source().isValid() and self.players[front_idx].duration() > 0:
            ref_player, ref_player_idx_for_source = self.players[front_idx], front_idx
        else: 
            for idx, p_alt in enumerate(self.players):
                if p_alt.source() and p_alt.source().isValid() and p_alt.duration() > 0:
                    ref_player, ref_player_idx_for_source = p_alt, idx; break
        if not ref_player: self.time_label.setText("Time: --:-- (Clip: --:--)"); return
        pos_ms, dur_ms = ref_player.position(), ref_player.duration()
        if dur_ms <= 0: self.time_label.setText("Loading..."); return
        current_clip_src = self.sources[ref_player_idx_for_source]
        if (ref_player_idx_for_source == front_idx or not self.current_segment_start_datetime) and current_clip_src:
            match = self.filename_pattern.match(os.path.basename(current_clip_src))
            if match: 
                time_f_corr = match.group(2).replace('-',':').replace('_',':')
                self.current_segment_start_datetime = datetime.strptime(f"{match.group(1)} {time_f_corr}", "%Y-%m-%d %H:%M:%S")
        time_str_24h = "YYYY-MM-DD HH:MM:SS"
        if self.current_segment_start_datetime: time_str_24h = (self.current_segment_start_datetime + timedelta(milliseconds=pos_ms)).strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.setText(f"{time_str_24h} (Clip: {self.format_time(pos_ms)} / {self.format_time(dur_ms)})")
        if self.first_timestamp_of_day and self.current_segment_start_datetime and not self.scrubber.isSliderDown():
            base_offset = (self.current_segment_start_datetime - self.first_timestamp_of_day).total_seconds()*1000.0
            self.scrubber.setValue(int(base_offset + pos_ms))

    def seek_all_global(self, global_ms): 
        if not self.is_daily_view_active or not self.first_timestamp_of_day: self.seek_individual_clips(global_ms); return
        target_dt = self.first_timestamp_of_day + timedelta(milliseconds=global_ms)
        front_clips = self.daily_clip_collections[self.camera_name_to_index["front"]]
        if not front_clips: return
        target_seg_idx, pos_in_seg_ms = -1, 0
        for idx, clip_path in enumerate(front_clips):
            match = self.filename_pattern.match(os.path.basename(clip_path))
            if match:
                time_f_corr_start = match.group(2).replace('-',':').replace('_',':')
                clip_start_dt = datetime.strptime(f"{match.group(1)} {time_f_corr_start}", "%Y-%m-%d %H:%M:%S")
                clip_end_dt = clip_start_dt + timedelta(seconds=59,milliseconds=999) 
                if idx<len(front_clips)-1:
                    next_m = self.filename_pattern.match(os.path.basename(front_clips[idx+1]))
                    if next_m: 
                        time_f_corr_next = next_m.group(2).replace('-',':').replace('_',':')
                        clip_end_dt = datetime.strptime(f"{next_m.group(1)} {time_f_corr_next}", "%Y-%m-%d %H:%M:%S")
                if clip_start_dt <= target_dt < clip_end_dt or (idx==len(front_clips)-1 and target_dt>=clip_start_dt):
                    target_seg_idx = idx; pos_in_seg_ms = int((target_dt-clip_start_dt).total_seconds()*1000)
                    if idx==len(front_clips)-1: pos_in_seg_ms = min(max(0,pos_in_seg_ms),59900); break
        if target_seg_idx != -1:
            was_playing=(self.play_btn.text()=="⏸️ Pause"); self.pause_all()
            for i in range(6): self.load_next_clip_for_player(i, target_clip_index_override=target_seg_idx)
            if not self.scrubber.isSliderDown(): self.scrubber.setValue(global_ms)
            def apply_pos():
                for i in range(6):
                    if self.players[i].source() and self.players[i].source().isValid():
                        dur=self.players[i].duration(); clamped_pos=min(max(0,pos_in_seg_ms),(dur-100 if dur>100 else 0) if dur>0 else 59900)
                        self.players[i].setPosition(clamped_pos)
                self.update_slider_and_time_display();
                if was_playing: self.play_all()
            QTimer.singleShot(350, apply_pos)

    def toggle_play_pause_all(self): 
        is_playing=any(p.playbackState()==QMediaPlayer.PlaybackState.PlayingState for p in self.players if p.source() and p.source().isValid())
        if is_playing: self.pause_all()
        else: self.play_all()

    def play_all(self): 
        self.play_btn.setText("⏸️ Pause") 
        rate=self.playback_rates.get(self.speed_selector.currentText(),1.0)
        for p_idx, p in enumerate(self.players): 
            if p_idx in self.ordered_visible_player_indices and p.source() and p.source().isValid(): 
                p.setPlaybackRate(rate); p.play()
            elif p.playbackState() == QMediaPlayer.PlaybackState.PlayingState: 
                 p.pause()

    def pause_all(self): 
        self.play_btn.setText("▶️ Play") 
        for p in self.players:
            if p.source() and p.source().isValid(): p.pause()
    
    def frame_action(self, offset_ms): 
        self.pause_all()
        for p in self.players:
            if p.source() and p.source().isValid():
                dur=p.duration(); new_pos=p.position()+offset_ms
                if dur>0: new_pos=min(max(0,new_pos), dur-1 if offset_ms > 0 else dur) 
                else: new_pos=max(0,new_pos)
                p.setPosition(new_pos)
        self.update_slider_and_time_display()
    def frame_forward(self): self.frame_action(33)
    def frame_back(self): self.frame_action(-33)

    def sync_playback(self): 
        if not self.is_daily_view_active or self.play_btn.text()!="⏸️ Pause": return
        active_sync_players = [self.players[idx] for idx in self.ordered_visible_player_indices 
                               if self.players[idx].source() and self.players[idx].source().isValid()]
        if not active_sync_players: return
        
        positions = [p.position() for p in active_sync_players if p.playbackState() == QMediaPlayer.PlaybackState.PlayingState]
        if not positions: return 

        avg_pos=sum(positions)//len(positions); rate=self.playback_rates.get(self.speed_selector.currentText(),1.0)
        for p in active_sync_players: 
            if p.playbackState() == QMediaPlayer.PlaybackState.PlayingState and abs(p.position()-avg_pos)>700: 
                p.setPosition(avg_pos)
            elif p.playbackState() == QMediaPlayer.PlaybackState.PausedState and abs(p.position()-avg_pos)<=700: 
                p.setPlaybackRate(rate); p.play()

    def format_time(self, ms): 
        s=max(0,ms//1000); return f"{s//60:02}:{s%60:02}"

    def update_layout(self):
        while self.video_grid.count():
            item = self.video_grid.takeAt(0)
            if item and item.widget(): item.widget().setParent(None); item.widget().hide()

        num_visible = len(self.ordered_visible_player_indices)
        if DEBUG_UI: print(f"Update layout: {num_visible} visible. Order: {self.ordered_visible_player_indices}")

        cols, rows = 0, 0
        if num_visible == 0: self.video_grid.update(); return 
        elif num_visible == 1: cols, rows = 1, 1
        elif num_visible == 2: cols, rows = 2, 1
        elif num_visible == 3: cols, rows = 3, 1
        elif num_visible == 4: cols, rows = 2, 2
        elif num_visible == 5: cols, rows = 3, 2 # For 5, use 3 columns, 2 rows (one empty slot)
        elif num_visible >= 6: cols, rows = 3, 2 # Max 6, in 3x2
        
        current_col, current_row = 0, 0
        for player_idx in self.ordered_visible_player_indices:
            if 0 <= player_idx < len(self.video_player_item_widgets): 
                widget_container = self.video_player_item_widgets[player_idx]
                widget_container.setVisible(True)
                widget_container.reset_view() 
                self.video_grid.addWidget(widget_container, current_row, current_col)
                if self.players[player_idx].videoOutput() is not widget_container.video_item:
                     self.players[player_idx].setVideoOutput(widget_container.video_item)
                current_col += 1
                if current_col >= cols: current_col = 0; current_row += 1
            else:
                if DEBUG_UI: print(f"Warning: Player index {player_idx} out of bounds during layout.")
        
        all_indices_set = set(range(len(self.video_player_item_widgets)))
        visible_set = set(self.ordered_visible_player_indices)
        for hidden_idx in (all_indices_set - visible_set):
            if 0 <= hidden_idx < len(self.video_player_item_widgets): 
                self.video_player_item_widgets[hidden_idx].setVisible(False)
        self.video_grid_widget.update()
        if DEBUG_UI: print(f"Layout updated: {rows}r, {cols}c. Visible indices: {self.ordered_visible_player_indices}")
