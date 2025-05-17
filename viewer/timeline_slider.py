from PyQt6.QtWidgets import QSlider, QStyle, QStyleOptionSlider, QStylePainter, QApplication
from PyQt6.QtCore import Qt, QRect, QPoint
from PyQt6.QtGui import QPainter, QColor, QPen

class TimelineSlider(QSlider):
    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.event_positions = []
        self.highlighted_event = -1
        self.setMouseTracking(True)
    
    def set_event_positions(self, positions):
        """Set the positions of event markers as a list of values from 0 to maximum()"""
        self.event_positions = positions
        self.update()
    
    def set_highlighted_event(self, index):
        """Highlight a specific event by its index"""
        self.highlighted_event = index
        self.update()
    
    def paintEvent(self, event):
        # First draw the standard slider
        super().paintEvent(event)
        
        if not hasattr(self, 'event_positions') or not self.event_positions:
            return
            
        # Now draw the event markers
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Calculate the available width for the slider groove
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        rect = self.style().subControlRect(QStyle.ComplexControl.CC_Slider, 
                                          opt, 
                                          QStyle.SubControl.SC_SliderGroove, 
                                          self)
        
        # Make sure we have a valid maximum value
        max_val = max(1, self.maximum())  # Avoid division by zero
        
        # Draw event markers
        for i, pos in enumerate(self.event_positions):
            # Calculate the x position of the marker, ensuring it's within bounds
            try:
                x = rect.x() + (float(pos) / max_val) * rect.width()
                # Ensure x is within the slider bounds
                x = max(rect.x(), min(rect.x() + rect.width(), x))
                
                # Always use red color for better visibility
                color = QColor(255, 0, 0)  # Red for all events
                width = 2
                
                # Draw a vertical line at the event position that spans the full height of the slider
                pen = QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                
                # Draw a line that extends slightly above and below the slider
                line_top = rect.top() - 5
                line_bottom = rect.bottom() + 5
                painter.drawLine(QPoint(int(x), line_top), 
                               QPoint(int(x), line_bottom))
                
                # Add a small triangle at the top of the line for better visibility
                triangle_size = 6
                triangle = [
                    QPoint(int(x), line_top - triangle_size),
                    QPoint(int(x - triangle_size/2), line_top),
                    QPoint(int(x + triangle_size/2), line_top)
                ]
                painter.setBrush(color)
                painter.drawPolygon(triangle)
                
            except (ValueError, ZeroDivisionError) as e:
                print(f"Error drawing event marker at position {pos}: {e}")
                continue
        
        painter.end()
    
    def mouseMoveEvent(self, event):
        # Highlight the nearest event when hovering
        if not self.event_positions:
            return super().mouseMoveEvent(event)
            
        # Calculate the position of the mouse relative to the slider
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        rect = self.style().subControlRect(QStyle.ComplexControl.CC_Slider, 
                                          opt, 
                                          QStyle.SubControl.SC_SliderGroove, 
                                          self)
        
        # Find the nearest event to the mouse position
        pos = event.pos().x()
        rel_pos = (pos - rect.x()) / rect.width() * self.maximum()
        
        nearest_idx = -1
        min_dist = float('inf')
        
        for i, event_pos in enumerate(self.event_positions):
            dist = abs(event_pos - rel_pos)
            if dist < min_dist and dist < 20:  # Only highlight if close enough
                min_dist = dist
                nearest_idx = i
        
        if nearest_idx != self.highlighted_event:
            self.highlighted_event = nearest_idx
            self.update()
            
        super().mouseMoveEvent(event)
    
    def leaveEvent(self, event):
        # Clear highlight when mouse leaves the slider
        if self.highlighted_event != -1:
            self.highlighted_event = -1
            self.update()
        super().leaveEvent(event)
