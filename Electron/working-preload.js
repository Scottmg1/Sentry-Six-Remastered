// Working Preload Script
// Simplified version for immediate functionality

const { contextBridge, ipcRenderer } = require('electron');

// Expose safe APIs to the renderer
contextBridge.exposeInMainWorld('electronAPI', {
    // Tesla file operations
    tesla: {
        selectFolder: () => ipcRenderer.invoke('tesla:select-folder')
    },

    // File system operations
    fs: {
        exists: (filePath) => ipcRenderer.invoke('fs:exists', filePath)
    },

    // Application info
    app: {
        getVersion: () => ipcRenderer.invoke('app:get-version')
    },

    // Event listeners
    on: (channel, callback) => {
        const allowedChannels = ['folder-selected', 'videos-loaded'];
        if (allowedChannels.includes(channel)) {
            ipcRenderer.on(channel, callback);
        }
    },

    off: (channel, callback) => {
        ipcRenderer.off(channel, callback);
    },

    // Utility functions
    log: (message) => {
        console.log('[Renderer]', message);
    }
});

console.log('Preload script loaded successfully');
