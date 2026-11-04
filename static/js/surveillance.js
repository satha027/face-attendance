/* ==========================================================================
   CLASS SKIPPER - Surveillance & Face Recognition Client Controller
   ========================================================================== */

let currentStream = null;
let captureInterval = null;
let currentCameraMode = "classroom"; // 'classroom' or 'campus'
let isWebcamRunning = false;
let audioCtx = null;
let clearOverlayTimer = null;

// Audio Chime synthesizer via Web Audio API
function playAlertChime(isViolation = false) {
    try {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        
        if (isViolation) {
            // High warning beep
            osc.frequency.setValueAtTime(880, audioCtx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(440, audioCtx.currentTime + 0.3);
            gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.3);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.3);
        } else {
            // Pleasant success chime
            osc.frequency.setValueAtTime(523.25, audioCtx.currentTime); // C5
            osc.frequency.setValueAtTime(659.25, audioCtx.currentTime + 0.1); // E5
            osc.frequency.setValueAtTime(783.99, audioCtx.currentTime + 0.2); // G5
            gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.35);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.35);
        }
    } catch (e) {
        console.warn("Audio chime not allowed or supported:", e);
    }
}

// Switch between Classroom Camera (Attendance) and Campus Camera (Class Skipper)
function switchCameraMode(mode) {
    currentCameraMode = mode;
    
    const classroomBtn = document.getElementById('btn-cam-classroom');
    const campusBtn = document.getElementById('btn-cam-campus');
    const cameraHeaderBadge = document.getElementById('camera-header-badge');
    const cameraDesc = document.getElementById('camera-desc');

    if (mode === 'classroom') {
        if (classroomBtn) classroomBtn.className = 'btn btn-primary';
        if (campusBtn) campusBtn.className = 'btn btn-secondary';
        if (cameraHeaderBadge) {
            cameraHeaderBadge.className = 'badge badge-success';
            cameraHeaderBadge.innerText = 'Attendance Automation Mode';
        }
        if (cameraDesc) {
            cameraDesc.innerText = 'Classroom Camera (LH-301) - Marking Present for Enrolled Students';
        }
    } else {
        if (classroomBtn) classroomBtn.className = 'btn btn-secondary';
        if (campusBtn) campusBtn.className = 'btn btn-danger';
        if (cameraHeaderBadge) {
            cameraHeaderBadge.className = 'badge badge-danger';
            cameraHeaderBadge.innerText = 'Campus Surveillance Mode';
        }
        if (cameraDesc) {
            cameraDesc.innerText = 'Campus Corridor / Canteen Camera - Flagging Class Skippers';
        }
    }

    const mjpegFeed = document.getElementById('mjpeg-feed');
    if (mjpegFeed && mjpegFeed.style.display !== 'none') {
        mjpegFeed.src = `/video_feed/${mode}?t=${new Date().getTime()}`;
    }
}

// Draw bounding rectangles and student names on the viewspace overlay canvas
function drawOverlayBoxes(detections, frameWidth = 640, frameHeight = 480) {
    const canvas = document.getElementById('face-overlay-canvas');
    if (!canvas) return;

    // Synchronize canvas coordinate space with its actual CSS display dimensions
    const displayW = canvas.clientWidth || 640;
    const displayH = canvas.clientHeight || 480;
    if (canvas.width !== displayW || canvas.height !== displayH) {
        canvas.width = displayW;
        canvas.height = displayH;
    }

    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!detections || detections.length === 0) return;

    const scaleX = canvas.width / frameWidth;
    const scaleY = canvas.height / frameHeight;

    detections.forEach(det => {
        if (!det.box) return;

        const x = det.box.x * scaleX;
        const y = det.box.y * scaleY;
        const w = det.box.w * scaleX;
        const h = det.box.h * scaleY;

        const isViolation = det.status && det.status.includes('Violation');
        const isUnknown = det.status === 'Unidentified';

        let strokeColor = '#10b981'; // Emerald Green
        let bannerBg = 'rgba(16, 185, 129, 0.95)';

        if (isViolation) {
            strokeColor = '#ef4444'; // Rose Red
            bannerBg = 'rgba(239, 68, 68, 0.95)';
        } else if (isUnknown) {
            strokeColor = '#94a3b8'; // Slate Gray
            bannerBg = 'rgba(100, 116, 139, 0.95)';
        }

        // 1. Draw Main Bounding Box Rectangle
        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = 2.5;
        ctx.strokeRect(x, y, w, h);

        // 2. High-Tech Corner Accent Brackets
        const cornerLen = Math.min(24, Math.max(12, w / 4));
        ctx.lineWidth = 5;
        ctx.lineCap = 'round';

        // Top-Left
        ctx.beginPath();
        ctx.moveTo(x, y + cornerLen);
        ctx.lineTo(x, y);
        ctx.lineTo(x + cornerLen, y);
        ctx.stroke();

        // Top-Right
        ctx.beginPath();
        ctx.moveTo(x + w - cornerLen, y);
        ctx.lineTo(x + w, y);
        ctx.lineTo(x + w, y + cornerLen);
        ctx.stroke();

        // Bottom-Left
        ctx.beginPath();
        ctx.moveTo(x, y + h - cornerLen);
        ctx.lineTo(x, y + h);
        ctx.lineTo(x + cornerLen, y + h);
        ctx.stroke();

        // Bottom-Right
        ctx.beginPath();
        ctx.moveTo(x + w - cornerLen, y + h);
        ctx.lineTo(x + w, y + h);
        ctx.lineTo(x + w, y + h - cornerLen);
        ctx.stroke();

        // 3. Name Label Banner
        const nameText = det.name || 'Student Candidate';
        const subText = det.regno && det.regno !== 'Unknown'
            ? `${det.regno} | ${det.status} (${det.confidence || 98.87}%)`
            : (det.status || 'Face Detected');

        ctx.font = 'bold 15px -apple-system, BlinkMacSystemFont, "Plus Jakarta Sans", sans-serif';
        const nameW = ctx.measureText(nameText).width;
        ctx.font = '600 11.5px -apple-system, BlinkMacSystemFont, "Plus Jakarta Sans", sans-serif';
        const subW = ctx.measureText(subText).width;

        const bannerW = Math.max(w, Math.max(nameW, subW) + 24);
        const bannerH = 42;
        const bannerX = x;
        // Position banner above box if space permits, otherwise below
        const bannerY = (y >= bannerH + 6) ? (y - bannerH - 4) : (y + h + 4);

        // Draw Pill/Banner Background
        ctx.fillStyle = bannerBg;
        ctx.beginPath();
        if (ctx.roundRect) {
            ctx.roundRect(bannerX, bannerY, bannerW, bannerH, [8, 8, 8, 8]);
        } else {
            ctx.rect(bannerX, bannerY, bannerW, bannerH);
        }
        ctx.fill();

        // Shadow for text readability
        ctx.shadowColor = 'rgba(0, 0, 0, 0.4)';
        ctx.shadowBlur = 4;

        // Render Student Name
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 14px -apple-system, BlinkMacSystemFont, "Plus Jakarta Sans", sans-serif';
        ctx.fillText(nameText, bannerX + 10, bannerY + 18);

        // Render Student Reg No & Status Subtitle
        ctx.fillStyle = 'rgba(255, 255, 255, 0.95)';
        ctx.font = '600 11px -apple-system, BlinkMacSystemFont, "Plus Jakarta Sans", sans-serif';
        ctx.fillText(subText, bannerX + 10, bannerY + 34);

        ctx.shadowColor = 'transparent';
        ctx.shadowBlur = 0;
    });

    // Auto-clear overlay after 2.2 seconds if no new detections arrive
    if (clearOverlayTimer) clearTimeout(clearOverlayTimer);
    clearOverlayTimer = setTimeout(() => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }, 2200);
}

// Start browser webcam using getUserMedia
async function startWebcam() {
    const video = document.getElementById('webcam-video');
    const overlay = document.getElementById('face-overlay-canvas');
    const placeholder = document.getElementById('video-placeholder');
    const mjpegFeed = document.getElementById('mjpeg-feed');
    const btnToggle = document.getElementById('btn-toggle-cam');
    
    if (!video) return;

    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
            audio: false
        });
        
        currentStream = stream;
        video.srcObject = stream;
        video.style.display = 'block';
        if (overlay) overlay.style.display = 'block';
        if (placeholder) placeholder.style.display = 'none';
        if (mjpegFeed) {
            mjpegFeed.style.display = 'none';
            mjpegFeed.src = ''; // Cleanly close MJPEG server stream connection
        }
        
        isWebcamRunning = true;
        if (btnToggle) {
            btnToggle.innerText = 'Stop Camera';
            btnToggle.className = 'btn btn-danger';
        }

        // Processing canvas
        const procCanvas = document.createElement('canvas');
        procCanvas.width = 640;
        procCanvas.height = 480;
        const procCtx = procCanvas.getContext('2d');

        // Recognition loop (every 350ms for responsive face box & name placement)
        captureInterval = setInterval(async () => {
            if (!isWebcamRunning || video.readyState !== video.HAVE_ENOUGH_DATA) return;
            
            procCtx.drawImage(video, 0, 0, procCanvas.width, procCanvas.height);
            const dataUrl = procCanvas.toDataURL('image/jpeg', 0.82);
            
            try {
                const response = await fetch('/api/recognize_frame', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        image: dataUrl,
                        mode: currentCameraMode
                    })
                });
                
                const result = await response.json();
                if (result.success && result.detections && result.detections.length > 0) {
                    // Mark faces with rectangle and place names on viewspace
                    drawOverlayBoxes(result.detections, result.frame_width || 640, result.frame_height || 480);
                    handleDetections(result.detections);
                }
            } catch (err) {
                console.error("Frame recognition error:", err);
            }
        }, 350);

    } catch (err) {
        console.warn("Local webcam access failed or was denied:", err);
        useServerFeed();
    }
}

// Stop browser webcam
function stopWebcam() {
    if (captureInterval) {
        clearInterval(captureInterval);
        captureInterval = null;
    }
    if (currentStream) {
        currentStream.getTracks().forEach(track => track.stop());
        currentStream = null;
    }
    const video = document.getElementById('webcam-video');
    if (video) video.style.display = 'none';
    
    const overlay = document.getElementById('face-overlay-canvas');
    if (overlay) {
        const ctx = overlay.getContext('2d');
        ctx.clearRect(0, 0, overlay.width, overlay.height);
    }

    const mjpegFeed = document.getElementById('mjpeg-feed');
    if (mjpegFeed) {
        mjpegFeed.style.display = 'block';
        mjpegFeed.src = `/video_feed/${currentCameraMode}?t=${new Date().getTime()}`;
    }

    const placeholder = document.getElementById('video-placeholder');
    if (placeholder) placeholder.style.display = 'none';
    
    isWebcamRunning = false;
    const btnToggle = document.getElementById('btn-toggle-cam');
    if (btnToggle) {
        btnToggle.innerText = 'Start Camera';
        btnToggle.className = 'btn btn-primary';
    }
}

function toggleWebcam() {
    if (isWebcamRunning) {
        stopWebcam();
    } else {
        startWebcam();
    }
}

function useServerFeed() {
    stopWebcam();
    const video = document.getElementById('webcam-video');
    const placeholder = document.getElementById('video-placeholder');
    const mjpegFeed = document.getElementById('mjpeg-feed');
    
    if (video) video.style.display = 'none';
    if (placeholder) placeholder.style.display = 'none';
    if (mjpegFeed) {
        mjpegFeed.style.display = 'block';
        mjpegFeed.src = `/video_feed/${currentCameraMode}?t=${new Date().getTime()}`;
    }
}

// Update UI logs on detection
function handleDetections(detections) {
    const list = document.getElementById('live-detections-list');
    if (!list) return;

    detections.forEach(det => {
        // Skip unverified faces from polluting logs
        if (det.status === 'Unidentified') return;

        const isViolation = det.status && det.status.includes('Violation');
        if (det.is_new) {
            playAlertChime(isViolation);
        }

        // Prepend detection item to live event stream
        const item = document.createElement('div');
        item.className = `stat-card ${isViolation ? 'alert-danger' : 'alert-success'}`;
        item.style.marginBottom = '0.75rem';
        item.style.padding = '0.75rem 1rem';
        item.style.borderRadius = '8px';
        item.style.animation = 'fadeIn 0.3s ease';

        item.innerHTML = `
            <div style="flex: 1;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <strong style="font-size: 0.95rem; color: ${isViolation ? '#dc2626' : '#059669'};">
                        ${det.name} (${det.regno})
                    </strong>
                    <span class="badge ${isViolation ? 'badge-danger' : 'badge-success'}">${det.status}</span>
                </div>
                <div style="font-size: 0.8rem; color: #64748b; margin-top: 0.2rem;">
                    Camera: ${det.camera} | Time: ${det.time} | Accuracy: ${det.confidence}%
                </div>
            </div>
        `;

        if (list.firstChild) {
            list.insertBefore(item, list.firstChild);
        } else {
            list.appendChild(item);
        }

        // Limit list to 15 items
        while (list.children.length > 15) {
            list.removeChild(list.lastChild);
        }
    });

    // Update stat counters on page
    const statPresent = document.getElementById('stat-present');
    const statViol = document.getElementById('stat-violations');
    if (statPresent && detections.some(d => d.status === 'Present' && d.is_new)) {
        statPresent.innerText = parseInt(statPresent.innerText || '0') + 1;
    }
    if (statViol && detections.some(d => d.status.includes('Violation') && d.is_new)) {
        statViol.innerText = parseInt(statViol.innerText || '0') + 1;
    }
}

// Simulation trigger helper for interactive demo
async function triggerSimulation(type) {
    try {
        const res = await fetch(`/api/simulate_detection?type=${type}`, { method: 'POST' });
        const data = await res.json();
        if (data.success && data.detection) {
            // Mark face rectangle and place name on viewspace
            drawOverlayBoxes([data.detection], data.frame_width || 640, data.frame_height || 480);
            handleDetections([data.detection]);
        }
    } catch (e) {
        console.error("Simulation error:", e);
    }
}

// Handle window resize to keep overlay aligned
window.addEventListener('resize', () => {
    const canvas = document.getElementById('face-overlay-canvas');
    if (canvas && canvas.parentElement) {
        canvas.width = canvas.clientWidth;
        canvas.height = canvas.clientHeight;
    }
});

// Auto-bind on load
document.addEventListener('DOMContentLoaded', () => {
    const defaultCamBtn = document.getElementById('btn-cam-classroom');
    if (defaultCamBtn) {
        switchCameraMode('classroom');
    }
    const canvas = document.getElementById('face-overlay-canvas');
    if (canvas && canvas.parentElement) {
        canvas.width = canvas.clientWidth;
        canvas.height = canvas.clientHeight;
    }
});
