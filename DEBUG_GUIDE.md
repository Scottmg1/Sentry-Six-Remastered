# 🐛 Sentry-Six Debug Guide

## Overview

The Sentry-Six Tesla Dashcam Viewer now includes comprehensive debugging capabilities to help diagnose timeline issues, missing clips, and playback problems.

## 🚀 **Accessing Debug Mode**

1. **Open Debug Panel**: Click the 🐛 Debug button in the top-right header
2. **Toggle Visibility**: Click the "Hide" button in the debug panel to close it
3. **Auto-Updates**: Debug information updates automatically every second when visible
sasdfasdfasfas
## 📊 **Debug Information Sections**

### **Timeline Overview**
- **Total Clips**: Number of clips in the current timeline
- **Duration**: Total duration of all clips combined
- **Time Range**: Start and end times for the day's footage
- **Date**: The selected date being viewed

### **Camera Coverage**
Shows how many clips are available for each camera:
- Front, Back, Left Pillar, Right Pillar, Left Repeater, Right Repeater
- Helps identify if specific cameras are missing data

### **Gap Analysis**
Automatically detects and categorizes gaps in footage:

#### **Gap Types**
- **Long break (>1 hour)**: Extended periods without recording
- **Extended break (>30 min)**: Medium gaps, possibly intentional
- **Medium break (>10 min)**: Short stops or parking
- **Short break (>3 min)**: Brief interruptions
- **Missing clip data**: Unexpected gaps in continuous recording

#### **Gap Information**
- **Start/End Time**: When the gap begins and ends
- **Duration**: How long the gap lasts
- **Reason**: Categorized explanation for the gap

### **Missing Camera Data**
- Shows specific times when expected cameras are missing
- Lists which cameras (front, back, pillars, repeaters) have no data
- Helps identify hardware or storage issues

### **Current State**
Real-time playback information:
- **Current Clip**: Filename of the currently playing clip
- **Playback**: Whether video is playing or paused
- **Timeline Position**: Current position in the daily timeline
- **Speed**: Current playback speed (0.25x to 4x)
- **Volume**: Current volume level (0-100%)

## 🔧 **Debug Actions**

### **Export Debug Data**
- Click "Export Debug Data" to download a JSON file
- Contains complete timeline analysis, gap detection, and settings
- Useful for sharing debug information or offline analysis
- Filename format: `sentry-six-debug-[timestamp].json`

### **Clear Console**
- Click "Clear Console" to clear the browser's debug console
- Useful for focusing on new debug messages
- Adds a timestamp marker when cleared

## 🚨 **Common Issues & Solutions**

### **Missing Clips (Gaps in Timeline)**

#### **Symptoms**
- Red warning sections in Gap Analysis
- Unexpected jumps in time during playback
- "Missing clip data" entries

#### **Possible Causes**
1. **SD Card Issues**: Corrupted or full storage
2. **Power Issues**: Car was off or low power mode
3. **Camera Malfunction**: Hardware failure
4. **File System Errors**: Corrupted file structure
5. **Manual Deletion**: Files were removed

#### **Debugging Steps**
1. Check Gap Analysis for pattern recognition
2. Note specific time ranges with issues
3. Verify if gaps occur at regular intervals (suggests power cycling)
4. Check if specific cameras are consistently missing
5. Export debug data for detailed analysis

### **Missing Camera Data**

#### **Symptoms**
- Specific cameras showing "No video available"
- Uneven camera coverage in Camera Coverage section
- Missing camera entries in clip metadata

#### **Possible Causes**
1. **Camera Hardware**: Physical camera failure
2. **Wiring Issues**: Loose connections
3. **Storage Partitioning**: Camera data saved to different location
4. **File Naming**: Non-standard Tesla file naming

#### **Debugging Steps**
1. Check which cameras are consistently missing
2. Verify if issue is time-specific or constant
3. Check physical camera functionality in car
4. Examine raw file structure in Tesla folder

### **Playback Issues**

#### **Symptoms**
- Videos not synchronizing
- Playback stuttering or freezing
- Timeline position incorrect

#### **Debugging Steps**
1. Monitor Current State section during playback
2. Check if all cameras are loading properly
3. Verify timeline position matches video content
4. Test different playback speeds

## 📈 **Performance Monitoring**

### **Timeline Loading**
- Monitor how long it takes to load daily timelines
- Large numbers of clips (>100) may cause slower loading
- Gap analysis runs automatically on timeline load

### **Memory Usage**
- Debug panel updates every second when visible
- Consider hiding debug panel during normal use for better performance
- Export debug data periodically to avoid memory buildup

## 🔍 **Advanced Debugging**

### **Browser Developer Tools**
1. Press F12 to open browser developer tools
2. Check Console tab for detailed error messages
3. Network tab shows file loading issues
4. Performance tab helps identify bottlenecks

### **Debug Data Analysis**
The exported JSON contains:
```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "timeline": {
    "clips": [...],
    "currentClipIndex": 0,
    "totalDuration": 3600000,
    "date": "01/15/24"
  },
  "gaps": [
    {
      "startTime": "10:15:30",
      "endTime": "10:45:30", 
      "duration": 1800,
      "reason": "Extended break (>30 min)"
    }
  ],
  "missingCameras": [...],
  "settings": {
    "gapThreshold": 60
  }
}
```

### **Customizing Gap Detection**
- Default gap threshold: 60 seconds
- Modify `debugManager.setGapThreshold(seconds)` in console
- Smaller values detect more minor gaps
- Larger values focus on major interruptions

## 🛠️ **Troubleshooting Debug Panel**

### **Debug Panel Not Showing**
1. Ensure JavaScript is enabled
2. Check browser console for errors
3. Refresh the application
4. Verify debug-manager.js is loaded

### **No Debug Data**
1. Load a Tesla folder first
2. Select a date from the timeline
3. Wait for clips to load
4. Debug data populates after timeline loads

### **Performance Issues**
1. Hide debug panel when not needed
2. Clear console regularly
3. Export and clear debug data periodically
4. Close other browser tabs

## 📞 **Getting Help**

When reporting issues, please include:
1. Exported debug data JSON file
2. Screenshots of debug panel showing gaps/issues
3. Description of expected vs actual behavior
4. Tesla car model and software version
5. Approximate date/time of problematic footage

The debug system provides comprehensive insight into timeline issues and helps identify both software bugs and hardware problems with your Tesla's dashcam system.
