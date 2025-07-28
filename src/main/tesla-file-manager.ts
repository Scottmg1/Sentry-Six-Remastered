/**
 * Tesla File Manager
 * Handles Tesla dashcam file discovery, organization, and metadata extraction
 * Ported from Python implementation with enhanced TypeScript features
 */

import * as fs from 'fs';
import * as path from 'path';
import { VideoProcessor } from './video-processor';

export interface TeslaVideoFile {
    path: string;
    filename: string;
    camera: 'front' | 'left_repeater' | 'right_repeater' | 'back';
    timestamp: Date;
    duration: number;
    size: number;
    type: 'SavedClips' | 'RecentClips' | 'SentryClips';
}

export interface TeslaEventData {
    timestamp: string;
    city?: string;
    est_lat?: string;
    est_lon?: string;
    reason: string;
    camera?: string;
    folderPath: string;
    thumbnailPath?: string;
    timestampDate: Date;
}

export interface TeslaClipGroup {
    timestamp: Date;
    files: {
        front?: TeslaVideoFile;
        left_repeater?: TeslaVideoFile;
        right_repeater?: TeslaVideoFile;
        back?: TeslaVideoFile;
    };
    type: 'SavedClips' | 'RecentClips' | 'SentryClips';
    duration: number;
    event?: TeslaEventData;
}

export class TeslaFileManager {
    private readonly TESLA_CAMERAS = ['front', 'left_repeater', 'right_repeater', 'back'] as const;
    private readonly TESLA_FOLDERS = ['SavedClips', 'RecentClips', 'SentryClips'] as const;
    private readonly VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi'] as const;
    private videoProcessor: VideoProcessor;

    constructor() {
        this.videoProcessor = new VideoProcessor();
    }

    /**
     * Scan a Tesla dashcam folder and organize files by timestamp
     */
    async scanFolder(folderPath: string): Promise<TeslaClipGroup[]> {
        console.log(`Scanning Tesla folder: ${folderPath}`);
        
        if (!fs.existsSync(folderPath)) {
            throw new Error(`Folder does not exist: ${folderPath}`);
        }

        const allFiles: TeslaVideoFile[] = [];

        // Scan each Tesla folder type
        for (const folderType of this.TESLA_FOLDERS) {
            const subFolderPath = path.join(folderPath, folderType);
            
            if (fs.existsSync(subFolderPath)) {
                const files = await this.scanSubFolder(subFolderPath, folderType);
                allFiles.push(...files);
            }
        }

        // Group files by timestamp
        const clipGroups = this.groupFilesByTimestamp(allFiles);

        // Detect events for each clip group
        await this.detectEventsForClipGroups(clipGroups, folderPath);

        console.log(`Found ${clipGroups.length} clip groups with ${allFiles.length} total files`);
        return clipGroups;
    }

    /**
     * Get video files from a specific folder
     */
    async getVideoFiles(folderPath: string): Promise<TeslaVideoFile[]> {
        const files: TeslaVideoFile[] = [];
        
        if (!fs.existsSync(folderPath)) {
            return files;
        }

        const entries = fs.readdirSync(folderPath, { withFileTypes: true });
        
        for (const entry of entries) {
            if (entry.isFile() && this.isVideoFile(entry.name)) {
                const filePath = path.join(folderPath, entry.name);
                const videoFile = await this.parseVideoFile(filePath);
                
                if (videoFile) {
                    files.push(videoFile);
                }
            }
        }

        return files;
    }

    /**
     * Scan a subfolder (SavedClips, RecentClips, SentryClips)
     */
    private async scanSubFolder(subFolderPath: string, folderType: string): Promise<TeslaVideoFile[]> {
        const files: TeslaVideoFile[] = [];

        try {
            const entries = fs.readdirSync(subFolderPath, { withFileTypes: true });

            for (const entry of entries) {
                if (entry.isFile() && this.isVideoFile(entry.name)) {
                    const filePath = path.join(subFolderPath, entry.name);
                    const videoFile = await this.parseVideoFile(filePath, folderType as any);

                    if (videoFile) {
                        files.push(videoFile);
                    }
                } else if (entry.isDirectory()) {
                    // Scan clip subfolders for video files and events
                    const clipFolderPath = path.join(subFolderPath, entry.name);
                    const clipFiles = await this.scanClipFolder(clipFolderPath, folderType as any);
                    files.push(...clipFiles);
                }
            }
        } catch (error) {
            console.error(`Error scanning subfolder ${subFolderPath}:`, error);
        }

        return files;
    }

    /**
     * Scan a Tesla clip folder (e.g., 2025-07-21_16-30-30) for video files and events
     */
    private async scanClipFolder(clipFolderPath: string, folderType: 'SavedClips' | 'RecentClips' | 'SentryClips'): Promise<TeslaVideoFile[]> {
        const files: TeslaVideoFile[] = [];

        try {
            const entries = fs.readdirSync(clipFolderPath, { withFileTypes: true });

            for (const entry of entries) {
                if (entry.isFile() && this.isVideoFile(entry.name)) {
                    const filePath = path.join(clipFolderPath, entry.name);
                    const videoFile = await this.parseVideoFile(filePath, folderType);

                    if (videoFile) {
                        files.push(videoFile);
                    }
                }
            }
        } catch (error) {
            console.error(`Error scanning clip folder ${clipFolderPath}:`, error);
        }

        return files;
    }

    /**
     * Parse a Tesla video file and extract metadata
     */
    private async parseVideoFile(filePath: string, folderType?: 'SavedClips' | 'RecentClips' | 'SentryClips'): Promise<TeslaVideoFile | null> {
        try {
            const filename = path.basename(filePath);
            const stats = fs.statSync(filePath);
            
            // Parse Tesla filename format: YYYY-MM-DD_HH-MM-SS-camera.mp4
            const match = filename.match(/^(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})-(.+)\.mp4$/);
            
            if (!match) {
                console.warn(`Invalid Tesla filename format: ${filename}`);
                return null;
            }

            const [, datePart, timePart, cameraPart] = match;

            // Parse timestamp
            const timestamp = this.parseTimestamp(datePart!, timePart!);
            if (!timestamp) {
                console.warn(`Could not parse timestamp from: ${filename}`);
                return null;
            }

            // Parse camera type
            const camera = this.parseCamera(cameraPart!);
            if (!camera) {
                console.warn(`Unknown camera type: ${cameraPart}`);
                return null;
            }

            // Determine folder type if not provided
            if (!folderType) {
                const parentFolder = path.basename(path.dirname(filePath));
                folderType = this.TESLA_FOLDERS.includes(parentFolder as any)
                    ? (parentFolder as 'SavedClips' | 'RecentClips' | 'SentryClips')
                    : 'RecentClips';
            }

            // Extract video metadata to get accurate duration
            let duration = 0;
            try {
                const metadata = await this.videoProcessor.getVideoMetadata(filePath);
                if (metadata && metadata.duration > 0) {
                    duration = metadata.duration * 1000; // Convert to milliseconds
                    console.log(`📹 Extracted metadata for ${filename}: ${(duration/1000).toFixed(1)}s duration`);
                } else {
                    console.warn(`⚠️ Could not extract metadata for ${filename}, using default duration`);
                    duration = 60000; // 60 seconds default
                }
            } catch (error) {
                console.warn(`⚠️ Error extracting metadata for ${filename}:`, error);
                duration = 60000; // 60 seconds default
            }

            return {
                path: filePath,
                filename,
                camera,
                timestamp,
                duration,
                size: stats.size,
                type: folderType
            };

        } catch (error) {
            console.error(`Error parsing video file ${filePath}:`, error);
            return null;
        }
    }

    /**
     * Parse timestamp from Tesla filename components
     */
    private parseTimestamp(datePart: string, timePart: string): Date | null {
        try {
            // Convert YYYY-MM-DD_HH-MM-SS to Date
            const dateTimeString = `${datePart}T${timePart.replace(/-/g, ':')}`;
            const timestamp = new Date(dateTimeString);
            
            return isNaN(timestamp.getTime()) ? null : timestamp;
        } catch (error) {
            return null;
        }
    }

    /**
     * Parse camera type from filename
     */
    private parseCamera(cameraPart: string): TeslaVideoFile['camera'] | null {
        const cameraMap: Record<string, TeslaVideoFile['camera']> = {
            'front': 'front',
            'left_repeater': 'left_repeater',
            'right_repeater': 'right_repeater',
            'back': 'back'
        };

        return cameraMap[cameraPart] || null;
    }

    /**
     * Check if file is a video file
     */
    private isVideoFile(filename: string): boolean {
        const ext = path.extname(filename).toLowerCase();
        return this.VIDEO_EXTENSIONS.includes(ext as any);
    }

    /**
     * Group video files by timestamp to create clip groups
     */
    private groupFilesByTimestamp(files: TeslaVideoFile[]): TeslaClipGroup[] {
        const groups = new Map<string, TeslaClipGroup>();

        for (const file of files) {
            // Use timestamp as key (rounded to nearest minute for grouping)
            const groupKey = this.getGroupKey(file.timestamp);
            
            if (!groups.has(groupKey)) {
                groups.set(groupKey, {
                    timestamp: file.timestamp,
                    files: {},
                    type: file.type,
                    duration: 0
                });
            }

            const group = groups.get(groupKey)!;
            group.files[file.camera] = file;
            
            // Update group duration (use longest video)
            if (file.duration > group.duration) {
                group.duration = file.duration;
            }
        }

        const clipGroups = Array.from(groups.values()).sort((a, b) => 
            a.timestamp.getTime() - b.timestamp.getTime()
        );
        
        // Analyze clip timestamps and estimate durations
        this.analyzeClipGroupTimestamps(clipGroups);
        
        return clipGroups;
    }

    /**
     * Analyze clip group timestamps to detect gaps and validate durations
     */
    private analyzeClipGroupTimestamps(clipGroups: TeslaClipGroup[]): void {
        if (clipGroups.length === 0) return;

        console.log(`🔍 Analyzing ${clipGroups.length} clip groups with actual durations`);

        for (let i = 0; i < clipGroups.length; i++) {
            const currentGroup = clipGroups[i];
            if (!currentGroup) continue; // Skip if undefined (shouldn't happen but TypeScript safety)
            
            const currentTime = currentGroup.timestamp;
            const actualDuration = currentGroup.duration / 1000; // Convert from ms to seconds

            console.log(`📹 Clip group ${i + 1}: ${currentTime.toLocaleTimeString()} - ${actualDuration.toFixed(1)}s duration`);

            // Validate duration (should be between 1 and 60 seconds for Tesla clips)
            if (actualDuration < 1) {
                console.warn(`⚠️ Clip group ${i + 1} has very short duration (${actualDuration}s) - may be corrupted`);
            } else if (actualDuration > 60) {
                console.warn(`⚠️ Clip group ${i + 1} has unusually long duration (${actualDuration}s) - may be incorrectly parsed`);
            }

            // Check for gaps with next clip
            if (i < clipGroups.length - 1) {
                const nextGroup = clipGroups[i + 1];
                if (!nextGroup) continue; // Skip if undefined (shouldn't happen but TypeScript safety)
                
                const nextTime = nextGroup.timestamp;
                const currentEndTime = new Date(currentTime.getTime() + (currentGroup.duration));
                const gapDuration = nextTime.getTime() - currentEndTime.getTime();

                if (gapDuration > 5000) { // Gap larger than 5 seconds
                    console.log(`⚠️ Gap detected: ${Math.round(gapDuration/1000)}s between clips ${i + 1} and ${i + 2}`);
                }
            }
        }

        // Detect timeline gaps
        const gaps = this.detectTimelineGaps(clipGroups);
        if (gaps.length > 0) {
            console.log(`⚠️ Detected ${gaps.length} timeline gaps in clip groups`);
            gaps.forEach((gap, index) => {
                console.log(`  Gap ${index + 1}: ${Math.round(gap.duration/1000)}s between clips ${gap.beforeIndex + 1} and ${gap.afterIndex + 1}`);
            });
        }
    }

    /**
     * Detect gaps between clip groups
     */
    private detectTimelineGaps(clipGroups: TeslaClipGroup[]): Array<{
        beforeIndex: number;
        afterIndex: number;
        duration: number;
        startTime: Date;
        endTime: Date;
    }> {
        const gaps = [];

        for (let i = 0; i < clipGroups.length - 1; i++) {
            const currentGroup = clipGroups[i];
            const nextGroup = clipGroups[i + 1];
            
            // Skip if either group is undefined (shouldn't happen but TypeScript safety)
            if (!currentGroup || !nextGroup) continue;
            
            // Calculate expected end time of current clip
            const currentEndTime = new Date(currentGroup.timestamp.getTime() + (currentGroup.duration * 1000));
            const nextStartTime = nextGroup.timestamp;
            
            const gapDuration = nextStartTime.getTime() - currentEndTime.getTime();
            
            // If gap is larger than 5 seconds, consider it a timeline gap
            if (gapDuration > 5000) {
                gaps.push({
                    beforeIndex: i,
                    afterIndex: i + 1,
                    duration: gapDuration,
                    startTime: currentEndTime,
                    endTime: nextStartTime
                });
            }
        }

        return gaps;
    }

    /**
     * Generate group key for timestamp-based grouping
     */
    private getGroupKey(timestamp: Date): string {
        // Group by exact timestamp (Tesla files from same event have same timestamp)
        return timestamp.toISOString();
    }

    /**
     * Get available cameras for a clip group
     */
    getAvailableCameras(clipGroup: TeslaClipGroup): Array<TeslaVideoFile['camera']> {
        return Object.keys(clipGroup.files) as Array<TeslaVideoFile['camera']>;
    }

    /**
     * Check if clip group has all cameras
     */
    hasAllCameras(clipGroup: TeslaClipGroup): boolean {
        return this.TESLA_CAMERAS.every(camera => clipGroup.files[camera]);
    }

    /**
     * Get total file size for a clip group
     */
    getClipGroupSize(clipGroup: TeslaClipGroup): number {
        return Object.values(clipGroup.files).reduce((total, file) =>
            total + (file?.size || 0), 0
        );
    }

    /**
     * Detect events for clip groups by scanning for event.json files
     */
    private async detectEventsForClipGroups(clipGroups: TeslaClipGroup[], baseFolderPath: string): Promise<void> {
        for (const clipGroup of clipGroups) {
            // Skip RecentClips folder as specified in requirements
            if (clipGroup.type === 'RecentClips') {
                continue;
            }

            try {
                const event = await this.detectEventForClipGroup(clipGroup, baseFolderPath);
                if (event) {
                    clipGroup.event = event;
                }
            } catch (error) {
                console.error(`Error detecting event for clip group ${clipGroup.timestamp}:`, error);
            }
        }
    }

    /**
     * Detect event for a specific clip group
     */
    private async detectEventForClipGroup(clipGroup: TeslaClipGroup, baseFolderPath: string): Promise<TeslaEventData | null> {
        try {
            // Generate the expected folder name from timestamp
            const folderName = this.generateClipFolderName(clipGroup.timestamp);
            const clipFolderPath = path.join(baseFolderPath, clipGroup.type, folderName);

            // Check if the clip folder exists
            if (!fs.existsSync(clipFolderPath)) {
                return null;
            }

            // Look for event.json file
            const eventJsonPath = path.join(clipFolderPath, 'event.json');
            if (!fs.existsSync(eventJsonPath)) {
                return null;
            }

            // Parse event.json
            const eventData = await this.parseEventJson(eventJsonPath, clipFolderPath);
            return eventData;

        } catch (error) {
            console.error(`Error detecting event for clip group:`, error);
            return null;
        }
    }

    /**
     * Generate Tesla clip folder name from timestamp
     */
    private generateClipFolderName(timestamp: Date): string {
        const year = timestamp.getFullYear();
        const month = String(timestamp.getMonth() + 1).padStart(2, '0');
        const day = String(timestamp.getDate()).padStart(2, '0');
        const hours = String(timestamp.getHours()).padStart(2, '0');
        const minutes = String(timestamp.getMinutes()).padStart(2, '0');
        const seconds = String(timestamp.getSeconds()).padStart(2, '0');

        return `${year}-${month}-${day}_${hours}-${minutes}-${seconds}`;
    }

    /**
     * Parse event.json file
     */
    private async parseEventJson(eventJsonPath: string, folderPath: string): Promise<TeslaEventData | null> {
        try {
            const eventJsonContent = fs.readFileSync(eventJsonPath, 'utf8');
            const eventData = JSON.parse(eventJsonContent);

            // Validate required fields
            if (!eventData.timestamp || !eventData.reason) {
                console.warn(`Invalid event.json format in ${eventJsonPath}`);
                return null;
            }

            // Parse timestamp
            const timestampDate = new Date(eventData.timestamp);
            if (isNaN(timestampDate.getTime())) {
                console.warn(`Invalid timestamp in event.json: ${eventData.timestamp}`);
                return null;
            }

            // Check for thumbnail
            const thumbnailPath = path.join(folderPath, 'thumb.png');
            const hasThumbnail = fs.existsSync(thumbnailPath);

            const result: TeslaEventData = {
                timestamp: eventData.timestamp,
                city: eventData.city,
                est_lat: eventData.est_lat,
                est_lon: eventData.est_lon,
                reason: eventData.reason,
                camera: eventData.camera,
                folderPath: folderPath,
                timestampDate: timestampDate
            };

            if (hasThumbnail) {
                result.thumbnailPath = thumbnailPath;
            }

            return result;

        } catch (error) {
            console.error(`Error parsing event.json at ${eventJsonPath}:`, error);
            return null;
        }
    }

    /**
     * Get event data for a specific clip group
     */
    getEventForClipGroup(clipGroup: TeslaClipGroup): TeslaEventData | null {
        return clipGroup.event || null;
    }

    /**
     * Get all events from clip groups
     */
    getAllEvents(clipGroups: TeslaClipGroup[]): TeslaEventData[] {
        return clipGroups
            .filter(group => group.event)
            .map(group => group.event!)
            .sort((a, b) => a.timestampDate.getTime() - b.timestampDate.getTime());
    }
}
