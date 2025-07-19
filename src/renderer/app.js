/**
 * Sentry-Six Electron Renderer
 * Main application logic for the frontend
 */

class SentrySixApp {
    constructor() {
        this.currentClipGroup = null;
        this.clipGroups = [];
        this.isPlaying = false;
        this.currentTime = 0;
        this.duration = 0;
        this.videos = {};
        this.config = {};
        this.currentTimeline = null;
        this.isLoadingClip = false; // Flag to prevent timeline updates during clip loading
        this.isAutoAdvancing = false; // Flag to prevent multiple rapid auto-advancements
        this.isSeekingTimeline = false; // Flag to prevent timeline updates during manual seeking

        this.initializeApp();
    }

    async initializeApp() {
        console.log('Initializing Sentry-Six Electron...');
        
        try {
            // Show loading screen
            this.showLoadingScreen('Initializing application...');
            
            // Load configuration
            await this.loadConfiguration();
            
            // Initialize UI components
            this.initializeUI();
            
            // Set up event listeners
            this.setupEventListeners();
            
            // Initialize video players
            this.initializeVideoPlayers();

            // Initialize debug manager
            this.initializeDebugManager();

            // Hide loading screen
            this.hideLoadingScreen();
            
            console.log('Sentry-Six Electron initialized successfully');
            
        } catch (error) {
            console.error('Failed to initialize application:', error);
            this.showError('Failed to initialize application', error.message);
        }
    }

    async loadConfiguration() {
        try {
            // For now, use default configuration
            this.config = {
                defaultVolume: 0.5,
                playbackSpeed: 1.0,
                autoPlay: false
            };
            console.log('Configuration loaded:', this.config);
        } catch (error) {
            console.error('Failed to load configuration:', error);
            this.config = {}; // Use defaults
        }
    }

    initializeUI() {
        // Set up timestamp display
        this.updateTimestampDisplay();
        
        // Set up volume from config
        const volumeSlider = document.getElementById('volume-slider');
        if (volumeSlider && this.config.defaultVolume !== undefined) {
            volumeSlider.value = this.config.defaultVolume;
        }
        
        // Set up playback speed from config
        const speedSelect = document.getElementById('speed-select');
        if (speedSelect && this.config.playbackSpeed !== undefined) {
            speedSelect.value = this.config.playbackSpeed;
        }
    }

    setupEventListeners() {
        // Folder selection
        const openFolderBtn = document.getElementById('open-folder-btn');
        openFolderBtn.addEventListener('click', () => this.selectTeslaFolder());

        // Playback controls
        const playPauseBtn = document.getElementById('play-pause-btn');
        playPauseBtn.addEventListener('click', () => this.togglePlayPause());

        const stopBtn = document.getElementById('stop-btn');
        stopBtn.addEventListener('click', () => this.stopPlayback());

        const prevClipBtn = document.getElementById('prev-clip-btn');
        prevClipBtn.addEventListener('click', () => this.previousClip());

        const nextClipBtn = document.getElementById('next-clip-btn');
        nextClipBtn.addEventListener('click', () => this.manualNextClip());

        // Timeline scrubber
        const timelineScrubber = document.getElementById('timeline-scrubber');
        timelineScrubber.addEventListener('input', (e) => this.seekToPosition(e.target.value));
        timelineScrubber.addEventListener('mousedown', () => {
            this.isSeekingTimeline = true;
            console.log('🎯 Started seeking');
        });
        timelineScrubber.addEventListener('mouseup', () => {
            // Keep seeking flag for a bit longer to prevent immediate override
            setTimeout(() => {
                this.isSeekingTimeline = false;
                console.log('🎯 Finished seeking');
            }, 500);
        });
        timelineScrubber.addEventListener('touchstart', () => this.isSeekingTimeline = true);
        timelineScrubber.addEventListener('touchend', () => {
            setTimeout(() => {
                this.isSeekingTimeline = false;
            }, 500);
        });

        // Speed control
        const speedSelect = document.getElementById('speed-select');
        speedSelect.addEventListener('change', (e) => this.setPlaybackSpeed(parseFloat(e.target.value)));

        // Volume control
        const volumeSlider = document.getElementById('volume-slider');
        volumeSlider.addEventListener('input', (e) => this.setVolume(parseFloat(e.target.value)));

        // Settings button
        const settingsBtn = document.getElementById('settings-btn');
        settingsBtn.addEventListener('click', () => this.openSettings());

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));

        // Listen for folder selection from main process
        window.electronAPI.on('folder-selected', (folderPath) => {
            this.loadTeslaFolder(folderPath);
        });
    }

    initializeVideoPlayers() {
        const cameras = ['left_pillar', 'front', 'right_pillar', 'left_repeater', 'back', 'right_repeater'];
        
        cameras.forEach(camera => {
            const video = document.getElementById(`video-${camera}`);
            if (video) {
                this.videos[camera] = video;
                
                // Set up video event listeners
                video.addEventListener('loadedmetadata', () => this.onVideoLoaded(camera));
                video.addEventListener('timeupdate', () => this.onVideoTimeUpdate(camera));
                video.addEventListener('ended', () => this.onVideoEnded(camera));
                video.addEventListener('error', (e) => this.onVideoError(camera, e));
                
                // Set initial volume
                video.volume = this.config.defaultVolume || 0.5;
                video.muted = true; // Start muted for auto-play compatibility
            }
        });
    }

    initializeDebugManager() {
        try {
            // Initialize debug manager
            this.debugManager = new DebugManager();
            console.log('Debug manager initialized successfully');
        } catch (error) {
            console.error('Failed to initialize debug manager:', error);
        }
    }

    async selectTeslaFolder() {
        try {
            this.showLoadingIndicator(true);

            const result = await window.electronAPI.tesla.selectFolder();

            if (result && result.success && result.videoFiles) {
                this.clipSections = result.videoFiles;
                this.renderCollapsibleClipList();

                // Count total clips across all sections
                let totalClips = 0;
                for (const sectionName in this.clipSections) {
                    for (const dateGroup of this.clipSections[sectionName]) {
                        totalClips += dateGroup.totalClips;
                    }
                }

                console.log(`Loaded ${totalClips} clips organized into sections from ${result.path}`);
                this.showStatus(`Found ${totalClips} Tesla video clips`);
            } else {
                console.log('No folder selected or no videos found');
                this.showStatus('No Tesla videos found in selected folder');
            }

        } catch (error) {
            console.error('Failed to select Tesla folder:', error);
            this.showError('Failed to load Tesla folder', error.message);
        } finally {
            this.showLoadingIndicator(false);
        }
    }

    async loadTeslaFolder(folderPath) {
        try {
            this.showLoadingIndicator(true);
            
            const clipGroups = await window.electronAPI.tesla.getVideoFiles(folderPath);
            
            if (clipGroups && clipGroups.length > 0) {
                this.clipGroups = clipGroups;
                this.renderClipList();
                console.log(`Loaded ${clipGroups.length} clip groups from ${folderPath}`);
            }
            
        } catch (error) {
            console.error('Failed to load Tesla folder:', error);
            this.showError('Failed to load Tesla folder', error.message);
        } finally {
            this.showLoadingIndicator(false);
        }
    }

    renderClipList() {
        const clipList = document.getElementById('clip-list');
        
        if (this.clipGroups.length === 0) {
            clipList.innerHTML = `
                <div class="no-clips-message">
                    <p>No Tesla clips found</p>
                    <p>Make sure you selected a valid Tesla dashcam folder</p>
                </div>
            `;
            return;
        }

        const clipItems = this.clipGroups.map((clipGroup, index) => {
            const timestamp = new Date(clipGroup.timestamp);
            const timeString = timestamp.toLocaleString();
            const availableCameras = Object.keys(clipGroup.files);
            
            return `
                <div class="clip-item" data-index="${index}">
                    <div class="clip-time">${timeString}</div>
                    <div class="clip-type">${clipGroup.type}</div>
                    <div class="clip-cameras">
                        ${availableCameras.map(camera => 
                            `<span class="camera-badge available">${this.getCameraDisplayName(camera)}</span>`
                        ).join('')}
                    </div>
                </div>
            `;
        }).join('');

        clipList.innerHTML = clipItems;

        // Add click listeners to clip items
        clipList.querySelectorAll('.clip-item').forEach(item => {
            item.addEventListener('click', () => {
                const index = parseInt(item.dataset.index);
                this.selectClipGroup(index);
            });
        });
    }

    renderCollapsibleClipList() {
        const clipList = document.getElementById('clip-list');

        if (!this.clipSections || Object.keys(this.clipSections).length === 0) {
            clipList.innerHTML = `
                <div class="no-clips-message">
                    <p>No Tesla clips found</p>
                    <p>Make sure you selected the correct Tesla dashcam folder</p>
                </div>
            `;
            return;
        }

        let sectionsHtml = '';

        for (const [sectionName, dateGroups] of Object.entries(this.clipSections)) {
            if (dateGroups.length === 0) continue;

            const totalClips = dateGroups.reduce((sum, group) => sum + group.totalClips, 0);

            sectionsHtml += `
                <div class="clip-section">
                    <div class="section-header collapsed" data-section="${sectionName}">
                        <span class="section-toggle">▼</span>
                        <span class="section-title">${sectionName}</span>
                        <span class="section-count">${totalClips}</span>
                    </div>
                    <div class="section-content collapsed" data-section-content="${sectionName}">
                        ${this.renderDateGroups(dateGroups, sectionName)}
                    </div>
                </div>
            `;
        }

        clipList.innerHTML = sectionsHtml;
        this.setupCollapsibleHandlers();
    }

    renderDateGroups(dateGroups, sectionName) {
        return dateGroups.map((dateGroup, dateIndex) => {
            // Calculate total duration for the day
            const totalDurationMs = dateGroup.clips.length * 60000; // Assume 60 seconds per clip
            const totalMinutes = Math.floor(totalDurationMs / 60000);
            const totalHours = Math.floor(totalMinutes / 60);
            const remainingMinutes = totalMinutes % 60;

            let durationText = '';
            if (totalHours > 0) {
                durationText = `${totalHours}h ${remainingMinutes}m`;
            } else {
                durationText = `${totalMinutes}m`;
            }

            // Create a single selectable date item (no collapsible clips)
            return `
                <div class="date-item" data-section="${sectionName}" data-date-index="${dateIndex}">
                    <div class="date-title">${dateGroup.displayDate}</div>
                    <div class="date-info">
                        <span class="date-duration">${durationText}</span>
                        <span class="date-count">${dateGroup.totalClips} clips</span>
                    </div>
                </div>
            `;
        }).join('');
    }

    setupCollapsibleHandlers() {
        // Section headers
        document.querySelectorAll('.section-header').forEach(header => {
            header.addEventListener('click', () => {
                const sectionName = header.dataset.section;
                const content = document.querySelector(`[data-section-content="${sectionName}"]`);
                const isCollapsed = content.classList.contains('collapsed');

                if (isCollapsed) {
                    content.classList.remove('collapsed');
                    content.classList.add('expanded');
                    header.classList.remove('collapsed');
                } else {
                    content.classList.remove('expanded');
                    content.classList.add('collapsed');
                    header.classList.add('collapsed');
                }
            });
        });

        // Date items (direct selection, no collapsing)
        document.querySelectorAll('.date-item').forEach(item => {
            item.addEventListener('click', () => {
                const sectionName = item.dataset.section;
                const dateIndex = parseInt(item.dataset.dateIndex);

                this.selectDateTimeline(sectionName, dateIndex);
            });
        });
    }

    selectDateTimeline(sectionName, dateIndex) {
        const dateGroup = this.clipSections[sectionName][dateIndex];

        // Remove previous selection
        document.querySelectorAll('.date-item.active').forEach(item => {
            item.classList.remove('active');
        });

        // Add selection to current item
        const selectedItem = document.querySelector(`[data-section="${sectionName}"][data-date-index="${dateIndex}"]`);
        if (selectedItem) {
            selectedItem.classList.add('active');
        }

        // Create continuous timeline from all clips in the day
        this.loadDailyTimeline(dateGroup);

        console.log('Selected daily timeline:', sectionName, 'date:', dateGroup.displayDate, 'clips:', dateGroup.clips.length);
    }

    loadDailyTimeline(dateGroup) {
        // Create a continuous timeline data structure
        this.currentTimeline = {
            clips: dateGroup.clips,
            currentClipIndex: 0,
            totalDuration: dateGroup.clips.length * 60000, // Assume 60 seconds per clip
            startTime: dateGroup.clips[0]?.timestamp || new Date(),
            isPlaying: false,
            currentPosition: 0, // Global position in milliseconds across all clips
            date: dateGroup.displayDate
        };

        // Notify debug manager of timeline load
        if (this.debugManager) {
            document.dispatchEvent(new CustomEvent('timelineLoaded', {
                detail: { timeline: this.currentTimeline }
            }));
        }

        // Load the first clip
        this.loadTimelineClip(0);

        // Update timeline UI with gap indicators
        this.updateTimelineDisplay();
        this.renderTimelineGaps();
    }

    loadTimelineClip(clipIndex) {
        if (!this.currentTimeline || clipIndex >= this.currentTimeline.clips.length) {
            return;
        }

        const clip = this.currentTimeline.clips[clipIndex];
        this.currentTimeline.currentClipIndex = clipIndex;

        // Set as current clip group for compatibility with existing video loading
        this.currentClipGroup = clip;
        this.loadClipGroupVideos(clip);

        console.log(`Loaded timeline clip ${clipIndex + 1}/${this.currentTimeline.clips.length}`);

        // Notify debug manager of clip change
        if (this.debugManager) {
            document.dispatchEvent(new CustomEvent('clipChanged', {
                detail: {
                    clip: clip,
                    clipIndex: clipIndex,
                    totalClips: this.currentTimeline.clips.length
                }
            }));
        }
    }

    createTimelineSegments(clips) {
        if (clips.length === 0) return [];

        const segments = [];
        let currentSegment = {
            startIndex: 0,
            endIndex: 0,
            startTime: new Date(clips[0].timestamp),
            endTime: new Date(clips[0].timestamp),
            duration: 60, // Each clip is 60 seconds
            clipCount: 1
        };

        const sortedClips = [...clips].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        for (let i = 1; i < sortedClips.length; i++) {
            const prevTime = new Date(sortedClips[i - 1].timestamp);
            const currentTime = new Date(sortedClips[i].timestamp);
            const gap = (currentTime - prevTime) / 1000; // seconds

            console.log(`🧩 Segment check: ${prevTime.toLocaleTimeString()} -> ${currentTime.toLocaleTimeString()}: ${gap}s gap`);

            // If gap is larger than 2 minutes, start a new segment
            if (gap > 120) {
                console.log(`🔄 Starting new segment due to ${Math.round(gap / 60)} minute gap`);
                // Finalize current segment - duration is number of clips * 60 seconds
                currentSegment.endIndex = i - 1;
                currentSegment.endTime = prevTime;
                currentSegment.duration = currentSegment.clipCount * 60; // 60 seconds per clip
                segments.push(currentSegment);

                console.log(`📊 Segment ${segments.length}: ${currentSegment.clipCount} clips, ${currentSegment.duration}s duration`);

                // Start new segment
                currentSegment = {
                    startIndex: i,
                    endIndex: i,
                    startTime: currentTime,
                    endTime: currentTime,
                    duration: 60, // Start with 60 seconds for first clip
                    clipCount: 1
                };
            } else {
                // Continue current segment
                currentSegment.endIndex = i;
                currentSegment.endTime = currentTime;
                currentSegment.clipCount++;
                currentSegment.duration = currentSegment.clipCount * 60; // Update duration
            }
        }

        // Add the final segment
        currentSegment.duration = currentSegment.clipCount * 60; // Final duration calculation
        segments.push(currentSegment);

        console.log(`📊 Final Segment ${segments.length}: ${currentSegment.clipCount} clips, ${currentSegment.duration}s duration`);

        return segments;
    }

    calculateActualDuration(segments) {
        // Calculate total duration of actual available footage
        return segments.reduce((total, segment) => total + segment.duration, 0) * 1000; // milliseconds
    }

    calculateCoverage(segments) {
        if (segments.length === 0) return 0;

        const firstTime = segments[0].startTime;
        const lastTime = segments[segments.length - 1].endTime;
        const totalTimeSpan = (lastTime - firstTime) / 1000; // seconds
        const actualFootage = segments.reduce((total, segment) => total + segment.duration, 0);

        return totalTimeSpan > 0 ? (actualFootage / totalTimeSpan) * 100 : 100;
    }

    detectTimelineGaps(clips) {
        const gaps = [];
        const sortedClips = [...clips].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        for (let i = 0; i < sortedClips.length - 1; i++) {
            const currentClip = sortedClips[i];
            const nextClip = sortedClips[i + 1];
            const currentTime = new Date(currentClip.timestamp);
            const nextTime = new Date(nextClip.timestamp);

            // Calculate actual gap (time between clip starts minus expected clip duration)
            const timeBetweenClips = (nextTime - currentTime) / 1000; // seconds
            const expectedInterval = 60; // Tesla clips are typically 60 seconds
            const gapDuration = timeBetweenClips - expectedInterval;

            console.log(`🔍 Gap Detection: ${currentTime.toLocaleTimeString()} -> ${nextTime.toLocaleTimeString()}: ${timeBetweenClips}s interval, ${gapDuration}s gap`);

            if (gapDuration > 120) { // Gaps larger than 2 minutes
                gaps.push({
                    startTime: new Date(currentTime.getTime() + 60000), // End of current clip
                    endTime: nextTime,
                    duration: gapDuration,
                    beforeClipIndex: i,
                    afterClipIndex: i + 1
                });
                console.log(`📍 Gap detected: ${Math.round(gapDuration / 60)} minutes`);
            }
        }

        return gaps;
    }

    calculateFootagePosition(clipIndex, timeInClip) {
        // Calculate position within available footage (excluding gaps)
        if (!this.currentTimeline || !this.currentTimeline.segments) {
            return clipIndex * 60000 + timeInClip; // Fallback to old method
        }

        let footagePosition = 0;
        const segments = this.currentTimeline.segments;

        // Find which segment contains the current clip
        for (let i = 0; i < segments.length; i++) {
            const segment = segments[i];

            if (clipIndex >= segment.startIndex && clipIndex <= segment.endIndex) {
                // Current clip is in this segment
                const clipsBeforeInSegment = clipIndex - segment.startIndex;
                const positionInSegment = (clipsBeforeInSegment * 60000) + timeInClip;
                const result = footagePosition + positionInSegment;

                console.log(`📍 Clip ${clipIndex} in segment ${i + 1}: ${clipsBeforeInSegment} clips before + ${Math.round(timeInClip/1000)}s = ${Math.round(result/1000)}s total`);
                return result;
            } else if (clipIndex > segment.endIndex) {
                // Current clip is after this segment, add full segment duration
                footagePosition += segment.duration * 1000; // Convert to milliseconds
                console.log(`⏭️ Adding segment ${i + 1} duration: ${segment.duration}s, total now: ${Math.round(footagePosition/1000)}s`);
            } else {
                // Current clip is before this segment (shouldn't happen)
                break;
            }
        }

        return footagePosition;
    }

    getCameraDisplayName(camera) {
        const displayNames = {
            'front': 'Front',
            'left_repeater': 'Left Rep',
            'right_repeater': 'Right Rep',
            'left_pillar': 'Left Pil',
            'right_pillar': 'Right Pil',
            'back': 'Back'
        };
        return displayNames[camera] || camera;
    }

    async selectClipGroup(index) {
        if (index < 0 || index >= this.clipGroups.length) {
            return;
        }

        try {
            // Update UI to show selected clip
            document.querySelectorAll('.clip-item').forEach((item, i) => {
                item.classList.toggle('active', i === index);
            });

            this.currentClipGroup = this.clipGroups[index];
            
            // Load videos for this clip group
            await this.loadClipGroupVideos(this.currentClipGroup);
            
            console.log('Selected clip group:', this.currentClipGroup);
            
        } catch (error) {
            console.error('Failed to select clip group:', error);
            this.showError('Failed to load clip', error.message);
        }
    }

    async loadClipGroupVideos(clipGroup) {
        const cameras = ['left_pillar', 'front', 'right_pillar', 'left_repeater', 'back', 'right_repeater'];

        // Reset all videos first
        cameras.forEach(camera => {
            const video = this.videos[camera];
            const overlay = video.parentElement.querySelector('.video-overlay');

            if (clipGroup.files[camera]) {
                // Load video file
                video.src = `file://${clipGroup.files[camera].path}`;
                overlay.style.display = 'none';

                // Set up event listeners for continuous playback
                video.removeEventListener('ended', this.handleVideoEnded);
                video.addEventListener('ended', this.handleVideoEnded.bind(this));

                // Set up time update for timeline tracking
                video.removeEventListener('timeupdate', this.handleTimeUpdate);
                video.addEventListener('timeupdate', this.handleTimeUpdate.bind(this));

            } else {
                // No video for this camera
                video.src = '';
                overlay.style.display = 'flex';
                overlay.querySelector('.video-status').textContent = 'No video available';
            }
        });

        // Update duration - use timeline duration if available, otherwise single clip duration
        if (this.currentTimeline) {
            this.duration = this.currentTimeline.totalDuration / 1000; // Convert to seconds
        } else {
            this.duration = clipGroup.duration || 60; // Default 60 seconds if unknown
        }

        this.updateTimelineDisplay();
    }

    handleVideoEnded() {
        // Prevent multiple rapid auto-advancements
        if (this.isAutoAdvancing) {
            console.log('🚫 Auto-advancement already in progress, ignoring video ended event');
            return;
        }

        // Auto-advance using the same logic as manual (which works!)
        if (this.currentTimeline && this.currentTimeline.currentClipIndex < this.currentTimeline.clips.length - 1) {
            console.log('Auto-advancing to next clip using working manual logic');
            this.autoAdvanceToNextClip();
        } else {
            console.log('Reached end of timeline');
            this.pauseAllVideos();
        }
    }

    manualNextClip() {
        if (!this.currentTimeline) {
            console.log('No timeline loaded');
            return;
        }

        const currentClipIndex = this.currentTimeline.currentClipIndex;
        const nextClipIndex = currentClipIndex + 1;

        if (nextClipIndex >= this.currentTimeline.clips.length) {
            console.log('Already at last clip');
            return;
        }

        console.log(`🎬 Manually advancing from clip ${currentClipIndex + 1} to clip ${nextClipIndex + 1}`);

        // Simply load the next clip and start from beginning
        this.loadTimelineClip(nextClipIndex);

        // Start playing the new clip from time 0
        setTimeout(() => {
            Object.keys(this.videos).forEach(camera => {
                const video = this.videos[camera];
                if (video && video.src) {
                    video.currentTime = 0;
                    video.play();
                }
            });
        }, 200);
    }

    autoAdvanceToNextClip() {
        // Set lock to prevent multiple rapid advancements
        this.isAutoAdvancing = true;

        // Use the EXACT same logic as manual advancement (which works!)
        if (!this.currentTimeline) {
            console.log('No timeline loaded');
            this.isAutoAdvancing = false;
            return;
        }

        const currentClipIndex = this.currentTimeline.currentClipIndex;
        const nextClipIndex = currentClipIndex + 1;

        if (nextClipIndex >= this.currentTimeline.clips.length) {
            console.log('Already at last clip');
            this.isAutoAdvancing = false;
            return;
        }

        // Load next clip
        this.loadTimelineClip(nextClipIndex);

        // Continue playing if we were playing
        setTimeout(() => {
            this.playAllVideos();

            // Release lock after advancement is complete
            setTimeout(() => {
                this.isAutoAdvancing = false;
            }, 1000);
        }, 200);
    }

    handleTimeUpdate(event) {
        // Don't update timeline position while user is seeking
        if (this.isSeekingTimeline) {
            console.log('🚫 Blocked timeline update during seeking');
            return;
        }

        if (this.currentTimeline) {
            // Calculate global position across all clips
            const currentClipTime = event.target.currentTime * 1000; // Convert to milliseconds
            const clipsBeforeCurrent = this.currentTimeline.currentClipIndex;
            const globalPosition = (clipsBeforeCurrent * 60000) + currentClipTime; // Assume 60s per clip

            this.currentTimeline.currentPosition = globalPosition;
            this.updateTimelineDisplay();
        } else {
            // Single clip mode - update current time
            this.currentTime = event.target.currentTime;
            this.updateTimelineDisplay();
        }
    }

    advanceToNextClip() {
        if (!this.currentTimeline) return;

        const nextClipIndex = this.currentTimeline.currentClipIndex + 1;
        if (nextClipIndex < this.currentTimeline.clips.length) {
            const wasPlaying = this.isPlaying;

            // Load next clip
            this.loadTimelineClip(nextClipIndex);

            // Continue playing if we were playing
            if (wasPlaying) {
                // Small delay to ensure video is loaded
                setTimeout(() => {
                    this.playAllVideos();
                }, 100);
            }
        }
    }

    advanceToNextAvailableClip() {
        if (!this.currentTimeline) return;

        const currentClipIndex = this.currentTimeline.currentClipIndex;
        const nextClipIndex = currentClipIndex + 1;

        if (nextClipIndex >= this.currentTimeline.clips.length) {
            console.log('Reached end of available clips');
            this.pauseAllVideos();
            return;
        }

        console.log(`🎬 Advancing from clip ${currentClipIndex + 1} to clip ${nextClipIndex + 1}`);

        // Calculate position based on actual durations of clips so far
        let currentPosition = 0;
        for (let i = 0; i < currentClipIndex; i++) {
            const clipDuration = (this.currentTimeline.clips[i].duration || 60) * 1000;
            currentPosition += clipDuration;
        }
        // Add the full duration of the clip that just ended
        const endedClipDuration = (this.currentTimeline.clips[currentClipIndex].duration || 60) * 1000;
        currentPosition += endedClipDuration;

        console.log(`📊 Position calculation: ${currentClipIndex + 1} clips completed = ${Math.round(currentPosition/1000)}s`);

        // Simply load the next clip
        const wasPlaying = this.isPlaying;
        this.loadTimelineClip(nextClipIndex);

        // AGGRESSIVELY force all videos to time 0 and start playing immediately
        if (wasPlaying) {
            setTimeout(() => {
                console.log(`🚀 FORCING all videos to time 0 and immediate playback`);

                // Force every video to time 0
                Object.keys(this.videos).forEach(camera => {
                    const video = this.videos[camera];
                    if (video && video.src) {
                        video.currentTime = 0;
                        console.log(`🎯 FORCED ${camera} to time 0`);
                    }
                });

                // Force immediate playback
                this.playAllVideos();

                // Double-check after a short delay
                setTimeout(() => {
                    Object.keys(this.videos).forEach(camera => {
                        const video = this.videos[camera];
                        if (video && video.src && video.currentTime > 5) {
                            console.log(`⚠️ ${camera} jumped to ${video.currentTime}s - forcing back to 0`);
                            video.currentTime = 0;
                        }
                    });
                }, 100);

            }, 100);
        }
    }

    // Playback Control Methods
    async togglePlayPause() {
        if (this.isPlaying) {
            this.pauseAllVideos();
        } else {
            this.playAllVideos();
        }
    }

    async playAllVideos() {
        if (!this.currentClipGroup) {
            console.warn('No clip group selected');
            return;
        }

        try {
            const playPromises = Object.keys(this.currentClipGroup.files).map(camera => {
                const video = this.videos[camera];
                if (video && video.src) {
                    return video.play();
                }
                return Promise.resolve();
            });

            await Promise.all(playPromises);
            this.isPlaying = true;
            this.updatePlayPauseButton();

            // Start time update loop
            this.startTimeUpdateLoop();

        } catch (error) {
            console.error('Failed to play videos:', error);
            this.showError('Playback Error', 'Failed to start video playback');
        }
    }

    pauseAllVideos() {
        Object.keys(this.videos).forEach(camera => {
            const video = this.videos[camera];
            if (video && !video.paused) {
                video.pause();
            }
        });

        this.isPlaying = false;
        this.updatePlayPauseButton();
        this.stopTimeUpdateLoop();
    }

    stopPlayback() {
        this.pauseAllVideos();
        this.seekToPosition(0);
    }

    seekToPosition(position) {
        console.log(`🎯 Seeking to position ${position}%`);
        if (this.currentTimeline) {
            // Timeline mode - seek across entire day
            const targetPositionMs = (position / 100) * this.currentTimeline.totalDuration;
            console.log(`🎯 Target position: ${Math.round(targetPositionMs/1000)}s`);
            this.seekToGlobalPosition(targetPositionMs);
        } else {
            // Single clip mode
            const timeInSeconds = (position / 100) * this.duration;

            Object.keys(this.videos).forEach(camera => {
                const video = this.videos[camera];
                if (video && video.src) {
                    video.currentTime = timeInSeconds;
                }
            });

            this.currentTime = timeInSeconds;
            this.updateTimelineDisplay();
        }
    }

    seekToActualPosition(targetPositionMs) {
        if (!this.currentTimeline || !this.currentTimeline.segments) return;

        // Find which segment and clip contains the target footage position
        let accumulatedDuration = 0;
        let targetSegment = null;
        let targetClipIndex = 0;
        let positionInClip = 0;

        for (let i = 0; i < this.currentTimeline.segments.length; i++) {
            const segment = this.currentTimeline.segments[i];
            const segmentDurationMs = segment.duration * 1000;

            if (targetPositionMs <= accumulatedDuration + segmentDurationMs) {
                targetSegment = segment;
                const positionInSegment = targetPositionMs - accumulatedDuration;

                // Calculate which clip within the segment
                const clipDurationMs = 60000; // Assume 60 seconds per clip
                const clipIndexInSegment = Math.floor(positionInSegment / clipDurationMs);
                positionInClip = positionInSegment % clipDurationMs;

                // Calculate absolute clip index
                targetClipIndex = Math.min(segment.startIndex + clipIndexInSegment, segment.endIndex);
                break;
            }

            accumulatedDuration += segmentDurationMs;
        }

        if (!targetSegment) {
            // Target position is beyond available footage, go to last clip
            const lastSegment = this.currentTimeline.segments[this.currentTimeline.segments.length - 1];
            targetClipIndex = lastSegment.endIndex;
            positionInClip = 60000; // End of clip
        }

        // Load the target clip if different from current
        if (targetClipIndex !== this.currentTimeline.currentClipIndex) {
            const wasPlaying = this.isPlaying;
            this.loadTimelineClip(targetClipIndex);

            // Seek to position after clip loads
            setTimeout(() => {
                this.seekWithinCurrentClip(positionInClip / 1000); // Convert to seconds
                if (wasPlaying) {
                    this.playAllVideos();
                }
            }, 100);
        } else {
            // Same clip, just seek within it
            this.seekWithinCurrentClip(positionInClip / 1000);
        }

        // Update timeline position to exact target (footage position)
        this.currentTimeline.currentPosition = targetPositionMs;
        this.updateTimelineDisplay();
    }

    seekWithinCurrentClip(timeInSeconds) {
        Object.keys(this.videos).forEach(camera => {
            const video = this.videos[camera];
            if (video && !isNaN(video.duration)) {
                video.currentTime = Math.min(timeInSeconds, video.duration);
            }
        });
    }

    seekToGlobalPosition(globalPositionMs) {
        if (!this.currentTimeline) return;

        // Calculate which clip and position within clip
        const clipDurationMs = 60000; // Assume 60 seconds per clip
        const targetClipIndex = Math.floor(globalPositionMs / clipDurationMs);
        const positionInClipMs = globalPositionMs % clipDurationMs;

        // Ensure target clip index is valid
        const validClipIndex = Math.min(targetClipIndex, this.currentTimeline.clips.length - 1);

        if (validClipIndex !== this.currentTimeline.currentClipIndex) {
            // Need to switch clips
            const wasPlaying = this.isPlaying;
            this.loadTimelineClip(validClipIndex);

            // Seek to position after clip loads
            setTimeout(() => {
                const cameras = ['left_pillar', 'front', 'right_pillar', 'left_repeater', 'back', 'right_repeater'];
                cameras.forEach(camera => {
                    const video = this.videos[camera];
                    if (video && video.src) {
                        video.currentTime = positionInClipMs / 1000;
                    }
                });

                if (wasPlaying) {
                    this.playAllVideos();
                }
            }, 200);
        } else {
            // Same clip - just seek
            const cameras = ['left_pillar', 'front', 'right_pillar', 'left_repeater', 'back', 'right_repeater'];
            cameras.forEach(camera => {
                const video = this.videos[camera];
                if (video && video.src) {
                    video.currentTime = positionInClipMs / 1000;
                }
            });
        }

        this.currentTimeline.currentPosition = globalPositionMs;
        this.updateTimelineDisplay();
    }

    setPlaybackSpeed(speed) {
        Object.keys(this.videos).forEach(camera => {
            const video = this.videos[camera];
            if (video) {
                video.playbackRate = speed;
            }
        });

        // Save to config (disabled for now)
        // window.electronAPI.config.set('playbackSpeed', speed);
    }

    setVolume(volume) {
        Object.keys(this.videos).forEach(camera => {
            const video = this.videos[camera];
            if (video) {
                video.volume = volume;
                video.muted = volume === 0;
            }
        });

        // Save to config (disabled for now)
        // window.electronAPI.config.set('defaultVolume', volume);
    }

    previousClip() {
        if (!this.currentClipGroup) return;

        const currentIndex = this.clipGroups.indexOf(this.currentClipGroup);
        if (currentIndex > 0) {
            this.selectClipGroup(currentIndex - 1);
        }
    }

    nextClip() {
        if (!this.currentClipGroup) return;

        const currentIndex = this.clipGroups.indexOf(this.currentClipGroup);
        if (currentIndex < this.clipGroups.length - 1) {
            this.selectClipGroup(currentIndex + 1);
        }
    }

    // Video Event Handlers
    onVideoLoaded(camera) {
        const video = this.videos[camera];
        console.log(`Video loaded for ${camera}: ${video.duration}s`);

        // Update duration if this video is longer
        if (video.duration > this.duration) {
            this.duration = video.duration;
            this.updateTimelineDisplay();
        }
    }

    recalculateTimelineDuration() {
        if (!this.currentTimeline) return;

        // Calculate total duration using actual clip durations where available
        const totalDuration = this.currentTimeline.clips.reduce((total, clip) => {
            return total + ((clip.duration || 60) * 1000); // Use actual duration or default to 60s
        }, 0);

        const oldDuration = this.currentTimeline.totalDuration;
        this.currentTimeline.totalDuration = totalDuration;

        console.log(`🔄 Timeline duration updated: ${Math.round(oldDuration/60000)}min -> ${Math.round(totalDuration/60000)}min`);
    }

    onVideoTimeUpdate(camera) {
        // Use front camera as the reference for time updates
        if (camera === 'front' && !this.isSeekingTimeline) {
            const video = this.videos[camera];
            this.currentTime = video.currentTime;
            this.updateTimelineDisplay();
        }
    }

    onVideoEnded(camera) {
        console.log(`Video ended for ${camera}`);

        // If all videos have ended, stop playback
        const allEnded = Object.keys(this.videos).every(cam => {
            const video = this.videos[cam];
            return !video.src || video.ended;
        });

        if (allEnded) {
            this.isPlaying = false;
            this.updatePlayPauseButton();
            this.stopTimeUpdateLoop();
        }
    }

    onVideoError(camera, error) {
        console.error(`Video error for ${camera}:`, error);

        const video = this.videos[camera];
        const overlay = video.parentElement.querySelector('.video-overlay');
        overlay.style.display = 'flex';
        overlay.querySelector('.video-status').textContent = 'Error loading video';
    }

    // UI Update Methods
    updatePlayPauseButton() {
        const playPauseBtn = document.getElementById('play-pause-btn');
        const icon = playPauseBtn.querySelector('.icon');

        if (this.isPlaying) {
            icon.textContent = '⏸️';
            playPauseBtn.title = 'Pause';
        } else {
            icon.textContent = '▶️';
            playPauseBtn.title = 'Play';
        }
    }

    updateTimelineDisplay() {
        // Update timeline scrubber
        const timelineScrubber = document.getElementById('timeline-scrubber');

        if (this.currentTimeline) {
            // Timeline mode - show position across entire day
            if (this.currentTimeline.totalDuration > 0) {
                const percentage = (this.currentTimeline.currentPosition / this.currentTimeline.totalDuration) * 100;
                timelineScrubber.value = percentage;
            }
        } else {
            // Single clip mode
            if (this.duration > 0) {
                const percentage = (this.currentTime / this.duration) * 100;
                timelineScrubber.value = percentage;
            }
        }

        // Update time display
        const currentTimeEl = document.getElementById('current-time');
        const totalTimeEl = document.getElementById('total-time');

        if (this.currentTimeline) {
            // Timeline mode - show daily timeline format
            const currentSeconds = Math.floor(this.currentTimeline.currentPosition / 1000);
            const totalSeconds = Math.floor(this.currentTimeline.totalDuration / 1000);

            currentTimeEl.textContent = this.formatTimelineTime(currentSeconds);
            totalTimeEl.textContent = this.formatTimelineTime(totalSeconds);
        } else {
            // Single clip mode
            currentTimeEl.textContent = this.formatTime(this.currentTime);
            totalTimeEl.textContent = this.formatTime(this.duration);
        }
    }

    renderTimelineGaps() {
        if (!this.currentTimeline || !this.currentTimeline.gaps) return;

        const timelineTrack = document.querySelector('.timeline-track');
        if (!timelineTrack) return;

        // Remove existing gap indicators
        timelineTrack.querySelectorAll('.gap-indicator, .gap-marker').forEach(el => el.remove());

        // Add compact gap markers between footage segments
        this.currentTimeline.gaps.forEach((gap) => {
            // Create compact gap marker (fixed 2-inch width)
            const gapMarker = document.createElement('div');
            gapMarker.className = 'gap-marker';

            // Position marker between segments (not proportional to gap size)
            const segmentPosition = this.calculateSegmentPosition(gap.beforeClipIndex);
            gapMarker.style.left = `${segmentPosition}%`;

            // Create gap label
            const gapLabel = document.createElement('div');
            gapLabel.className = 'gap-label';
            const gapMinutes = Math.round(gap.duration / 60);
            gapLabel.textContent = `Missing clips from ${gap.startTime.toLocaleTimeString()} - ${gap.endTime.toLocaleTimeString()}`;
            gapLabel.title = `${gapMinutes} minute gap`;

            // Create visual separator
            const gapSeparator = document.createElement('div');
            gapSeparator.className = 'gap-separator';
            gapSeparator.innerHTML = '|===|';

            gapMarker.appendChild(gapLabel);
            gapMarker.appendChild(gapSeparator);
            timelineTrack.appendChild(gapMarker);
        });
    }

    calculateSegmentPosition(clipIndex) {
        // Calculate position based on footage segments, not real time
        if (!this.currentTimeline.segments) return 0;

        let footagePosition = 0;
        for (let segment of this.currentTimeline.segments) {
            if (clipIndex <= segment.endIndex) {
                const positionInSegment = Math.max(0, clipIndex - segment.startIndex);
                const segmentFootage = (positionInSegment / (segment.endIndex - segment.startIndex + 1)) * segment.duration * 1000;
                footagePosition += segmentFootage;
                break;
            } else {
                footagePosition += segment.duration * 1000;
            }
        }

        return (footagePosition / this.currentTimeline.totalDuration) * 100;
    }

    showGapNotification(gapDuration, startTime, endTime) {
        const gapMinutes = Math.round(gapDuration / 60);
        const message = `Skipping ${gapMinutes} minute gap (${startTime.toLocaleTimeString()} - ${endTime.toLocaleTimeString()})`;

        // Create notification element
        const notification = document.createElement('div');
        notification.className = 'gap-notification';
        notification.innerHTML = `
            <div class="gap-notification-content">
                <span class="gap-icon">⏭️</span>
                <span class="gap-message">${message}</span>
            </div>
        `;

        // Add to page
        document.body.appendChild(notification);

        // Show with animation
        setTimeout(() => notification.classList.add('show'), 10);

        // Remove after 3 seconds
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 3000);

        console.log(`Gap notification: ${message}`);
    }

    updateTimelineInfo() {
        if (!this.currentTimeline) return;

        const timelineInfo = document.querySelector('.timeline-info');
        if (!timelineInfo) {
            console.warn('⚠️ Timeline info element not found');
            return;
        }

        const segments = this.currentTimeline.segments || [];
        const gaps = this.currentTimeline.gaps || [];
        const coverage = this.currentTimeline.actualCoverage || 100;

        const infoText = `${this.currentTimeline.clips.length} clips • ${segments.length} segments • ${gaps.length} gaps • ${coverage.toFixed(0)}% coverage`;
        timelineInfo.textContent = infoText;
    }

    formatTimelineTime(totalSeconds) {
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;

        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        } else {
            return `${minutes}:${seconds.toString().padStart(2, '0')}`;
        }
    }

    updateTimestampDisplay() {
        const timestampDisplay = document.getElementById('timestamp-display');

        if (this.currentClipGroup) {
            const timestamp = new Date(this.currentClipGroup.timestamp);
            // Add current playback time to the base timestamp
            timestamp.setSeconds(timestamp.getSeconds() + this.currentTime);

            const formatted = timestamp.toLocaleString('en-US', {
                month: '2-digit',
                day: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: true
            });

            timestampDisplay.textContent = formatted;
        } else {
            timestampDisplay.textContent = '--/--/---- --:--:-- --';
        }
    }

    // Time Update Loop
    startTimeUpdateLoop() {
        if (this.timeUpdateInterval) {
            clearInterval(this.timeUpdateInterval);
        }

        this.timeUpdateInterval = setInterval(() => {
            if (this.isPlaying) {
                this.updateTimestampDisplay();
            }
        }, 100); // Update every 100ms for smooth display
    }

    stopTimeUpdateLoop() {
        if (this.timeUpdateInterval) {
            clearInterval(this.timeUpdateInterval);
            this.timeUpdateInterval = null;
        }
    }

    // Utility Methods
    formatTime(seconds) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.floor(seconds % 60);
        return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
    }

    showLoadingScreen(message) {
        const loadingScreen = document.getElementById('loading-screen');
        const loadingMessage = document.getElementById('loading-message');

        if (message) {
            loadingMessage.textContent = message;
        }

        loadingScreen.classList.remove('hidden');
    }

    hideLoadingScreen() {
        const loadingScreen = document.getElementById('loading-screen');
        loadingScreen.classList.add('hidden');
    }

    showLoadingIndicator(show) {
        const loadingIndicator = document.getElementById('loading-indicator');

        if (show) {
            loadingIndicator.classList.remove('hidden');
        } else {
            loadingIndicator.classList.add('hidden');
        }
    }

    showError(title, message) {
        // Simple error display - could be enhanced with a modal
        console.error(`${title}: ${message}`);
        alert(`${title}\n\n${message}`);
    }

    showStatus(message) {
        console.log('[Status]', message);
        // Could update a status bar in the UI
        const timestampDisplay = document.getElementById('timestamp-display');
        if (timestampDisplay) {
            timestampDisplay.textContent = message;
            setTimeout(() => {
                this.updateTimestampDisplay();
            }, 3000);
        }
    }

    // Keyboard Shortcuts
    handleKeyboardShortcuts(event) {
        // Prevent shortcuts when typing in inputs
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'SELECT') {
            return;
        }

        switch (event.code) {
            case 'Space':
                event.preventDefault();
                this.togglePlayPause();
                break;

            case 'ArrowLeft':
                event.preventDefault();
                if (event.ctrlKey) {
                    this.previousClip();
                } else {
                    // Seek backward 5 seconds
                    const newTime = Math.max(0, this.currentTime - 5);
                    this.seekToPosition((newTime / this.duration) * 100);
                }
                break;

            case 'ArrowRight':
                event.preventDefault();
                if (event.ctrlKey) {
                    this.nextClip();
                } else {
                    // Seek forward 5 seconds
                    const newTime = Math.min(this.duration, this.currentTime + 5);
                    this.seekToPosition((newTime / this.duration) * 100);
                }
                break;

            case 'Home':
                event.preventDefault();
                this.seekToPosition(0);
                break;

            case 'End':
                event.preventDefault();
                this.seekToPosition(100);
                break;

            case 'KeyS':
                if (event.ctrlKey) {
                    event.preventDefault();
                    this.stopPlayback();
                }
                break;
        }
    }

    // Settings
    openSettings() {
        // Placeholder for settings dialog
        console.log('Settings dialog would open here');
        alert('Settings dialog coming soon!');
    }
    // Test function for debugging timeline positioning
    testTimelinePositioning() {
        if (!this.currentTimeline) {
            console.log('❌ No timeline loaded. Load a date first.');
            return;
        }

        console.log('🧪 Testing Timeline Positioning:');
        console.log(`Timeline has ${this.currentTimeline.clips.length} clips`);
        console.log(`Timeline has ${this.currentTimeline.segments.length} segments`);
        console.log(`Timeline has ${this.currentTimeline.gaps.length} gaps`);
        console.log(`Total duration: ${Math.round(this.currentTimeline.totalDuration / 60000)} minutes`);

        // Test footage position calculation for each clip
        this.currentTimeline.clips.forEach((clip, index) => {
            const footagePos = this.calculateFootagePosition(index, 0);
            const timestamp = new Date(clip.timestamp).toLocaleTimeString();
            console.log(`Clip ${index}: ${timestamp} -> Footage position: ${Math.round(footagePos / 1000)}s`);
        });

        // Test what happens when we advance through clips
        console.log('\n🎬 Simulating playback advancement:');
        for (let i = 0; i < Math.min(5, this.currentTimeline.clips.length - 1); i++) {
            const currentClip = this.currentTimeline.clips[i];
            const nextClip = this.currentTimeline.clips[i + 1];
            const currentTime = new Date(currentClip.timestamp);
            const nextTime = new Date(nextClip.timestamp);
            const gap = (nextTime - currentTime) / 1000 - 60;

            const currentFootagePos = this.calculateFootagePosition(i, 60000); // End of current clip
            const nextFootagePos = this.calculateFootagePosition(i + 1, 0); // Start of next clip

            console.log(`${currentTime.toLocaleTimeString()} (${Math.round(currentFootagePos / 1000)}s) -> ${nextTime.toLocaleTimeString()} (${Math.round(nextFootagePos / 1000)}s)`);
            if (gap > 120) {
                console.log(`  📍 Gap: ${Math.round(gap / 60)} minutes - but footage position advances continuously`);
            }
        }
    }
}

// Make test function available globally
window.testTimeline = function() {
    if (window.sentrySixApp) {
        window.sentrySixApp.testTimelinePositioning();
    } else {
        console.log('❌ App not ready');
    }
};

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.sentrySixApp = new SentrySixApp();
});

// Handle app focus/blur for performance
window.addEventListener('focus', () => {
    console.log('App focused');
});

window.addEventListener('blur', () => {
    console.log('App blurred');
    // Could pause videos here to save resources
});
