// Working Sentry-Six Electron Main Process
// Simplified JavaScript version to get the app running

const path = require('path');
const fs = require('fs');

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

        // Simple file system check
        ipcMain.handle('fs:exists', async (_, filePath) => {
            return fs.existsSync(filePath);
        });

        // Get app version
        ipcMain.handle('app:get-version', async () => {
            return app.getVersion();
        });

        console.log('IPC handlers set up successfully');
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
                // RecentClips has direct MP4 files, no date subfolders
                const files = fs.readdirSync(folderPath);

                for (const filename of files) {
                    if (filename.toLowerCase().endsWith('.mp4') && !this.shouldSkipFile(filename)) {
                        const filePath = path.join(folderPath, filename);
                        const videoFile = this.parseTeslaFilename(filePath, filename, folderType);

                        if (videoFile) {
                            videoFiles.push(videoFile);
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
}

// Initialize the application
console.log('Starting Sentry-Six Electron application...');
new SentrySixApp();
