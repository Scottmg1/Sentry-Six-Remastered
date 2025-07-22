import { spawn, ChildProcess } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

// Types for our export system
export interface ExportTimeline {
    startTime: string;
    displayDuration: number;
    clips: Array<{
        timestamp: string;
        files: Record<string, string>;
    }>;
}

export interface ExportData {
    timeline: ExportTimeline;
    startTime: number;
    endTime: number;
    quality: 'full' | 'mobile';
    cameras: string[];
    timestamp: {
        enabled: boolean;
        position: string;
    };
    outputPath: string;
}

export interface ExportProgress {
    type: 'progress' | 'complete';
    percentage?: number;
    currentTime?: number;
    totalTime?: number;
    message: string;
    success?: boolean;
    outputPath?: string;
    error?: string;
    errorCode?: number;
}

interface ActiveExport {
    process: ChildProcess;
    startTime: number;
    duration: number;
}

export class FFmpegHandler {
    private ffmpegPath: string;
    private activeExports: Map<string, ActiveExport>;
    private tempFiles: Set<string>;

    constructor() {
        this.ffmpegPath = this.findFFmpegPath();
        this.activeExports = new Map();
        this.tempFiles = new Set();
    }

    private findFFmpegPath(): string {
        // Try common FFMPEG locations
        const possiblePaths = [
            'ffmpeg', // System PATH
            path.join(__dirname, '..', '..', 'ffmpeg_bin', 'ffmpeg.exe'), // Bundled Windows
            path.join(__dirname, '..', '..', 'ffmpeg_bin', 'ffmpeg'), // Bundled Unix
            '/usr/local/bin/ffmpeg', // Homebrew macOS
            '/usr/bin/ffmpeg' // Linux
        ];

        for (const ffmpegPath of possiblePaths) {
            try {
                // Test if FFMPEG is available
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

        throw new Error('FFMPEG not found. Please install FFMPEG or place it in the ffmpeg_bin directory.');
    }

    /**
     * Calculate real timestamp for export based on timeline position
     * Reuses the existing timestamp logic from renderer
     */
    private calculateExportTimestamp(timeline: ExportTimeline, positionMs: number): Date {
        const startTime = new Date(timeline.startTime);
        const exportTime = new Date(startTime.getTime() + positionMs);
        return exportTime;
    }

    /**
     * Generate FFMPEG timestamp overlay filter
     * Adapts PyQt6 implementation to use our existing timestamp format
     */
    private createTimestampFilter(timeline: ExportTimeline, startPositionMs: number, timestampPosition: string = 'bottom-center'): string {
        const exportStartTime = this.calculateExportTimestamp(timeline, startPositionMs);
        const basetimeUs = Math.floor(exportStartTime.getTime() * 1000); // Convert to microseconds

        // Position mapping
        const positions: Record<string, string> = {
            'bottom-center': 'x=(w-text_w)/2:y=h-th-10',
            'bottom-left': 'x=10:y=h-th-10',
            'bottom-right': 'x=w-text_w-10:y=h-th-10',
            'top-center': 'x=(w-text_w)/2:y=10',
            'top-left': 'x=10:y=10',
            'top-right': 'x=w-text_w-10:y=10'
        };

        const position = positions[timestampPosition] || positions['bottom-center'];

        // Use the same format as our UI: MM/DD/YYYY HH:MM:SS AM/PM
        return [
            'drawtext=font=Arial',
            'expansion=strftime',
            `basetime=${basetimeUs}`,
            "text='%m/%d/%Y %I\\:%M\\:%S %p'",
            'fontcolor=white',
            'fontsize=36',
            'box=1',
            'boxcolor=black@0.4',
            'boxborderw=5',
            position
        ].join(':');
    }

    /**
     * Create temporary concat file for FFMPEG
     */
    private createConcatFile(clipPaths: string[]): string {
        const tempFile = path.join(os.tmpdir(), `sentry_six_concat_${Date.now()}.txt`);
        const content = clipPaths.map(clipPath => `file '${path.resolve(clipPath)}'`).join('\n');
        
        fs.writeFileSync(tempFile, content, 'utf8');
        this.tempFiles.add(tempFile);
        
        console.log(`📝 Created concat file: ${tempFile} with ${clipPaths.length} clips`);
        return tempFile;
    }

    /**
     * Build FFMPEG command for Tesla dashcam export
     * Adapts PyQt6 FFmpegCommandBuilder logic
     */
    private buildExportCommand(exportData: ExportData): { command: string[], duration: number } {
        const { timeline, startTime, endTime, quality, cameras, timestamp, outputPath } = exportData;
        
        // Calculate duration and offset
        const durationMs = endTime - startTime;
        const durationSeconds = durationMs / 1000;
        const offsetSeconds = startTime / 1000;

        console.log(`🎬 Building export command: ${durationSeconds}s duration, ${offsetSeconds}s offset`);

        // Standard Tesla camera resolution (from PyQt6 analysis)
        const cameraWidth = 1448;
        const cameraHeight = 938;

        const cmd = [this.ffmpegPath, '-y']; // -y to overwrite output
        const inputStreams: string[] = [];
        const filterChains: string[] = [];

        // Create input streams for each selected camera
        cameras.forEach((camera, index) => {
            // Find clips for this camera in the timeline
            const cameraClips = timeline.clips
                .filter(clip => clip.files && clip.files[camera])
                .map(clip => clip.files[camera])
                .filter((clipPath): clipPath is string => clipPath !== undefined);

            if (cameraClips.length === 0) {
                console.warn(`⚠️ No clips found for camera: ${camera}`);
                return;
            }

            // Create concat file for this camera
            const concatFile = this.createConcatFile(cameraClips);
            
            // Add input stream
            cmd.push('-f', 'concat', '-safe', '0', '-ss', offsetSeconds.toString(), '-i', concatFile);
            
            // Create scaling filter for this stream
            filterChains.push(`[${index}:v]setpts=PTS-STARTPTS,scale=${cameraWidth}:${cameraHeight}[v${index}]`);
            inputStreams.push(`[v${index}]`);
        });

        if (inputStreams.length === 0) {
            throw new Error('No valid camera streams found for export');
        }

        // Build grid layout
        const numCameras = inputStreams.length;
        const cols = numCameras === 2 || numCameras === 4 ? 2 : numCameras > 2 ? 3 : 1;
        const rows = Math.ceil(numCameras / cols);

        let layoutFilter = '';
        let lastOutputTag = '';

        if (numCameras > 1) {
            // Create xstack layout
            const layout: string[] = [];
            for (let i = 0; i < numCameras; i++) {
                const row = Math.floor(i / cols);
                const col = i % cols;
                layout.push(`${col * cameraWidth}_${row * cameraHeight}`);
            }
            
            layoutFilter = `${inputStreams.join('')}xstack=inputs=${numCameras}:layout=${layout.join('|')}[stacked]`;
            lastOutputTag = '[stacked]';
        } else {
            lastOutputTag = '[v0]';
        }

        // Add layout filter to chain
        if (layoutFilter) {
            filterChains.push(layoutFilter);
        }

        // Add timestamp overlay if enabled
        if (timestamp.enabled) {
            const timestampFilter = this.createTimestampFilter(timeline, startTime, timestamp.position);
            filterChains.push(`${lastOutputTag}${timestampFilter}[timestamped]`);
            lastOutputTag = '[timestamped]';
        }

        // Mobile scaling if requested
        if (quality === 'mobile') {
            const totalWidth = cameraWidth * cols;
            const totalHeight = cameraHeight * rows;
            const mobileWidth = Math.floor(1080 * (totalWidth / totalHeight) / 2) * 2; // Ensure even width
            filterChains.push(`${lastOutputTag}scale=${mobileWidth}:1080[final]`);
            lastOutputTag = '[final]';
        } else {
            // Rename final output for consistency
            if (lastOutputTag !== '[final]') {
                filterChains.push(`${lastOutputTag}copy[final]`);
                lastOutputTag = '[final]';
            }
        }

        // Combine all filter chains
        const filterComplex = filterChains.join(';');
        cmd.push('-filter_complex', filterComplex);

        // Map final video stream
        cmd.push('-map', lastOutputTag);

        // Add audio from front camera if available
        const frontCameraIndex = cameras.indexOf('front');
        if (frontCameraIndex !== -1) {
            cmd.push('-map', `${frontCameraIndex}:a?`); // ? makes audio optional
        }

        // Video encoding settings
        const videoSettings = quality === 'mobile' 
            ? ['-c:v', 'libx264', '-preset', 'fast', '-crf', '23']
            : ['-c:v', 'libx264', '-preset', 'medium', '-crf', '18'];
        
        cmd.push(...videoSettings);

        // Audio encoding
        cmd.push('-c:a', 'aac', '-b:a', '128k');

        // Duration and output
        cmd.push('-t', durationSeconds.toString(), outputPath);

        console.log(`🔧 FFMPEG command built: ${cmd.length} arguments`);
        console.log(`📊 Export details: ${numCameras} cameras, ${cols}x${rows} grid, ${quality} quality`);

        return { command: cmd, duration: durationSeconds };
    }

    /**
     * Start video export process
     */
    async startExport(exportId: string, exportData: ExportData, progressCallback: (progress: ExportProgress) => void): Promise<boolean> {
        try {
            console.log(`🚀 Starting export ${exportId}`);
            
            const { command, duration } = this.buildExportCommand(exportData);
            
            // Create FFMPEG process
            const ffmpegCommand = command[0];
            if (!ffmpegCommand) {
                throw new Error('FFMPEG command is undefined');
            }

            const ffmpegProcess = spawn(ffmpegCommand, command.slice(1), {
                stdio: ['pipe', 'pipe', 'pipe'],
                windowsHide: true // Hide console window on Windows
            });

            // Store active export
            this.activeExports.set(exportId, {
                process: ffmpegProcess,
                startTime: Date.now(),
                duration: duration
            });

            // Progress tracking regex (from PyQt6 analysis)
            const timePattern = /time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})/;

            // Handle FFMPEG output for progress tracking
            ffmpegProcess.stderr.on('data', (data: Buffer) => {
                const output = data.toString();

                // Parse progress
                const match = timePattern.exec(output);
                if (match && duration > 0 && match.length >= 5) {
                    const hours = parseInt(match[1] || '0', 10);
                    const minutes = parseInt(match[2] || '0', 10);
                    const seconds = parseInt(match[3] || '0', 10);
                    const hundredths = parseInt(match[4] || '0', 10);

                    const currentProgressS = (hours * 3600) + (minutes * 60) + seconds + (hundredths / 100);
                    const percentage = Math.max(0, Math.min(100, Math.floor((currentProgressS / duration) * 100)));

                    progressCallback({
                        type: 'progress',
                        percentage,
                        currentTime: currentProgressS,
                        totalTime: duration,
                        message: `Exporting... ${percentage}%`
                    });
                }
            });

            // Handle process completion
            ffmpegProcess.on('close', (code: number | null) => {
                const exportInfo = this.activeExports.get(exportId);
                const exportDuration = exportInfo ? (Date.now() - exportInfo.startTime) / 1000 : 0;

                this.activeExports.delete(exportId);
                this.cleanupTempFiles();

                if (code === 0) {
                    console.log(`✅ Export ${exportId} completed successfully in ${exportDuration.toFixed(1)}s`);
                    progressCallback({
                        type: 'complete',
                        success: true,
                        message: `Export completed successfully! (${exportDuration.toFixed(1)}s)`,
                        outputPath: exportData.outputPath
                    });
                } else {
                    console.error(`❌ Export ${exportId} failed with code ${code}`);
                    progressCallback({
                        type: 'complete',
                        success: false,
                        message: `Export failed with error code ${code}`,
                        errorCode: code || -1
                    });
                }
            });

            // Handle process errors
            ffmpegProcess.on('error', (error: Error) => {
                console.error(`💥 Export ${exportId} process error:`, error);
                this.activeExports.delete(exportId);
                this.cleanupTempFiles();

                progressCallback({
                    type: 'complete',
                    success: false,
                    message: `Export failed: ${error.message}`,
                    error: error.message
                });
            });

            return true;

        } catch (error: any) {
            console.error(`💥 Failed to start export ${exportId}:`, error);
            this.cleanupTempFiles();
            
            progressCallback({
                type: 'complete',
                success: false,
                message: `Failed to start export: ${error.message}`,
                error: error.message
            });
            
            return false;
        }
    }

    /**
     * Cancel active export
     */
    cancelExport(exportId: string): boolean {
        const exportInfo = this.activeExports.get(exportId);
        if (exportInfo && exportInfo.process) {
            console.log(`🛑 Cancelling export ${exportId}`);
            exportInfo.process.kill('SIGTERM');
            this.activeExports.delete(exportId);
            this.cleanupTempFiles();
            return true;
        }
        return false;
    }

    /**
     * Clean up temporary files
     */
    private cleanupTempFiles(): void {
        for (const tempFile of this.tempFiles) {
            try {
                if (fs.existsSync(tempFile)) {
                    fs.unlinkSync(tempFile);
                    console.log(`🗑️ Cleaned up temp file: ${tempFile}`);
                }
            } catch (error: any) {
                console.warn(`⚠️ Failed to clean up temp file ${tempFile}:`, error.message);
            }
        }
        this.tempFiles.clear();
    }

    /**
     * Get export status
     */
    getExportStatus(exportId: string): boolean {
        return this.activeExports.has(exportId);
    }

    /**
     * Cleanup all exports and temp files
     */
    cleanup(): void {
        console.log('🧹 Cleaning up FFMPEG handler...');
        
        // Cancel all active exports
        for (const [exportId] of this.activeExports) {
            this.cancelExport(exportId);
        }
        
        // Clean up temp files
        this.cleanupTempFiles();
    }
}
