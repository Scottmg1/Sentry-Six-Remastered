// Minimal Electron app to test basic functionality
console.log('Starting minimal Electron app...');

try {
    const electron = require('electron');
    console.log('Electron module loaded:', !!electron);
    
    const { app, BrowserWindow } = electron;
    console.log('App:', !!app);
    console.log('BrowserWindow:', !!BrowserWindow);
    
    if (!app) {
        console.error('Electron app is undefined!');
        process.exit(1);
    }
    
    function createWindow() {
        console.log('Creating window...');
        const mainWindow = new BrowserWindow({
            width: 1200,
            height: 800,
            webPreferences: {
                nodeIntegration: false,
                contextIsolation: true
            }
        });

        // Load a simple HTML content
        mainWindow.loadURL('data:text/html,<h1>Sentry-Six Electron Test</h1><p>If you see this, Electron is working!</p>');
        
        console.log('Window created successfully');
    }

    app.whenReady().then(() => {
        console.log('App is ready');
        createWindow();
    });

    app.on('window-all-closed', () => {
        console.log('All windows closed');
        if (process.platform !== 'darwin') {
            app.quit();
        }
    });

    app.on('activate', () => {
        console.log('App activated');
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
    
} catch (error) {
    console.error('Error loading Electron:', error);
    process.exit(1);
}
