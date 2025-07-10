"""
Layout Manager for Sentry-Six.

Handles UI layout management including camera visibility, widget positioning,
and layout state persistence.
"""

from typing import List, Optional, Callable
from PyQt6.QtWidgets import QWidget, QGridLayout, QCheckBox
from PyQt6.QtCore import QObject, pyqtSignal

from ..state import AppState
from .. import widgets


class LayoutManager(QObject):
    """Manages UI layout and camera visibility."""
    
    # Signals
    layout_changed = pyqtSignal()
    visibility_changed = pyqtSignal()
    
    def __init__(self, parent: QWidget, app_state: AppState, camera_map: dict):
        super().__init__(parent)
        self._parent = parent
        self.app_state = app_state
        self.camera_map = camera_map
        
        # Layout components
        self.video_grid_widget: Optional[QWidget] = None
        self.video_grid: Optional[QGridLayout] = None
        self.video_player_item_widgets: List[widgets.VideoPlayerItemWidget] = []
        
        # Camera visibility
        self.camera_visibility_checkboxes: List[QCheckBox] = []
        self.checkbox_info: List[tuple] = []
        self.ordered_visible_player_indices: List[int] = []
        
        # Callbacks
        self.on_layout_update: Optional[Callable] = None
        self.on_settings_save: Optional[Callable] = None
    
    def set_callbacks(self, on_layout_update: Callable, on_settings_save: Callable):
        """Set callback functions for layout events."""
        self.on_layout_update = on_layout_update
        self.on_settings_save = on_settings_save
    
    def create_video_grid(self, parent_widget: QWidget) -> QWidget:
        """Create the video grid layout."""
        self.video_grid_widget = QWidget(parent_widget)
        self.video_grid = QGridLayout(self.video_grid_widget)
        self.video_grid.setSpacing(3)
        return self.video_grid_widget
    
    def set_player_widgets(self, widgets: List[widgets.VideoPlayerItemWidget]):
        """Set the video player widgets for layout management."""
        self.video_player_item_widgets = widgets
    
    def set_visibility_checkboxes(self, checkboxes: List[QCheckBox], checkbox_info: List[tuple]):
        """Set the camera visibility checkboxes."""
        self.camera_visibility_checkboxes = checkboxes
        self.checkbox_info = checkbox_info
        
        # Connect checkbox signals
        for checkbox in checkboxes:
            checkbox.toggled.connect(self._on_visibility_changed)
    
    def _on_visibility_changed(self):
        """Handle camera visibility checkbox changes."""
        self.ordered_visible_player_indices = [
            self.checkbox_info[i][2] 
            for i, cb in enumerate(self.camera_visibility_checkboxes) 
            if cb.isChecked()
        ]
        
        self.update_layout()
        self.visibility_changed.emit()
        
        # Save settings
        if self.on_settings_save:
            self.on_settings_save()
    
    def update_layout(self):
        """Update the video grid layout based on current visibility settings."""
        if not self.video_grid or not self.video_player_item_widgets:
            return
        
        # Clear existing layout
        while self.video_grid.count():
            item = self.video_grid.takeAt(0)
            widget = item.widget() if item else None
            if widget:
                widget.setParent(None)
                widget.hide()
        
        num_visible = len(self.ordered_visible_player_indices)
        if num_visible == 0:
            if self.video_grid_widget:
                self.video_grid_widget.update()
            return
        
        # Calculate grid dimensions
        cols = 1 if num_visible == 1 else 2 if num_visible in [2, 4] else 3
        
        # Position widgets
        current_col, current_row = 0, 0
        for p_idx in self.ordered_visible_player_indices:
            widget = self.video_player_item_widgets[p_idx]
            widget.setVisible(True)
            widget.reset_view()
            self.video_grid.addWidget(widget, current_row, current_col)
            
            current_col += 1
            if current_col >= cols:
                current_col = 0
                current_row += 1
        
        # Hide unused widgets
        for hidden_idx in (set(range(6)) - set(self.ordered_visible_player_indices)):
            self.video_player_item_widgets[hidden_idx].setVisible(False)
        
        if self.video_grid_widget:
            self.video_grid_widget.update()
        
        self.layout_changed.emit()
        
        # Call callback if set
        if self.on_layout_update:
            self.on_layout_update()
    
    def reset_to_default_layout(self):
        """Reset layout to default state."""
        # Reset visibility checkboxes
        for checkbox in self.camera_visibility_checkboxes:
            checkbox.blockSignals(True)
            checkbox.setChecked(True)
            checkbox.blockSignals(False)
        
        # Update layout
        self._on_visibility_changed()
    
    def handle_widget_swap(self, dragged_index: int, dropped_on_index: int):
        """Handle widget swap requests."""
        try:
            drag_pos = self.ordered_visible_player_indices.index(dragged_index)
            drop_pos = self.ordered_visible_player_indices.index(dropped_on_index)
            
            # Swap the items in the list
            self.ordered_visible_player_indices[drag_pos], self.ordered_visible_player_indices[drop_pos] = \
                self.ordered_visible_player_indices[drop_pos], self.ordered_visible_player_indices[drag_pos]
            
            self.update_layout()
            
            # Save settings
            if self.on_settings_save:
                self.on_settings_save()
                
        except ValueError:
            # Tried to swap indices that are not in the visible list
            pass
    
    def get_visible_indices(self) -> List[int]:
        """Get the currently visible camera indices in order."""
        return self.ordered_visible_player_indices.copy()
    
    def set_visible_indices(self, indices: List[int]):
        """Set the visible camera indices and update layout."""
        self.ordered_visible_player_indices = indices.copy()
        self.update_layout()
    
    def get_visibility_states(self) -> List[bool]:
        """Get the current visibility states of all cameras."""
        return [cb.isChecked() for cb in self.camera_visibility_checkboxes]
    
    def set_visibility_states(self, states: List[bool]):
        """Set the visibility states of all cameras."""
        if len(states) != len(self.camera_visibility_checkboxes):
            return
        
        for checkbox, state in zip(self.camera_visibility_checkboxes, states):
            checkbox.blockSignals(True)
            checkbox.setChecked(state)
            checkbox.blockSignals(False)
        
        self._on_visibility_changed()
    
    def get_grid_dimensions(self) -> tuple[int, int]:
        """Get the current grid dimensions (rows, cols)."""
        num_visible = len(self.ordered_visible_player_indices)
        if num_visible == 0:
            return 0, 0
        
        cols = 1 if num_visible == 1 else 2 if num_visible in [2, 4] else 3
        rows = (num_visible + cols - 1) // cols  # Ceiling division
        
        return rows, cols
    
    def is_camera_visible(self, camera_index: int) -> bool:
        """Check if a specific camera is currently visible."""
        return camera_index in self.ordered_visible_player_indices
    
    def get_camera_position(self, camera_index: int) -> Optional[tuple[int, int]]:
        """Get the grid position of a specific camera (row, col)."""
        if camera_index not in self.ordered_visible_player_indices:
            return None
        
        position = self.ordered_visible_player_indices.index(camera_index)
        rows, cols = self.get_grid_dimensions()
        
        row = position // cols
        col = position % cols
        
        return row, col
    
    def cleanup(self):
        """Clean up resources before shutdown."""
        # Disconnect signals
        for checkbox in self.camera_visibility_checkboxes:
            try:
                checkbox.toggled.disconnect()
            except:
                pass 