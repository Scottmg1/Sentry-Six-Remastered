/**
 * Debug Analysis Tool for Tesla Dashcam Timeline Issues
 * Analyzes exported debug data to identify patterns and issues
 */

function analyzeDebugData(debugData) {
    const analysis = {
        summary: {},
        gaps: [],
        fileIssues: [],
        patterns: {},
        recommendations: []
    };

    const clips = debugData.timeline?.clips || [];
    
    // Basic timeline analysis
    analysis.summary = {
        totalClips: clips.length,
        dateRange: getDateRange(clips),
        timeRange: getTimeRange(clips),
        totalDuration: calculateDuration(clips),
        clipTypes: getClipTypes(clips)
    };

    // Gap analysis
    analysis.gaps = analyzeGaps(clips);
    
    // File size analysis
    analysis.fileIssues = analyzeFileSizes(clips);
    
    // Pattern detection
    analysis.patterns = detectPatterns(clips, analysis.gaps);
    
    // Generate recommendations
    analysis.recommendations = generateRecommendations(analysis);

    return analysis;
}

function getDateRange(clips) {
    if (clips.length === 0) return 'No clips';
    
    const dates = clips.map(clip => new Date(clip.timestamp).toDateString());
    const uniqueDates = [...new Set(dates)];
    
    if (uniqueDates.length === 1) {
        return uniqueDates[0];
    }
    
    return `${uniqueDates[0]} to ${uniqueDates[uniqueDates.length - 1]}`;
}

function getTimeRange(clips) {
    if (clips.length === 0) return 'No clips';
    
    const times = clips.map(clip => new Date(clip.timestamp));
    const start = new Date(Math.min(...times));
    const end = new Date(Math.max(...times));
    
    return {
        start: start.toLocaleTimeString(),
        end: end.toLocaleTimeString(),
        duration: (end - start) / 1000 / 60 // minutes
    };
}

function calculateDuration(clips) {
    // Estimate based on clip count (Tesla clips are typically 1 minute each)
    return clips.length * 60; // seconds
}

function getClipTypes(clips) {
    const types = {};
    clips.forEach(clip => {
        const type = clip.type || 'Unknown';
        types[type] = (types[type] || 0) + 1;
    });
    return types;
}

function analyzeGaps(clips) {
    if (clips.length < 2) return [];

    const gaps = [];
    const sortedClips = [...clips].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    for (let i = 0; i < sortedClips.length - 1; i++) {
        const currentClip = sortedClips[i];
        const nextClip = sortedClips[i + 1];

        const currentTime = new Date(currentClip.timestamp);
        const nextTime = new Date(nextClip.timestamp);
        
        // Assume each clip is 1 minute long
        const expectedNextTime = new Date(currentTime.getTime() + 60000);
        const actualGap = (nextTime - expectedNextTime) / 1000; // seconds

        if (actualGap > 60) { // Gap larger than 1 minute
            gaps.push({
                index: i,
                startTime: currentTime.toLocaleTimeString(),
                endTime: nextTime.toLocaleTimeString(),
                startClip: currentClip.files ? Object.values(currentClip.files)[0]?.filename : 'Unknown',
                endClip: nextClip.files ? Object.values(nextClip.files)[0]?.filename : 'Unknown',
                duration: actualGap,
                durationFormatted: formatDuration(actualGap),
                severity: getGapSeverity(actualGap),
                likelyReason: determineGapReason(actualGap)
            });
        }
    }

    return gaps;
}

function analyzeFileSizes(clips) {
    const issues = [];
    const expectedSizes = {
        front: { min: 70, max: 85, name: 'Front Camera' },
        back: { min: 35, max: 45, name: 'Back Camera' },
        left_pillar: { min: 35, max: 45, name: 'Left Pillar' },
        right_pillar: { min: 35, max: 45, name: 'Right Pillar' },
        left_repeater: { min: 35, max: 45, name: 'Left Repeater' },
        right_repeater: { min: 35, max: 45, name: 'Right Repeater' }
    };

    clips.forEach((clip, index) => {
        if (!clip.files) return;

        Object.entries(clip.files).forEach(([camera, file]) => {
            const expected = expectedSizes[camera];
            if (!expected || !file.size) return;

            const sizeMB = file.size / 1024 / 1024;
            const time = new Date(clip.timestamp).toLocaleTimeString();

            if (sizeMB < expected.min) {
                issues.push({
                    clipIndex: index,
                    time: time,
                    camera: expected.name,
                    filename: file.filename,
                    issue: 'Unusually small file',
                    size: `${sizeMB.toFixed(1)}MB`,
                    expected: `${expected.min}-${expected.max}MB`,
                    severity: sizeMB < expected.min * 0.5 ? 'High' : 'Medium'
                });
            }
        });
    });

    return issues;
}

function detectPatterns(clips, gaps) {
    const patterns = {
        gapPattern: 'None detected',
        timePattern: 'None detected',
        sizePattern: 'None detected',
        folderPattern: 'None detected'
    };

    // Analyze gap patterns
    if (gaps.length > 0) {
        const gapDurations = gaps.map(gap => gap.duration);
        const avgGapDuration = gapDurations.reduce((a, b) => a + b, 0) / gapDurations.length;
        
        if (gaps.length === 1 && gaps[0].duration > 1200) {
            patterns.gapPattern = 'Single large gap detected - likely intentional stop';
        } else if (gaps.length > 3) {
            patterns.gapPattern = 'Multiple gaps detected - possible SD card or power issues';
        } else {
            patterns.gapPattern = `${gaps.length} gap(s) detected, average duration: ${formatDuration(avgGapDuration)}`;
        }
    }

    // Analyze time patterns
    const hours = clips.map(clip => new Date(clip.timestamp).getHours());
    const uniqueHours = [...new Set(hours)];
    if (uniqueHours.length === 1) {
        patterns.timePattern = `All clips within same hour (${uniqueHours[0]}:00)`;
    } else {
        patterns.timePattern = `Clips span ${uniqueHours.length} hours (${Math.min(...uniqueHours)}:00 - ${Math.max(...uniqueHours)}:00)`;
    }

    // Analyze folder patterns
    const folders = clips.map(clip => {
        if (clip.files) {
            const firstFile = Object.values(clip.files)[0];
            return firstFile?.path?.split('\\').slice(-2, -1)[0] || 'Unknown';
        }
        return 'Unknown';
    });
    const uniqueFolders = [...new Set(folders)];
    patterns.folderPattern = `${uniqueFolders.length} folder(s): ${uniqueFolders.join(', ')}`;

    return patterns;
}

function generateRecommendations(analysis) {
    const recommendations = [];

    // Gap-based recommendations
    if (analysis.gaps.length > 0) {
        const largeGaps = analysis.gaps.filter(gap => gap.duration > 600);
        if (largeGaps.length > 0) {
            recommendations.push({
                type: 'Gap Analysis',
                priority: 'High',
                issue: `${largeGaps.length} gap(s) longer than 10 minutes detected`,
                recommendation: 'Check if these gaps correspond to intentional stops. If not, verify SD card health and Tesla dashcam settings.',
                action: 'Review timeline around: ' + largeGaps.map(gap => gap.startTime).join(', ')
            });
        }

        const multipleSmallGaps = analysis.gaps.filter(gap => gap.duration < 300);
        if (multipleSmallGaps.length > 3) {
            recommendations.push({
                type: 'Recording Stability',
                priority: 'Medium',
                issue: `${multipleSmallGaps.length} small gaps detected`,
                recommendation: 'Multiple small gaps may indicate SD card performance issues or power fluctuations.',
                action: 'Consider formatting SD card or checking power connections'
            });
        }
    }

    // File size recommendations
    if (analysis.fileIssues.length > 0) {
        const highSeverityIssues = analysis.fileIssues.filter(issue => issue.severity === 'High');
        if (highSeverityIssues.length > 0) {
            recommendations.push({
                type: 'File Integrity',
                priority: 'High',
                issue: `${highSeverityIssues.length} file(s) with unusual sizes detected`,
                recommendation: 'Small file sizes may indicate corrupted or incomplete recordings.',
                action: 'Check affected files: ' + highSeverityIssues.map(issue => issue.filename).join(', ')
            });
        }
    }

    // Timeline continuity
    const timeRange = analysis.summary.timeRange;
    if (timeRange.duration > 60 && analysis.summary.totalClips < timeRange.duration) {
        recommendations.push({
            type: 'Timeline Continuity',
            priority: 'Medium',
            issue: 'Timeline has significant gaps relative to time span',
            recommendation: 'Expected more clips for the time duration. Check Tesla dashcam settings and storage capacity.',
            action: 'Verify dashcam is set to continuous recording mode'
        });
    }

    return recommendations;
}

function getGapSeverity(duration) {
    if (duration > 3600) return 'Critical';
    if (duration > 1800) return 'High';
    if (duration > 600) return 'Medium';
    return 'Low';
}

function determineGapReason(duration) {
    if (duration > 3600) return 'Extended parking/charging (>1 hour)';
    if (duration > 1800) return 'Long stop - parking/errands (>30 min)';
    if (duration > 600) return 'Medium stop - shopping/appointment (>10 min)';
    if (duration > 300) return 'Short stop - traffic/gas station (>5 min)';
    if (duration > 120) return 'Brief stop - traffic light/pickup (>2 min)';
    return 'Recording gap - possible technical issue';
}

function formatDuration(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
        return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

// Export for use in browser console or Node.js
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { analyzeDebugData };
} else {
    window.analyzeDebugData = analyzeDebugData;
}
