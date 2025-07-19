/**
 * Video Processor
 * Handles video metadata extraction and processing using FFmpeg
 * Provides video duration, frame rate, and export functionality
 */

import * as fs from 'fs';
import * as path from 'path';
import { spawn } from 'child_process';

export interface VideoMetadata {
    duration: number;
    frameRate: number;
    width: number;
    height: number;
    codec: string;
    bitrate: number;
    size: number;
}

export interface ExportOptions {
    inputFiles: string[];
    outputPath: string;
    startTime?: number;
    endTime?: number;
    quality?: 'high' | 'medium' | 'low';
    includeAudio?: boolean;
}

export class VideoProcessor {
    private ffmpegPath: string;
    private ffprobePath: string;

    constructor() {
        // Try to find FFmpeg in common locations or use bundled version
        this.ffmpegPath = this.findFFmpegPath();
        this.ffprobePath = this.findFFprobePath();
    }

    /**
     * Get video metadata using FFprobe
     */
    async getVideoMetadata(filePath: string): Promise<VideoMetadata | null> {
        if (!fs.existsSync(filePath)) {
            throw new Error(`Video file does not exist: ${filePath}`);
        }

        try {
            const stats = fs.statSync(filePath);
            const probeResult = await this.runFFprobe(filePath);
            
            if (!probeResult.streams || probeResult.streams.length === 0) {
                throw new Error('No video streams found');
            }

            const videoStream = probeResult.streams.find((stream: any) => 
                stream.codec_type === 'video'
            );

            if (!videoStream) {
                throw new Error('No video stream found');
            }

            // Parse frame rate (handle both formats: "30/1" and "30.0")
            let frameRate = 30; // Default for Tesla videos
            if (videoStream.r_frame_rate) {
                const [num, den] = videoStream.r_frame_rate.split('/').map(Number);
                frameRate = den ? num / den : num;
            } else if (videoStream.avg_frame_rate) {
                const [num, den] = videoStream.avg_frame_rate.split('/').map(Number);
                frameRate = den ? num / den : num;
            }

            // Tesla videos are typically 36.02 FPS
            if (Math.abs(frameRate - 36.02) < 0.1) {
                frameRate = 36.02;
            }

            return {
                duration: parseFloat(videoStream.duration) || 0,
                frameRate,
                width: parseInt(videoStream.width) || 0,
                height: parseInt(videoStream.height) || 0,
                codec: videoStream.codec_name || 'unknown',
                bitrate: parseInt(videoStream.bit_rate) || 0,
                size: stats.size
            };

        } catch (error) {
            console.error(`Error getting video metadata for ${filePath}:`, error);
            return null;
        }
    }

    /**
     * Export video with specified options
     */
    async exportVideo(options: ExportOptions): Promise<boolean> {
        try {
            console.log('Starting video export:', options);

            const args = this.buildFFmpegArgs(options);
            const success = await this.runFFmpeg(args);

            if (success) {
                console.log('Video export completed successfully');
            } else {
                console.error('Video export failed');
            }

            return success;

        } catch (error) {
            console.error('Error during video export:', error);
            return false;
        }
    }

    /**
     * Run FFprobe command and parse JSON output
     */
    private async runFFprobe(filePath: string): Promise<any> {
        return new Promise((resolve, reject) => {
            const args = [
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                filePath
            ];

            const process = spawn(this.ffprobePath, args);
            let stdout = '';
            let stderr = '';

            process.stdout.on('data', (data) => {
                stdout += data.toString();
            });

            process.stderr.on('data', (data) => {
                stderr += data.toString();
            });

            process.on('close', (code) => {
                if (code === 0) {
                    try {
                        const result = JSON.parse(stdout);
                        resolve(result);
                    } catch (error) {
                        reject(new Error(`Failed to parse FFprobe output: ${error}`));
                    }
                } else {
                    reject(new Error(`FFprobe failed with code ${code}: ${stderr}`));
                }
            });

            process.on('error', (error) => {
                reject(new Error(`Failed to start FFprobe: ${error}`));
            });
        });
    }

    /**
     * Run FFmpeg command
     */
    private async runFFmpeg(args: string[]): Promise<boolean> {
        return new Promise((resolve) => {
            const process = spawn(this.ffmpegPath, args);
            let stderr = '';

            process.stderr.on('data', (data) => {
                stderr += data.toString();
                // Could emit progress events here
            });

            process.on('close', (code) => {
                if (code === 0) {
                    resolve(true);
                } else {
                    console.error(`FFmpeg failed with code ${code}: ${stderr}`);
                    resolve(false);
                }
            });

            process.on('error', (error) => {
                console.error(`Failed to start FFmpeg: ${error}`);
                resolve(false);
            });
        });
    }

    /**
     * Build FFmpeg arguments for export
     */
    private buildFFmpegArgs(options: ExportOptions): string[] {
        const args: string[] = [];

        // Input files
        for (const inputFile of options.inputFiles) {
            args.push('-i', inputFile);
        }

        // Time range
        if (options.startTime !== undefined) {
            args.push('-ss', options.startTime.toString());
        }
        if (options.endTime !== undefined) {
            args.push('-t', (options.endTime - (options.startTime || 0)).toString());
        }

        // Video codec and quality
        args.push('-c:v', 'libx264');

        switch (options.quality) {
            case 'high':
                args.push('-crf', '18');
                break;
            case 'medium':
                args.push('-crf', '23');
                break;
            case 'low':
                args.push('-crf', '28');
                break;
            default:
                args.push('-crf', '23');
        }

        // Audio handling
        if (options.includeAudio) {
            args.push('-c:a', 'aac');
        } else {
            args.push('-an'); // No audio
        }

        // Output settings
        args.push('-preset', 'fast');
        args.push('-y'); // Overwrite output file
        args.push(options.outputPath);

        return args;
    }

    /**
     * Find FFmpeg executable path
     */
    private findFFmpegPath(): string {
        // Common locations to check
        const possiblePaths = [
            'ffmpeg', // System PATH
            path.join(process.cwd(), 'ffmpeg_bin', 'ffmpeg.exe'), // Bundled Windows
            path.join(process.cwd(), 'ffmpeg_bin', 'ffmpeg'), // Bundled Unix
            '/usr/local/bin/ffmpeg', // Homebrew macOS
            '/usr/bin/ffmpeg', // Linux package manager
        ];

        for (const ffmpegPath of possiblePaths) {
            try {
                if (fs.existsSync(ffmpegPath)) {
                    return ffmpegPath;
                }
            } catch (error) {
                // Continue checking
            }
        }

        // Default to system PATH
        return 'ffmpeg';
    }

    /**
     * Find FFprobe executable path
     */
    private findFFprobePath(): string {
        // Common locations to check
        const possiblePaths = [
            'ffprobe', // System PATH
            path.join(process.cwd(), 'ffmpeg_bin', 'ffprobe.exe'), // Bundled Windows
            path.join(process.cwd(), 'ffmpeg_bin', 'ffprobe'), // Bundled Unix
            '/usr/local/bin/ffprobe', // Homebrew macOS
            '/usr/bin/ffprobe', // Linux package manager
        ];

        for (const ffprobePath of possiblePaths) {
            try {
                if (fs.existsSync(ffprobePath)) {
                    return ffprobePath;
                }
            } catch (error) {
                // Continue checking
            }
        }

        // Default to system PATH
        return 'ffprobe';
    }
}
