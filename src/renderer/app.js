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
        this.seekTimeout = null; // Debounce timer for seeking
        this.cameraVisibility = {
            left_pillar: true,
            front: true,
            right_pillar: true,
            left_repeater: true,
            back: true,
            right_repeater: true
        };

        this.initializeApp();
    }

    async initializeApp() {
        console.log('Initializing Sentry-Six Electron...');
        
        try {
            // Show loading screen
            this.showLoadingScreen('Initializing application...');
            
            // Load configuration
            await this.loadConfiguration();
            
            // Onboarding: Show welcome modal if first run or no folder selected
            this.checkOnboarding();
            
            // Initialize UI components
            this.initializeUI();
            
            // Set up event listeners
            this.setupEventListeners();

        // Set up sticky header behavior
        this.setupStickyHeaders();

        // Set up export system
        this.setupExportSystem();
            
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
        // Detect and apply system dark mode preference, and listen for changes
        const applySystemDarkMode = () => {
            if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
                document.body.classList.add('dark');
            } else {
                document.body.classList.remove('dark');
            }
            // Update onboarding modal theme immediately
            if (this.checkOnboarding) this.checkOnboarding();
        };
        applySystemDarkMode();
        if (window.matchMedia) {
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', applySystemDarkMode);
        }
        
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

        // Enable drag-and-drop for camera grid
        this.setupCameraGridDragAndDrop();
        // Setup reset layout button
        const resetBtn = document.getElementById('reset-camera-layout');
        if (resetBtn) {
            resetBtn.onclick = () => this.resetCameraGridLayout();
        }
    }

    resetCameraGridLayout() {
        const grid = document.getElementById('video-grid');
        if (!grid) return;
        const defaultOrder = ['left_pillar', 'front', 'right_pillar', 'left_repeater', 'back', 'right_repeater'];
        const containers = {};
        Array.from(grid.querySelectorAll('.video-container')).forEach(c => {
            containers[c.dataset.camera] = c;
        });
        defaultOrder.forEach(cam => {
            if (containers[cam]) grid.appendChild(containers[cam]);
        });
    }

    setupCameraGridDragAndDrop() {
        const grid = document.getElementById('video-grid');
        if (!grid) return;
        const containers = Array.from(grid.querySelectorAll('.video-container'));
        containers.forEach(container => {
            container.setAttribute('draggable', 'true');
            container.addEventListener('dragstart', (e) => {
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/plain', container.dataset.camera);
                container.classList.add('dragging');
            });
            container.addEventListener('dragend', () => {
                container.classList.remove('dragging');
            });
            container.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                container.classList.add('drag-over');
            });
            container.addEventListener('dragleave', () => {
                container.classList.remove('drag-over');
            });
            container.addEventListener('drop', (e) => {
                e.preventDefault();
                container.classList.remove('drag-over');
                const draggedCamera = e.dataTransfer.getData('text/plain');
                if (!draggedCamera || draggedCamera === container.dataset.camera) return;
                const allContainers = Array.from(grid.querySelectorAll('.video-container'));
                const draggedElem = grid.querySelector(`.video-container[data-camera="${draggedCamera}"]`);
                const targetElem = container;
                const draggedIdx = allContainers.indexOf(draggedElem);
                const targetIdx = allContainers.indexOf(targetElem);
                if (draggedElem && targetElem && draggedIdx !== -1 && targetIdx !== -1 && draggedElem !== targetElem) {
                    // Swap in array
                    const newOrder = [...allContainers];
                    newOrder[draggedIdx] = targetElem;
                    newOrder[targetIdx] = draggedElem;
                    // Re-append in new order
                    newOrder.forEach(el => grid.appendChild(el));
                }
            });
        });
    }

    setupEventListeners() {
        // Folder selection
        const openFolderBtn = document.getElementById('open-folder-btn');
        if (openFolderBtn) openFolderBtn.addEventListener('click', () => this.selectTeslaFolder());

        // Playback controls
        const playPauseBtn = document.getElementById('play-pause-btn');
        if (playPauseBtn) playPauseBtn.addEventListener('click', () => this.togglePlayPause());

        const stopBtn = document.getElementById('stop-btn');
        if (stopBtn) stopBtn.addEventListener('click', () => this.stopPlayback());

        // Frame-by-frame and skip buttons
        const frameBackBtn = document.getElementById('frame-back-btn');
        if (frameBackBtn) frameBackBtn.addEventListener('click', () => this.frameStep(-1));
        const frameForwardBtn = document.getElementById('frame-forward-btn');
        if (frameForwardBtn) frameForwardBtn.addEventListener('click', () => this.frameStep(1));
        const skipBackBtn = document.getElementById('skip-back-15-btn');
        if (skipBackBtn) skipBackBtn.addEventListener('click', () => this.skipSeconds(-15));
        const skipForwardBtn = document.getElementById('skip-forward-15-btn');
        if (skipForwardBtn) skipForwardBtn.addEventListener('click', () => this.skipSeconds(15));

        // Timeline scrubber with debouncing
        const timelineScrubber = document.getElementById('timeline-scrubber');
        if (timelineScrubber) {
            timelineScrubber.addEventListener('input', (e) => this.debouncedSeek(e.target.value));
            timelineScrubber.addEventListener('mousedown', () => {
                this.isSeekingTimeline = true;
                console.log('🎯 Started seeking');
            });
            timelineScrubber.addEventListener('mouseup', () => {
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
        }

        // Speed control
        const speedSelect = document.getElementById('speed-select');
        if (speedSelect) speedSelect.addEventListener('change', (e) => this.setPlaybackSpeed(parseFloat(e.target.value)));

        // Volume control
        const volumeSlider = document.getElementById('volume-slider');
        if (volumeSlider) volumeSlider.addEventListener('input', (e) => this.setVolume(parseFloat(e.target.value)));

        // Settings button
        const settingsBtn = document.getElementById('settings-btn');
        if (settingsBtn) settingsBtn.addEventListener('click', () => this.openSettings());

        // Camera visibility panel
        const cameraToggleBtn = document.getElementById('camera-toggle-btn');
        if (cameraToggleBtn) cameraToggleBtn.addEventListener('click', () => this.toggleCameraPanel());

        const closeCameraPanel = document.getElementById('close-camera-panel');
        if (closeCameraPanel) closeCameraPanel.addEventListener('click', () => this.hideCameraPanel());

        // Camera visibility toggles
        const cameras = ['left_pillar', 'front', 'right_pillar', 'left_repeater', 'back', 'right_repeater'];
        cameras.forEach(camera => {
            const toggle = document.getElementById(`toggle-${camera}`);
            if (toggle) toggle.addEventListener('change', (e) => this.toggleCameraVisibility(camera, e.target.checked));
        });

        // Show/Hide all cameras
        const showAllBtn = document.getElementById('show-all-cameras');
        if (showAllBtn) showAllBtn.addEventListener('click', () => this.showAllCameras());

        const hideAllBtn = document.getElementById('hide-all-cameras');
        if (hideAllBtn) hideAllBtn.addEventListener('click', () => this.hideAllCameras());

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));

        // Listen for folder selection from main process
        if (window.electronAPI && window.electronAPI.on) {
            window.electronAPI.on('folder-selected', (folderPath) => {
                this.loadTeslaFolder(folderPath);
            });
        }
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

    async selectTeslaFolder(fromOnboarding = false, dontShow = false) {
        try {
            this.showLoadingIndicator(true);

            const result = await window.electronAPI.tesla.selectFolder();

            if (result && result.success && result.videoFiles) {
                this.clipSections = result.videoFiles;
                this.renderCollapsibleClipList();
                // Save folder path for onboarding persistence
                localStorage.setItem('teslaFolder', result.path);
                if (dontShow) {
                    localStorage.setItem('onboardingNeverShow', 'true');
                } else {
                    // If user did NOT check 'Don't show again', clear onboarding flags so modal shows next time
                    localStorage.removeItem('onboardingShown');
                    localStorage.removeItem('onboardingNeverShow');
                }
                // Hide onboarding modal only after successful folder selection
                const onboardingModal = document.getElementById('onboarding-modal');
                if (onboardingModal) onboardingModal.classList.add('hidden');

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
            // Calculate total duration for the day using actual clip analysis
            let totalDurationMs = 0;

            // Try to get actual duration from clip analysis if available
            if (dateGroup.actualTotalDuration) {
                totalDurationMs = dateGroup.actualTotalDuration;
            } else {
                // Use filtered clip count for more accurate estimation
                const clipCount = dateGroup.clips.length;

                // Use more realistic estimation for Tesla clips
                // Many Tesla clips are shorter than 60s, especially after corruption filtering
                const estimatedSecondsPerClip = clipCount === 1 ? 35 : 45; // Single clips often shorter
                totalDurationMs = clipCount * estimatedSecondsPerClip * 1000;
            }

            const totalMinutes = Math.floor(totalDurationMs / 60000);
            const totalHours = Math.floor(totalMinutes / 60);
            const remainingMinutes = totalMinutes % 60;

            let durationText = '';
            if (totalHours > 0) {
                durationText = `${totalHours}h ${remainingMinutes}m`;
            } else if (totalMinutes > 0) {
                durationText = `${totalMinutes}m`;
            } else {
                // Show seconds for very short timelines
                const totalSeconds = Math.floor(totalDurationMs / 1000);
                durationText = `${totalSeconds}s`;
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
            totalDuration: dateGroup.clips.length * 60000, // Start with conservative estimate
            displayDuration: dateGroup.clips.length * 60000, // Stable duration for display
            startTime: dateGroup.clips[0]?.timestamp || new Date(),
            isPlaying: false,
            currentPosition: 0, // Global position in milliseconds across all clips
            date: dateGroup.displayDate,
            actualDurations: [], // Store actual clip durations as they load
            loadedClipCount: 0 // Track how many clips have loaded
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

        // Safety timeout to release lock if something goes wrong
        setTimeout(() => {
            if (this.isAutoAdvancing) {
                console.warn('⚠️ Auto-advancement lock timeout - releasing lock');
                this.isAutoAdvancing = false;
            }
        }, 5000); // 5 second timeout

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
            // Calculate global position using actual clip durations
            const currentClipTime = event.target.currentTime * 1000; // Convert to milliseconds
            let globalPosition = 0;

            // Add durations of all clips before current clip
            for (let i = 0; i < this.currentTimeline.currentClipIndex; i++) {
                const actualDuration = this.currentTimeline.actualDurations[i];
                globalPosition += actualDuration || 60000; // Use actual duration or default 60s
            }

            // Add current time within current clip
            globalPosition += currentClipTime;

            this.currentTimeline.currentPosition = globalPosition;
            this.throttledUpdateTimelineDisplay();
        } else {
            // Single clip mode - update current time
            this.currentTime = event.target.currentTime;
            this.throttledUpdateTimelineDisplay();
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
            // Ignore play interruption errors (common during seeking)
            if (error.name === 'AbortError' || error.message.includes('interrupted by a new load request')) {
                console.log('Play request interrupted (normal during seeking)');
                return;
            }

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

    debouncedSeek(position) {
        // Clear any existing seek timeout
        if (this.seekTimeout) {
            clearTimeout(this.seekTimeout);
        }

        // Set a new timeout to seek after user stops dragging
        this.seekTimeout = setTimeout(() => {
            console.log(`🎯 Debounced seek to position ${position}%`);
            this.seekToPosition(position);
        }, 150); // Wait 150ms after user stops dragging
    }

    seekToPosition(position) {
        console.log(`🎯 Seeking to position ${position}%`);
        if (this.currentTimeline) {
            // Timeline mode - seek using stable display duration
            const targetPositionMs = (position / 100) * this.currentTimeline.displayDuration;
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

        // Calculate which clip and position within clip using actual durations
        let accumulatedTime = 0;
        let targetClipIndex = 0;
        let positionInClipMs = globalPositionMs;

        // Find which clip contains the target position
        for (let i = 0; i < this.currentTimeline.clips.length; i++) {
            const clipDuration = this.currentTimeline.actualDurations[i] || 60000; // Use actual or default

            if (accumulatedTime + clipDuration > globalPositionMs) {
                targetClipIndex = i;
                positionInClipMs = globalPositionMs - accumulatedTime;
                break;
            }

            accumulatedTime += clipDuration;
        }

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

        // Update timeline duration dynamically
        if (this.currentTimeline && camera === 'front') {
            const clipIndex = this.currentTimeline.currentClipIndex;
            this.currentTimeline.actualDurations[clipIndex] = video.duration * 1000; // Convert to milliseconds
            this.currentTimeline.loadedClipCount++;

            // Check for truly corrupted clips (extremely short)
            if (video.duration < 1) { // Less than 1 second is likely corrupted
                console.warn(`⚠️ Corrupted clip detected: Clip ${clipIndex + 1} is only ${video.duration}s`);
                this.handleCorruptedClip(clipIndex);
                return;
            }

            // Update dynamic total duration estimate
            this.updateDynamicTimelineDuration();

            console.log(`📏 Clip ${clipIndex + 1} duration: ${video.duration}s | Loaded: ${this.currentTimeline.loadedClipCount}/${this.currentTimeline.clips.length} | Display: ${Math.round(this.currentTimeline.displayDuration/1000)}s | Total: ${Math.round(this.currentTimeline.totalDuration/1000)}s`);
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

    updateDynamicTimelineDuration() {
        if (!this.currentTimeline) return;

        // Calculate current estimate based on what we know so far
        let knownDuration = 0;
        let knownClips = 0;

        // Add up all known clip durations
        for (let i = 0; i < this.currentTimeline.clips.length; i++) {
            const actualDuration = this.currentTimeline.actualDurations[i];
            if (actualDuration !== undefined) {
                knownDuration += actualDuration;
                knownClips++;
            }
        }

        // Always update working duration for calculations
        if (knownClips > 0) {
            if (knownClips === this.currentTimeline.clips.length) {
                // All clips loaded, use exact total
                this.currentTimeline.totalDuration = knownDuration;
                this.currentTimeline.displayDuration = knownDuration;
                console.log(`📏 Final timeline duration: ${Math.round(knownDuration/1000)}s (exact from ${knownClips} clips) - updating display`);
                this.updateTimelineDisplay();

                // Update the sidebar duration display
                this.updateSidebarDuration(knownDuration);
            } else {
                // Estimate based on loaded clips, but also update display for better UX
                const averageDuration = knownDuration / knownClips;
                const unknownClips = this.currentTimeline.clips.length - knownClips;
                const estimatedTotal = knownDuration + (unknownClips * averageDuration);

                this.currentTimeline.totalDuration = estimatedTotal;

                // For small timelines (≤3 clips), wait for all clips before updating display
                // For larger timelines, update when we have most clips loaded
                const shouldUpdateDisplay = this.currentTimeline.clips.length > 3 ?
                    knownClips >= Math.ceil(this.currentTimeline.clips.length * 0.8) :
                    false; // Wait for exact duration on small timelines

                if (shouldUpdateDisplay) {
                    this.currentTimeline.displayDuration = estimatedTotal;
                    console.log(`📏 Estimated timeline duration: ${Math.round(estimatedTotal/1000)}s (from ${knownClips}/${this.currentTimeline.clips.length} clips, avg: ${Math.round(averageDuration/1000)}s)`);
                    this.updateTimelineDisplay();
                } else {
                    console.log(`📏 Calculated estimate: ${Math.round(estimatedTotal/1000)}s (waiting for more clips before updating display)`);
                }
            }
        }
    }

    onVideoTimeUpdate(camera) {
        // Use front camera as the reference for time updates
        if (camera === 'front' && !this.isSeekingTimeline) {
            const video = this.videos[camera];
            this.currentTime = video.currentTime;
            this.throttledUpdateTimelineDisplay();
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
        // Prevent infinite loops
        if (this.isUpdatingDisplay) {
            return;
        }
        this.isUpdatingDisplay = true;

        // Update timeline scrubber
        const timelineScrubber = document.getElementById('timeline-scrubber');

        if (this.currentTimeline) {
            // Timeline mode - use stable display duration for consistent scrubber
            if (this.currentTimeline.displayDuration > 0) {
                const percentage = Math.min(100, Math.max(0,
                    (this.currentTimeline.currentPosition / this.currentTimeline.displayDuration) * 100
                ));
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
            // Timeline mode - use stable display duration for consistent time display
            const currentSeconds = Math.floor(this.currentTimeline.currentPosition / 1000);
            const totalSeconds = Math.floor(this.currentTimeline.displayDuration / 1000);

            // Use simple time format for timeline (like video players)
            currentTimeEl.textContent = this.formatTime(currentSeconds);
            totalTimeEl.textContent = this.formatTime(totalSeconds);
        } else {
            // Single clip mode
            currentTimeEl.textContent = this.formatTime(this.currentTime);
            totalTimeEl.textContent = this.formatTime(this.duration);
        }

        // Release the update guard
        this.isUpdatingDisplay = false;
    }

    throttledUpdateTimelineDisplay() {
        // Throttle timeline updates to prevent infinite loops during playback
        if (this.timelineUpdateTimeout) {
            return; // Update already scheduled
        }

        this.timelineUpdateTimeout = setTimeout(() => {
            this.updateTimelineDisplay();
            this.timelineUpdateTimeout = null;
        }, 100); // Update at most every 100ms
    }

    updateSidebarDuration(actualDurationMs) {
        if (!this.currentTimeline) return;

        // Find the active date item in the sidebar
        const activeDateItem = document.querySelector('.date-item.active');
        if (!activeDateItem) return;

        // Update the duration display
        const durationElement = activeDateItem.querySelector('.date-duration');
        if (!durationElement) return;

        // Calculate and format the new duration
        const totalMinutes = Math.floor(actualDurationMs / 60000);
        const totalHours = Math.floor(totalMinutes / 60);
        const remainingMinutes = totalMinutes % 60;

        let durationText = '';
        if (totalHours > 0) {
            durationText = `${totalHours}h ${remainingMinutes}m`;
        } else if (totalMinutes > 0) {
            durationText = `${totalMinutes}m`;
        } else {
            // Show seconds for very short timelines
            const totalSeconds = Math.floor(actualDurationMs / 1000);
            durationText = `${totalSeconds}s`;
        }

        durationElement.textContent = durationText;
    }

    setupStickyHeaders() {
        // Set up intersection observer for sticky header effects
        const sidebarContent = document.getElementById('sidebar-content');
        if (!sidebarContent) return;

        // Create intersection observer to detect when headers become sticky
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                const header = entry.target;
                if (entry.isIntersecting) {
                    // Header is visible normally
                    header.classList.remove('sticky');
                } else {
                    // Header is sticky (out of normal view)
                    header.classList.add('sticky');
                }
            });
        }, {
            root: sidebarContent,
            rootMargin: '-1px 0px 0px 0px',
            threshold: [0, 1]
        });

        // Observe all section headers
        const headers = document.querySelectorAll('.section-header');
        headers.forEach(header => observer.observe(header));

        // Store observer for cleanup
        this.stickyHeaderObserver = observer;
    }

    setupExportSystem() {
        // Initialize export markers
        this.exportMarkers = {
            start: null,
            end: null
        };

        // Set up export control event listeners
        const setStartMarkerBtn = document.getElementById('set-start-marker');
        const setEndMarkerBtn = document.getElementById('set-end-marker');
        const clearMarkersBtn = document.getElementById('clear-markers');
        const exportVideoBtn = document.getElementById('export-video');

        setStartMarkerBtn?.addEventListener('click', () => this.setExportMarker('start'));
        setEndMarkerBtn?.addEventListener('click', () => this.setExportMarker('end'));
        clearMarkersBtn?.addEventListener('click', () => this.clearExportMarkers());
        exportVideoBtn?.addEventListener('click', () => this.openExportDialog());

        // Set up export modal event listeners
        const exportModal = document.getElementById('export-modal');
        const closeModalBtn = document.getElementById('close-export-modal');
        const cancelExportBtn = document.getElementById('cancel-export');
        const startExportBtn = document.getElementById('start-export');

        closeModalBtn?.addEventListener('click', () => this.closeExportDialog());
        cancelExportBtn?.addEventListener('click', () => this.closeExportDialog());
        startExportBtn?.addEventListener('click', () => this.startVideoExport());

        // Close modal when clicking outside
        exportModal?.addEventListener('click', (e) => {
            if (e.target === exportModal) {
                this.closeExportDialog();
            }
        });

        // Update export info when settings change
        const qualityInputs = document.querySelectorAll('input[name="export-quality"]');
        const cameraToggles = document.querySelectorAll('.camera-export-toggle');

        qualityInputs.forEach(input => {
            input.addEventListener('change', () => this.updateExportEstimates());
        });

        cameraToggles.forEach(toggle => {
            toggle.addEventListener('change', () => this.updateExportEstimates());
        });
    }

    setExportMarker(type) {
        if (!this.currentTimeline) {
            alert('Please load a timeline first');
            return;
        }

        const currentPosition = this.currentTimeline.currentPosition;
        
        // Sync is now handled at the FFmpeg level, so we use the original position
        this.exportMarkers[type] = currentPosition;

        // Update visual markers on timeline
        this.updateExportMarkers();

        // Update export controls state
        this.updateExportControlsState();

        const time = Math.floor(currentPosition/1000);
        console.log(`Export ${type} marker set at ${time}s (sync handled at FFmpeg level)`);
        this.showStatus(`📹 ${type.charAt(0).toUpperCase() + type.slice(1)} marker set (sync handled at export level)`);
    }

    findSyncStartPosition(targetPosition) {
        // Find the earliest position where all cameras are available and synchronized
        const cameras = ['left_pillar', 'front', 'right_pillar', 'left_repeater', 'back', 'right_repeater'];
        let earliestSyncPosition = targetPosition;

        // Sync is now handled at the FFmpeg level, so we don't need to adjust the start marker
        // The right_repeater will be delayed by 1 second in the FFmpeg command
        console.log(`📹 Sync handled at FFmpeg level - using original position`);
        return targetPosition;

        // Fallback to original logic if no sync offset detected
        for (let i = 0; i < this.currentTimeline.clips.length; i++) {
            const clip = this.currentTimeline.clips[i];
            const clipStartTime = this.calculateClipStartTime(i);
            const clipEndTime = clipStartTime + (clip.duration || 60) * 1000;

            // Check if this clip has all cameras
            const availableCameras = cameras.filter(camera => clip.files[camera]);
            
            if (availableCameras.length === cameras.length) {
                if (clipStartTime <= targetPosition && clipEndTime > targetPosition) {
                    return targetPosition;
                } else if (clipStartTime > targetPosition) {
                    earliestSyncPosition = clipStartTime;
                    break;
                }
            } else {
                console.log(`📹 Clip ${i + 1} missing cameras: ${cameras.filter(c => !clip.files[c]).join(', ')}`);
            }
        }

        return earliestSyncPosition;
    }

    getCameraSyncOffset(clip) {
        // Check for timing differences between cameras in the same clip
        // This is a simplified approach - in a real implementation, you'd analyze video metadata
        // For now, we'll use a conservative estimate based on common Tesla camera sync issues
        
        const cameras = ['left_pillar', 'front', 'right_pillar', 'left_repeater', 'back', 'right_repeater'];
        let maxOffset = 0;

        // Check if right_repeater is present and might have sync issues
        if (clip.files.right_repeater) {
            // Right repeater often starts 0.5-1.5 seconds after other cameras
            // Based on user feedback, it can be up to 1 second delay
            maxOffset = Math.max(maxOffset, 1000); // 1 second
        }

        // Check if left_repeater is present and might have sync issues
        if (clip.files.left_repeater) {
            // Left repeater can also have slight delays
            maxOffset = Math.max(maxOffset, 800); // 0.8 seconds
        }

        // Check if back camera is present and might have sync issues
        if (clip.files.back) {
            // Back camera can have timing differences
            maxOffset = Math.max(maxOffset, 600); // 0.6 seconds
        }

        // Try to get actual sync offset from current video playback if available
        const actualOffset = this.getActualSyncOffset();
        if (actualOffset > 0) {
            maxOffset = Math.max(maxOffset, actualOffset);
        }

        return maxOffset;
    }

    getActualSyncOffsetWithDirection() {
        // Try to detect actual sync offset and direction from current video playback
        if (!this.videos || !this.currentTimeline) {
            console.log(`📹 Sync detection: No videos or timeline available`);
            return { offset: 0, direction: 'none' };
        }

        const cameras = ['left_pillar', 'front', 'right_pillar', 'left_repeater', 'back', 'right_repeater'];
        let maxOffset = 0;
        let maxDirection = 'none';
        
        console.log(`📹 Starting sync detection for cameras: ${cameras.join(', ')}`);

        // Check each camera's current time (even if paused)
        cameras.forEach(camera => {
            const video = this.videos[camera];
            console.log(`📹 Checking ${camera}: video=${!!video}, src=${!!video?.src}, readyState=${video?.readyState}`);
            
            if (video && video.src && video.readyState >= 2) { // HAVE_CURRENT_DATA or higher
                const currentTime = video.currentTime * 1000; // Convert to milliseconds
                console.log(`📹 ${camera} current time: ${currentTime}ms`);
                
                // Compare with front camera (usually the reference)
                const frontVideo = this.videos.front;
                if (frontVideo && frontVideo.src && frontVideo.readyState >= 2) {
                    const frontTime = frontVideo.currentTime * 1000;
                    const offset = Math.abs(currentTime - frontTime);
                    const direction = currentTime > frontTime ? 'ahead' : 'behind';
                    
                    console.log(`📹 ${camera} vs front: offset=${offset}ms, direction=${direction}`);
                    
                    if (offset > maxOffset && offset > 100) { // Only consider significant offsets
                        maxOffset = offset;
                        maxDirection = direction;
                        console.log(`📹 Detected sync offset for ${camera}: ${offset}ms ${direction} of front camera`);
                    }
                } else {
                    console.log(`📹 Front camera not available for comparison`);
                }
            } else {
                console.log(`📹 ${camera} not ready: video=${!!video}, src=${!!video?.src}, readyState=${video?.readyState}`);
            }
        });

        // If no sync offset detected from current playback, use conservative estimate
        if (maxOffset === 0) {
            // Based on user feedback, right_repeater often starts ahead of front camera
            const rightRepeater = this.videos.right_repeater;
            const frontVideo = this.videos.front;
            
            if (rightRepeater && frontVideo && rightRepeater.readyState >= 2 && frontVideo.readyState >= 2) {
                const rightTime = rightRepeater.currentTime * 1000;
                const frontTime = frontVideo.currentTime * 1000;
                const offset = Math.abs(rightTime - frontTime);
                
                if (offset > 50) { // Even small offsets
                    maxOffset = offset;
                    maxDirection = rightTime > frontTime ? 'ahead' : 'behind';
                    console.log(`📹 Conservative sync detection for right_repeater: ${offset}ms ${maxDirection} of front camera`);
                } else {
                    // Use default conservative estimate
                    maxOffset = 1000; // 1 second
                    maxDirection = 'ahead'; // Right repeater typically starts ahead
                    console.log(`📹 Using default sync estimate: ${maxOffset}ms ${maxDirection} for right_repeater`);
                }
            }
        }

        return { offset: maxOffset, direction: maxDirection };
    }

    getActualSyncOffset() {
        // Legacy function for backward compatibility
        const { offset } = this.getActualSyncOffsetWithDirection();
        return offset;
    }

    getInitialSyncOffsetWithDirection() {
        // Check for initial sync delays when videos first start
        const cameras = ['left_pillar', 'front', 'right_pillar', 'left_repeater', 'back', 'right_repeater'];
        let maxOffset = 0;
        let maxDirection = 'none';

        // Check if right_repeater is significantly ahead or behind
        const rightRepeater = this.videos.right_repeater;
        const frontVideo = this.videos.front;
        
        if (rightRepeater && frontVideo && rightRepeater.src && frontVideo.src) {
            const rightTime = rightRepeater.currentTime * 1000;
            const frontTime = frontVideo.currentTime * 1000;
            const offset = Math.abs(frontTime - rightTime);
            
            if (offset > 100 && offset < 2000) { // Between 0.1-2 seconds difference
                maxOffset = Math.max(maxOffset, offset);
                maxDirection = frontTime > rightTime ? 'behind' : 'ahead';
                console.log(`📹 Right repeater initial sync: ${offset}ms ${maxDirection} of front camera`);
            }
        }

        return { offset: maxOffset, direction: maxDirection };
    }

    getInitialSyncOffset() {
        // Legacy function for backward compatibility
        const { offset } = this.getInitialSyncOffsetWithDirection();
        return offset;
    }

    getSyncAdjustedExportRange() {
        // Get the sync-adjusted export range that ensures all cameras are synchronized
        let startTime = 0;
        let endTime = this.currentTimeline.displayDuration;

        if (this.exportMarkers.start !== null && this.exportMarkers.end !== null) {
            // Both markers set - apply sync adjustments
            const originalStart = Math.min(this.exportMarkers.start, this.exportMarkers.end);
            const originalEnd = Math.max(this.exportMarkers.start, this.exportMarkers.end);
            
            // Apply sync adjustments
            startTime = this.findSyncStartPosition(originalStart);
            endTime = this.findSyncEndPosition(originalEnd);
            
            console.log(`📹 Export range adjusted: ${Math.floor(originalStart/1000)}s → ${Math.floor(startTime/1000)}s, ${Math.floor(originalEnd/1000)}s → ${Math.floor(endTime/1000)}s`);
            
        } else if (this.exportMarkers.start !== null) {
            // Only start marker set - apply sync adjustment
            startTime = this.findSyncStartPosition(this.exportMarkers.start);
            console.log(`📹 Start marker adjusted: ${Math.floor(this.exportMarkers.start/1000)}s → ${Math.floor(startTime/1000)}s`);
            
        } else if (this.exportMarkers.end !== null) {
            // Only end marker set - apply sync adjustment
            endTime = this.findSyncEndPosition(this.exportMarkers.end);
            console.log(`📹 End marker adjusted: ${Math.floor(this.exportMarkers.end/1000)}s → ${Math.floor(endTime/1000)}s`);
        }

        return { startTime, endTime };
    }

    findSyncEndPosition(targetPosition) {
        // Find the latest position where all cameras are still available and synchronized
        const cameras = ['left_pillar', 'front', 'right_pillar', 'left_repeater', 'back', 'right_repeater'];
        let latestSyncPosition = targetPosition;

        // Check each clip from the end to find where cameras start dropping
        for (let i = this.currentTimeline.clips.length - 1; i >= 0; i--) {
            const clip = this.currentTimeline.clips[i];
            const clipStartTime = this.calculateClipStartTime(i);
            const clipEndTime = clipStartTime + (clip.duration || 60) * 1000;

            // Check if this clip has all cameras
            const availableCameras = cameras.filter(camera => clip.files[camera]);
            
            if (availableCameras.length === cameras.length) {
                // All cameras available in this clip, now check sync timing
                const syncOffset = this.getCameraSyncOffset(clip);
                
                if (syncOffset > 0) {
                    // Cameras have sync offset, adjust end position
                    const adjustedClipEnd = clipEndTime - syncOffset;
                    
                    if (clipStartTime <= targetPosition && adjustedClipEnd > targetPosition) {
                        // Target position is within this clip, but need to account for sync
                        return Math.min(targetPosition, adjustedClipEnd);
                    } else if (adjustedClipEnd <= targetPosition) {
                        // This clip ends before target, use adjusted clip end
                        latestSyncPosition = adjustedClipEnd;
                        break;
                    }
                } else {
                    // No sync offset, use original logic
                    if (clipStartTime <= targetPosition && clipEndTime > targetPosition) {
                        return targetPosition;
                    } else if (clipEndTime <= targetPosition) {
                        latestSyncPosition = clipEndTime;
                        break;
                    }
                }
            } else {
                // Some cameras missing, continue to previous clip
                console.log(`📹 Clip ${i + 1} missing cameras: ${cameras.filter(c => !clip.files[c]).join(', ')}`);
            }
        }

        return latestSyncPosition;
    }

    calculateClipStartTime(clipIndex) {
        // Calculate the start time of a clip in the timeline
        let startTime = 0;
        for (let i = 0; i < clipIndex; i++) {
            const clipDuration = (this.currentTimeline.clips[i].duration || 60) * 1000;
            startTime += clipDuration;
        }
        return startTime;
    }

    clearExportMarkers() {
        this.exportMarkers.start = null;
        this.exportMarkers.end = null;

        // Remove visual markers
        this.updateExportMarkers();

        // Update export controls state
        this.updateExportControlsState();

        console.log('Export markers cleared');
    }

    updateExportMarkers() {
        const timelineMarkers = document.getElementById('timeline-markers');
        if (!timelineMarkers || !this.currentTimeline) return;

        // Clear existing export markers
        const existingMarkers = timelineMarkers.querySelectorAll('.export-marker');
        existingMarkers.forEach(marker => marker.remove());

        // Add start marker
        if (this.exportMarkers.start !== null) {
            const startMarker = this.createExportMarker('start', this.exportMarkers.start);
            timelineMarkers.appendChild(startMarker);
        }

        // Add end marker
        if (this.exportMarkers.end !== null) {
            const endMarker = this.createExportMarker('end', this.exportMarkers.end);
            timelineMarkers.appendChild(endMarker);
        }

        // Add range highlight if both markers are set
        if (this.exportMarkers.start !== null && this.exportMarkers.end !== null) {
            const rangeHighlight = this.createExportRangeHighlight();
            timelineMarkers.appendChild(rangeHighlight);
        }
    }

    createExportMarker(type, position) {
        const marker = document.createElement('div');
        marker.className = `export-marker export-marker-${type}`;

        const percentage = (position / this.currentTimeline.displayDuration) * 100;
        marker.style.left = `${percentage}%`;

        marker.innerHTML = type === 'start' ? '📍' : '🏁';
        marker.title = `${type.charAt(0).toUpperCase() + type.slice(1)} marker: ${this.formatTime(Math.floor(position/1000))}`;

        // Make marker draggable
        this.makeMarkerDraggable(marker, type);

        return marker;
    }

    createExportRangeHighlight() {
        const highlight = document.createElement('div');
        highlight.className = 'export-range-highlight';

        const startPos = Math.min(this.exportMarkers.start, this.exportMarkers.end);
        const endPos = Math.max(this.exportMarkers.start, this.exportMarkers.end);

        const startPercentage = (startPos / this.currentTimeline.displayDuration) * 100;
        const endPercentage = (endPos / this.currentTimeline.displayDuration) * 100;

        highlight.style.left = `${startPercentage}%`;
        highlight.style.width = `${endPercentage - startPercentage}%`;

        return highlight;
    }

    makeMarkerDraggable(marker, type) {
        let isDragging = false;

        marker.addEventListener('mousedown', (e) => {
            isDragging = true;
            e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;

            const timelineScrubber = document.getElementById('timeline-scrubber');
            const rect = timelineScrubber.getBoundingClientRect();
            const percentage = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100));
            const newPosition = (percentage / 100) * this.currentTimeline.displayDuration;

            this.exportMarkers[type] = newPosition;
            this.updateExportMarkers();
        });

        document.addEventListener('mouseup', () => {
            if (isDragging) {
                isDragging = false;
                this.updateExportControlsState();
            }
        });
    }

    updateExportControlsState() {
        const exportBtn = document.getElementById('export-video');
        const clearBtn = document.getElementById('clear-markers');

        const hasMarkers = this.exportMarkers.start !== null || this.exportMarkers.end !== null;

        if (clearBtn) {
            clearBtn.disabled = !hasMarkers;
        }

        if (exportBtn) {
            exportBtn.disabled = !this.currentTimeline;
        }
    }

    openExportDialog() {
        if (!this.currentTimeline) {
            alert('Please load a timeline first');
            return;
        }

        const modal = document.getElementById('export-modal');
        if (!modal) return;

        // Update export range display
        this.updateExportRangeDisplay();

        // Update camera toggles based on current visibility
        this.updateCameraExportToggles();

        // Calculate initial estimates
        this.updateExportEstimates();

        // Show modal
        modal.classList.remove('hidden');
    }

    closeExportDialog() {
        const modal = document.getElementById('export-modal');
        if (!modal) return;

        modal.classList.add('hidden');

        // Hide progress if visible
        const progressSection = document.getElementById('export-progress');
        if (progressSection) {
            progressSection.classList.add('hidden');
        }
    }

    updateExportRangeDisplay() {
        const rangeDisplay = document.getElementById('export-range-display');
        const durationDisplay = document.getElementById('export-duration-display');

        if (!rangeDisplay || !durationDisplay) return;

        let startTime, endTime, duration;

        if (this.exportMarkers.start !== null && this.exportMarkers.end !== null) {
            const startPos = Math.min(this.exportMarkers.start, this.exportMarkers.end);
            const endPos = Math.max(this.exportMarkers.start, this.exportMarkers.end);

            startTime = this.formatTime(Math.floor(startPos / 1000));
            endTime = this.formatTime(Math.floor(endPos / 1000));
            duration = Math.floor((endPos - startPos) / 1000);

            rangeDisplay.textContent = `${startTime} - ${endTime}`;
            
            // Check for sync issues in the export range
            this.checkExportRangeSync(startPos, endPos);
        } else if (this.exportMarkers.start !== null) {
            startTime = this.formatTime(Math.floor(this.exportMarkers.start / 1000));
            endTime = this.formatTime(Math.floor(this.currentTimeline.displayDuration / 1000));
            duration = Math.floor((this.currentTimeline.displayDuration - this.exportMarkers.start) / 1000);

            rangeDisplay.textContent = `${startTime} - End`;
        } else if (this.exportMarkers.end !== null) {
            startTime = '0:00';
            endTime = this.formatTime(Math.floor(this.exportMarkers.end / 1000));
            duration = Math.floor(this.exportMarkers.end / 1000);

            rangeDisplay.textContent = `Start - ${endTime}`;
        } else {
            duration = Math.floor(this.currentTimeline.displayDuration / 1000);
            rangeDisplay.textContent = 'Full Timeline';
        }

        durationDisplay.textContent = `(${this.formatTime(duration)})`;
    }

    checkExportRangeSync(startPos, endPos) {
        const cameras = ['left_pillar', 'front', 'right_pillar', 'left_repeater', 'back', 'right_repeater'];
        const syncIssues = [];

        // Check each clip in the export range
        for (let i = 0; i < this.currentTimeline.clips.length; i++) {
            const clip = this.currentTimeline.clips[i];
            const clipStartTime = this.calculateClipStartTime(i);
            const clipEndTime = clipStartTime + (clip.duration || 60) * 1000;

            // Check if this clip overlaps with the export range
            if (clipStartTime < endPos && clipEndTime > startPos) {
                const availableCameras = cameras.filter(camera => clip.files[camera]);
                if (availableCameras.length < cameras.length) {
                    const missingCameras = cameras.filter(c => !clip.files[c]);
                    syncIssues.push({
                        clipIndex: i,
                        missingCameras: missingCameras,
                        timeRange: `${this.formatTime(Math.floor(Math.max(startPos, clipStartTime) / 1000))} - ${this.formatTime(Math.floor(Math.min(endPos, clipEndTime) / 1000))}`
                    });
                }
            }
        }

        // Show warning if sync issues found
        if (syncIssues.length > 0) {
            const missingCameras = [...new Set(syncIssues.flatMap(issue => issue.missingCameras))];
            console.warn(`⚠️ Export range has sync issues: ${syncIssues.length} clips missing cameras: ${missingCameras.join(', ')}`);
            
            // Update export button to show warning
            const exportBtn = document.getElementById('start-export');
            if (exportBtn) {
                exportBtn.title = `Warning: Some clips in export range are missing cameras (${missingCameras.join(', ')})`;
                exportBtn.classList.add('warning');
            }
        } else {
            // Clear warning
            const exportBtn = document.getElementById('start-export');
            if (exportBtn) {
                exportBtn.title = 'Start export';
                exportBtn.classList.remove('warning');
            }
        }
    }

    updateCameraExportToggles() {
        const cameraToggles = document.querySelectorAll('.camera-export-toggle');

        cameraToggles.forEach(toggle => {
            const cameraSlot = toggle.closest('.camera-slot');
            const camera = cameraSlot?.dataset.camera;

            if (camera) {
                // Check if camera is currently visible in the main view
                const videoElement = document.getElementById(`video-${camera}`);
                const isVisible = videoElement && !videoElement.closest('.video-container').classList.contains('hidden');

                toggle.checked = isVisible;

                // Disable if camera is not available
                if (!videoElement) {
                    toggle.disabled = true;
                    cameraSlot.style.opacity = '0.5';
                }
            }
        });
    }

    updateExportEstimates() {
        const fileSizeElement = document.getElementById('estimated-file-size');
        const durationElement = document.getElementById('export-duration-estimate');

        if (!fileSizeElement || !durationElement || !this.currentTimeline) return;

        // Get selected quality
        const qualityInput = document.querySelector('input[name="export-quality"]:checked');
        const quality = qualityInput?.value || 'full';

        // Get selected cameras
        const selectedCameras = Array.from(document.querySelectorAll('.camera-export-toggle:checked')).length;

        // Calculate export duration using sync-adjusted range
        const { startTime, endTime } = this.getSyncAdjustedExportRange();
        const exportDuration = Math.floor((endTime - startTime) / 1000);

        // More accurate file size estimation based on quality and camera count
        let baseSizePerMinute;
        if (quality === 'full') {
            // Full quality: higher bitrate, more cameras = larger file
            baseSizePerMinute = selectedCameras <= 2 ? 80 : 
                               selectedCameras <= 4 ? 120 : 
                               selectedCameras <= 6 ? 180 : 200;
        } else {
            // Mobile quality: lower bitrate, scaled down
            baseSizePerMinute = selectedCameras <= 2 ? 25 : 
                               selectedCameras <= 4 ? 40 : 
                               selectedCameras <= 6 ? 60 : 80;
        }
        
        // Adjust for duration (longer videos may have better compression)
        const durationFactor = exportDuration < 60 ? 1.2 : 
                              exportDuration < 300 ? 1.0 : 
                              exportDuration < 600 ? 0.9 : 0.8;
        
        const estimatedSize = Math.round((exportDuration / 60) * baseSizePerMinute * durationFactor);

        // Estimate processing time (rough calculation)
        const processingTime = Math.round(exportDuration * 0.5); // Assume 0.5x real-time processing

        fileSizeElement.textContent = `~${estimatedSize} MB`;
        durationElement.textContent = `~${Math.max(1, Math.round(processingTime / 60))} minutes`;
    }

    async startVideoExport() {
        console.log('🚀 Debug: startVideoExport called');
        console.log('🔍 Debug: window.electronAPI at start:', window.electronAPI);

        if (!this.currentTimeline) {
            alert('No timeline loaded');
            return;
        }

        // Get export settings
        const qualityInput = document.querySelector('input[name="export-quality"]:checked');
        const quality = qualityInput?.value || 'full';

        const selectedCameras = Array.from(document.querySelectorAll('.camera-export-toggle:checked'))
            .map(toggle => toggle.closest('.camera-slot').dataset.camera)
            .filter(Boolean);

        if (selectedCameras.length === 0) {
            alert('Please select at least one camera to export');
            return;
        }

        const timestampEnabled = document.getElementById('timestamp-overlay-enabled')?.checked || false;
        const timestampPosition = document.getElementById('timestamp-position')?.value || 'bottom-center';

        // Calculate export range with sync adjustments
        const { startTime, endTime } = this.getSyncAdjustedExportRange();

        // Show progress section
        const progressSection = document.getElementById('export-progress');
        const startButton = document.getElementById('start-export');

        if (progressSection) progressSection.classList.remove('hidden');
        if (startButton) startButton.disabled = true;

        try {
            // Prepare export data
            const exportData = {
                timeline: this.currentTimeline,
                startTime,
                endTime,
                quality,
                cameras: selectedCameras,
                timestamp: {
                    enabled: timestampEnabled,
                    position: timestampPosition
                }
            };

            console.log('Starting video export with settings:', exportData);

            // Call backend export function
            await this.performVideoExport(exportData);

            // Export completed
            this.updateExportProgress(100, 'Export completed successfully!');

            // Re-enable the export button
            if (startButton) startButton.disabled = false;

            setTimeout(() => {
                this.closeExportDialog();
            }, 2000);

        } catch (error) {
            console.error('Export failed:', error);
            this.updateExportProgress(0, `Export failed: ${error.message}`);

            // Re-enable the export button on error too
            if (startButton) startButton.disabled = false;
        }
    }

    async performVideoExport(exportData) {
        try {
            // Debug: Check what's available
            const apiKeys = Object.keys(window.electronAPI || {});
            console.log('🔍 Debug: window.electronAPI keys:', apiKeys);
            console.log('🔍 Debug: Keys are:', apiKeys.join(', '));
            console.log('🔍 Debug: window.electronAPI:', window.electronAPI);
            console.log('🔍 Debug: window.electronAPI.dialog:', window.electronAPI?.dialog);
            console.log('🔍 Debug: window.electronAPI.dialog.saveFile:', window.electronAPI?.dialog?.saveFile);
            console.log('🔍 Debug: typeof window.electronAPI:', typeof window.electronAPI);

            if (!window.electronAPI) {
                throw new Error('electronAPI is not available');
            }
            if (!window.electronAPI.dialog) {
                // Try to add dialog API manually as a workaround
                console.log('🔧 Attempting to add dialog API manually...');
                if (window.electronAPI.invoke) {
                    window.electronAPI.dialog = {
                        saveFile: (options) => window.electronAPI.invoke('dialog:save-file', options)
                    };
                    console.log('✅ Dialog API added manually');
                } else {
                    throw new Error('electronAPI.dialog is not available and cannot be added manually');
                }
            }
            if (!window.electronAPI.dialog.saveFile) {
                throw new Error('electronAPI.dialog.saveFile is not available');
            }

            // Get save location from user
            const outputPath = await window.electronAPI.dialog.saveFile({
                title: 'Save Tesla Dashcam Export',
                defaultPath: `tesla_export_${new Date().toISOString().slice(0, 10)}.mp4`,
                filters: [
                    { name: 'Video Files', extensions: ['mp4'] },
                    { name: 'All Files', extensions: ['*'] }
                ]
            });

            if (!outputPath) {
                throw new Error('Export cancelled by user');
            }

            // Add output path to export data
            exportData.outputPath = outputPath;

            // Generate unique export ID
            const exportId = `export_${Date.now()}`;

            // Set up progress listener
            const progressHandler = (event, receivedExportId, progress) => {
                if (receivedExportId === exportId) {
                    if (progress.type === 'progress') {
                        this.updateExportProgress(progress.percentage, progress.message);
                    } else if (progress.type === 'complete') {
                        if (progress.success) {
                            this.updateExportProgress(100, progress.message);

                            // Re-enable export button
                            const startButton = document.getElementById('start-export');
                            if (startButton) startButton.disabled = false;

                            // Show success message with option to open file location
                            setTimeout(() => {
                                const openLocation = confirm(`${progress.message}\n\nWould you like to open the file location?`);
                                if (openLocation) {
                                    window.electronAPI.fs.showItemInFolder(outputPath);
                                }
                                this.closeExportDialog();
                            }, 1000);
                        } else {
                            this.updateExportProgress(0, progress.message);
                            
                            // Re-enable export button on failure
                            const startButton = document.getElementById('start-export');
                            if (startButton) startButton.disabled = false;
                            
                            alert(`Export failed: ${progress.message}`);
                        }

                        // Remove progress listener
                        window.electronAPI.removeListener('tesla:export-progress', progressHandler);
                    }
                }
            };

            // Add progress listener
            window.electronAPI.on('tesla:export-progress', progressHandler);

            // Start the export
            console.log('🚀 Starting Tesla video export with data:', exportData);
            const success = await window.electronAPI.tesla.exportVideo(exportId, exportData);

            if (!success) {
                throw new Error('Failed to start export process');
            }

        } catch (error) {
            console.error('💥 Export failed:', error);
            this.updateExportProgress(0, `Export failed: ${error.message}`);
            alert(`Export failed: ${error.message}`);
        }
    }

    updateExportProgress(percentage, status) {
        const progressFill = document.getElementById('progress-fill');
        const progressPercentage = document.getElementById('progress-percentage');
        const progressStatus = document.getElementById('progress-status');

        if (progressFill) progressFill.style.width = `${percentage}%`;
        if (progressPercentage) progressPercentage.textContent = `${percentage}%`;
        if (progressStatus) progressStatus.textContent = status;
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
        // Space or Enter: Play/Pause
        if (event.code === 'Space' || event.code === 'Enter') {
            event.preventDefault();
            this.togglePlayPause();
            this.showStatus('Play/Pause');
        }
        // Shift+Left: Skip Back 15s
        else if (event.code === 'ArrowLeft' && event.shiftKey) {
            event.preventDefault();
            this.skipSeconds(-15);
            this.showStatus('⏪ Skip Back 15s');
        }
        // Shift+Right: Skip Forward 15s
        else if (event.code === 'ArrowRight' && event.shiftKey) {
            event.preventDefault();
            this.skipSeconds(15);
            this.showStatus('⏩ Skip Forward 15s');
        }
        // Left: Frame Back
        else if (event.code === 'ArrowLeft') {
            event.preventDefault();
            this.frameStep(-1);
            this.showStatus('⬅️ Frame Back');
        }
        // Right: Frame Forward
        else if (event.code === 'ArrowRight') {
            event.preventDefault();
            this.frameStep(1);
            this.showStatus('➡️ Frame Forward');
        }
        // Up: Increase speed
        else if (event.code === 'ArrowUp') {
            event.preventDefault();
            this.adjustPlaybackSpeed(1);
        }
        // Down: Decrease speed
        else if (event.code === 'ArrowDown') {
            event.preventDefault();
            this.adjustPlaybackSpeed(-1);
        }
    }

    adjustPlaybackSpeed(direction) {
        const speedSelect = document.getElementById('speed-select');
        if (!speedSelect) return;
        const options = Array.from(speedSelect.options);
        const currentIdx = options.findIndex(opt => opt.selected);
        let newIdx = currentIdx + direction;
        newIdx = Math.max(0, Math.min(newIdx, options.length - 1));
        if (newIdx !== currentIdx) {
            options[newIdx].selected = true;
            speedSelect.dispatchEvent(new Event('change'));
            this.showStatus(`Speed: ${options[newIdx].text}`);
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

    // Camera Visibility Methods
    toggleCameraPanel() {
        const panel = document.getElementById('camera-visibility-panel');
        panel.classList.toggle('hidden');
    }

    hideCameraPanel() {
        const panel = document.getElementById('camera-visibility-panel');
        panel.classList.add('hidden');
    }

    toggleCameraVisibility(camera, isVisible) {
        this.cameraVisibility[camera] = isVisible;
        const container = document.querySelector(`[data-camera="${camera}"]`);

        if (container) {
            if (isVisible) {
                container.classList.remove('hidden-camera');
            } else {
                container.classList.add('hidden-camera');
            }
        }

        console.log(`Camera ${camera} ${isVisible ? 'shown' : 'hidden'}`);
        this.updateVideoGridLayout();
    }

    showAllCameras() {
        const cameras = ['left_pillar', 'front', 'right_pillar', 'left_repeater', 'back', 'right_repeater'];
        cameras.forEach(camera => {
            this.cameraVisibility[camera] = true;
            const toggle = document.getElementById(`toggle-${camera}`);
            const container = document.querySelector(`[data-camera="${camera}"]`);

            if (toggle) toggle.checked = true;
            if (container) container.classList.remove('hidden-camera');
        });

        console.log('All cameras shown');
        this.updateVideoGridLayout();
    }

    hideAllCameras() {
        const cameras = ['left_pillar', 'front', 'right_pillar', 'left_repeater', 'back', 'right_repeater'];
        cameras.forEach(camera => {
            this.cameraVisibility[camera] = false;
            const toggle = document.getElementById(`toggle-${camera}`);
            const container = document.querySelector(`[data-camera="${camera}"]`);

            if (toggle) toggle.checked = false;
            if (container) container.classList.add('hidden-camera');
        });

        console.log('All cameras hidden');
        this.updateVideoGridLayout();
    }

    updateVideoGridLayout() {
        const videoGrid = document.getElementById('video-grid');
        const visibleCameras = Object.values(this.cameraVisibility).filter(visible => visible).length;

        // Adjust grid layout based on number of visible cameras
        if (visibleCameras === 1) {
            videoGrid.style.gridTemplateColumns = '1fr';
            videoGrid.style.gridTemplateRows = '1fr';
        } else if (visibleCameras === 2) {
            videoGrid.style.gridTemplateColumns = '1fr 1fr';
            videoGrid.style.gridTemplateRows = '1fr';
        } else if (visibleCameras === 3) {
            videoGrid.style.gridTemplateColumns = '1fr 1fr 1fr';
            videoGrid.style.gridTemplateRows = '1fr';
        } else if (visibleCameras === 4) {
            videoGrid.style.gridTemplateColumns = '1fr 1fr';
            videoGrid.style.gridTemplateRows = '1fr 1fr';
            // Ensure grid fits properly in available space
            videoGrid.style.height = '100%';
            videoGrid.style.maxHeight = 'calc(100vh - 180px)'; // Account for header + timeline
        } else if (visibleCameras === 5) {
            videoGrid.style.gridTemplateColumns = '1fr 1fr 1fr';
            videoGrid.style.gridTemplateRows = '1fr 1fr';
        } else {
            // Default 6-camera layout
            videoGrid.style.gridTemplateColumns = '1fr 1fr 1fr';
            videoGrid.style.gridTemplateRows = '1fr 1fr';
            videoGrid.style.height = '';
            videoGrid.style.maxHeight = '';
        }

        console.log(`Grid layout updated for ${visibleCameras} visible cameras`);
    }

    handleCorruptedClip(clipIndex) {
        console.warn(`🚨 Handling corrupted clip ${clipIndex + 1}`);

        // Release auto-advancement lock immediately
        this.isAutoAdvancing = false;

        // Skip to next clip if available
        if (this.currentTimeline && clipIndex < this.currentTimeline.clips.length - 1) {
            console.log(`⏭️ Skipping corrupted clip ${clipIndex + 1}, advancing to clip ${clipIndex + 2}`);

            // Small delay to ensure videos have stopped
            setTimeout(() => {
                this.loadTimelineClip(clipIndex + 1);

                // Start playing the next clip
                setTimeout(() => {
                    this.playAllVideos();
                }, 200);
            }, 100);
        } else {
            console.log(`🏁 Corrupted clip ${clipIndex + 1} was the last clip, ending timeline`);
            this.pauseAllVideos();
        }
    }

    checkOnboarding() {
        const onboardingNeverShow = localStorage.getItem('onboardingNeverShow');
        const onboardingShown = localStorage.getItem('onboardingShown');
        const lastFolder = localStorage.getItem('teslaFolder');
        const onboardingModal = document.getElementById('onboarding-modal');
        // Dark mode support
        if (document.body.classList.contains('dark')) {
            onboardingModal.classList.add('dark');
        } else {
            onboardingModal.classList.remove('dark');
        }
        if (onboardingNeverShow === 'true') {
            onboardingModal.classList.add('hidden');
            return;
        }
        // Show onboarding if not suppressed
        if (!onboardingShown || !lastFolder) {
            onboardingModal.classList.remove('hidden');
            // Wire up modal buttons
            document.getElementById('onboarding-select-folder').onclick = () => {
                const dontShow = document.getElementById('onboarding-dont-show').checked;
                if (dontShow) {
                    localStorage.setItem('onboardingNeverShow', 'true');
                } else {
                    localStorage.removeItem('onboardingNeverShow');
                }
                // Show spinner and disable button
                const btn = document.getElementById('onboarding-select-folder');
                const spinner = document.getElementById('onboarding-folder-spinner');
                if (btn) btn.disabled = true;
                if (spinner) spinner.style.display = '';
                this.selectTeslaFolder(true, dontShow).finally(() => {
                    if (btn) btn.disabled = false;
                    if (spinner) spinner.style.display = 'none';
                });
            };
            document.getElementById('close-onboarding-modal').onclick = () => {
                const dontShow = document.getElementById('onboarding-dont-show').checked;
                if (dontShow) {
                    localStorage.setItem('onboardingNeverShow', 'true');
                } else {
                    localStorage.removeItem('onboardingNeverShow');
                }
                onboardingModal.classList.add('hidden');
                localStorage.setItem('onboardingShown', 'true');
            };
        } else {
            onboardingModal.classList.add('hidden');
        }
    }

    frameStep(direction) {
        // Tesla dashcam videos are ~36 fps, so frame ≈ 1/36s
        const frameDuration = 1 / 36.0;
        Object.values(this.videos).forEach(video => {
            if (video && !isNaN(video.duration)) {
                let newTime = video.currentTime + direction * frameDuration;
                newTime = Math.max(0, Math.min(newTime, video.duration));
                video.currentTime = newTime;
            }
        });
        // Pause after frame step
        this.pauseAllVideos();
    }

    skipSeconds(seconds) {
        Object.values(this.videos).forEach(video => {
            if (video && !isNaN(video.duration)) {
                let newTime = video.currentTime + seconds;
                newTime = Math.max(0, Math.min(newTime, video.duration));
                video.currentTime = newTime;
            }
        });
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
