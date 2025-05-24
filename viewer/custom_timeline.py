from PyQt6.QtWidgets import QWidget, QToolTip
from PyQt6.QtCore import Qt, QRect, QSize, pyqtSignal, pyqtSlot, QPoint
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QLinearGradient
import datetime

class CustomTimeline(QWidget):
    """A custom timeline widget that displays event markers and allows seeking through video."""
    
    # Signal emitted when the user changes the position
    positionChanged = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set a fixed height for the timeline
        self.setFixedHeight(50)
        
        # Initialize timeline properties
        self._minimum = 0
        self._maximum = 60000  # 1 minute in milliseconds
        self._value = 0
        self._pressed = False
        
        # Initialize event data
        self._events = []  # List of event timestamps in milliseconds
        self._event_data = []  # List of event data objects
        self._hovered_event_index = -1  # Index of event currently being hovered over
        self._highlighted_event_index = -1  # Index of event currently highlighted
        
        # Event marker colors
        self._event_colors = {
            "user_interaction": QColor(255, 165, 0),  # Orange
            "sentry": QColor(255, 0, 0),  # Red
            "autopilot": QColor(0, 255, 0),  # Green
            "default": QColor(255, 255, 0)  # Yellow
        }
        
        # Set cursor to pointing hand to indicate it's interactive
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click or drag to seek through the video")
        
        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
    
    def setMinimum(self, value):
        """Set the minimum value of the timeline."""
        self._minimum = max(0, value)
        self.update()
    
    def minimum(self):
        """Get the minimum value of the timeline."""
        return self._minimum
    
    def setMaximum(self, value):
        """Set the maximum value of the timeline."""
        self._maximum = max(self._minimum + 1, value)
        self.update()
    
    def maximum(self):
        """Get the maximum value of the timeline."""
        return self._maximum
    
    def setValue(self, value):
        """Set the current position of the timeline."""
        # Clamp value to valid range
        value = max(self._minimum, min(self._maximum, value))
        
        if value != self._value:
            self._value = value
            self.update()
    
    def value(self):
        """Get the current position of the timeline."""
        return self._value
    
    def set_events(self, event_times, event_data=None):
        """Set the event timestamps to display on the timeline.
        
        Args:
            event_times (list): List of event timestamps in milliseconds
            event_data (list, optional): List of event data objects corresponding to each timestamp
        """
        self._events = event_times if event_times else []
        # If event_data is provided, use it; otherwise, create empty data objects
        if event_data and len(event_data) == len(event_times):
            self._event_data = event_data
        else:
            self._event_data = [{'reason': 'unknown'} for _ in range(len(self._events))]
        
        # Only update if events have actually changed
        if hasattr(self, '_last_events') and self._last_events == event_times:
            return
            
        self._last_events = event_times.copy() if event_times else []
        self._hovered_event_index = -1
        self.update()
        
    def set_event_positions(self, positions):
        """Set the positions of event markers as a list of values from minimum() to maximum()
        
        This is a compatibility method to match the old TimelineSlider API.
        """
        if not positions:
            self._events = []
            self._event_data = []
            self.update()
            return
            
        # Convert the positions to the internal format (milliseconds)
        min_val = self.minimum()
        max_val = self.maximum()
        range_val = max(1, max_val - min_val)
        
        # Convert positions to milliseconds based on the current range
        self._events = [int(min_val + pos * range_val) for pos in positions]
        self._event_data = [{'reason': 'event'} for _ in self._events]
        self.update()
    
    def paintEvent(self, event):
        """Paint the timeline and event markers."""
        # Use direct initialization with the widget as parameter
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get widget dimensions
        rect = self.rect()
        width = rect.width()
        height = rect.height()
        
        # Draw timeline background
        background_rect = QRect(0, height // 2 - 3, width, 6)
        
        # Create gradient for timeline background
        gradient = QLinearGradient(0, 0, width, 0)
        gradient.setColorAt(0, QColor(40, 40, 40))
        gradient.setColorAt(1, QColor(60, 60, 60))
        
        painter.setBrush(gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(background_rect, 3, 3)
        
        # Draw elapsed portion of timeline
        if self._maximum > self._minimum:
            progress_ratio = (self._value - self._minimum) / (self._maximum - self._minimum)
            progress_width = int(progress_ratio * width)
            
            progress_rect = QRect(0, height // 2 - 3, progress_width, 6)
            progress_gradient = QLinearGradient(0, 0, width, 0)
            progress_gradient.setColorAt(0, QColor(74, 156, 255))
            progress_gradient.setColorAt(1, QColor(100, 180, 255))
            
            painter.setBrush(progress_gradient)
            painter.drawRoundedRect(progress_rect, 3, 3)
        
        # Draw handle at current position
        if self._maximum > self._minimum:
            handle_pos = int((self._value - self._minimum) / (self._maximum - self._minimum) * width)
            handle_rect = QRect(handle_pos - 6, height // 2 - 8, 12, 16)
            
            # Draw handle shadow
            shadow_rect = handle_rect.adjusted(1, 1, 1, 1)
            painter.setBrush(QColor(0, 0, 0, 80))
            painter.drawRoundedRect(shadow_rect, 6, 6)
            
            # Draw handle
            painter.setBrush(QColor(240, 240, 240))
            painter.setPen(QPen(QColor(120, 120, 120), 1))
            painter.drawRoundedRect(handle_rect, 6, 6)
        
        # Draw event markers
        if self._events:
            marker_width = 12
            marker_height = 16
            
            for i, event_time in enumerate(self._events):
                # For events outside the timeline range, we'll still show them at the edges
                clamped_event_time = max(self._minimum, min(self._maximum, event_time))
                is_outside_range = event_time < self._minimum or event_time > self._maximum
                
                # Get event type and color
                event_data = self._event_data[i] if i < len(self._event_data) else {'reason': 'unknown'}
                
                # Check if this is an adjusted event (event that was after timeline end)
                is_adjusted = event_data.get('adjusted', False)
                
                # Calculate position using the clamped time
                # For adjusted events, ensure they're displayed at the intended position
                if is_adjusted:
                    # For adjusted events, place them 15 seconds before the end of the timeline
                    # This matches our calculation in ui.py
                    if self._maximum > self._minimum:
                        # Calculate position for 15 seconds before the end
                        fifteen_sec_ms = 15000  # 15 seconds in milliseconds
                        if self._maximum > fifteen_sec_ms:
                            adjusted_pos = self._maximum - fifteen_sec_ms
                            pos_ratio = (adjusted_pos - self._minimum) / (self._maximum - self._minimum)
                        else:
                            # If timeline is shorter than 15 seconds, use 85% position
                            pos_ratio = 0.85
                    else:
                        pos_ratio = 0.85
                    # Debug print removed for performance
                else:
                    pos_ratio = (clamped_event_time - self._minimum) / (self._maximum - self._minimum)
                
                pos_x = int(pos_ratio * width)
                
                # Use a different appearance for events outside the range
                edge_marker = False
                if is_outside_range:
                    edge_marker = True
                
                # Get event type and color
                event_data = self._event_data[i] if i < len(self._event_data) else {'reason': 'unknown'}
                event_type = event_data.get('reason', 'default').lower()
                
                # Check if this is an adjusted event (event that was after timeline end)
                is_adjusted = event_data.get('adjusted', False)
                
                # Determine color based on event type
                if 'user' in event_type:
                    color = self._event_colors['user_interaction']
                elif 'sentry' in event_type:
                    # Make sentry events more distinct
                    if is_adjusted:
                        color = QColor(255, 100, 100)  # Brighter red for adjusted sentry events
                    else:
                        color = QColor(255, 0, 0)  # Regular red for normal sentry events
                elif 'autopilot' in event_type:
                    color = self._event_colors['autopilot']
                else:
                    color = self._event_colors['default']
                    
                # Debug info for adjusted events has been removed
                
                # Highlight the hovered or selected event
                marker_w = marker_width
                marker_h = marker_height
                if i == self._hovered_event_index or i == self._highlighted_event_index:
                    color = color.lighter(130)  # Make color lighter
                    marker_w += 4
                    marker_h += 4
                
                # Draw marker triangle pointing down to the timeline
                marker_rect = QRect(
                    int(pos_x - marker_w/2),
                    5,  # Position at top with padding
                    marker_w,
                    marker_h
                )
                
                # Make sure marker is within widget bounds with some padding
                padding = 20  # Add padding to ensure marker is fully visible
                if marker_rect.left() < padding:
                    marker_rect.moveLeft(padding)
                if marker_rect.right() > (width - padding):
                    marker_rect.moveRight(width - padding)
                
                # Update the position for drawing
                pos_x = marker_rect.center().x()
                
                # Always use diamond shape for all markers for consistency
                painter.setPen(QPen(Qt.GlobalColor.black, 1))
                
                # Create a complete diamond shape with consistent size
                marker_top = marker_rect.top()
                marker_middle = marker_rect.top() + marker_rect.height() // 2
                marker_bottom = marker_rect.bottom()
                
                # Create diamond points explicitly - always use full diamond shape
                points = [
                    QPoint(pos_x, marker_top),                  # Top point
                    QPoint(pos_x + 7, marker_middle),          # Right point
                    QPoint(pos_x, marker_bottom),              # Bottom point
                    QPoint(pos_x - 7, marker_middle)           # Left point
                ]
                
                # For adjusted events, add a tooltip and use a distinct color
                if is_adjusted:
                    if 'original_time' in event_data:
                        original_time = event_data['original_time']
                        original_time_str = self._format_timestamp(original_time)
                        self.setToolTip(f"Event occurs after timeline end (actual time: {original_time_str})")
                    # Make adjusted events more distinct
                    color = color.lighter(130)  # Make it brighter
                    if 'sentry' in event_type:
                        color = QColor(255, 80, 80)  # Brighter red for sentry events
                
                # For edge markers, use a dashed border
                if edge_marker:
                    dash_pen = QPen(Qt.GlobalColor.black, 1)
                    dash_pen.setStyle(Qt.PenStyle.DashLine)
                    painter.setPen(dash_pen)
                    color = color.lighter(130)  # Make edge markers brighter
                else:
                    painter.setPen(QPen(Qt.GlobalColor.black, 1))
                
                # Drawing marker at position
                painter.setBrush(color)
                
                # Draw the polygon for all marker types
                painter.drawPolygon(points)
        else:
            # If no events, draw a fixed marker at the center for visual confirmation
            marker_width = 14
            marker_height = 18
            pos_x = int(width // 2)
            
            # Make sure marker is within widget bounds with some padding
            padding = 20  # Add padding to ensure marker is fully visible
            if pos_x < padding:
                pos_x = padding
            if pos_x > (width - padding):
                pos_x = width - padding
                
            # Use the same approach as adjusted events for the fallback marker
            # Create a diamond shape
            marker_top = 5
            marker_middle = 13
            marker_bottom = 20
            
            # Create diamond points explicitly
            points = [
                QPoint(pos_x, marker_top),          # Top point
                QPoint(pos_x + 7, marker_middle),   # Right point
                QPoint(pos_x, marker_bottom),       # Bottom point
                QPoint(pos_x - 7, marker_middle)    # Left point
            ]
            
            painter.setPen(QPen(Qt.GlobalColor.red, 1))
            painter.setBrush(QColor(255, 0, 0, 180))
            # Drawing fallback marker at center
            
            # Draw the polygon directly
            painter.drawPolygon(points)
        
        # Draw time labels
        painter.setPen(QColor(200, 200, 200))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        # Current position time
        current_time = self._format_timestamp(self._value)
        total_time = self._format_timestamp(self._maximum)
        # Draw time text in format "00:00/10:00"
        time_text = f"{current_time}/{total_time}"
        painter.drawText(rect.adjusted(5, 0, -5, -5), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, time_text)
    
    def _format_timestamp(self, ms):
        """Format milliseconds as MM:SS."""
        total_seconds = ms // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def mousePressEvent(self, event):
        """Handle mouse press events for seeking."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self._update_position_from_mouse(event.pos())
            self.update()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events for seeking and hovering."""
        if self._pressed:
            self._update_position_from_mouse(event.pos())
        else:
            # Check for hovering over event markers
            self._update_hovered_event(event.pos())
        
        self.update()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events."""
        if event.button() == Qt.MouseButton.LeftButton and self._pressed:
            self._pressed = False
            self._update_position_from_mouse(event.pos())
            self.update()
    
    def mouseDoubleClickEvent(self, event):
        """Handle mouse double click events to jump to events."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if we're clicking on an event
            if 0 <= self._hovered_event_index < len(self._events):
                # Emit the position of the clicked event
                event_time = self._events[self._hovered_event_index]
                self.positionChanged.emit(event_time)
                self.update()
    
    def _update_position_from_mouse(self, pos):
        """Update the timeline position based on mouse position."""
        if self._maximum <= self._minimum:
            return
        
        width = self.width()
        if width <= 0:
            return
        
        # Calculate new position
        pos_ratio = max(0, min(1, pos.x() / width))
        new_value = int(self._minimum + pos_ratio * (self._maximum - self._minimum))
        
        # Update value and emit signal
        if new_value != self._value:
            self._value = new_value
            self.positionChanged.emit(new_value)
    
    def _update_hovered_event(self, pos):
        """Check if mouse is hovering over an event marker."""
        if not self._events or self._maximum <= self._minimum:
            return
        
        width = self.width()
        if width <= 0:
            return
        
        # Find the closest event to the mouse position
        mouse_x = pos.x()
        closest_event_index = -1
        closest_distance = float('inf')
        
        for i, event_time in enumerate(self._events):
            # Skip if event is outside the timeline range
            if event_time < self._minimum or event_time > self._maximum:
                continue
                
            # Calculate event position
            pos_ratio = (event_time - self._minimum) / (self._maximum - self._minimum)
            event_x = int(pos_ratio * width)
            
            # Check if mouse is close to this event
            distance = abs(mouse_x - event_x)
            if distance < 15 and distance < closest_distance:  # 15 pixels threshold
                closest_distance = distance
                closest_event_index = i
        
        # Update hovered event index if changed
        if closest_event_index != self._hovered_event_index:
            self._hovered_event_index = closest_event_index
            
            # Show tooltip if hovering over an event
            if self._hovered_event_index >= 0:
                event_data = self._event_data[self._hovered_event_index]
                event_time = self._events[self._hovered_event_index]
                event_time_str = self._format_timestamp(event_time)
                
                # Format tooltip with event information
                reason = event_data.get('reason', 'Unknown').replace('_', ' ').title()
                city = event_data.get('city', '')
                
                tooltip = f"Event: {reason}\n"
                if city:
                    tooltip += f"Location: {city}\n"
                tooltip += f"Time: {event_time_str}"
                
                # Show tooltip at the event marker position
                pos_ratio = (event_time - self._minimum) / (self._maximum - self._minimum)
                marker_pos = int(pos_ratio * width)
                QToolTip.showText(self.mapToGlobal(QPoint(marker_pos, 0)), tooltip, self)
            else:
                QToolTip.hideText()
    
    def _update_highlighted_event(self, current_time):
        """Highlight the event closest to the current time."""
        if not self._events:
            return
            
        # Find the closest event to the current time
        closest_event_index = -1
        closest_distance = float('inf')
        
        for i, event_time in enumerate(self._events):
            distance = abs(event_time - current_time)
            if distance < closest_distance:
                closest_distance = distance
                closest_event_index = i
        
        # Only highlight if within 2 seconds (2000ms)
        if closest_distance <= 2000:
            self.set_highlighted_event(closest_event_index)
        else:
            self.set_highlighted_event(-1)
    
    def set_highlighted_event(self, index):
        """Highlight a specific event by its index.
        
        Args:
            index (int): Index of the event to highlight, or -1 to clear highlight
        """
        if self._highlighted_event_index != index:
            self._highlighted_event_index = index
            self.update()
    
    def sizeHint(self):
        """Suggested size for the widget."""
        return QSize(400, 50)
