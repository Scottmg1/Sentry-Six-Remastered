/**
 * Debug Manager for Timeline Analysis and Gap Detection
 * Provides comprehensive debugging information for Tesla dashcam timeline issues
 */

class DebugManager {
    constructor() {
        this.isVisible = false;
        this.currentTimeline = null;
        this.gapThreshold = 60; // seconds - gap threshold for detection
        this.updateInterval = null;
        this.init();
    }

    init() {
        this.createDebugPanel();
        this.bindEvents();
    }

    createDebugPanel() {
        // Debug panel is already in HTML, just get references
        this.panel = document.getElementById('debug-panel');
        this.toggleBtn = document.getElementById('debug-btn');
        this.hideBtn = document.getElementById('debug-toggle');
        this.timelineInfo = document.getElementById('debug-timeline-info');
        this.clipGaps = document.getElementById('debug-clip-gaps');
        this.currentState = document.getElementById('debug-current-state');
    }

    bindEvents() {
        // Toggle debug panel
        this.toggleBtn?.addEventListener('click', () => this.toggle());
        this.hideBtn?.addEventListener('click', () => this.hide());

        // Debug action buttons
        const exportBtn = document.getElementById('export-debug-btn');
        exportBtn?.addEventListener('click', () => this.exportDebugData());

        const clearBtn = document.getElementById('clear-debug-btn');
        clearBtn?.addEventListener('click', () => this.clearConsole());

        const testBtn = document.getElementById('test-timeline-btn');
        testBtn?.addEventListener('click', () => this.testTimeline());

        // Auto-update when timeline changes
        document.addEventListener('timelineLoaded', (event) => {
            this.analyzeTimeline(event.detail.timeline);
        });

        document.addEventListener('clipChanged', (event) => {
            this.updateCurrentState(event.detail);
        });
    }

    toggle() {
        if (this.isVisible) {
            this.hide();
        } else {
            this.show();
        }
    }

    show() {
        this.isVisible = true;
        this.panel.style.display = 'block';
        this.toggleBtn.classList.add('active');
        this.startAutoUpdate();
        this.updateDebugInfo();
    }

    hide() {
        this.isVisible = false;
        this.panel.style.display = 'none';
        this.toggleBtn.classList.remove('active');
        this.stopAutoUpdate();
    }

    startAutoUpdate() {
        this.stopAutoUpdate();
        this.updateInterval = setInterval(() => {
            if (this.isVisible) {
                this.updateDebugInfo();
            }
        }, 1000);
    }

    stopAutoUpdate() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }

    analyzeTimeline(timeline) {
        this.currentTimeline = timeline;
        if (this.isVisible) {
            this.updateDebugInfo();
        }
    }

    updateDebugInfo() {
        if (!this.currentTimeline) {
            this.displayNoTimelineInfo();
            return;
        }

        this.displayTimelineInfo();
        this.displayGapAnalysis();
        this.displayCurrentState();
    }

    displayNoTimelineInfo() {
        this.timelineInfo.innerHTML = `
            <div class="debug-section">
                <h4>Timeline Status</h4>
                <div class="debug-item">
                    <span class="debug-label">Status:</span>
                    <span class="debug-value debug-warning">No timeline loaded</span>
                </div>
            </div>
        `;
        this.clipGaps.innerHTML = '';
        this.currentState.innerHTML = '';
    }

    displayTimelineInfo() {
        const clips = this.currentTimeline.clips || [];
        const totalDuration = this.calculateTotalDuration(clips);
        const timeRange = this.getTimeRange(clips);
        const cameraStats = this.getCameraStats(clips);

        this.timelineInfo.innerHTML = `
            <div class="debug-section">
                <h4>Timeline Overview</h4>
                <div class="debug-item">
                    <span class="debug-label">Total Clips:</span>
                    <span class="debug-value">${clips.length}</span>
                </div>
                <div class="debug-item">
                    <span class="debug-label">Duration:</span>
                    <span class="debug-value">${this.formatDuration(totalDuration)}</span>
                </div>
                <div class="debug-item">
                    <span class="debug-label">Time Range:</span>
                    <span class="debug-value">${timeRange.start} - ${timeRange.end}</span>
                </div>
                <div class="debug-item">
                    <span class="debug-label">Date:</span>
                    <span class="debug-value">${this.currentTimeline.date || 'Unknown'}</span>
                </div>
            </div>
            <div class="debug-section">
                <h4>Camera Coverage</h4>
                ${Object.entries(cameraStats).map(([camera, count]) => `
                    <div class="debug-item">
                        <span class="debug-label">${camera}:</span>
                        <span class="debug-value">${count} clips</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    displayGapAnalysis() {
        const clips = this.currentTimeline.clips || [];
        const gaps = this.detectGaps(clips);
        const missingCameras = this.detectMissingCameras(clips);

        let gapHtml = `
            <div class="debug-section">
                <h4>Gap Analysis</h4>
                <div class="debug-item">
                    <span class="debug-label">Gaps Found:</span>
                    <span class="debug-value ${gaps.length > 0 ? 'debug-warning' : 'debug-success'}">${gaps.length}</span>
                </div>
        `;

        if (gaps.length > 0) {
            gapHtml += `
                <div class="debug-item">
                    <span class="debug-label">Gap Threshold:</span>
                    <span class="debug-value">${this.gapThreshold}s</span>
                </div>
            `;

            gaps.forEach((gap, index) => {
                gapHtml += `
                    <div class="debug-section debug-gap">
                        <h4>Gap #${index + 1}</h4>
                        <div class="debug-item">
                            <span class="debug-label">Start:</span>
                            <span class="debug-value">${gap.startTime}</span>
                        </div>
                        <div class="debug-item">
                            <span class="debug-label">End:</span>
                            <span class="debug-value">${gap.endTime}</span>
                        </div>
                        <div class="debug-item">
                            <span class="debug-label">Duration:</span>
                            <span class="debug-value debug-error">${this.formatDuration(gap.duration)}</span>
                        </div>
                        <div class="debug-item">
                            <span class="debug-label">Reason:</span>
                            <span class="debug-value">${gap.reason}</span>
                        </div>
                    </div>
                `;
            });
        }

        if (missingCameras.length > 0) {
            gapHtml += `
                <div class="debug-section debug-gap">
                    <h4>Missing Camera Data</h4>
                    ${missingCameras.map(missing => `
                        <div class="debug-item">
                            <span class="debug-label">${missing.time}:</span>
                            <span class="debug-value debug-warning">${missing.cameras.join(', ')}</span>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        // Add file size analysis
        const fileSizeIssues = this.analyzeFileSizes(clips);
        if (fileSizeIssues.length > 0) {
            gapHtml += `
                <div class="debug-section debug-gap">
                    <h4>File Size Issues</h4>
                    ${fileSizeIssues.map(issue => `
                        <div class="debug-item">
                            <span class="debug-label">${issue.time}:</span>
                            <span class="debug-value debug-warning">${issue.description}</span>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        gapHtml += '</div>';
        this.clipGaps.innerHTML = gapHtml;
    }

    displayCurrentState() {
        const currentClip = this.getCurrentClip();
        const playbackState = this.getPlaybackState();

        this.currentState.innerHTML = `
            <div class="debug-section">
                <h4>Current State</h4>
                <div class="debug-item">
                    <span class="debug-label">Current Clip:</span>
                    <span class="debug-value">${currentClip ? currentClip.filename : 'None'}</span>
                </div>
                <div class="debug-item">
                    <span class="debug-label">Playback:</span>
                    <span class="debug-value ${playbackState.playing ? 'debug-success' : ''}">${playbackState.playing ? 'Playing' : 'Paused'}</span>
                </div>
                <div class="debug-item">
                    <span class="debug-label">Timeline Pos:</span>
                    <span class="debug-value">${this.formatDuration(playbackState.currentTime)}</span>
                </div>
                <div class="debug-item">
                    <span class="debug-label">Speed:</span>
                    <span class="debug-value">${playbackState.speed}x</span>
                </div>
                <div class="debug-item">
                    <span class="debug-label">Volume:</span>
                    <span class="debug-value">${Math.round(playbackState.volume * 100)}%</span>
                </div>
            </div>
        `;
    }

    detectGaps(clips) {
        if (clips.length < 2) return [];

        const gaps = [];
        const sortedClips = [...clips].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        for (let i = 0; i < sortedClips.length - 1; i++) {
            const currentClip = sortedClips[i];
            const nextClip = sortedClips[i + 1];

            const currentEnd = new Date(currentClip.timestamp).getTime() + (currentClip.duration * 1000);
            const nextStart = new Date(nextClip.timestamp).getTime();
            const gapDuration = (nextStart - currentEnd) / 1000;

            if (gapDuration > this.gapThreshold) {
                gaps.push({
                    startTime: new Date(currentEnd).toLocaleTimeString(),
                    endTime: new Date(nextStart).toLocaleTimeString(),
                    duration: gapDuration,
                    reason: this.determineGapReason(gapDuration, currentClip, nextClip)
                });
            }
        }

        return gaps;
    }

    determineGapReason(duration, clipBefore, clipAfter) {
        // Analyze gap patterns to determine likely cause
        if (duration > 3600) return 'Long break (>1 hour) - Likely parked/off';
        if (duration > 1800) return 'Extended break (>30 min) - Possible parking/charging';
        if (duration > 600) return 'Medium break (>10 min) - Short stop/errand';
        if (duration > 300) return 'Break (>5 min) - Traffic light/brief stop';
        if (duration > 180) return 'Short break (>3 min) - Normal stop';
        if (duration > 120) return 'Brief gap (>2 min) - Possible file issue';
        if (duration > 60) return 'Small gap (>1 min) - Normal Tesla recording gap';
        return 'Missing clip data - Potential SD card/hardware issue';
    }

    detectMissingCameras(clips) {
        const expectedCameras = ['front', 'back', 'left_pillar', 'right_pillar', 'left_repeater', 'right_repeater'];
        const missing = [];

        clips.forEach(clip => {
            // Get available cameras from the files object, not a cameras array
            const availableCameras = clip.files ? Object.keys(clip.files) : [];
            const missingCameras = expectedCameras.filter(cam => !availableCameras.includes(cam));

            if (missingCameras.length > 0) {
                missing.push({
                    time: new Date(clip.timestamp).toLocaleTimeString(),
                    cameras: missingCameras,
                    filename: clip.files ? Object.values(clip.files)[0]?.filename : 'Unknown'
                });
            }
        });

        return missing;
    }

    analyzeFileSizes(clips) {
        const issues = [];
        const expectedSizes = {
            front: { min: 70000000, max: 85000000 }, // ~70-85MB for front camera
            back: { min: 35000000, max: 45000000 },  // ~35-45MB for back camera
            left_pillar: { min: 35000000, max: 45000000 },
            right_pillar: { min: 35000000, max: 45000000 },
            left_repeater: { min: 35000000, max: 45000000 },
            right_repeater: { min: 35000000, max: 45000000 }
        };

        clips.forEach(clip => {
            if (!clip.files) return;

            Object.entries(clip.files).forEach(([camera, file]) => {
                const expected = expectedSizes[camera];
                if (!expected || !file.size) return;

                const size = file.size;
                const time = new Date(clip.timestamp).toLocaleTimeString();

                if (size < expected.min) {
                    issues.push({
                        time: time,
                        camera: camera,
                        description: `${camera} file unusually small (${Math.round(size/1024/1024)}MB)`
                    });
                } else if (size > expected.max) {
                    issues.push({
                        time: time,
                        camera: camera,
                        description: `${camera} file unusually large (${Math.round(size/1024/1024)}MB)`
                    });
                }
            });
        });

        return issues;
    }

    calculateTotalDuration(clips) {
        return clips.reduce((total, clip) => total + (clip.duration || 60), 0);
    }

    getTimeRange(clips) {
        if (clips.length === 0) return { start: 'N/A', end: 'N/A' };

        const times = clips.map(clip => new Date(clip.timestamp).getTime());
        const start = new Date(Math.min(...times)).toLocaleTimeString();
        const end = new Date(Math.max(...times)).toLocaleTimeString();

        return { start, end };
    }

    getCameraStats(clips) {
        const stats = {};
        clips.forEach(clip => {
            // Get cameras from the files object
            const availableCameras = clip.files ? Object.keys(clip.files) : [];
            availableCameras.forEach(camera => {
                stats[camera] = (stats[camera] || 0) + 1;
            });
        });
        return stats;
    }

    getCurrentClip() {
        // Get current clip from the main app
        return window.sentrySixApp?.currentClipGroup || null;
    }

    getPlaybackState() {
        // Get real playback state from the main app
        const app = window.sentrySixApp;
        if (!app) {
            return {
                playing: false,
                currentTime: 0,
                speed: 1,
                volume: 1
            };
        }

        // Get speed from UI
        const speedSelect = document.getElementById('speed-select');
        const speed = speedSelect ? parseFloat(speedSelect.value) : 1;

        // Get volume from UI
        const volumeSlider = document.getElementById('volume-slider');
        const volume = volumeSlider ? volumeSlider.value / 100 : 1;

        // Get current time from timeline
        let currentTime = 0;
        if (app.currentTimeline) {
            currentTime = app.currentTimeline.currentPosition / 1000; // Convert to seconds
        } else {
            currentTime = app.currentTime || 0;
        }

        return {
            playing: app.isPlaying || false,
            currentTime: currentTime,
            speed: speed,
            volume: volume
        };
    }

    formatDuration(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);

        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }

    updateCurrentState(clipData) {
        if (this.isVisible) {
            this.displayCurrentState();
        }
    }

    // Public method to set gap threshold
    setGapThreshold(seconds) {
        this.gapThreshold = seconds;
        if (this.isVisible) {
            this.updateDebugInfo();
        }
    }

    // Public method to export debug data
    exportDebugData() {
        const debugData = {
            timestamp: new Date().toISOString(),
            timeline: this.currentTimeline,
            gaps: this.detectGaps(this.currentTimeline?.clips || []),
            missingCameras: this.detectMissingCameras(this.currentTimeline?.clips || []),
            settings: {
                gapThreshold: this.gapThreshold
            }
        };

        const blob = new Blob([JSON.stringify(debugData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `sentry-six-debug-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }

    // Clear browser console
    clearConsole() {
        console.clear();
        console.log('🐛 Debug console cleared by user');
    }

    // Test timeline positioning
    testTimeline() {
        const app = window.sentrySixApp;
        if (!app) {
            console.log('❌ App not ready');
            return;
        }

        if (!app.currentTimeline) {
            console.log('❌ No timeline loaded. Load a date first.');
            return;
        }

        console.log('🧪 Testing Timeline Positioning:');
        console.log(`Timeline has ${app.currentTimeline.clips.length} clips`);
        console.log(`Timeline has ${app.currentTimeline.segments?.length || 0} segments`);
        console.log(`Timeline has ${app.currentTimeline.gaps?.length || 0} gaps`);
        console.log(`Total duration: ${Math.round(app.currentTimeline.totalDuration / 60000)} minutes`);

        // Check actual clip durations and file sizes
        console.log('\n📊 Clip Duration Analysis:');
        app.currentTimeline.clips.forEach((clip, index) => {
            const timestamp = new Date(clip.timestamp).toLocaleTimeString();
            const duration = clip.duration || 'unknown';
            const frontFileSize = clip.files?.front?.size || 'unknown';
            const hasAllCameras = Object.keys(clip.files || {}).length;

            console.log(`Clip ${index}: ${timestamp} | Duration: ${duration}s | Front file: ${frontFileSize} bytes | Cameras: ${hasAllCameras}`);

            // Flag potentially problematic clips
            if (duration && duration < 50) {
                console.log(`  ⚠️ SHORT CLIP: Only ${duration}s (expected ~60s)`);
            }
            if (frontFileSize && frontFileSize < 1000000) { // Less than 1MB
                console.log(`  ⚠️ SMALL FILE: Only ${frontFileSize} bytes (might be corrupted)`);
            }
        });

        console.log('✅ Timeline test complete - check output above');
    }
}

// Export for use in other modules
window.DebugManager = DebugManager;
