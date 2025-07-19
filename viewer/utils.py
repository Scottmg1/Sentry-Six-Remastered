import os
import sys
import shutil
import subprocess
import re
from dataclasses import dataclass
from datetime import datetime

try:
    import __main__
    DEBUG_UI = __main__.DEBUG if hasattr(__main__, 'DEBUG') else False
except (ImportError, AttributeError):
    DEBUG_UI = False

# Enhanced debugging flags for timestamp synchronization issues
DEBUG_TIMING = DEBUG_UI  # Enable detailed timing logs
DEBUG_POSITION_UPDATES = DEBUG_UI  # Track position update conflicts
DEBUG_UI_PERFORMANCE = DEBUG_UI  # Monitor UI thread performance

from .ffmpeg_manager import FFMPEG_EXE, FFPROBE_EXE

# --- Constants ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(os.path.dirname(BASE_DIR), 'assets')

# Remove FFMPEG_PATH, FFPROBE_PATH, FFMPEG_FOUND, and find_ffmpeg logic
# Use FFMPEG_EXE and FFPROBE_EXE everywhere instead

filename_pattern = re.compile(r"(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})-(front|left_repeater|right_repeater|back|left_pillar|right_pillar)\.mp4")

# --- FFmpeg Functions ---
# Remove FFMPEG_PATH, FFPROBE_PATH, FFMPEG_FOUND, and find_ffmpeg logic
# Use FFMPEG_EXE and FFPROBE_EXE everywhere instead

def get_video_duration_ms(video_path):
    if not FFPROBE_EXE or not os.path.exists(video_path):
        return 60000  # Default to 1 minute if ffprobe is not found or file doesn't exist

    command = [
        FFPROBE_EXE,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

    try:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
        stdout, _ = proc.communicate(timeout=5)  # 5-second timeout
        if proc.returncode == 0 and stdout:
            return int(float(stdout.strip()) * 1000)
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass  # Ignore errors and return default

    return 60000

def format_time(ms):
    """Optimized time formatting to reduce UI thread blocking."""
    if ms is None:
        return "--:--"
    seconds = max(0, ms // 1000)
    return f"{seconds // 60:02}:{seconds % 60:02}"

# Performance monitoring utilities for timestamp synchronization debugging
import time
import threading
from collections import deque

class PerformanceMonitor:
    """Monitor UI performance and timing conflicts during video playback."""

    def __init__(self, max_samples=100):
        self.max_samples = max_samples
        self.timer_updates = deque(maxlen=max_samples)
        self.position_updates = deque(maxlen=max_samples)
        self.ui_update_times = deque(maxlen=max_samples)
        self.timestamp_calc_times = deque(maxlen=max_samples)
        self._lock = threading.Lock()

    def record_timer_update(self, timestamp=None):
        """Record when timer-based position update occurs."""
        if timestamp is None:
            timestamp = time.time()
        with self._lock:
            self.timer_updates.append(timestamp)
            if DEBUG_TIMING:
                print(f"[TIMING] Timer update at {timestamp:.3f}")

    def record_position_update(self, position_ms, timestamp=None):
        """Record when video player position update occurs."""
        if timestamp is None:
            timestamp = time.time()
        with self._lock:
            self.position_updates.append((timestamp, position_ms))
            if DEBUG_POSITION_UPDATES:
                print(f"[POSITION] Player update: {position_ms}ms at {timestamp:.3f}")

    def record_ui_update_duration(self, duration_ms):
        """Record how long UI updates take."""
        with self._lock:
            self.ui_update_times.append(duration_ms)
            if DEBUG_UI_PERFORMANCE and duration_ms > 16.67:  # > 60fps threshold
                print(f"[UI_PERF] Slow UI update: {duration_ms:.2f}ms")

    def record_timestamp_calc_duration(self, duration_ms):
        """Record how long timestamp calculations take."""
        with self._lock:
            self.timestamp_calc_times.append(duration_ms)
            if DEBUG_UI_PERFORMANCE and duration_ms > 5:  # > 5ms threshold
                print(f"[TIMESTAMP_PERF] Slow timestamp calc: {duration_ms:.2f}ms")

    def get_performance_stats(self):
        """Get current performance statistics."""
        with self._lock:
            stats = {
                'timer_update_frequency': 0,
                'position_update_frequency': 0,
                'avg_ui_update_time': 0,
                'avg_timestamp_calc_time': 0,
                'max_ui_update_time': 0,
                'conflicts_detected': 0
            }

            if len(self.timer_updates) > 1:
                time_span = self.timer_updates[-1] - self.timer_updates[0]
                stats['timer_update_frequency'] = len(self.timer_updates) / time_span if time_span > 0 else 0

            if len(self.position_updates) > 1:
                time_span = self.position_updates[-1][0] - self.position_updates[0][0]
                stats['position_update_frequency'] = len(self.position_updates) / time_span if time_span > 0 else 0

            if self.ui_update_times:
                stats['avg_ui_update_time'] = sum(self.ui_update_times) / len(self.ui_update_times)
                stats['max_ui_update_time'] = max(self.ui_update_times)

            if self.timestamp_calc_times:
                stats['avg_timestamp_calc_time'] = sum(self.timestamp_calc_times) / len(self.timestamp_calc_times)

            # Detect timing conflicts (timer and position updates too close together)
            conflicts = 0
            for timer_time in list(self.timer_updates):
                for pos_time, _ in list(self.position_updates):
                    if abs(timer_time - pos_time) < 0.05:  # Within 50ms
                        conflicts += 1
            stats['conflicts_detected'] = conflicts

            return stats

# Global performance monitor instance
performance_monitor = PerformanceMonitor()

class OptimizedTimestampFormatter:
    """Optimized timestamp formatter to reduce string operations and improve performance."""

    def __init__(self):
        self._cache = {}
        self._cache_size_limit = 100

    def format_timestamp(self, global_time):
        """
        Optimized timestamp formatting without milliseconds.
        Uses caching to reduce repeated strftime calls.
        """
        try:
            # Create cache key based on date and time (excluding microseconds)
            cache_key = (global_time.year, global_time.month, global_time.day,
                        global_time.hour, global_time.minute, global_time.second)

            # Check cache first
            if cache_key in self._cache:
                base_str, am_pm = self._cache[cache_key]
            else:
                # Generate base timestamp string
                base_str = global_time.strftime('%m/%d/%Y %I:%M:%S')
                am_pm = global_time.strftime('%p')

                # Cache the result
                self._cache[cache_key] = (base_str, am_pm)

                # Limit cache size
                if len(self._cache) > self._cache_size_limit:
                    # Remove oldest entries (simple FIFO)
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]

            # Return timestamp without milliseconds
            return f"{base_str} {am_pm}"

        except Exception as e:
            if DEBUG_UI_PERFORMANCE:
                print(f"Error in optimized timestamp formatting: {e}")
            # Fallback to simple formatting
            return global_time.strftime('%m/%d/%Y %I:%M:%S %p')

    def clear_cache(self):
        """Clear the timestamp cache."""
        self._cache.clear()

# Global optimized timestamp formatter
timestamp_formatter = OptimizedTimestampFormatter()

def setup_assets():
    """Creates the assets directory and the SVG icon files if they don't exist."""
    if not os.path.exists(ASSETS_DIR):
        os.makedirs(ASSETS_DIR)
    
    icons = {
        'check.svg': '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#282c34" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>',
        'camera.svg': '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#e06c75" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path><circle cx="12" cy="13" r="4"></circle></svg>',
        'hand.svg': '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#c678dd" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11.5l3.5 3.5.9-1.8"/><path d="M20 13.3c.2-.3.2-.7 0-1l-3-5a2 2 0 00-3.5 0l-3.5 6a2 2 0 002 3h9.4a2 2 0 011.6.8L22 22V8.5A2.5 2.5 0 0019.5 6Z"/><path d="M2 16.5a2.5 2.5 0 012.5-2.5H8"/><path d="M10 20.5a2.5 2.5 0 01-2.5 2.5H4a2 2 0 01-2-2V16"/></svg>',
        'horn.svg': '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#d19a66" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.53 4.53 12 2 4 10v10h10v-4.07"/><path d="M12 10a2 2 0 00-2 2v0a2 2 0 002 2v0a2 2 0 002-2v0a2 2 0 00-2-2z"/><path d="M18 8a6 6 0 010 8"/></svg>'
    }

    for filename, svg_data in icons.items():
        path = os.path.join(ASSETS_DIR, filename)
        if not os.path.exists(path):
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(svg_data)
            except IOError as e:
                print(f"Could not write asset file {path}: {e}")

# Initial call to find FFmpeg on startup
# Remove FFMPEG_PATH, FFPROBE_PATH, FFMPEG_FOUND, and find_ffmpeg logic
# Use FFMPEG_EXE and FFPROBE_EXE everywhere instead