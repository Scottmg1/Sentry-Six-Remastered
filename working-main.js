// Working Sentry-Six Electron Main Process
// Simplified JavaScript version to get the app running

const path = require('path');
const fs = require('fs');
const os = require('os');

// Try different ways to import Electron
let electron;
try {
    electron = require('electron');
    console.log('Electron loaded successfully');
} catch (error) {
    console.error('Failed to load Electron:', error);
    process.exit(1);
}

const { app, BrowserWindow, ipcMain, dialog, Menu } = electron;

if (!app) {
    console.error('Electron app is undefined - this might be a version compatibility issue');
    process.exit(1);
}

class SentrySixApp {
    constructor() {
        this.mainWindow = null;
        this.initializeApp();
    }

    initializeApp() {
        console.log('Initializing Sentry-Six...');
        
        // Handle app ready
        app.whenReady().then(() => {
            console.log('App is ready, creating window...');
            this.createMainWindow();
            this.setupIpcHandlers();
            this.createApplicationMenu();

            app.on('activate', () => {
                if (BrowserWindow.getAllWindows().length === 0) {
                    this.createMainWindow();
                }
            });
        });

        // Handle app window closed
        app.on('window-all-closed', () => {
            if (process.platform !== 'darwin') {
                app.quit();
            }
        });
    }

    createMainWindow() {
        console.log('Creating main window...');
        
        this.mainWindow = new BrowserWindow({
            width: 1400,
            height: 900,
            minWidth: 1200,
            minHeight: 700,
            webPreferences: {
                nodeIntegration: false,
                contextIsolation: true,
                preload: path.join(__dirname, 'working-preload.js')
            },
            title: 'Sentry-Six - Tesla Dashcam Viewer',
            show: false
        });

        // Load the renderer HTML
        this.mainWindow.loadFile(path.join(__dirname, 'src', 'renderer', 'index.html'));

        // Show window when ready
        this.mainWindow.once('ready-to-show', () => {
            console.log('Window ready to show');
            this.mainWindow.show();
        });

        // Handle window closed
        this.mainWindow.on('closed', () => {
            this.mainWindow = null;
        });

        console.log('Main window created successfully');
    }

    setupIpcHandlers() {
        console.log('Setting up IPC handlers...');
        
        // Tesla file operations
        ipcMain.handle('tesla:select-folder', async () => {
            const result = await dialog.showOpenDialog(this.mainWindow, {
                properties: ['openDirectory'],
                title: 'Select Tesla Dashcam Folder'
            });

            if (!result.canceled && result.filePaths.length > 0) {
                const selectedPath = result.filePaths[0];
                console.log('Selected folder:', selectedPath);

                // Scan for Tesla video files
                const videoFiles = await this.scanTeslaFolder(selectedPath);
                console.log(`Found ${videoFiles.length} Tesla video files`);

                return {
                    success: true,
                    path: selectedPath,
                    videoFiles: videoFiles
                };
            }
            return { success: false };
        });

        // Get video files for a specific folder
        ipcMain.handle('tesla:get-video-files', async (_, folderPath) => {
            console.log('Getting video files for folder:', folderPath);
            const videoFiles = await this.scanTeslaFolder(folderPath);
            return videoFiles;
        });

        // Simple file system check
        ipcMain.handle('fs:exists', async (_, filePath) => {
            return fs.existsSync(filePath);
        });

        // Show item in folder
        ipcMain.handle('fs:show-item-in-folder', async (_, filePath) => {
            const { shell } = require('electron');
            shell.showItemInFolder(filePath);
        });

        // File save dialog for exports
        ipcMain.handle('dialog:save-file', async (_, options) => {
            const result = await dialog.showSaveDialog(this.mainWindow, {
                title: options.title || 'Save Export',
                defaultPath: options.defaultPath || 'tesla_export.mp4',
                filters: options.filters || [
                    { name: 'Video Files', extensions: ['mp4'] },
                    { name: 'All Files', extensions: ['*'] }
                ]
            });

            return result.canceled ? null : result.filePath;
        });

        // Get app version
        ipcMain.handle('app:get-version', async () => {
            return app.getVersion();
        });

        // Hardware acceleration detection
        ipcMain.handle('tesla:detect-hwaccel', async () => {
            try {
                const ffmpegPath = this.findFFmpegPath();
                if (!ffmpegPath) {
                    return { available: false, type: null, encoder: null, error: 'FFmpeg not found' };
                }

                const hwAccel = await this.detectHardwareAcceleration(ffmpegPath);
                return hwAccel;
            } catch (error) {
                console.error('Error detecting hardware acceleration:', error);
                return { available: false, type: null, encoder: null, error: error.message };
            }
        });

        // Tesla video export
        ipcMain.handle('tesla:export-video', async (event, exportId, exportData) => {
            console.log('🚀 Starting Tesla video export:', exportId);
            
            try {
                console.log('📋 Export data received:', exportData);
                
                // Validate export data
                if (!exportData.timeline || !exportData.outputPath) {
                    throw new Error('Invalid export data: missing timeline or output path');
                }

                console.log('🔍 Validating FFmpeg availability...');
                // Check if FFmpeg is available
                const { spawn } = require('child_process');
                const ffmpegPath = this.findFFmpegPath();
                
                console.log('🔍 FFmpeg path found:', ffmpegPath);
                
                if (!ffmpegPath) {
                    throw new Error('FFmpeg not found. Please install FFmpeg or place it in the ffmpeg_bin directory.');
                }

                console.log('🔍 Starting video export process...');
                // Start the export process
                const result = await this.performVideoExport(event, exportId, exportData, ffmpegPath);
                console.log('🔍 Export process completed with result:', result);

                return result;
            } catch (error) {
                console.error('💥 Export failed:', error);
                event.sender.send('tesla:export-progress', exportId, {
                    type: 'complete',
                    success: false,
                    message: `Export failed: ${error.message}`
                });
                return false;
            }
        });

        // Tesla export cancellation
        ipcMain.handle('tesla:cancel-export', async (_, exportId) => {
            console.log('🚫 Cancelling export:', exportId);
            return true;
        });

        // Tesla export status
        ipcMain.handle('tesla:get-export-status', async (_, exportId) => {
            console.log('📊 Getting export status:', exportId);
            return false; // Not currently exporting
        });

        // Tesla event data
        ipcMain.handle('tesla:get-event-data', async (_, folderPath) => {
            console.log('📅 Getting event data for:', folderPath);
            try {
                const events = await this.scanTeslaEvents(folderPath);
                console.log(`Found ${events.length} events`);
                return events;
            } catch (error) {
                console.error('Error getting event data:', error);
                return [];
            }
        });

        // Tesla event thumbnail
        ipcMain.handle('tesla:get-event-thumbnail', async (_, thumbnailPath) => {
            console.log('🖼️ Getting event thumbnail:', thumbnailPath);
            try {
                if (fs.existsSync(thumbnailPath)) {
                    const imageBuffer = fs.readFileSync(thumbnailPath);
                    return `data:image/png;base64,${imageBuffer.toString('base64')}`;
                }
                return null;
            } catch (error) {
                console.error('Error reading event thumbnail:', error);
                return null;
            }
        });

        console.log('IPC handlers set up successfully');
    }

    // FFmpeg path finding
    findFFmpegPath() {
        const possiblePaths = [
            'ffmpeg', // System PATH
            path.join(__dirname, 'ffmpeg_bin', 'ffmpeg.exe'), // Bundled Windows
            path.join(__dirname, 'ffmpeg_bin', 'ffmpeg'), // Bundled Unix
            path.join(process.cwd(), 'ffmpeg_bin', 'ffmpeg.exe'), // Current working directory
            path.join(process.cwd(), 'ffmpeg_bin', 'ffmpeg'), // Current working directory Unix
            '/usr/local/bin/ffmpeg', // Homebrew macOS
            '/usr/bin/ffmpeg' // Linux
        ];

        for (const ffmpegPath of possiblePaths) {
            try {
                const { spawnSync } = require('child_process');
                const result = spawnSync(ffmpegPath, ['-version'], { 
                    timeout: 5000,
                    stdio: 'pipe'
                });
                if (result.status === 0) {
                    console.log(`✅ Found FFMPEG at: ${ffmpegPath}`);
                    return ffmpegPath;
                }
            } catch (error) {
                // Continue to next path
            }
        }

        return null;
    }

    // Detect available hardware acceleration
    async detectHardwareAcceleration(ffmpegPath) {
        if (!ffmpegPath) return { available: false, type: null, encoder: null };

        const { spawnSync } = require('child_process');

        try {
            // Get FFmpeg encoders list
            const result = spawnSync(ffmpegPath, ['-encoders'], {
                timeout: 10000,
                stdio: 'pipe'
            });

            if (result.status !== 0) {
                return { available: false, type: null, encoder: null };
            }

            const encodersOutput = result.stdout.toString();
            const platform = process.platform;

            console.log('🔍 Checking hardware acceleration availability...');

            // Test each hardware encoder by actually trying to use it
            const hwAccelOptions = [];

            // Test NVIDIA NVENC (Windows/Linux)
            if (encodersOutput.includes('h264_nvenc')) {
                console.log('🔍 Testing NVIDIA NVENC...');
                if (await this.testHardwareEncoder(ffmpegPath, 'h264_nvenc')) {
                    hwAccelOptions.push({
                        type: 'NVIDIA NVENC',
                        encoder: 'h264_nvenc',
                        decoder: 'h264_cuvid',
                        priority: 1
                    });
                    console.log('✅ NVIDIA NVENC test passed');
                } else {
                    console.log('❌ NVIDIA NVENC test failed');
                }
            }

            // Test AMD AMF (Windows)
            if (encodersOutput.includes('h264_amf') && platform === 'win32') {
                console.log('🔍 Testing AMD AMF...');
                if (await this.testHardwareEncoder(ffmpegPath, 'h264_amf')) {
                    hwAccelOptions.push({
                        type: 'AMD AMF',
                        encoder: 'h264_amf',
                        decoder: null,
                        priority: 2
                    });
                    console.log('✅ AMD AMF test passed');
                } else {
                    console.log('❌ AMD AMF test failed');
                }
            }

            // Test Intel Quick Sync (Windows/Linux)
            if (encodersOutput.includes('h264_qsv')) {
                console.log('🔍 Testing Intel Quick Sync...');
                if (await this.testHardwareEncoder(ffmpegPath, 'h264_qsv')) {
                    hwAccelOptions.push({
                        type: 'Intel Quick Sync',
                        encoder: 'h264_qsv',
                        decoder: 'h264_qsv',
                        priority: 3
                    });
                    console.log('✅ Intel Quick Sync test passed');
                } else {
                    console.log('❌ Intel Quick Sync test failed');
                }
            }

            // Test Apple VideoToolbox (macOS)
            if (encodersOutput.includes('h264_videotoolbox') && platform === 'darwin') {
                console.log('🔍 Testing Apple VideoToolbox...');
                if (await this.testHardwareEncoder(ffmpegPath, 'h264_videotoolbox')) {
                    hwAccelOptions.push({
                        type: 'Apple VideoToolbox',
                        encoder: 'h264_videotoolbox',
                        decoder: null,
                        priority: 1
                    });
                    console.log('✅ Apple VideoToolbox test passed');
                } else {
                    console.log('❌ Apple VideoToolbox test failed');
                }
            }

            // Sort by priority and return the best option
            if (hwAccelOptions.length > 0) {
                const bestOption = hwAccelOptions.sort((a, b) => a.priority - b.priority)[0];
                console.log(`🚀 Hardware acceleration detected: ${bestOption.type}`);
                return {
                    available: true,
                    type: bestOption.type,
                    encoder: bestOption.encoder,
                    decoder: bestOption.decoder
                };
            }

            console.log('⚠️ No hardware acceleration detected');
            return { available: false, type: null, encoder: null };

        } catch (error) {
            console.error('Error detecting hardware acceleration:', error);
            return { available: false, type: null, encoder: null };
        }
    }

    // Test if a hardware encoder actually works
    async testHardwareEncoder(ffmpegPath, encoder) {
        const { spawnSync } = require('child_process');

        try {
            // Create a minimal test command to see if the encoder initializes
            const testArgs = [
                '-f', 'lavfi',
                '-i', 'testsrc2=duration=1:size=320x240:rate=1',
                '-c:v', encoder,
                '-frames:v', '1',
                '-f', 'null',
                '-'
            ];

            const result = spawnSync(ffmpegPath, testArgs, {
                timeout: 5000,
                stdio: 'pipe'
            });

            // If the command succeeds (exit code 0), the encoder works
            return result.status === 0;

        } catch (error) {
            console.log(`❌ Hardware encoder test failed for ${encoder}:`, error.message);
            return false;
        }
    }

    // Video export implementation
    async performVideoExport(event, exportId, exportData, ffmpegPath) {
        const { spawn } = require('child_process');
        const fs = require('fs');
        const os = require('os');
        const { timeline, startTime, endTime, quality, cameras, timestamp, outputPath, hwaccel } = exportData;

        // Initialize tempFiles array for cleanup
        const tempFiles = [];

        try {
            console.log('🔍 Starting performVideoExport...');
            console.log('🔍 Timeline clips:', timeline.clips?.length);
            console.log('🔍 Selected cameras:', cameras);
            
            // Calculate duration and offset
            const durationMs = endTime - startTime;
            const durationSeconds = durationMs / 1000;
            const offsetSeconds = startTime / 1000;

            console.log(`🎬 Building export command: ${durationSeconds}s duration, ${offsetSeconds}s offset`);
            console.log(`📍 Export range: ${offsetSeconds}s to ${offsetSeconds + durationSeconds}s (${durationSeconds}s total)`);

            // Find clips that contain the export range
            const exportClips = this.findClipsForExportRange(timeline, startTime, endTime);
            console.log(`🔍 Found ${exportClips.length} clips for export range`);

            if (exportClips.length === 0) {
                throw new Error('No video clips found in the specified export range');
            }

            // Create input streams for all selected cameras from the relevant clips
            const inputs = [];

            for (let i = 0; i < cameras.length; i++) {
                const camera = cameras[i];

                // Collect all clips for this camera in the export range
                const cameraClips = exportClips
                    .filter(clip => clip.files && clip.files[camera])
                    .map(clip => ({
                        path: clip.files[camera].path,
                        clipRelativeStart: clip.clipRelativeStart || 0,
                        clipDuration: clip.clipDuration || 60000
                    }))
                    .sort((a, b) => a.clipRelativeStart - b.clipRelativeStart);

                if (cameraClips.length === 0) {
                    console.log(`⚠️ Skipping camera ${camera}: no files available in export range`);
                    continue;
                }

                if (cameraClips.length === 1) {
                    // Single clip - use existing logic
                    const clip = cameraClips[0];
                    const relativeOffset = Math.max(0, startTime - clip.clipRelativeStart) / 1000;

                    console.log(`🔍 Adding camera ${camera}: ${clip.path}`);
                    console.log(`📍 Camera ${camera}: clip starts at ${clip.clipRelativeStart}ms, relative offset: ${relativeOffset}s`);

                    inputs.push({
                        camera: camera,
                        path: clip.path,
                        index: i,
                        relativeOffset: relativeOffset
                    });
                } else {
                    // Multiple clips - create concat file
                    console.log(`🔗 Camera ${camera}: creating concat file for ${cameraClips.length} clips`);

                    const concatFilePath = path.join(os.tmpdir(), `tesla_export_${camera}_${Date.now()}.txt`);
                    const concatContent = cameraClips.map(clip => `file '${clip.path}'`).join('\n');

                    fs.writeFileSync(concatFilePath, concatContent);
                    tempFiles.push(concatFilePath);

                    // Calculate offset for the concatenated stream
                    const firstClipStart = cameraClips[0].clipRelativeStart;
                    const relativeOffset = Math.max(0, startTime - firstClipStart) / 1000;

                    console.log(`🔍 Adding camera ${camera}: concat file with ${cameraClips.length} clips`);
                    console.log(`📍 Camera ${camera}: concat starts at ${firstClipStart}ms, relative offset: ${relativeOffset}s`);

                    inputs.push({
                        camera: camera,
                        path: concatFilePath,
                        index: i,
                        relativeOffset: relativeOffset,
                        isConcat: true
                    });
                }
            }
            
            if (inputs.length === 0) {
                throw new Error('No valid camera files found for export');
            }

            // Build FFmpeg command with multi-camera support
            const cmd = [ffmpegPath, '-y'];
            const initialFilters = [];
            const streamMaps = [];
            
            // Add input streams with individual relative offsets
            for (let i = 0; i < inputs.length; i++) {
                const input = inputs[i];
                // Add relative offset for this specific camera/clip
                if (input.relativeOffset > 0) {
                    cmd.push('-ss', input.relativeOffset.toString());
                }

                if (input.isConcat) {
                    // Use concat demuxer for multiple clips
                    cmd.push('-f', 'concat', '-safe', '0', '-i', input.path);
                } else {
                    // Regular single file input
                    cmd.push('-i', input.path);
                }
            }

            // Build filter chains for each input stream

            for (let i = 0; i < inputs.length; i++) {
                const input = inputs[i];

                // Apply sync offset for right_repeater (starts 1 second early)
                let ptsFilter = 'setpts=PTS-STARTPTS';
                if (input.camera === 'right_repeater') {
                    // Delay right_repeater by 1 second to sync with other cameras
                    ptsFilter = 'setpts=PTS-STARTPTS+1/TB';
                    console.log(`🔍 Applying 1-second delay to right_repeater`);
                }

                // Check if camera should be mirrored (Tesla back and repeater cameras are mirrored)
                const isMirroredCamera = ['back', 'left_repeater', 'right_repeater'].includes(input.camera);
                let filterChain = ptsFilter;

                if (isMirroredCamera) {
                    // Add horizontal flip for mirrored cameras
                    filterChain += ',hflip';
                    console.log(`🔍 Applying horizontal flip to ${input.camera}`);
                }

                // Scale each stream to standard Tesla camera resolution
                const scaleFilter = `[${i}:v]${filterChain},scale=1448:938[v${i}]`;
                initialFilters.push(scaleFilter);
                streamMaps.push(`[v${i}]`);
            }

            // Build grid layout using xstack
            const numStreams = inputs.length;
            const w = 1448; // Camera width
            const h = 938;  // Camera height
            
            let mainProcessingChain = [];
            let lastOutputTag = '';
            
            if (numStreams > 1) {
                // Calculate grid layout for better aspect ratio (16:9)
                let cols, rows;
                
                if (numStreams === 2) {
                    cols = 2; rows = 1; // 2x1 layout
                } else if (numStreams === 3) {
                    cols = 3; rows = 1; // 3x1 layout
                } else if (numStreams === 4) {
                    cols = 2; rows = 2; // 2x2 layout
                } else if (numStreams === 5) {
                    cols = 3; rows = 2; // 3x2 layout (one empty space)
                } else if (numStreams === 6) {
                    cols = 3; rows = 2; // 3x2 layout (16:9 aspect ratio)
                } else {
                    // For more than 6 cameras, use 3 columns
                    cols = 3; rows = Math.ceil(numStreams / 3);
                }
                
                // Create layout positions
                const layout = [];
                for (let i = 0; i < numStreams; i++) {
                    const row = Math.floor(i / cols);
                    const col = i % cols;
                    layout.push(`${col * w}_${row * h}`);
                }
                
                const layoutStr = layout.join('|');
                const xstackFilter = `${streamMaps.join('')}xstack=inputs=${numStreams}:layout=${layoutStr}[stacked]`;
                mainProcessingChain.push(xstackFilter);
                lastOutputTag = '[stacked]';
                
                console.log(`🔍 Grid layout: ${cols}x${rows}, cameras: ${numStreams}, layout: ${layoutStr}`);
            } else {
                lastOutputTag = '[v0]';
            }
            
            // Add timestamp overlay if enabled
            if (timestamp.enabled) {
                // Calculate the actual timestamp for the export start time
                const timelineStartUnix = new Date(timeline.startTime).getTime();
                const exportStartUnix = (timelineStartUnix + startTime) / 1000; // startTime is in milliseconds
                const basetimeUs = Math.floor(exportStartUnix * 1000000);

                console.log(`🕐 Timestamp calculation: timeline start=${new Date(timelineStartUnix).toISOString()}, export offset=${startTime}ms, export start=${new Date(exportStartUnix * 1000).toISOString()}`);
                
                const drawtextFilter = [
                    'drawtext=font=Arial',
                    'expansion=strftime',
                    `basetime=${basetimeUs}`,
                    "text='%m/%d/%Y %I\\:%M\\:%S %p'",
                    'fontcolor=white',
                    'fontsize=36',
                    'box=1',
                    'boxcolor=black@0.4',
                    'boxborderw=5',
                    'x=(w-text_w)/2:y=h-th-10'
                ].join(':');
                
                mainProcessingChain.push(`${lastOutputTag}${drawtextFilter}[timestamped]`);
                lastOutputTag = '[timestamped]';
            }
            
            // Add mobile scaling if requested
            if (quality === 'mobile') {
                // Calculate grid dimensions for proper scaling
                let cols, rows;
                if (numStreams === 2) {
                    cols = 2; rows = 1;
                } else if (numStreams === 3) {
                    cols = 3; rows = 1;
                } else if (numStreams === 4) {
                    cols = 2; rows = 2;
                } else if (numStreams === 5) {
                    cols = 3; rows = 2;
                } else if (numStreams === 6) {
                    cols = 3; rows = 2;
                } else {
                    cols = 3; rows = Math.ceil(numStreams / 3);
                }
                
                const totalWidth = w * cols;
                const totalHeight = h * rows;
                const mobileWidth = Math.floor(1080 * (totalWidth / totalHeight) / 2) * 2; // Ensure even width
                
                mainProcessingChain.push(`${lastOutputTag}scale=${mobileWidth}:1080[final]`);
                lastOutputTag = '[final]';
            } else {
                // Rename final output for consistency
                if (lastOutputTag !== '[final]') {
                    mainProcessingChain.push(`${lastOutputTag}copy[final]`);
                    lastOutputTag = '[final]';
                }
            }
            
            // Combine all filter chains
            const filterComplex = [...initialFilters, ...mainProcessingChain].join(';');
            cmd.push('-filter_complex', filterComplex);
            cmd.push('-map', '[final]');
            
            // Add audio from front camera if available
            const frontCameraIndex = inputs.findIndex(input => input.camera === 'front');
            if (frontCameraIndex !== -1) {
                cmd.push('-map', `${frontCameraIndex}:a?`);
            }
            
            // Add encoding settings with hardware acceleration support
            let vCodec;

            if (hwaccel && hwaccel.enabled && hwaccel.encoder) {
                console.log(`🚀 Using hardware acceleration: ${hwaccel.type}`);

                // Add hardware decoder if available
                if (hwaccel.decoder) {
                    cmd.push('-hwaccel', hwaccel.decoder.replace('h264_', ''));
                }

                // Hardware encoder settings
                switch (hwaccel.encoder) {
                    case 'h264_nvenc':
                        vCodec = quality === 'mobile' ?
                            ['-c:v', 'h264_nvenc', '-preset', 'fast', '-cq', '25'] :
                            ['-c:v', 'h264_nvenc', '-preset', 'medium', '-cq', '20'];
                        break;
                    case 'h264_amf':
                        vCodec = quality === 'mobile' ?
                            ['-c:v', 'h264_amf', '-quality', 'speed', '-rc', 'cqp', '-qp_i', '25', '-qp_p', '25'] :
                            ['-c:v', 'h264_amf', '-quality', 'balanced', '-rc', 'cqp', '-qp_i', '20', '-qp_p', '20'];
                        break;
                    case 'h264_qsv':
                        vCodec = quality === 'mobile' ?
                            ['-c:v', 'h264_qsv', '-preset', 'fast', '-global_quality', '25'] :
                            ['-c:v', 'h264_qsv', '-preset', 'medium', '-global_quality', '20'];
                        break;
                    case 'h264_videotoolbox':
                        vCodec = quality === 'mobile' ?
                            ['-c:v', 'h264_videotoolbox', '-q:v', '65'] :
                            ['-c:v', 'h264_videotoolbox', '-q:v', '55'];
                        break;
                    default:
                        // Fallback to software encoding
                        vCodec = quality === 'mobile' ?
                            ['-c:v', 'libx264', '-preset', 'fast', '-crf', '23'] :
                            ['-c:v', 'libx264', '-preset', 'medium', '-crf', '18'];
                }
            } else {
                // Software encoding (default)
                console.log('🔧 Using software encoding (CPU)');
                vCodec = quality === 'mobile' ?
                    ['-c:v', 'libx264', '-preset', 'fast', '-crf', '23'] :
                    ['-c:v', 'libx264', '-preset', 'medium', '-crf', '18'];
            }
            
            // Use the calculated duration for the export
            cmd.push('-t', durationSeconds.toString(), ...vCodec, '-c:a', 'aac', '-b:a', '128k', outputPath);
            
            console.log('🚀 FFmpeg command:', cmd.join(' '));

            // Send initial progress
            event.sender.send('tesla:export-progress', exportId, {
                type: 'progress',
                percentage: 10,
                message: 'Starting multi-camera video export...'
            });

            // Execute FFmpeg
            return new Promise((resolve, reject) => {
                const process = spawn(cmd[0], cmd.slice(1));
                let stderr = '';
                let startTime = Date.now();
                let lastProgressUpdate = 0;
                let lastProgressTime = 0;
                let ffmpegProgressStarted = false;
                
                // Fallback timer that only runs if FFmpeg doesn't provide progress
                const fallbackTimer = setInterval(() => {
                    if (!ffmpegProgressStarted) {
                        const elapsed = (Date.now() - startTime) / 1000;
                        const estimatedTotal = durationSeconds * 2; // Assume 2x real-time
                        const progress = Math.min(90, Math.floor((elapsed / estimatedTotal) * 100));
                        
                        if (progress > lastProgressUpdate) {
                            lastProgressUpdate = progress;
                            event.sender.send('tesla:export-progress', exportId, {
                                type: 'progress',
                                percentage: progress,
                                message: `Initializing... (${progress}%)`
                            });
                        }
                    }
                }, 2000); // Update every 2 seconds
                
                process.stderr.on('data', (data) => {
                    const dataStr = data.toString();
                    stderr += dataStr;
                    
                    // Debug: Log all FFmpeg output to see what we're getting
                    console.log(`[FFmpeg stderr]: ${dataStr.trim()}`);
                    
                    // Parse FFmpeg time output like PyQt6 version
                    const timeMatch = dataStr.match(/time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})/);
                    if (timeMatch && durationSeconds > 0) {
                        const hours = parseInt(timeMatch[1]);
                        const minutes = parseInt(timeMatch[2]);
                        const seconds = parseInt(timeMatch[3]);
                        const centiseconds = parseInt(timeMatch[4]);
                        
                        const currentProgressSeconds = (hours * 3600) + (minutes * 60) + seconds + (centiseconds / 100);
                        const percentage = Math.max(0, Math.min(90, Math.floor((currentProgressSeconds / durationSeconds) * 100)));
                        
                        console.log(`[Progress] Time: ${hours}:${minutes}:${seconds}.${centiseconds}, Progress: ${percentage}%`);
                        
                        // Only update if progress has increased
                        if (percentage > lastProgressUpdate) {
                            lastProgressUpdate = percentage;
                            ffmpegProgressStarted = true;
                            
                            event.sender.send('tesla:export-progress', exportId, {
                                type: 'progress',
                                percentage: percentage,
                                message: `Exporting... (${percentage}%)`
                            });
                        }
                    }
                });

                // Add timeout to prevent hanging
                const timeout = setTimeout(() => {
                    console.log('⚠️ Export timeout - killing process');
                    process.kill('SIGTERM');
                    clearInterval(fallbackTimer);
                    event.sender.send('tesla:export-progress', exportId, {
                        type: 'complete',
                        success: false,
                        message: 'Export timed out after 5 minutes'
                    });
                    reject(new Error('Export timed out'));
                }, 5 * 60 * 1000); // 5 minute timeout
                
                process.on('close', (code) => {
                    // Clear the timeout and fallback timer
                    clearTimeout(timeout);
                    clearInterval(fallbackTimer);
                    
                    if (code === 0) {
                        // Get final file size and show comparison
                        try {
                            const stats = fs.statSync(outputPath);
                            const fileSizeMB = (stats.size / (1024 * 1024)).toFixed(1);
                            
                            // Calculate estimated size for comparison
                            const durationMinutes = durationSeconds / 60;
                            const numCameras = inputs.length;
                            
                            let estimatedSize;
                            if (quality === 'full') {
                                estimatedSize = Math.round(durationMinutes * (numCameras <= 2 ? 80 : numCameras <= 4 ? 120 : 180));
                            } else {
                                estimatedSize = Math.round(durationMinutes * (numCameras <= 2 ? 25 : numCameras <= 4 ? 40 : 60));
                            }
                            
                            const sizeDifference = Math.abs(parseFloat(fileSizeMB) - estimatedSize);
                            const accuracy = sizeDifference < 10 ? 'accurate' : sizeDifference < 30 ? 'close' : 'off';
                            
                            let message = `Export completed! File size: ${fileSizeMB} MB (${numCameras} cameras)`;
                            if (accuracy !== 'accurate') {
                                message += ` (estimated: ~${estimatedSize} MB)`;
                            }
                            
                            event.sender.send('tesla:export-progress', exportId, {
                                type: 'complete',
                                success: true,
                                message: message,
                                outputPath: outputPath
                            });
                        } catch (error) {
                            event.sender.send('tesla:export-progress', exportId, {
                                type: 'complete',
                                success: true,
                                message: `Export completed successfully! (${inputs.length} cameras)`,
                                outputPath: outputPath
                            });
                        }
                        // Clean up temporary concat files on success
                        tempFiles.forEach(tempFile => {
                            try {
                                fs.unlinkSync(tempFile);
                                console.log(`🗑️ Cleaned up temp file: ${tempFile}`);
                            } catch (error) {
                                console.warn(`⚠️ Failed to clean up temp file ${tempFile}:`, error.message);
                            }
                        });
                        resolve(true);
                    } else {
                        const error = `FFmpeg failed with code ${code}: ${stderr}`;
                        console.error(error);
                        event.sender.send('tesla:export-progress', exportId, {
                            type: 'complete',
                            success: false,
                            message: `Export failed: ${error}`
                        });
                        // Clean up temporary concat files on failure
                        tempFiles.forEach(tempFile => {
                            try {
                                fs.unlinkSync(tempFile);
                                console.log(`🗑️ Cleaned up temp file: ${tempFile}`);
                            } catch (error) {
                                console.warn(`⚠️ Failed to clean up temp file ${tempFile}:`, error.message);
                            }
                        });
                        reject(new Error(error));
                    }
                });

                process.on('error', (error) => {
                    // Clear the timeout and fallback timer
                    clearTimeout(timeout);
                    clearInterval(fallbackTimer);

                    const errorMsg = `Failed to start FFmpeg: ${error.message}`;
                    console.error(errorMsg);
                    event.sender.send('tesla:export-progress', exportId, {
                        type: 'complete',
                        success: false,
                        message: errorMsg
                    });
                    // Clean up temporary concat files on error
                    tempFiles.forEach(tempFile => {
                        try {
                            fs.unlinkSync(tempFile);
                            console.log(`🗑️ Cleaned up temp file: ${tempFile}`);
                        } catch (error) {
                            console.warn(`⚠️ Failed to clean up temp file ${tempFile}:`, error.message);
                        }
                    });
                    reject(new Error(errorMsg));
                });
            });

        } catch (error) {
            console.error('💥 Export process failed:', error);
            event.sender.send('tesla:export-progress', exportId, {
                type: 'complete',
                success: false,
                message: `Export failed: ${error.message}`
            });
            throw error;
        }
    }

    createApplicationMenu() {
        const template = [
            {
                label: 'File',
                submenu: [
                    {
                        label: 'Open Tesla Folder...',
                        accelerator: 'CmdOrCtrl+O',
                        click: async () => {
                            const result = await dialog.showOpenDialog(this.mainWindow, {
                                properties: ['openDirectory'],
                                title: 'Select Tesla Dashcam Folder'
                            });

                            if (!result.canceled && result.filePaths.length > 0) {
                                this.mainWindow.webContents.send('folder-selected', result.filePaths[0]);
                            }
                        }
                    },
                    { type: 'separator' },
                    {
                        label: 'Exit',
                        accelerator: process.platform === 'darwin' ? 'Cmd+Q' : 'Ctrl+Q',
                        click: () => {
                            app.quit();
                        }
                    }
                ]
            },
            {
                label: 'View',
                submenu: [
                    { role: 'reload' },
                    { role: 'forceReload' },
                    { role: 'toggleDevTools' },
                    { type: 'separator' },
                    { role: 'resetZoom' },
                    { role: 'zoomIn' },
                    { role: 'zoomOut' },
                    { type: 'separator' },
                    { role: 'togglefullscreen' }
                ]
            },
            {
                label: 'Help',
                submenu: [
                    {
                        label: 'About Sentry-Six',
                        click: () => {
                            dialog.showMessageBox(this.mainWindow, {
                                type: 'info',
                                title: 'About Sentry-Six',
                                message: 'Sentry-Six - Tesla Dashcam Viewer',
                                detail: `Version: ${app.getVersion()}\nElectron Edition - No more freezing!`
                            });
                        }
                    }
                ]
            }
        ];

        const menu = Menu.buildFromTemplate(template);
        Menu.setApplicationMenu(menu);
    }

    // Tesla file scanning functionality
    async scanTeslaFolder(folderPath) {
        console.log('Scanning Tesla folder:', folderPath);
        const allVideoFiles = [];

        try {
            // Check if this is a direct SavedClips/RecentClips/SentryClips folder
            const isDirectClipFolder = ['SavedClips', 'RecentClips', 'SentryClips'].some(folder =>
                folderPath.toLowerCase().includes(folder.toLowerCase())
            );

            if (isDirectClipFolder) {
                // Scan the selected folder directly
                const files = await this.scanVideoFiles(folderPath, path.basename(folderPath));
                allVideoFiles.push(...files);
            } else {
                // Scan for Tesla subfolders
                const subFolders = ['SavedClips', 'RecentClips', 'SentryClips'];

                for (const subFolder of subFolders) {
                    const subFolderPath = path.join(folderPath, subFolder);
                    if (fs.existsSync(subFolderPath)) {
                        console.log(`Scanning ${subFolder}...`);
                        const files = await this.scanVideoFiles(subFolderPath, subFolder);
                        allVideoFiles.push(...files);
                    }
                }
            }

            // Group files by date and folder type
            const groupedByDateAndType = this.groupVideosByDateAndType(allVideoFiles);
            console.log(`Organized into ${Object.keys(groupedByDateAndType).length} sections`);

            return groupedByDateAndType;

        } catch (error) {
            console.error('Error scanning Tesla folder:', error);
            return {};
        }
    }

    async scanVideoFiles(folderPath, folderType) {
        const videoFiles = [];

        try {
            if (folderType.toLowerCase() === 'recentclips') {
                // RecentClips can have either direct MP4 files OR date subfolders
                const items = fs.readdirSync(folderPath);

                // Check if RecentClips has date subfolders (YYYY-MM-DD pattern)
                const hasDateSubfolders = items.some(item => {
                    const itemPath = path.join(folderPath, item);
                    const stats = fs.statSync(itemPath);
                    return stats.isDirectory() && /^\d{4}-\d{2}-\d{2}$/.test(item);
                });

                if (hasDateSubfolders) {
                    console.log('RecentClips with date subfolders detected');
                    // Handle RecentClips with date subfolders (like SavedClips/SentryClips)
                    for (const item of items) {
                        const itemPath = path.join(folderPath, item);
                        const stats = fs.statSync(itemPath);

                        if (stats.isDirectory() && /^\d{4}-\d{2}-\d{2}$/.test(item)) {
                            console.log(`Scanning RecentClips date folder: ${item}`);
                            // Scan date subfolder
                            const subFiles = fs.readdirSync(itemPath);

                            for (const filename of subFiles) {
                                if (filename.toLowerCase().endsWith('.mp4') && !this.shouldSkipFile(filename)) {
                                    const filePath = path.join(itemPath, filename);
                                    const videoFile = this.parseTeslaFilename(filePath, filename, folderType);

                                    if (videoFile) {
                                        videoFiles.push(videoFile);
                                    }
                                }
                            }
                        }
                    }
                } else {
                    console.log('RecentClips with direct files detected');
                    // Handle RecentClips with direct MP4 files (original behavior)
                    for (const filename of items) {
                        if (filename.toLowerCase().endsWith('.mp4') && !this.shouldSkipFile(filename)) {
                            const filePath = path.join(folderPath, filename);
                            const videoFile = this.parseTeslaFilename(filePath, filename, folderType);

                            if (videoFile) {
                                videoFiles.push(videoFile);
                            }
                        }
                    }
                }
            } else {
                // SavedClips and SentryClips have date subfolders
                const items = fs.readdirSync(folderPath);

                for (const item of items) {
                    const itemPath = path.join(folderPath, item);
                    const stats = fs.statSync(itemPath);

                    if (stats.isDirectory()) {
                        // Scan date subfolder
                        const subFiles = fs.readdirSync(itemPath);

                        for (const filename of subFiles) {
                            if (filename.toLowerCase().endsWith('.mp4') && !this.shouldSkipFile(filename)) {
                                const filePath = path.join(itemPath, filename);
                                const videoFile = this.parseTeslaFilename(filePath, filename, folderType);

                                if (videoFile) {
                                    videoFiles.push(videoFile);
                                }
                            }
                        }
                    } else if (item.toLowerCase().endsWith('.mp4') && !this.shouldSkipFile(item)) {
                        // Direct MP4 file in main folder
                        const videoFile = this.parseTeslaFilename(itemPath, item, folderType);

                        if (videoFile) {
                            videoFiles.push(videoFile);
                        }
                    }
                }
            }

        } catch (error) {
            console.error(`Error scanning ${folderPath}:`, error);
        }

        return videoFiles;
    }

    shouldSkipFile(filename) {
        const skipPatterns = [
            'event.mp4',           // Tesla's compiled event video
            'temp_scaled.mp4',     // Temporary scaled video
            '._',                  // macOS metadata files
            '.DS_Store'            // macOS system files
        ];

        const lowerFilename = filename.toLowerCase();
        return skipPatterns.some(pattern =>
            lowerFilename === pattern || lowerFilename.startsWith(pattern)
        );
    }

    parseTeslaFilename(filePath, filename, folderType) {
        // Parse Tesla filename format: YYYY-MM-DD_HH-MM-SS-camera.mp4
        const match = filename.match(/^(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})-(.+)\.mp4$/);

        if (!match) {
            console.warn(`Invalid Tesla filename format: ${filename}`);
            return null;
        }

        const [, datePart, timePart, cameraPart] = match;

        // Parse timestamp
        const timestamp = this.parseTimestamp(datePart, timePart);
        if (!timestamp) {
            console.warn(`Could not parse timestamp from: ${filename}`);
            return null;
        }

        // Parse camera type
        const camera = this.parseCamera(cameraPart);
        if (!camera) {
            console.warn(`Unknown camera type: ${cameraPart}`);
            return null;
        }

        const stats = fs.statSync(filePath);

        // Mark file as potentially corrupted but don't skip yet
        // We'll do group-based filtering later
        const isCorrupted = this.isClipCorrupted(stats.size, filename);
        if (isCorrupted) {
            console.log(`🔍 Potentially corrupted: ${filename} (${Math.round(stats.size/1024)}KB)`);
        }

        return {
            path: filePath,
            filename,
            camera,
            timestamp,
            size: stats.size,
            type: folderType,
            isCorrupted: isCorrupted // Mark corruption status
        };
    }

    parseTimestamp(datePart, timePart) {
        try {
            // Parse as local time to avoid timezone offset issues
            // Split the date and time parts
            const [year, month, day] = datePart.split('-').map(Number);
            const [hour, minute, second] = timePart.split('-').map(Number);

            // Create Date object in local timezone (not UTC)
            const timestamp = new Date(year, month - 1, day, hour, minute, second);

            return isNaN(timestamp.getTime()) ? null : timestamp;
        } catch (error) {
            console.error('Error parsing timestamp:', error);
            return null;
        }
    }

    parseCamera(cameraPart) {
        const cameraMap = {
            'front': 'front',
            'left_repeater': 'left_repeater',
            'right_repeater': 'right_repeater',
            'left_pillar': 'left_pillar',      // Keep pillar cameras separate
            'right_pillar': 'right_pillar',    // Keep pillar cameras separate
            'back': 'back'
        };

        return cameraMap[cameraPart] || null;
    }

    isClipCorrupted(fileSize, filename) {
        // Tesla clips are typically 40-80MB for 60-second recordings
        // Corrupted clips are usually under 5MB
        const MIN_VALID_SIZE = 5 * 1024 * 1024; // 5MB threshold

        if (fileSize < MIN_VALID_SIZE) {
            // Additional check: very small files (under 2MB) are almost certainly corrupted
            const VERY_SMALL_SIZE = 2 * 1024 * 1024; // 2MB
            if (fileSize < VERY_SMALL_SIZE) {
                return true; // Definitely corrupted
            }

            // For files between 2-5MB, be more lenient for legitimate short clips
            // But still flag extremely small ones
            const TINY_SIZE = 1.5 * 1024 * 1024; // 1.5MB
            if (fileSize < TINY_SIZE) {
                return true; // Likely corrupted
            }

            // Log suspicious files for user awareness
            console.log(`🔍 Suspicious small file: ${filename} (${Math.round(fileSize/1024)}KB) - including but monitoring`);
        }

        return false; // File appears valid
    }

    filterCorruptedTimestampGroups(clips) {
        const validClips = [];
        let totalClipsScanned = 0;
        let corruptedGroupsRemoved = 0;

        for (const clip of clips) {
            totalClipsScanned++;

            // Count corrupted vs valid cameras for this timestamp
            let corruptedCameras = 0;
            let totalCameras = 0;

            for (const [camera, file] of Object.entries(clip.files)) {
                totalCameras++;
                if (file.isCorrupted) {
                    corruptedCameras++;
                }
            }

            // Apply majority rule: if more than half the cameras are corrupted, skip entire group
            const corruptionRatio = corruptedCameras / totalCameras;
            if (corruptionRatio > 0.5) { // More than 50% corrupted
                console.warn(`⚠️ Skipping timestamp group ${clip.timestamp.toISOString()}: ${corruptedCameras}/${totalCameras} cameras corrupted`);
                corruptedGroupsRemoved++;
            } else {
                // Keep the group, but remove corrupted individual files
                const cleanClip = {
                    ...clip,
                    files: {}
                };

                for (const [camera, file] of Object.entries(clip.files)) {
                    if (!file.isCorrupted) {
                        cleanClip.files[camera] = file;
                    }
                }

                validClips.push(cleanClip);

                if (corruptedCameras > 0) {
                    console.log(`🔧 Cleaned timestamp group ${clip.timestamp.toISOString()}: removed ${corruptedCameras} corrupted cameras, kept ${totalCameras - corruptedCameras}`);
                }
            }
        }

        if (corruptedGroupsRemoved > 0) {
            console.log(`📊 Corruption filtering: ${corruptedGroupsRemoved}/${totalClipsScanned} timestamp groups removed due to majority corruption`);
        }

        return validClips;
    }

    groupVideosByDateAndType(videoFiles) {
        const sections = {
            'User Saved': [],
            'Sentry Detection': [],
            'Recent Clips': []
        };

        // Group files by date and type
        const dateGroups = new Map();

        for (const file of videoFiles) {
            // Create date key using local time (not UTC)
            const year = file.timestamp.getFullYear();
            const month = String(file.timestamp.getMonth() + 1).padStart(2, '0');
            const day = String(file.timestamp.getDate()).padStart(2, '0');
            const dateKey = `${year}-${month}-${day}`; // YYYY-MM-DD in local time
            const sectionKey = this.getSectionKey(file.type);

            if (!dateGroups.has(sectionKey)) {
                dateGroups.set(sectionKey, new Map());
            }

            const sectionMap = dateGroups.get(sectionKey);
            if (!sectionMap.has(dateKey)) {
                sectionMap.set(dateKey, new Map());
            }

            const dayMap = sectionMap.get(dateKey);
            // Create timestamp key using local time (not UTC)
            const timestampKey = file.timestamp.getTime().toString(); // Use milliseconds as key

            if (!dayMap.has(timestampKey)) {
                dayMap.set(timestampKey, {
                    timestamp: file.timestamp,
                    files: {},
                    type: file.type,
                    date: dateKey
                });
            }

            const group = dayMap.get(timestampKey);
            group.files[file.camera] = file;
        }

        // Convert to organized structure
        for (const [sectionKey, sectionMap] of dateGroups) {
            for (const [dateKey, dayMap] of sectionMap) {
                const allClips = Array.from(dayMap.values()).sort((a, b) =>
                    a.timestamp.getTime() - b.timestamp.getTime()
                );

                // Filter out timestamp groups where majority of cameras are corrupted
                const clips = this.filterCorruptedTimestampGroups(allClips);

                // Parse date key as local time (not UTC)
                const [year, month, day] = dateKey.split('-').map(Number);
                const dateObj = new Date(year, month - 1, day); // Local time
                const displayDate = dateObj.toLocaleDateString('en-US', {
                    month: '2-digit',
                    day: '2-digit',
                    year: '2-digit'
                });

                // Calculate actual total duration from filtered clips if possible
                let actualTotalDuration = null;
                let hasAllDurations = true;
                let totalDurationMs = 0;

                for (const clip of clips) {
                    // Check if we have actual durations for all cameras in this clip
                    let clipDuration = 0;
                    let cameraCount = 0;

                    for (const [camera, file] of Object.entries(clip.files)) {
                        cameraCount++;
                        // For now, we don't have actual durations during initial scan
                        // This will be calculated when the timeline is loaded
                        hasAllDurations = false;
                        break;
                    }

                    if (!hasAllDurations) break;
                }

                sections[sectionKey].push({
                    date: dateKey,
                    displayDate: displayDate,
                    clips: clips,
                    totalClips: clips.length,
                    originalClipCount: allClips.length,
                    filteredClipCount: clips.length,
                    actualTotalDuration: actualTotalDuration
                });
            }
        }

        // Sort dates within each section (newest first)
        for (const sectionKey in sections) {
            sections[sectionKey].sort((a, b) => new Date(b.date) - new Date(a.date));
        }

        return sections;
    }

    getSectionKey(folderType) {
        switch (folderType.toLowerCase()) {
            case 'savedclips':
                return 'User Saved';
            case 'sentryclips':
                return 'Sentry Detection';
            case 'recentclips':
                return 'Recent Clips';
            default:
                return 'User Saved';
        }
    }

    groupVideosByTimestamp(videoFiles) {
        const groups = new Map();

        for (const file of videoFiles) {
            // Use timestamp as key for grouping
            const groupKey = file.timestamp.toISOString();

            if (!groups.has(groupKey)) {
                groups.set(groupKey, {
                    timestamp: file.timestamp,
                    files: {},
                    type: file.type
                });
            }

            const group = groups.get(groupKey);
            group.files[file.camera] = file;
        }

        // Convert to array and sort by timestamp
        return Array.from(groups.values()).sort((a, b) =>
            a.timestamp.getTime() - b.timestamp.getTime()
        );
    }

    // Tesla event scanning functionality
    async scanTeslaEvents(folderPath) {
        console.log('Scanning Tesla events in:', folderPath);
        const events = [];

        try {
            const teslaFolders = ['SavedClips', 'SentryClips']; // Skip RecentClips as per requirements

            for (const folderType of teslaFolders) {
                const subFolderPath = path.join(folderPath, folderType);

                if (fs.existsSync(subFolderPath)) {
                    const clipEvents = await this.scanClipFoldersForEvents(subFolderPath, folderType);
                    events.push(...clipEvents);
                }
            }

            console.log(`Found ${events.length} events`);
            return events.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        } catch (error) {
            console.error('Error scanning Tesla events:', error);
            return [];
        }
    }

    async scanClipFoldersForEvents(subFolderPath, folderType) {
        const events = [];

        try {
            const entries = fs.readdirSync(subFolderPath, { withFileTypes: true });

            for (const entry of entries) {
                if (entry.isDirectory()) {
                    const clipFolderPath = path.join(subFolderPath, entry.name);
                    const eventJsonPath = path.join(clipFolderPath, 'event.json');

                    if (fs.existsSync(eventJsonPath)) {
                        try {
                            const eventData = JSON.parse(fs.readFileSync(eventJsonPath, 'utf8'));

                            if (eventData.timestamp && eventData.reason) {
                                const thumbnailPath = path.join(clipFolderPath, 'thumb.png');
                                const hasThumbnail = fs.existsSync(thumbnailPath);

                                events.push({
                                    timestamp: eventData.timestamp,
                                    reason: eventData.reason,
                                    city: eventData.city,
                                    est_lat: eventData.est_lat,
                                    est_lon: eventData.est_lon,
                                    camera: eventData.camera,
                                    folderPath: clipFolderPath,
                                    thumbnailPath: hasThumbnail ? thumbnailPath : null,
                                    timestampDate: new Date(eventData.timestamp),
                                    type: folderType
                                });
                            }
                        } catch (parseError) {
                            console.warn(`Error parsing event.json in ${clipFolderPath}:`, parseError);
                        }
                    }
                }
            }
        } catch (error) {
            console.error(`Error scanning clip folders in ${subFolderPath}:`, error);
        }

        return events;
    }

    // Find clips that overlap with the export range
    findClipsForExportRange(timeline, startTime, endTime) {
        const timelineStartTime = timeline.startTime.getTime();
        const exportClips = [];
        let currentPosition = 0;

        for (let i = 0; i < timeline.clips.length; i++) {
            const clip = timeline.clips[i];
            if (!clip || !clip.timestamp) continue;

            // Use actual duration from timeline if available, otherwise estimate
            let clipDuration = 60000; // Default 60 seconds
            if (timeline.actualDurations && timeline.actualDurations[i]) {
                clipDuration = timeline.actualDurations[i];
            }

            const clipRelativeStart = currentPosition;
            const clipRelativeEnd = currentPosition + clipDuration;

            // Check if clip overlaps with export range
            const clipOverlaps = (clipRelativeStart < endTime) && (clipRelativeEnd > startTime);

            if (clipOverlaps) {
                console.log(`📹 Clip ${i} (${clip.timestamp}) overlaps with export range (${clipRelativeStart}-${clipRelativeEnd}ms)`);
                exportClips.push({
                    ...clip,
                    clipIndex: i,
                    clipRelativeStart: clipRelativeStart,
                    clipDuration: clipDuration
                });
            }

            currentPosition += clipDuration;
        }

        return exportClips;
    }
}

// Initialize the application
console.log('Starting Sentry-Six Electron application...');
new SentrySixApp();
