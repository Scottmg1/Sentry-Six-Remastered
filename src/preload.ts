/**
 * Preload Script
 * Secure bridge between main and renderer processes
 * Exposes safe APIs to the renderer while maintaining security
 */

import { contextBridge, ipcRenderer } from 'electron';

// Define the API interface that will be available in the renderer
export interface ElectronAPI {
    // Tesla file operations
    tesla: {
        selectFolder: () => Promise<any>;
        getVideoFiles: (folderPath: string) => Promise<any>;
        getVideoMetadata: (filePath: string) => Promise<any>;
        exportVideo: (exportId: string, exportData: any) => Promise<boolean>;
        cancelExport: (exportId: string) => Promise<boolean>;
        getExportStatus: (exportId: string) => Promise<boolean>;
    };

    // Configuration management
    config: {
        get: (key: string) => Promise<any>;
        set: (key: string, value: any) => Promise<any>;
        getAll: () => Promise<any>;
    };

    // Video processing
    video: {
        export: (options: any) => Promise<boolean>;
    };

    // File system operations
    fs: {
        exists: (filePath: string) => Promise<boolean>;
        readFile: (filePath: string) => Promise<string>;
        showItemInFolder: (filePath: string) => Promise<void>;
    };

    // Dialog operations
    dialog: {
        saveFile: (options: any) => Promise<string | null>;
    };

    // Application info
    app: {
        getVersion: () => Promise<string>;
        getPath: (name: string) => Promise<string>;
    };

    // Event listeners
    on: (channel: string, callback: (...args: any[]) => void) => void;
    off: (channel: string, callback: (...args: any[]) => void) => void;
    once: (channel: string, callback: (...args: any[]) => void) => void;
    removeListener: (channel: string, callback: (...args: any[]) => void) => void;

    // Generic invoke for backward compatibility
    invoke: (channel: string, ...args: any[]) => Promise<any>;
}

// Expose the API to the renderer process
const electronAPI: ElectronAPI = {
    // Tesla file operations
    tesla: {
        selectFolder: () => ipcRenderer.invoke('tesla:select-folder'),
        getVideoFiles: (folderPath: string) => ipcRenderer.invoke('tesla:get-video-files', folderPath),
        getVideoMetadata: (filePath: string) => ipcRenderer.invoke('tesla:get-video-metadata', filePath),
        exportVideo: (exportId: string, exportData: any) => ipcRenderer.invoke('tesla:export-video', exportId, exportData),
        cancelExport: (exportId: string) => ipcRenderer.invoke('tesla:cancel-export', exportId),
        getExportStatus: (exportId: string) => ipcRenderer.invoke('tesla:get-export-status', exportId),
    },

    // Configuration management
    config: {
        get: (key: string) => ipcRenderer.invoke('config:get', key),
        set: (key: string, value: any) => ipcRenderer.invoke('config:set', key, value),
        getAll: () => ipcRenderer.invoke('config:get-all'),
    },

    // Video processing
    video: {
        export: (options: any) => ipcRenderer.invoke('video:export', options),
    },

    // File system operations
    fs: {
        exists: (filePath: string) => ipcRenderer.invoke('fs:exists', filePath),
        readFile: (filePath: string) => ipcRenderer.invoke('fs:read-file', filePath),
        showItemInFolder: (filePath: string) => ipcRenderer.invoke('fs:show-item-in-folder', filePath),
    },

    // Dialog operations
    dialog: {
        saveFile: (options: any) => ipcRenderer.invoke('dialog:save-file', options),
    },

    // Application info
    app: {
        getVersion: () => ipcRenderer.invoke('app:get-version'),
        getPath: (name: string) => ipcRenderer.invoke('app:get-path', name),
    },

    // Event listeners
    on: (channel: string, callback: (...args: any[]) => void) => {
        // Validate allowed channels for security
        const allowedChannels = [
            'folder-selected',
            'video-loaded',
            'export-progress',
            'export-complete',
            'tesla:export-progress',
            'config-changed'
        ];

        if (allowedChannels.includes(channel)) {
            ipcRenderer.on(channel, callback);
        } else {
            console.warn(`Attempted to listen to unauthorized channel: ${channel}`);
        }
    },

    off: (channel: string, callback: (...args: any[]) => void) => {
        ipcRenderer.off(channel, callback);
    },

    once: (channel: string, callback: (...args: any[]) => void) => {
        const allowedChannels = [
            'folder-selected',
            'video-loaded',
            'export-progress',
            'export-complete',
            'tesla:export-progress',
            'config-changed'
        ];

        if (allowedChannels.includes(channel)) {
            ipcRenderer.once(channel, callback);
        } else {
            console.warn(`Attempted to listen to unauthorized channel: ${channel}`);
        }
    },

    removeListener: (channel: string, callback: (...args: any[]) => void) => {
        ipcRenderer.removeListener(channel, callback);
    },

    // Generic invoke for backward compatibility
    invoke: (channel: string, ...args: any[]) => {
        return ipcRenderer.invoke(channel, ...args);
    }
};

// Debug: Log what we're exposing
console.log('🔧 Preload: Creating electronAPI object...');
console.log('🔧 Preload: electronAPI keys:', Object.keys(electronAPI));
console.log('🔧 Preload: electronAPI.dialog exists:', !!electronAPI.dialog);
console.log('🔧 Preload: electronAPI.dialog.saveFile type:', typeof electronAPI.dialog?.saveFile);
console.log('🔧 Preload: Full electronAPI object:', electronAPI);

// Expose the API to the global window object
try {
    contextBridge.exposeInMainWorld('electronAPI', electronAPI);
    console.log('✅ Preload: electronAPI exposed successfully');
} catch (error) {
    console.error('❌ Preload: Failed to expose electronAPI:', error);
}

// Also expose it as a typed interface for TypeScript
declare global {
    interface Window {
        electronAPI: ElectronAPI;
    }
}
