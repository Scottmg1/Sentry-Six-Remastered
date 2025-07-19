# Sentry-Six Electron

A modern Tesla dashcam viewer built with Electron and TypeScript, featuring synchronized multi-camera video playback and advanced timeline controls.

## Features

### 🎥 **Multi-Camera Synchronization**
- Simultaneous playback of up to 6 Tesla camera feeds
- Frame-accurate synchronization using HTML5 video elements
- Optimized for Tesla's 36.02 FPS video format

### 📁 **Tesla File Management**
- Automatic detection of Tesla dashcam folder structure
- Support for SavedClips, RecentClips, and SentryClips
- Intelligent file grouping by timestamp

### ⏯️ **Advanced Playback Controls**
- Play/pause/stop with keyboard shortcuts
- Variable speed playback (0.25x to 2x)
- Frame-accurate timeline scrubbing
- Volume control and muting

### 🎨 **Modern Interface**
- Dark theme optimized for video viewing
- Responsive grid layout for multiple cameras
- Real-time timestamp display
- Intuitive clip navigation

### 🔧 **Export & Processing**
- FFmpeg integration for video export
- Multiple quality settings
- Custom time range selection
- Audio inclusion options

## Installation

### Prerequisites
- Node.js 18+ and npm
- FFmpeg (for video processing)

### Setup
1. **Clone or download the project**
   ```bash
   cd Sentry-Six-Electron
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Build the application**
   ```bash
   npm run build
   ```

4. **Start the application**
   ```bash
   npm start
   ```

### Development Mode
For development with hot reload:
```bash
npm run dev
```

## Usage

### Loading Tesla Videos
1. Click "📁 Open Folder" in the sidebar
2. Select your Tesla dashcam folder (usually on USB drive)
3. The app will automatically scan and organize your clips

### Video Playback
- **Play/Pause**: Space bar or play button
- **Stop**: Ctrl+S or stop button
- **Seek**: Click timeline or use arrow keys
- **Speed**: Use speed dropdown or number keys
- **Volume**: Use volume slider

### Keyboard Shortcuts
- `Space` - Play/Pause
- `←/→` - Seek backward/forward 5 seconds
- `Ctrl+←/→` - Previous/Next clip
- `Home/End` - Jump to start/end
- `Ctrl+S` - Stop playback

### Navigation
- Click any clip in the sidebar to load it
- Use previous/next buttons for sequential playback
- Timeline shows current position and total duration

## Architecture

### Main Process (`src/main/`)
- **main.ts** - Electron main process and window management
- **tesla-file-manager.ts** - Tesla file discovery and organization
- **video-processor.ts** - FFmpeg integration for metadata and export
- **config-manager.ts** - Application settings and preferences

### Renderer Process (`src/renderer/`)
- **index.html** - Main application UI
- **styles.css** - Modern CSS styling
- **app.js** - Frontend application logic and video synchronization

### Shared (`src/shared/`)
- Type definitions and interfaces
- Common utilities and constants

## Performance Optimizations

### Video Synchronization
- Uses HTML5 video elements for hardware acceleration
- Chromium's optimized video engine handles multiple streams efficiently
- Frame-accurate seeking with minimal UI blocking

### Memory Management
- Lazy loading of video metadata
- Efficient clip list rendering
- Automatic cleanup of unused video elements

### Tesla-Specific Optimizations
- 36.02 FPS frame rate detection
- Optimized for Tesla's H.264 encoding
- Intelligent timestamp parsing from filenames

## Migration from PyQt6

This Electron version replaces the previous PyQt6 implementation to solve:
- **Video freezing issues** - Qt QMediaPlayer limitations with multiple streams
- **Synchronization problems** - Better control over video timing
- **Cross-platform compatibility** - Consistent behavior across Windows, macOS, Linux
- **Modern UI** - Web-based interface with better responsiveness

### Key Improvements
- **No more 1-3 second UI freezes** during video operations
- **Smoother timeline scrubbing** with real-time updates
- **Better hardware acceleration** through Chromium's video engine
- **Unified codebase** - Single technology stack for easier maintenance

## Building for Distribution

### Windows
```bash
npm run dist
```
Creates an NSIS installer in the `release/` directory.

### macOS
```bash
npm run dist
```
Creates a DMG file in the `release/` directory.

### Linux
```bash
npm run dist
```
Creates an AppImage in the `release/` directory.

## Configuration

Settings are stored in:
- **Windows**: `%APPDATA%/sentry-six-electron/config.json`
- **macOS**: `~/Library/Application Support/sentry-six-electron/config.json`
- **Linux**: `~/.config/sentry-six-electron/config.json`

## Troubleshooting

### Video Won't Play
- Ensure FFmpeg is installed and accessible
- Check that video files aren't corrupted
- Verify Tesla folder structure is correct

### Performance Issues
- Close other video applications
- Reduce number of concurrent cameras in settings
- Check available system memory

### File Loading Problems
- Ensure proper Tesla folder structure:
  ```
  TeslaCam/
  ├── SavedClips/
  ├── RecentClips/
  └── SentryClips/
  ```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Tesla for creating an amazing dashcam system
- Electron team for the excellent framework
- FFmpeg project for video processing capabilities
- Original PyQt6 implementation contributors
