from PyQt6.QtWidgets import QSlider, QStyle, QStyleOptionSlider
from PyQt6.QtCore import Qt, QRect, QSize, pyqtSignal, QPoint
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush

class EventTimeline(QSlider):
    positionChanged = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set orientation first
        self.setOrientation(Qt.Orientation.Horizontal)
        
        # Set a fixed height for the slider
        self.setFixedHeight(30)
        
        # Initialize QSlider properties
        self.setMinimum(0)
        self.setMaximum(60000)  # 1 minute in milliseconds
        self.setSingleStep(1000)  # 1 second steps
        self.setPageStep(10000)   # 10 second page steps
        
        # Track mouse press state
        self._pressed = False
        
        # Set up the style
        self.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #444;
                height: 3px;
                background: #333;
                margin: 0px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #f0f0f0;
                border: 1px solid #888;
                width: 12px;
                height: 12px;
                margin: -5px 0;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                background: #ffffff;
            }
            QSlider::sub-page:horizontal {
                background: #4a9cff;
                border-radius: 2px;
                margin: 0;
            }
        """)
        self.setToolTip("Click or drag to seek through the video")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
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
        """This method is kept for backward compatibility but no longer has any effect."""
        pass
    
    def paintEvent(self, event):
        """Let the base class handle painting."""
        super().paintEvent(event)
    
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
    def mousePressEvent(self, event):
        # Handle clicking on the slider
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self._update_value_from_pos(event.pos())
            event.accept()
        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event):
        self._pressed = False
        super().mouseReleaseEvent(event)
    
    def mouseMoveEvent(self, event):
        # Handle dragging the slider
        if self._pressed:
            self._update_value_from_pos(event.pos())
        # Update tooltip with current time
        groove = self._get_groove_rect()
        if groove.isValid() and groove.width() > 0:
            pos_in_groove = event.pos().x() - groove.left()
            visible_range = self.maximum() - self.minimum()
            current_time = self.minimum() + (pos_in_groove / groove.width()) * visible_range
            time_str = self._format_timestamp(current_time)
            self.setToolTip(f"Time: {time_str}\nClick and drag to seek")
            
        super().mouseMoveEvent(event)
            
    def mouseReleaseEvent(self, event):
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(event)
        
    def leaveEvent(self, event):
        # Reset tooltip when mouse leaves the widget
        self.setToolTip("Click and drag to seek through the video")
        super().leaveEvent(event)
        
    def _format_timestamp(self, ms):
        """Format milliseconds into a human-readable time string (HH:MM:SS.sss)."""
        seconds = ms / 1000
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        
        if hours > 0:
            return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
        else:
            return f"{int(minutes):02d}:{int(seconds):02d}"
    
    def _update_value_from_pos(self, pos):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        
        # Get the groove rectangle
        groove = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, 
            opt, 
            QStyle.SubControl.SC_SliderGroove, 
            self
        )
        
        # Calculate the position within the groove
        if self.orientation() == Qt.Orientation.Horizontal:
            if groove.width() <= 0:
                return
                
            pos_in_groove = pos.x() - groove.left()
            value_span = self.maximum() - self.minimum()
            value = self.minimum() + (pos_in_groove / groove.width()) * value_span
        else:
            if groove.height() <= 0:
                return
                
            pos_in_groove = groove.bottom() - pos.y()
            value_span = self.maximum() - self.minimum()
            value = self.minimum() + (pos_in_groove / groove.height()) * value_span
        
        # Clamp the value to the valid range and update
        value = max(self.minimum(), min(self.maximum(), value))
        self.setValue(int(value))
        self.positionChanged.emit(int(value))
        
    def _update_hovered_event(self, pos):
        """Update the tooltip with the current time at the mouse position."""
        groove = self._get_groove_rect()
        if not groove.isValid() or groove.width() <= 0:
            return
            
        # Calculate the time at the mouse position
        pos_in_groove = pos.x() - groove.left()
        visible_range = self.maximum() - self.minimum()
        current_time = self.minimum() + (pos_in_groove / groove.width()) * visible_range
        time_str = self._format_timestamp(current_time)
        
        # Update tooltip with current time
        self.setToolTip(f"Time: {time_str}\nClick and drag to seek")
    
    def _update_highlighted_event(self, current_time):
        """This method is kept for backward compatibility but no longer has any effect."""
        pass
    
    def set_highlighted_event(self, index):
        """Highlight a specific event by its index.
        
        Args:
            index (int): Index of the event to highlight, or -1 to clear highlight
        """
        # This method is kept for compatibility with the UI
        # The actual highlighting is handled by the UI
        pass
        
    def sizeHint(self):
        return QSize(100, 30)  # Standard slider height
    
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
