/**
 * Configuration Manager
 * Handles application settings and preferences using simple JSON storage
 * Provides persistent storage for user preferences
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export interface AppConfig {
    // Video playback settings
    defaultVolume: number;
    playbackSpeed: number;
    autoPlay: boolean;
    
    // Display settings
    showTimestamp: boolean;
    timestampFormat: string;
    theme: 'light' | 'dark' | 'auto';
    
    // Tesla-specific settings
    lastTeslaFolder: string;
    preferredCameras: string[];
    syncTolerance: number; // milliseconds
    
    // Export settings
    defaultExportQuality: 'high' | 'medium' | 'low';
    defaultExportFormat: string;
    includeAudioByDefault: boolean;
    
    // Performance settings
    hardwareAcceleration: boolean;
    maxConcurrentVideos: number;
    preloadNextClip: boolean;
    
    // UI settings
    windowBounds: {
        width: number;
        height: number;
        x?: number;
        y?: number;
    };
    sidebarWidth: number;
    timelineHeight: number;
}

export class ConfigManager {
    private config: AppConfig;
    private configPath: string;

    constructor() {
        this.configPath = path.join(os.homedir(), '.sentry-six-config.json');
        this.config = this.loadConfig();
    }

    /**
     * Load configuration from file
     */
    private loadConfig(): AppConfig {
        try {
            if (fs.existsSync(this.configPath)) {
                const data = fs.readFileSync(this.configPath, 'utf8');
                const loaded = JSON.parse(data);
                return { ...this.getDefaultConfig(), ...loaded };
            }
        } catch (error) {
            console.error('Failed to load config:', error);
        }
        return this.getDefaultConfig();
    }

    /**
     * Save configuration to file
     */
    private saveConfig(): void {
        try {
            fs.writeFileSync(this.configPath, JSON.stringify(this.config, null, 2));
        } catch (error) {
            console.error('Failed to save config:', error);
        }
    }

    /**
     * Get configuration value
     */
    get<K extends keyof AppConfig>(key: K): AppConfig[K] {
        return this.config[key];
    }

    /**
     * Set configuration value
     */
    set<K extends keyof AppConfig>(key: K, value: AppConfig[K]): void {
        this.config[key] = value;
        this.saveConfig();
    }

    /**
     * Get all configuration
     */
    getAll(): AppConfig {
        return { ...this.config };
    }

    /**
     * Reset configuration to defaults
     */
    reset(): void {
        this.config = this.getDefaultConfig();
        this.saveConfig();
    }

    /**
     * Check if configuration key exists
     */
    has<K extends keyof AppConfig>(key: K): boolean {
        return key in this.config;
    }

    /**
     * Delete configuration key
     */
    delete<K extends keyof AppConfig>(key: K): void {
        delete this.config[key];
        this.saveConfig();
    }

    /**
     * Get configuration file path
     */
    getConfigPath(): string {
        return this.configPath;
    }

    /**
     * Default configuration values
     */
    private getDefaultConfig(): AppConfig {
        return {
            // Video playback settings
            defaultVolume: 0.5,
            playbackSpeed: 1.0,
            autoPlay: false,
            
            // Display settings
            showTimestamp: true,
            timestampFormat: 'MM/DD/YYYY HH:MM:SS AM/PM',
            theme: 'auto',
            
            // Tesla-specific settings
            lastTeslaFolder: '',
            preferredCameras: ['front', 'left_repeater', 'right_repeater', 'back'],
            syncTolerance: 100, // 100ms tolerance for synchronization
            
            // Export settings
            defaultExportQuality: 'medium',
            defaultExportFormat: 'mp4',
            includeAudioByDefault: false,
            
            // Performance settings
            hardwareAcceleration: true,
            maxConcurrentVideos: 6,
            preloadNextClip: true,
            
            // UI settings
            windowBounds: {
                width: 1400,
                height: 900
            },
            sidebarWidth: 300,
            timelineHeight: 100
        };
    }



    /**
     * Update window bounds
     */
    updateWindowBounds(bounds: Partial<AppConfig['windowBounds']>): void {
        const currentBounds = this.get('windowBounds');
        this.set('windowBounds', { ...currentBounds, ...bounds });
    }

    /**
     * Add camera to preferred list
     */
    addPreferredCamera(camera: string): void {
        const cameras = this.get('preferredCameras');
        if (!cameras.includes(camera)) {
            this.set('preferredCameras', [...cameras, camera]);
        }
    }

    /**
     * Remove camera from preferred list
     */
    removePreferredCamera(camera: string): void {
        const cameras = this.get('preferredCameras');
        this.set('preferredCameras', cameras.filter(c => c !== camera));
    }

    /**
     * Export configuration to JSON
     */
    exportConfig(): string {
        return JSON.stringify(this.getAll(), null, 2);
    }

    /**
     * Import configuration from JSON
     */
    importConfig(configJson: string): boolean {
        try {
            const config = JSON.parse(configJson);
            
            // Validate and merge with current config
            for (const [key, value] of Object.entries(config)) {
                if (this.isValidConfigKey(key)) {
                    this.set(key as keyof AppConfig, value as any);
                }
            }
            
            return true;
        } catch (error) {
            console.error('Failed to import configuration:', error);
            return false;
        }
    }

    /**
     * Check if key is valid configuration key
     */
    private isValidConfigKey(key: string): key is keyof AppConfig {
        return key in this.getDefaultConfig();
    }
}
