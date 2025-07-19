// Test different import methods for Electron
console.log('Testing Electron import methods...');

// Method 1: Standard require
try {
    console.log('\n=== Method 1: Standard require ===');
    const electron1 = require('electron');
    console.log('electron1:', typeof electron1, Object.keys(electron1 || {}));
    
    if (electron1) {
        const { app, BrowserWindow } = electron1;
        console.log('app:', typeof app);
        console.log('BrowserWindow:', typeof BrowserWindow);
    }
} catch (error) {
    console.error('Method 1 failed:', error.message);
}

// Method 2: Direct property access
try {
    console.log('\n=== Method 2: Direct property access ===');
    const electron2 = require('electron');
    console.log('electron2.app:', typeof electron2?.app);
    console.log('electron2.BrowserWindow:', typeof electron2?.BrowserWindow);
} catch (error) {
    console.error('Method 2 failed:', error.message);
}

// Method 3: Check if running in Electron context
try {
    console.log('\n=== Method 3: Context check ===');
    console.log('process.versions.electron:', process.versions.electron);
    console.log('process.type:', process.type);
    console.log('process.env.ELECTRON_RUN_AS_NODE:', process.env.ELECTRON_RUN_AS_NODE);
} catch (error) {
    console.error('Method 3 failed:', error.message);
}

// Method 4: Try alternative import
try {
    console.log('\n=== Method 4: Alternative import ===');
    const electronPath = require.resolve('electron');
    console.log('Electron path:', electronPath);
    
    const electron4 = require(electronPath);
    console.log('electron4:', typeof electron4);
} catch (error) {
    console.error('Method 4 failed:', error.message);
}
