"""
Video Player Manager for Sentry-Six.

Handles all video player operations including creation, management, playback control,
and player set switching for seamless video playback.
"""

import os
from typing import List, Set, Optional, Callable
from datetime import datetime, timedelta

from PyQt6.QtWidgets import QWidget
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt6.QtCore import QUrl, pyqtSignal, QObject

from .. import utils
from ..state import AppState, PlaybackState
from .. import widgets


class VideoPlayerManager(QObject):
    """Manages video players and their lifecycle operations."""
    
    # Signals
    media_status_changed = pyqtSignal(object, object, int)  # status, player, index
    player_swap_requested = pyqtSignal()
    
    def __init__(self, parent: QWidget, app_state: AppState, camera_map: dict):
        super().__init__(parent)
        self._parent = parent
        self.app_state = app_state
        self.camera_map = camera_map
        
        # Player sets for seamless switching
        self.players_a: List[QMediaPlayer] = []
        self.players_b: List[QMediaPlayer] = []
        self.video_items_a: List[QGraphicsVideoItem] = []
        self.video_items_b: List[QGraphicsVideoItem] = []
        self.active_player_set = 'a'
        
        # Player widgets
        self.video_player_item_widgets: List[widgets.VideoPlayerItemWidget] = []
        
        # State for robust seeking
        self.pending_seek_position = -1
        self.players_awaiting_seek: Set[QMediaPlayer] = set()
        
        self._create_players_and_items()
    
    def _create_players_and_items(self):
        """Create all video players and their associated widgets."""
        for i in range(6):
            # Create players for both sets
            player_a = QMediaPlayer()
            player_a.setAudioOutput(QAudioOutput())
            player_a.mediaStatusChanged.connect(
                lambda s, p=player_a, idx=i: self._handle_media_status_changed(s, p, idx)
            )
            
            player_b = QMediaPlayer()
            player_b.setAudioOutput(QAudioOutput())
            player_b.mediaStatusChanged.connect(
                lambda s, p=player_b, idx=i: self._handle_media_status_changed(s, p, idx)
            )
            
            self.players_a.append(player_a)
            self.players_b.append(player_b)
            
            # Create video items
            self.video_items_a.append(QGraphicsVideoItem())
            self.video_items_b.append(QGraphicsVideoItem())
            
            # Connect players to video items
            self.players_a[i].setVideoOutput(self.video_items_a[i])
            self.players_b[i].setVideoOutput(self.video_items_b[i])
            
            # Create widget
            widget = widgets.VideoPlayerItemWidget(i, self._parent)
            widget.set_video_item(self.video_items_a[i])
            widget.swap_requested.connect(self._handle_widget_swap)
            self.video_player_item_widgets.append(widget)
    
    def _handle_media_status_changed(self, status, player_instance, player_index):
        """Handle media status changes and emit signals."""
        self.media_status_changed.emit(status, player_instance, player_index)
    
    def _handle_widget_swap(self, dragged_index, dropped_on_index):
        """Handle widget swap requests from the UI."""
        # This will be handled by the layout manager
        pass
    
    def get_active_players(self) -> List[QMediaPlayer]:
        """Get the currently active player set."""
        return self.players_a if self.active_player_set == 'a' else self.players_b
    
    def get_inactive_players(self) -> List[QMediaPlayer]:
        """Get the currently inactive player set."""
        return self.players_b if self.active_player_set == 'a' else self.players_a
    
    def get_active_video_items(self) -> List[QGraphicsVideoItem]:
        """Get the currently active video items."""
        return self.video_items_a if self.active_player_set == 'a' else self.video_items_b
    
    def get_player_widgets(self) -> List[widgets.VideoPlayerItemWidget]:
        """Get all video player widgets."""
        return self.video_player_item_widgets
    
    def play_all(self):
        """Start playback on all active players."""
        for player in self.get_active_players():
            if player.source() and player.source().isValid():
                player.play()
    
    def pause_all(self):
        """Pause all active players."""
        for player in self.get_active_players():
            player.pause()
    
    def stop_all(self):
        """Stop all players in both sets."""
        for player_set in [self.players_a, self.players_b]:
            for player in player_set:
                player.stop()
    
    def set_playback_rate(self, rate: float):
        """Set playback rate for all players."""
        for player_set in [self.players_a, self.players_b]:
            for player in player_set:
                player.setPlaybackRate(rate)
    
    def seek_all(self, position_ms: int):
        """Seek all active players to the specified position."""
        for player in self.get_active_players():
            if player.source() and player.source().isValid():
                player.setPosition(position_ms)
    
    def load_segment(self, segment_index: int, position_ms: int = 0):
        """Load a specific segment into the active players."""
        # Cancel any previous pending seek operation
        self.pending_seek_position = -1
        self.players_awaiting_seek.clear()
        
        # Switch to player set 'a' for consistent state
        self.active_player_set = 'a'
        active_players = self.get_active_players()
        active_video_items = self.get_active_video_items()
        
        # Stop inactive players
        for player in self.get_inactive_players():
            player.stop()
        
        # Validate segment index
        front_clips = self.app_state.daily_clip_collections[self.camera_map["front"]]
        if not (0 <= segment_index < len(front_clips)):
            if utils.DEBUG_UI:
                print(f"Segment index {segment_index} out of range. Aborting load.")
            return
        
        # Calculate segment timing
        m = utils.filename_pattern.match(os.path.basename(front_clips[segment_index]))
        if m and self.app_state.first_timestamp_of_day:
            s_dt = datetime.strptime(f"{m.group(1)} {m.group(2).replace('-', ':')}", "%Y-%m-%d %H:%M:%S")
            segment_start_ms = int((s_dt - self.app_state.first_timestamp_of_day).total_seconds() * 1000)
        else:
            segment_start_ms = 0
        
        # Update playback state
        self.app_state.playback_state = PlaybackState(
            clip_indices=[segment_index] * 6, 
            segment_start_ms=segment_start_ms
        )
        
        # Update UI widgets
        for i in range(6):
            self.video_player_item_widgets[i].set_video_item(active_video_items[i])
        
        # Determine which players need loading
        players_to_load = set()
        for i in range(6):
            clips = self.app_state.daily_clip_collections[i]
            if 0 <= segment_index < len(clips):
                players_to_load.add(active_players[i])
        
        if not players_to_load:
            return
        
        if utils.DEBUG_UI:
            print(f"--- Loading segment {segment_index}, preparing pending seek to {position_ms}ms ---")
        
        # Set up pending seek operation
        self.pending_seek_position = position_ms
        self.players_awaiting_seek = players_to_load
        
        # Load clips into active players
        for i in range(6):
            self._load_clip_for_player(active_players, i)
        
        # Preload next segment
        self._preload_next_segment()
    
    def _load_clip_for_player(self, player_set: List[QMediaPlayer], player_index: int, force_index: Optional[int] = None):
        """Load a clip for a specific player."""
        idx_to_load = force_index if force_index is not None else self.app_state.playback_state.clip_indices[player_index]
        clips = self.app_state.daily_clip_collections[player_index]
        
        if 0 <= idx_to_load < len(clips):
            player_set[player_index].setSource(QUrl.fromLocalFile(clips[idx_to_load]))
        else:
            player_set[player_index].setSource(QUrl())
    
    def _preload_next_segment(self):
        """Preload the next segment into inactive players."""
        if not self.app_state.is_daily_view_active:
            return
        
        next_segment_index = self.app_state.playback_state.clip_indices[0] + 1
        front_cam_idx = self.camera_map["front"]
        
        if next_segment_index >= len(self.app_state.daily_clip_collections[front_cam_idx]):
            return
        
        inactive_players = self.get_inactive_players()
        
        # Check if already preloaded
        if inactive_players[front_cam_idx].source().isValid():
            path = inactive_players[front_cam_idx].source().path()
            if os.path.basename(path) == os.path.basename(
                self.app_state.daily_clip_collections[front_cam_idx][next_segment_index]
            ):
                return
        
        if utils.DEBUG_UI:
            print(f"--- Preloading segment {next_segment_index} ---")
        
        for i in range(6):
            self._load_clip_for_player(inactive_players, i, next_segment_index)
    
    def swap_player_sets(self):
        """Swap between player sets for seamless playback."""
        # Cancel any pending seeks
        self.pending_seek_position = -1
        self.players_awaiting_seek.clear()
        
        if utils.DEBUG_UI:
            print(f"--- Swapping player sets. New active set: {'b' if self.active_player_set == 'a' else 'a'} ---")
        
        # Stop current active players
        for player in self.get_active_players():
            player.stop()
        
        # Switch active set
        self.active_player_set = 'b' if self.active_player_set == 'a' else 'a'
        active_players = self.get_active_players()
        active_video_items = self.get_active_video_items()
        
        # Calculate next segment
        next_segment_index = self.app_state.playback_state.clip_indices[0] + 1
        front_cam_idx = self.camera_map["front"]
        
        if next_segment_index >= len(self.app_state.daily_clip_collections[front_cam_idx]):
            return False  # No more segments
        
        # Update playback state
        front_clips = self.app_state.daily_clip_collections[front_cam_idx]
        m = utils.filename_pattern.match(os.path.basename(front_clips[next_segment_index]))
        if m and self.app_state.first_timestamp_of_day:
            s_dt = datetime.strptime(f"{m.group(1)} {m.group(2).replace('-', ':')}", "%Y-%m-%d %H:%M:%S")
            segment_start_ms = int((s_dt - self.app_state.first_timestamp_of_day).total_seconds() * 1000)
        else:
            segment_start_ms = 0
        
        self.app_state.playback_state = PlaybackState(
            clip_indices=[next_segment_index] * 6, 
            segment_start_ms=segment_start_ms
        )
        
        # Update UI widgets
        for i in range(6):
            self.video_player_item_widgets[i].set_video_item(active_video_items[i])
            active_players[i].setPosition(0)
        
        # Check if next segment is valid
        if active_players[front_cam_idx].mediaStatus() == QMediaPlayer.MediaStatus.InvalidMedia:
            if utils.DEBUG_UI:
                print(f"--- Segment {next_segment_index} is invalid, skipping. ---")
            return False
        
        # Preload next segment
        self._preload_next_segment()
        return True
    
    def handle_media_status_changed(self, status, player_instance, player_index):
        """Handle media status changes from players."""
        front_idx = self.camera_map["front"]
        
        if status == QMediaPlayer.MediaStatus.EndOfMedia and player_instance.source() and player_instance.source().isValid():
            if player_index == front_idx and player_instance in self.get_active_players():
                self.swap_player_sets()
        
        elif status == QMediaPlayer.MediaStatus.LoadedMedia:
            self.video_player_item_widgets[player_index].fit_video_to_view()
            
            # Handle pending seek operations
            if self.pending_seek_position != -1 and player_instance in self.players_awaiting_seek:
                player_instance.setPosition(self.pending_seek_position)
                self.players_awaiting_seek.remove(player_instance)
                
                if not self.players_awaiting_seek:
                    if utils.DEBUG_UI:
                        print(f"--- Pending seek to {self.pending_seek_position}ms completed. ---")
                    self.pending_seek_position = -1
        
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            # Remove from await set if player fails to load
            if player_instance in self.players_awaiting_seek:
                self.players_awaiting_seek.remove(player_instance)
                if not self.players_awaiting_seek and self.pending_seek_position != -1:
                    if utils.DEBUG_UI:
                        print(f"--- Pending seek to {self.pending_seek_position}ms completed (with invalid media). ---")
                    self.pending_seek_position = -1
    
    def clear_all_players(self):
        """Clear all players and reset state."""
        self.pending_seek_position = -1
        self.players_awaiting_seek.clear()
        
        for player_set in [self.players_a, self.players_b]:
            for player in player_set:
                player.stop()
                player.setSource(QUrl())
        
        # Reset playback state
        root_path = self.app_state.root_clips_path
        self.app_state = AppState()
        self.app_state.root_clips_path = root_path
    
    def cleanup(self):
        """Clean up resources before shutdown."""
        self.clear_all_players()
        for player_set in [self.players_a, self.players_b]:
            for player in player_set:
                player.deleteLater()
        
        for widget in self.video_player_item_widgets:
            widget.deleteLater() 