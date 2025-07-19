/**
 * Tesla File Manager
 * Handles Tesla dashcam file discovery, organization, and metadata extraction
 * Ported from Python implementation with enhanced TypeScript features
 */

import * as fs from 'fs';
import * as path from 'path';

export interface TeslaVideoFile {
    path: string;
    filename: string;
    camera: 'front' | 'left_repeater' | 'right_repeater' | 'back';
    timestamp: Date;
    duration: number;
    size: number;
    type: 'SavedClips' | 'RecentClips' | 'SentryClips';
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
}

export class TeslaFileManager {
    private readonly TESLA_CAMERAS = ['front', 'left_repeater', 'right_repeater', 'back'] as const;
    private readonly TESLA_FOLDERS = ['SavedClips', 'RecentClips', 'SentryClips'] as const;
    private readonly VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi'] as const;

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
                }
            }
        } catch (error) {
            console.error(`Error scanning subfolder ${subFolderPath}:`, error);
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

            return {
                path: filePath,
                filename,
                camera,
                timestamp,
                duration: 0, // Will be filled by video processor
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

        // Convert to array and sort by timestamp
        return Array.from(groups.values()).sort((a, b) => 
            a.timestamp.getTime() - b.timestamp.getTime()
        );
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
}
