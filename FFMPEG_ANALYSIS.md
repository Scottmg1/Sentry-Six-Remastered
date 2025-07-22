# FFMPEG Implementation Analysis - PyQt6 to Electron Migration

## 🔧 **1. Core FFMPEG Command Structure**

### **Base Command Pattern**
```bash
ffmpeg -y -f concat -safe 0 -ss <offset> -i <input_list> [additional inputs...] 
-filter_complex "<complex_filters>" -map <video_stream> -map <audio_stream> 
-t <duration> -c:v libx264 -preset <preset> -crf <quality> -c:a aac -b:a 128k <output>
```

### **Key Components from PyQt6 Implementation**

#### **Input Stream Creation**
- **Concat Demuxer**: Uses `-f concat -safe 0` for seamless clip joining
- **Offset Handling**: `-ss <offset>` for precise start time positioning
- **Temp File Lists**: Creates temporary `.txt` files listing video paths
- **Multi-Camera Support**: Separate input streams for each camera

#### **Video Processing Pipeline**
```javascript
// From ffmpeg_builder.py lines 39-41
const scaleFilter = ",scale=1448:938";
const initialFilters = `[${i}:v]setpts=PTS-STARTPTS${scaleFilter}[v${i}]`;
```

#### **Grid Layout Logic**
```javascript
// From ffmpeg_builder.py lines 47-50
const cols = numStreams === 2 || numStreams === 4 ? 2 : numStreams > 2 ? 3 : 1;
const layout = streams.map((_, i) => {
    const row = Math.floor(i / cols);
    const col = i % cols;
    return `${col * width}_${row * height}`;
}).join('|');
```

## ⏰ **2. Timestamp Overlay Implementation**

### **Dynamic Timestamp Generation**
```javascript
// From ffmpeg_builder.py lines 56-64
const startTimeUnix = startDateTime.getTime() / 1000;
const basetimeUs = Math.floor(startTimeUnix * 1_000_000);

const drawTextFilter = [
    "drawtext=font='Arial'",
    "expansion=strftime",
    `basetime=${basetimeUs}`,
    "text='%m/%d/%Y %I\\:%M\\:%S %p'",
    "fontcolor=white",
    "fontsize=36",
    "box=1",
    "boxcolor=black@0.4",
    "boxborderw=5",
    "x=(w-text_w)/2",
    "y=h-th-10"
].join(':');
```

### **Timestamp Features**
- **Live Clock**: Uses `strftime` expansion with `basetime` for real-time timestamps
- **Format**: MM/DD/YYYY HH:MM:SS AM/PM
- **Styling**: White text, black semi-transparent background, centered bottom
- **Font**: Arial, 36px size with 5px border

## 📐 **3. Camera Size Handling & Normalization**

### **Standard Resolution**
```javascript
// From ffmpeg_builder.py line 45
const standardWidth = 1448;
const standardHeight = 938;
```

### **Scaling Strategy**
- **Uniform Scaling**: All cameras scaled to 1448x938 regardless of source resolution
- **Aspect Ratio**: Maintains Tesla's native 1.54:1 aspect ratio
- **Quality Preservation**: Uses high-quality scaling algorithms

### **Grid Layout Calculations**
```javascript
// Camera arrangement logic
const gridLayouts = {
    1: { cols: 1, rows: 1 },
    2: { cols: 2, rows: 1 },
    3: { cols: 3, rows: 1 },
    4: { cols: 2, rows: 2 },
    5: { cols: 3, rows: 2 },
    6: { cols: 3, rows: 2 }  // Tesla's 6-camera layout
};
```

### **Tesla 6-Camera Layout**
```
[Left Pillar] [Front] [Right Pillar]
[Left Repeat] [Back]  [Right Repeat]
```

## 🎯 **4. Quality & Compression Settings**

### **Full Resolution Export**
```javascript
const fullQualitySettings = [
    "-c:v", "libx264",
    "-preset", "medium",
    "-crf", "18"  // High quality
];
```

### **Mobile-Friendly Export**
```javascript
const mobileSettings = [
    "-c:v", "libx264", 
    "-preset", "fast",
    "-crf", "23"  // Balanced quality/size
];

// Mobile scaling calculation
const totalWidth = width * cols;
const totalHeight = height * Math.ceil(numStreams / cols);
const mobileWidth = Math.floor(1080 * (totalWidth / totalHeight) / 2) * 2;
const mobileScale = `scale=${mobileWidth}:1080`;
```

## 🔄 **5. Progress Tracking Implementation**

### **FFMPEG Output Parsing**
```javascript
// From workers.py lines 27, 50-56
const timePattern = /time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})/;

function parseProgress(line, totalDurationSeconds) {
    const match = timePattern.exec(line);
    if (match) {
        const [, hours, minutes, seconds, hundredths] = match.map(Number);
        const currentProgressS = (hours * 3600) + (minutes * 60) + seconds + (hundredths / 100);
        const percentage = Math.max(0, Math.min(100, Math.floor((currentProgressS / totalDurationSeconds) * 100)));
        return { percentage, currentTime: currentProgressS };
    }
    return null;
}
```

## 🚀 **6. Hardware Acceleration Support**

### **GPU Detection**
```javascript
// From hwacc_detector.py
const hwAccEncoders = {
    nvidia: ["h264_nvenc", "hevc_nvenc"],
    amd: ["h264_amf", "hevc_amf"], 
    intel: ["h264_qsv", "hevc_qsv"]
};
```

### **Performance Optimization**
- **NVENC**: NVIDIA hardware encoding (fastest)
- **AMF**: AMD hardware encoding
- **Quick Sync**: Intel hardware encoding
- **Fallback**: Software encoding with optimized presets

## 📁 **7. File Management**

### **Temporary File Handling**
```javascript
// From ffmpeg_builder.py lines 105-115
function createConcatFile(clipPaths) {
    const tempFile = path.join(os.tmpdir(), `concat_${Date.now()}.txt`);
    const content = clipPaths.map(p => `file '${path.resolve(p)}'`).join('\n');
    fs.writeFileSync(tempFile, content);
    return tempFile;
}
```

### **Cleanup Strategy**
- **Automatic Cleanup**: Remove temp files after export completion
- **Error Handling**: Cleanup on export failure or cancellation
- **Resource Management**: Track all temporary files for proper disposal

## 🔧 **8. Error Handling & Recovery**

### **Process Management**
```javascript
// From workers.py lines 35-42
const ffmpegProcess = spawn('ffmpeg', args, {
    stdio: ['pipe', 'pipe', 'pipe'],
    windowsHide: true  // Hide console window on Windows
});

// Graceful termination
function cancelExport() {
    if (ffmpegProcess && !ffmpegProcess.killed) {
        ffmpegProcess.kill('SIGTERM');
    }
}
```

## 📊 **9. Size Estimation Algorithm**

### **File Size Calculation**
```javascript
// Estimated from export.py usage patterns
function estimateFileSize(durationSeconds, quality, cameraCount) {
    const baseSizeMBPerMinute = quality === 'full' ? 50 : 20;
    const cameraMultiplier = cameraCount / 6; // Normalize to 6-camera baseline
    return Math.round((durationSeconds / 60) * baseSizeMBPerMinute * cameraMultiplier);
}
```

## 🎬 **10. Audio Handling**

### **Audio Stream Selection**
```javascript
// From ffmpeg_builder.py lines 79-81
// Always use front camera audio as primary source
const frontCameraIndex = cameraMap.front;
const audioStreamIndex = inputs.findIndex(input => input.cameraIndex === frontCameraIndex);
if (audioStreamIndex !== -1) {
    command.push("-map", `${audioStreamIndex}:a?`);
}
```

### **Audio Settings**
- **Codec**: AAC encoding
- **Bitrate**: 128k for all exports
- **Source**: Front camera audio only (Tesla standard)
- **Fallback**: Graceful handling if no audio available

---

## 🔄 **Migration Strategy for Electron**

### **Phase 2 Implementation Plan**

1. **Main Process Handler** - Create IPC handlers for export requests
2. **FFMPEG Integration** - Port command building logic to Node.js
3. **Progress Streaming** - Implement real-time progress updates via IPC
4. **File Management** - Adapt temp file handling for Electron environment
5. **Error Recovery** - Port error handling and cleanup mechanisms

### **Key Adaptations Needed**

- **Path Handling**: Convert Windows-specific paths to cross-platform
- **Process Management**: Use Node.js `child_process` instead of Python `subprocess`
- **IPC Communication**: Replace PyQt signals with Electron IPC
- **File System**: Use Node.js `fs` module for temp file management
- **Progress Updates**: Stream FFMPEG output through IPC to renderer

This analysis provides the complete technical foundation for implementing Phase 2 of the video export feature in our Electron-based Tesla dashcam viewer.
