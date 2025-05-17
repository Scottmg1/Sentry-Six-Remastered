from PyQt6.QtWidgets import QSlider, QStyle, QStyleOptionSlider, QStyleOption
from PyQt6.QtCore import Qt, QRect, QRectF, QPoint, pyqtSignal, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QPainterPath, QPalette
import math

class EventTimeline(QSlider):
    positionChanged = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set orientation first
        self.setOrientation(Qt.Orientation.Horizontal)
        
        # Initialize QSlider properties
        self.setMinimum(0)
        self.setMaximum(60000)  # 1 minute in milliseconds
        self.setSingleStep(1000)  # 1 second steps
        self.setPageStep(10000)   # 10 second page steps
        self.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.setTickInterval(5000)  # 5 second ticks
        
        # Initialize event tracking
        self.events = []
        self.highlighted_event = -1
        self.hovered_event = -1
        self._pressed = False
        self.setMouseTracking(True)
        
        # Visual settings
        self._handle_color = QColor(100, 180, 255)
        self._event_marker_color = QColor(255, 50, 50)
        self._hover_marker_color = QColor(255, 200, 0)
        self._highlight_marker_color = QColor(255, 255, 0)
        self._event_marker_size = 4
        self._event_marker_line_height = 8
        
        # Set up the style
        self.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #444;
                height: 8px;
                background: #333;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #fff;
                border: 1px solid #888;
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #4a9cff;
                border-radius: 4px;
            }
        """)
        self.setToolTip("Click on an event marker to jump to that event")
        
        # Slider properties
        self._minimum = 0
        self._maximum = 1000
        self._value = 0
        self._pressed = False
        self._handle_radius = 6
        self._groove_height = 6
        
        # Colors
        self._groove_color = QColor(70, 70, 70)
        self._handle_color = QColor(200, 200, 200)
        self._event_color = QColor(255, 50, 50)
        self._highlight_color = QColor(255, 150, 150)
        self._hover_color = QColor(255, 100, 100)
    
    def setMinimum(self, value):
        super().setMinimum(max(1, value))  # Ensure we don't divide by zero
        self.update()
    
    def setMaximum(self, value):
        super().setMaximum(max(1, value))  # Ensure we don't divide by zero
        self.update()
    
    def setValue(self, value):
        super().setValue(max(self.minimum(), min(self.maximum(), value)))
        self.update()
    
    def value(self):
        return super().value()
    
    def minimum(self):
        return super().minimum()
    
    def maximum(self):
        return super().maximum()
    
    def set_events(self, event_times):
        """Set the list of event times to display on the timeline.
        
        Args:
            event_times: List of datetime objects or timestamps representing event times
        """
        print("\n[EventTimeline] ====== Setting Events ======")
        print(f"Received {len(event_times) if event_times else 0} events")
        
        if not event_times:
            print("No events provided, clearing timeline")
            self.events = []
            self.update()
            print("==================================\n")
            return
            
        # Convert datetime objects to timestamps if needed
        self.events = []
        for i, event_time in enumerate(event_times):
            try:
                if isinstance(event_time, (int, float)) and event_time > 0:
                    timestamp = event_time
                elif hasattr(event_time, 'timestamp'):
                    timestamp = event_time.timestamp()
                else:
                    print(f"[EventTimeline] Warning: Invalid event time at index {i}: {event_time}")
                    continue
                
                self.events.append(timestamp)
                print(f"Event {i}: {event_time} -> {timestamp}")
                
            except Exception as e:
                print(f"[EventTimeline] Error processing event {i} ({event_time}): {e}")
        
        if not self.events:
            print("No valid events to display")
            self.update()
            print("==================================\n")
            return
        
        # Sort events by time
        self.events.sort()
        print(f"Sorted {len(self.events)} events")
        
        # Update the timeline range
        try:
            # Add padding to the range
            time_range = self.events[-1] - self.events[0]
            padding = max(60, time_range * 0.1)  # At least 60 seconds padding or 10%
            min_time = max(0, self.events[0] - padding)
            max_time = self.events[-1] + padding
            
            print(f"Setting timeline range: {min_time} to {max_time} (duration: {max_time - min_time:.2f}s)")
            print(f"First event at: {self.events[0]} ({self._format_timestamp(self.events[0])})")
            print(f"Last event at: {self.events[-1]} ({self._format_timestamp(self.events[-1])})")
            
            # Update the slider range
            self.setRange(int(min_time), int(max_time))
            
            # Set initial position to first event
            self.setValue(int(self.events[0]))
            
        except Exception as e:
            print(f"[EventTimeline] Error updating timeline range: {e}")
            import traceback
            traceback.print_exc()
        
        # Force an update
        self.update()
        print("==================================\n")
    
    def _format_timestamp(self, timestamp):
        """Format a timestamp for display."""
        from datetime import datetime
        try:
            return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        except:
            return str(timestamp)
        print("======================================\n")
    
    def set_event_positions(self, positions):
        """Alias for set_events for backward compatibility."""
        print("[EventTimeline] Using deprecated set_event_positions, use set_events instead")
        self.set_events(positions)
    
    def set_highlighted_event(self, index):
        """Highlight a specific event by its index"""
        self.highlighted_event = index
        self.update()
    
    def _get_handle_rect(self):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        handle = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider,
            opt,
            QStyle.SubControl.SC_SliderHandle,
            self
        )
        # Make handle taller to match the groove
        groove = self._get_groove_rect()
        if handle.isValid() and groove.isValid():
            handle.setTop(groove.top() - 6)
            handle.setBottom(groove.bottom() + 6)
        return handle
    
    def _get_groove_rect(self):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        groove = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider,
            opt,
            QStyle.SubControl.SC_SliderGroove,
            self
        )
        # Make the groove taller and center it vertically
        if groove.isValid():
            groove.setHeight(8)
            center_y = self.rect().center().y()
            groove.moveTop(center_y - groove.height() // 2)
        return groove
        
    def _value_to_position(self, value):
        """Convert a value to a position on the timeline."""
        min_val = self.minimum()
        max_val = self.maximum()
        if max_val <= min_val:
            return 0
        return (value - min_val) / (max_val - min_val) * self.width()
    
    def paintEvent(self, event):
        """Handle paint events for the timeline."""
        # Let the base class handle the basic slider painting
        super().paintEvent(event)
        
        # Set up the painter
        painter = QPainter()
        if not painter.begin(self):
            print("[EventTimeline] Failed to initialize painter")
            return
            
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
            # Debug: Track if we're drawing any events
            debug_info = {
                'groove_valid': False,
                'visible_range': 0,
                'events_processed': 0,
                'events_drawn': 0,
                'errors': []
            }
            # Get the style options for the slider
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            
            # Get the groove and handle rectangles
            groove = self._get_groove_rect()
            debug_info['groove_rect'] = (groove.x(), groove.y(), groove.width(), groove.height())
            
            # Skip painting if we don't have valid dimensions or no events
            if not groove.isValid():
                debug_info['errors'].append("Groove rectangle is invalid")
                return
                
            if self.maximum() <= self.minimum():
                debug_info['errors'].append(f"Invalid timeline range: min={self.minimum()}, max={self.maximum()}")
                return
                
            if not self.events:
                debug_info['errors'].append("No events to display")
                return
                
            debug_info['groove_valid'] = True
            debug_info['visible_range'] = self.maximum() - self.minimum()
            debug_info['event_count'] = len(self.events)
            
            # Calculate the visible range
            visible_min = self.minimum()
            visible_max = self.maximum()
            visible_range = visible_max - visible_min
            debug_info['visible_range'] = visible_range
            
            if visible_range <= 0:
                debug_info['errors'].append(f"Visible range is not positive: {visible_range}")
                return
                
            # Set up marker appearance
            marker_radius = 4
            marker_line_height = 10
            marker_color = QColor(255, 0, 0)  # Red color for markers
            
            # Get the groove rectangle
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            groove = self.style().subControlRect(
                QStyle.ComplexControl.CC_Slider, 
                opt, 
                QStyle.SubControl.SC_SliderGroove, 
                self
            )
            
            if not groove.isValid():
                debug_info['errors'].append("Could not get valid groove rectangle")
                return
                
            debug_info['groove_rect'] = (groove.x(), groove.y(), groove.width(), groove.height())
            
            # Draw event markers
            debug_info['event_count'] = len(self.events)
            
            for i, event_time in enumerate(self.events):
                try:
                    debug_info['events_processed'] += 1
                    
                    # Calculate position
                    if visible_range > 0:
                        pos_ratio = (event_time - visible_min) / visible_range
                        pos = groove.left() + pos_ratio * groove.width()
                    else:
                        pos = groove.left()
                    
                    # Ensure position is within groove bounds
                    pos = max(groove.left() + 2, min(groove.right() - 2, pos))
                    
                    # Set color based on state
                    if i == self.highlighted_event:
                        color = QColor(255, 165, 0)  # Orange for highlighted
                    elif i == self.hovered_event:
                        color = QColor(255, 100, 100)  # Light red for hovered
                    else:
                        color = QColor(255, 0, 0)  # Red for normal
                    
                    # Draw line to timeline
                    line_top = groove.top() - marker_line_height
                    line_bottom = groove.top()
                    
                    line_path = QPainterPath()
                    line_path.moveTo(pos, line_top)
                    line_path.lineTo(pos, line_bottom)
                    
                    painter.setPen(QPen(color, 2))
                    painter.drawPath(line_path)
                    
                    # Draw event marker (triangle pointing down)
                    marker_path = QPainterPath()
                    marker_top = line_top - marker_radius * 1.5
                    marker_path.moveTo(pos - marker_radius, marker_top + marker_radius)
                    marker_path.lineTo(pos + marker_radius, marker_top + marker_radius)
                    marker_path.lineTo(pos, marker_top)
                    marker_path.closeSubpath()
                    
                    painter.fillPath(marker_path, color)
                    
                    debug_info['events_drawn'] += 1
                    
                except Exception as e:
                    error_msg = f"Error drawing event {i}: {str(e)}"
                    debug_info['errors'].append(error_msg)
                    print(f"[EventTimeline] {error_msg}")
                    import traceback
                    traceback.print_exc()
            
            # Draw the handle on top of everything
            handle = self._get_handle_rect()
            if handle.isValid():
                # Draw the handle with a nice style
                handle_color = QColor(0, 120, 215)  # Blue handle
                painter.setPen(QPen(handle_color.darker(130), 1))
                painter.setBrush(handle_color)
                painter.drawRoundedRect(handle, 4, 4)
                
                # Add a subtle highlight
                highlight = handle.adjusted(1, 1, -1, -1)
                painter.setPen(QPen(handle_color.lighter(150), 1))
                painter.drawLine(highlight.topLeft(), highlight.topRight())
            
            debug_info['success'] = True
            
        except Exception as e:
            error_msg = f"Paint error: {str(e)}"
            debug_info['errors'].append(error_msg)
            print(f"[EventTimeline] {error_msg}")
            import traceback
            traceback.print_exc()
            
        finally:
            painter.end()
            
        # Log debug info if we're in debug mode or there are errors
        if debug_info.get('errors') or not debug_info.get('success', False):
            print("\n[EventTimeline] ====== Paint Debug Info ======")
            print(f"Widget size: {self.width()}x{self.height()}")
            print(f"Groove valid: {debug_info.get('groove_valid')}")
            print(f"Groove rect: {debug_info.get('groove_rect', 'N/A')}")
            print(f"Visible range: {debug_info.get('visible_range')}ms ({(debug_info.get('visible_range', 0)/1000):.2f}s)")
            print(f"Events: {debug_info.get('events_processed', 0)} processed, {debug_info.get('events_drawn', 0)} drawn")
            if debug_info.get('errors'):
                print("Errors:")
                for error in debug_info['errors']:
                    print(f"  - {error}")
            print("=================================\n")
        
        # Draw event highlights and markers
        if hasattr(self, 'events') and self.events and visible_range > 0:
            thirty_seconds = 30000  # 30 seconds in milliseconds
            
            # Sort events to ensure they're in order
            sorted_events = sorted(self.events)
            
            for i, event_time in enumerate(sorted_events):
                try:
                    # Skip events outside the visible range
                    if event_time < visible_min or event_time > visible_max:
                        continue
                    
                    # Calculate the X position of the event
                    event_pos = ((event_time - visible_min) / visible_range) * groove.width() + groove.left()
                    
                    # Draw highlight area (30 seconds before the event)
                    highlight_start = max(visible_min, event_time - thirty_seconds)
                    highlight_start_pos = ((highlight_start - visible_min) / visible_range) * groove.width() + groove.left()
                    highlight_rect = QRectF(
                        highlight_start_pos,
                        groove.top() - 5,
                        max(1, event_pos - highlight_start_pos),
                        groove.height() + 10
                    )
                    
                    # Draw highlight area with semi-transparent red
                    painter.setBrush(QColor(255, 0, 0, 40))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRoundedRect(highlight_rect, 3, 3)
                    
                    # Set color based on highlight/hover state
                    if hasattr(self, 'highlighted_event') and i == self.highlighted_event:
                        color = QColor(255, 255, 0)  # Yellow for highlighted
                        marker_width = 2
                    elif hasattr(self, 'hovered_event') and i == self.hovered_event:
                        color = QColor(255, 200, 0)  # Orange for hovered
                        marker_width = 2
                    else:
                        color = QColor(255, 50, 50)  # Red for normal
                        marker_width = 1
                    
                    # Draw event marker (a small vertical line)
                    marker_height = 12
                    painter.setPen(QPen(color, marker_width))
                    painter.drawLine(
                        QPointF(event_pos, groove.center().y() - marker_height//2),
                        QPointF(event_pos, groove.center().y() + marker_height//2)
                    )
                    
                    # Draw a small circle at the top of the marker
                    marker_radius = 3
                    painter.setBrush(color)
                    painter.drawEllipse(
                        QPointF(event_pos, groove.center().y() - marker_height//2 - marker_radius//2),
                        marker_radius, marker_radius
                    )
                    
                    # Draw time label for the current event if it's highlighted or hovered
                    is_highlighted = hasattr(self, 'highlighted_event') and i == self.highlighted_event
                    is_hovered = hasattr(self, 'hovered_event') and i == self.hovered_event
                    
                    if is_highlighted or is_hovered:
                        # Format the time (convert from ms to seconds)
                        seconds = event_time / 1000
                        minutes = int(seconds // 60)
                        seconds = int(seconds % 60)
                        time_str = f"{minutes:02d}:{seconds:02d}"
                        
                        # Calculate text position (ensure it stays within the widget)
                        text_width = 50
                        text_x = max(groove.left() + 5, min(event_pos - text_width//2, groove.right() - text_width - 5))
                        text_rect = QRectF(text_x, groove.top() - 25, text_width, 20)
                        
                        # Draw text background for better readability
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(QColor(0, 0, 0, 180))  # Semi-transparent black
                        painter.drawRoundedRect(text_rect, 3, 3)
                        
                        # Draw the time text
                        painter.setPen(Qt.GlobalColor.white)
                        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, time_str)
                        
                except Exception as e:
                    # Silently skip any errors when drawing events
                    continue
        
        # Draw the handle last (on top of everything)
        if handle.isValid():
            self.style().drawComplexControl(
                QStyle.ComplexControl.CC_Slider,
                opt,
                painter,
                self
            )
        
        # Draw the groove border on top
        painter.setPen(QColor(120, 120, 120))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(groove, 3, 3)
        
        # Draw the handle
        handle = self._get_handle_rect()
        painter.setPen(QPen(self._handle_color.lighter(120), 1))
        painter.setBrush(self._handle_color)
        painter.drawEllipse(handle)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self._update_value_from_pos(event.pos())
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if self._pressed:
            self._update_value_from_pos(event.pos())
            event.accept()
        else:
            # Check for hover over events
            self._update_hovered_event(event.pos())
            event.accept()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def leaveEvent(self, event):
        if self.hovered_event != -1:
            self.hovered_event = -1
            self.update()
        super().leaveEvent(event)
    
    def _update_value_from_pos(self, pos):
        groove = self._get_groove_rect()
        if not groove.isValid() or groove.width() <= 0:
            return
            
        x = max(groove.left(), min(groove.right(), pos.x()))
        min_val = self.minimum()
        max_val = self.maximum()
        value = min_val + (x - groove.left()) / groove.width() * (max_val - min_val)
        value = max(min_val, min(max_val, value))
        
        current_value = self.value()
        if abs(value - current_value) > 1:  # Only update if the value has changed significantly
            self.setValue(int(value))
            self.positionChanged.emit(int(value))
            self.update()
            
            # Update highlighted event
            self._update_highlighted_event(int(value))
    
    def _update_hovered_event(self, pos):
        if not self.events or not self.rect().contains(pos):
            if self.hovered_event != -1:
                self.hovered_event = -1
                self.update()
            return
        
        groove = self._get_groove_rect()
        if not groove.isValid():
            return
            
        x = pos.x()
        
        # Find the closest event
        closest_idx = -1
        min_dist = float('inf')
        
        for i, event_pos in enumerate(self.events):
            event_x = groove.left() + ((event_pos - self.minimum()) / max(1, (self.maximum() - self.minimum()))) * groove.width()
            dist = abs(event_x - x)
            
            # Only consider events within a certain distance
            if dist < 20 and dist < min_dist:
                min_dist = dist
                closest_idx = i
        
        if closest_idx != self.hovered_event:
            self.hovered_event = closest_idx
            self.update()
    
    def _update_highlighted_event(self, current_time):
        """Update which event is currently highlighted based on the current time."""
        if not self.events:
            self.highlighted_event = -1
            return
            
        # Find the closest event to the current time
        closest_idx = -1
        min_diff = float('inf')
        
        for i, event_time in enumerate(self.events):
            diff = abs(event_time - current_time)
            if diff < min_diff and diff < 2000:  # Within 2 seconds
                min_diff = diff
                closest_idx = i
        
        if closest_idx != self.highlighted_event:
            self.highlighted_event = closest_idx
            self.update()
    
    def sizeHint(self):
        return QSize(100, 60)  # Taller to accommodate event markers
    
    def minimumSizeHint(self):
        return self.size() if not self.size().isNull() else super().minimumSizeHint()
    
    def initStyleOption(self, option):
        """Initialize the style option with the current state of the slider."""
        super().initStyleOption(option)
        
        # Set up the style options for our custom slider
        option.minimum = self.minimum()
        option.maximum = self.maximum()
        option.orientation = self.orientation()
        option.upsideDown = self.invertedAppearance()
        option.tickPosition = self.tickPosition()
        option.tickInterval = self.tickInterval()
        option.singleStep = self.singleStep()
        option.pageStep = self.pageStep()
        option.sliderPosition = self.sliderPosition()
        option.sliderValue = self.value()
