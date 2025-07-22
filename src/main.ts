/**
 * Sentry-Six Electron Main Process
 * Tesla Dashcam Viewer - Main Application Entry Point
 */

import { app, BrowserWindow, ipcMain, dialog, Menu, shell } from 'electron';
import * as path from 'path';
import * as fs from 'fs';
import { TeslaFileManager } from './main/tesla-file-manager';
import { VideoProcessor } from './main/video-processor';
import { ConfigManager } from './main/config-manager';

class SentrySixApp {
    private mainWindow: BrowserWindow | null = null;
    private teslaFileManager: TeslaFileManager;
    private videoProcessor: VideoProcessor;
    private configManager: ConfigManager;

    constructor() {
        this.teslaFileManager = new TeslaFileManager();
        this.videoProcessor = new VideoProcessor();
        this.configManager = new ConfigManager();
        
        this.initializeApp();
    }

    private initializeApp(): void {
        // Handle app ready
        app.whenReady().then(() => {
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
            // Cleanup video processor resources
            this.videoProcessor.cleanup();

            if (process.platform !== 'darwin') {
                app.quit();
            }
        });

        // Security: Prevent new window creation
        app.on('web-contents-created', (_, contents) => {
            contents.setWindowOpenHandler(({ url }) => {
                shell.openExternal(url);
                return { action: 'deny' };
            });
        });
    }

    private createMainWindow(): void {
        this.mainWindow = new BrowserWindow({
            width: 1400,
            height: 900,
            minWidth: 1200,
            minHeight: 700,
            webPreferences: {
                nodeIntegration: false,
                contextIsolation: true,
                preload: path.join(__dirname, 'preload.js'),
                webSecurity: true
            },
            icon: path.join(__dirname, '../assets/icon.png'),
            title: 'Sentry-Six - Tesla Dashcam Viewer',
            show: false // Don't show until ready
        });

        // Load the renderer
        const isDev = process.env['NODE_ENV'] === 'development';
        if (isDev) {
            this.mainWindow.loadURL('http://localhost:3000');
            this.mainWindow.webContents.openDevTools();
        } else {
            this.mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
        }

        // Show window when ready
        this.mainWindow.once('ready-to-show', () => {
            this.mainWindow?.show();
            
            if (isDev) {
                this.mainWindow?.webContents.openDevTools();
            }
        });

        // Handle window closed
        this.mainWindow.on('closed', () => {
            this.mainWindow = null;
        });
    }

    private setupIpcHandlers(): void {
        // Tesla file operations
        ipcMain.handle('tesla:select-folder', async () => {
            const result = await dialog.showOpenDialog(this.mainWindow!, {
                properties: ['openDirectory'],
                title: 'Select Tesla Dashcam Folder'
            });

            if (!result.canceled && result.filePaths.length > 0) {
                return await this.teslaFileManager.scanFolder(result.filePaths[0]!);
            }
            return null;
        });

        ipcMain.handle('tesla:get-video-files', async (_, folderPath: string) => {
            return await this.teslaFileManager.getVideoFiles(folderPath);
        });

        ipcMain.handle('tesla:get-video-metadata', async (_, filePath: string) => {
            return await this.videoProcessor.getVideoMetadata(filePath);
        });

        ipcMain.handle('tesla:get-event-data', async (_, folderPath: string) => {
            try {
                const clipGroups = await this.teslaFileManager.scanFolder(folderPath);
                const events = this.teslaFileManager.getAllEvents(clipGroups);
                return events;
            } catch (error) {
                console.error('Error getting event data:', error);
                return [];
            }
        });

        ipcMain.handle('tesla:get-event-thumbnail', async (_, thumbnailPath: string) => {
            try {
                const fs = require('fs');
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

        // Configuration management
        ipcMain.handle('config:get', async (_, key: string) => {
            return this.configManager.get(key as any);
        });

        ipcMain.handle('config:set', async (_, key: string, value: any) => {
            return this.configManager.set(key as any, value);
        });

        ipcMain.handle('config:get-all', async () => {
            return this.configManager.getAll();
        });

        // Video processing
        ipcMain.handle('video:export', async (_, exportOptions: any) => {
            return await this.videoProcessor.exportVideo(exportOptions);
        });

        // Tesla video export with advanced features
        ipcMain.handle('tesla:export-video', async (event, exportId: string, exportData: any) => {
            const progressCallback = (progress: any) => {
                event.sender.send('tesla:export-progress', exportId, progress);
            };

            return await this.videoProcessor.exportTeslaVideo(exportId, exportData, progressCallback);
        });

        ipcMain.handle('tesla:cancel-export', async (_, exportId: string) => {
            return this.videoProcessor.cancelTeslaExport(exportId);
        });

        ipcMain.handle('tesla:get-export-status', async (_, exportId: string) => {
            return this.videoProcessor.getTeslaExportStatus(exportId);
        });

        // File save dialog for exports
        ipcMain.handle('dialog:save-file', async (_, options: any) => {
            const result = await dialog.showSaveDialog(this.mainWindow!, {
                title: options.title || 'Save Export',
                defaultPath: options.defaultPath || 'tesla_export.mp4',
                filters: options.filters || [
                    { name: 'Video Files', extensions: ['mp4'] },
                    { name: 'All Files', extensions: ['*'] }
                ]
            });

            return result.canceled ? null : result.filePath;
        });

        // File system operations
        ipcMain.handle('fs:exists', async (_, filePath: string) => {
            return fs.existsSync(filePath);
        });

        ipcMain.handle('fs:read-file', async (_, filePath: string) => {
            try {
                return fs.readFileSync(filePath, 'utf8');
            } catch (error) {
                throw new Error(`Failed to read file: ${error}`);
            }
        });

        ipcMain.handle('fs:show-item-in-folder', async (_, filePath: string) => {
            const { shell } = require('electron');
            shell.showItemInFolder(filePath);
        });

        // Application info
        ipcMain.handle('app:get-version', async () => {
            return app.getVersion();
        });

        ipcMain.handle('app:get-path', async (_, name: string) => {
            return app.getPath(name as any);
        });
    }

    private createApplicationMenu(): void {
        const template: Electron.MenuItemConstructorOptions[] = [
            {
                label: 'File',
                submenu: [
                    {
                        label: 'Open Tesla Folder...',
                        accelerator: 'CmdOrCtrl+O',
                        click: async () => {
                            const result = await dialog.showOpenDialog(this.mainWindow!, {
                                properties: ['openDirectory'],
                                title: 'Select Tesla Dashcam Folder'
                            });

                            if (!result.canceled && result.filePaths.length > 0) {
                                this.mainWindow?.webContents.send('folder-selected', result.filePaths[0]);
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
                label: 'Window',
                submenu: [
                    { role: 'minimize' },
                    { role: 'close' }
                ]
            },
            {
                label: 'Help',
                submenu: [
                    {
                        label: 'About Sentry-Six',
                        click: () => {
                            dialog.showMessageBox(this.mainWindow!, {
                                type: 'info',
                                title: 'About Sentry-Six',
                                message: 'Sentry-Six - Tesla Dashcam Viewer',
                                detail: `Version: ${app.getVersion()}\nElectron Edition with synchronized video playback`
                            });
                        }
                    }
                ]
            }
        ];

        const menu = Menu.buildFromTemplate(template);
        Menu.setApplicationMenu(menu);
    }
}

// Initialize the application
new SentrySixApp();
