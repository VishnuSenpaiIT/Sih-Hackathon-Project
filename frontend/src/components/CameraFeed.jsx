import React, { useState, useEffect, useRef } from 'react';

/**
 * CameraFeed.jsx
 * Smart Traffic Monitoring & Prediction System (SIH26222)
 *
 * Displays live MJPEG stream from edge YOLOv8 pipeline or placeholder with
 * live detection bounding box stats, live inference badges, and completion overlays.
 */
export default function CameraFeed({
  activeCamera,
  latestEvent,
  wsStatus,
  analysisState = {},
  onReplay,
  onOpenUpload,
  onQuickDemo,
}) {
  const detections = latestEvent?.detections || [];
  const cameraId = activeCamera?.id || 'cam_01';
  const isUploadCam = cameraId === 'cam_upload';

  const {
    status: analysisStatus = 'idle',
    currentFrame = 0,
    totalFrames = 0,
    totalVehicles = 0,
    fps = 10,
    replayCount = 0,
  } = analysisState;

  const isAnalyzing = analysisStatus === 'analyzing';
  const isComplete = analysisStatus === 'completed';

  // Stable stream key to prevent image flickering on rapid 15Hz React re-renders
  const [streamSessionId, setStreamSessionId] = useState(() => Date.now());
  const [mjpegActive, setMjpegActive] = useState(false);
  const imgRef = useRef(null);
  const checkTimer = useRef(null);

  const mjpegUrl = `/api/streams/${cameraId}/mjpeg`;

  // Reset stream connection key when camera switches or replay is invoked
  useEffect(() => {
    setStreamSessionId(Date.now());
    if (isUploadCam && isAnalyzing) {
      setMjpegActive(true);
    }
  }, [cameraId, replayCount, isAnalyzing]);

  useEffect(() => {
    let alive = true;

    async function checkMjpeg() {
      // If actively analyzing uploaded video, assume stream is live
      if (isUploadCam && isAnalyzing) {
        if (alive) setMjpegActive(true);
        return;
      }

      try {
        const res = await fetch(mjpegUrl, { method: 'HEAD', signal: AbortSignal.timeout(900) });
        if (alive) setMjpegActive(res.ok);
      } catch {
        if (alive) {
          // If we recently received events for this camera, keep active
          if (latestEvent && latestEvent.camera_id === cameraId) {
            setMjpegActive(true);
          } else {
            setMjpegActive(false);
          }
        }
      }
    }

    checkMjpeg();
    checkTimer.current = setInterval(checkMjpeg, 3000);

    return () => {
      alive = false;
      clearInterval(checkTimer.current);
    };
  }, [cameraId, isUploadCam, isAnalyzing]);

  // If latestEvent comes in for current camera, ensure stream is active
  useEffect(() => {
    if (!mjpegActive && latestEvent && latestEvent.camera_id === cameraId) {
      setMjpegActive(true);
    }
  }, [latestEvent?.frame_id, cameraId]);

  const handleImageError = () => {
    // Only fall back to placeholder if not in active analysis
    if (!isAnalyzing) {
      setMjpegActive(false);
    }
  };

  // Formats camera title cleanly, truncating overly long uploaded video filenames
  const getDisplayTitle = () => {
    if (!activeCamera) return 'All Cameras Overview';
    let name = activeCamera.name || 'Camera Feed';
    if (name.startsWith('Uploaded:')) {
      let raw = name.replace(/^Uploaded:\s*/, '').trim();
      if (raw.length > 28) {
        const dotIdx = raw.lastIndexOf('.');
        const ext = dotIdx !== -1 ? raw.slice(dotIdx) : '';
        const base = dotIdx !== -1 ? raw.slice(0, dotIdx) : raw;
        raw = base.slice(0, 20) + '…' + ext;
      }
      return `Uploaded: ${raw}`;
    }
    return name;
  };

  return (
    <div className="feed-card">
      {/* Feed Header */}
      <div className="feed-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <h2>{getDisplayTitle()}</h2>
            {isUploadCam && (
              <span className="badge badge-upload-cam" style={{ fontSize: '0.7rem' }}>
                CUSTOM VIDEO
              </span>
            )}
          </div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {activeCamera?.junction_name || 'Multi-Stream Aggregation'} &bull; Target: {activeCamera?.fps || fps || 5} FPS
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {mjpegActive && (
            <span className="badge badge-connected" style={{ fontSize: '0.7rem', padding: '0.15rem 0.4rem' }}>
              📹 LIVE VIDEO
            </span>
          )}
          <span className={`badge ${wsStatus === 'CONNECTED' ? 'badge-connected' : 'badge-disconnected'}`}>
            {wsStatus}
          </span>
        </div>
      </div>

      {/* Camera Viewport */}
      <div className="camera-viewport" style={{ position: 'relative', overflow: 'hidden' }}>
        {mjpegActive ? (
          <>
            {/* Crisp MJPEG stream with zero-flicker stable session URL */}
            <img
              ref={imgRef}
              src={`${mjpegUrl}?sid=${streamSessionId}`}
              alt="Live traffic video feed"
              className="mjpeg-stream-image"
              onError={handleImageError}
            />

            {/* Subtle top-left badge overlay: LIVE YOLOv8 INFERENCE */}
            <div className="feed-overlay-badge">
              <span className="pulse-dot-green" />
              <span>LIVE YOLOv8 INFERENCE</span>
              {latestEvent?.processing_time_ms && (
                <span className="overlay-badge-latency">
                  &bull; {latestEvent.processing_time_ms}ms
                </span>
              )}
            </div>

            {/* Live In-Video Telemetry Bar (Bottom) */}
            <div className="feed-overlay-bottom">
              <span className="feed-metric">
                Density: <strong>{(latestEvent?.density ?? 0).toFixed(0)}%</strong>
              </span>
              <span className="feed-metric">
                Vehicles: <strong>{latestEvent?.vehicle_count ?? detections.length}</strong>
              </span>
              {latestEvent?.queue_length != null && (
                <span className="feed-metric">
                  Queue: <strong>{latestEvent.queue_length}</strong>
                </span>
              )}
            </div>
          </>
        ) : (
          /* Placeholder View */
          <div className="feed-placeholder">
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              style={{ margin: '0 auto 0.5rem', display: 'block', color: 'var(--text-muted)' }}
            >
              <path d="M23 7l-7 5 7 5V7z" />
              <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
            </svg>

            {isUploadCam ? (
              <div>
                <strong style={{ fontSize: '1rem', color: 'var(--text-main)' }}>
                  Uploaded Video Ingestion Standby
                </strong>
                <p style={{ fontSize: '0.82rem', margin: '0.35rem auto 1rem', maxWidth: '380px', color: 'var(--text-muted)' }}>
                  Upload a recorded CCTV traffic video file or launch the Quick Demo to start real-time YOLOv8 vehicle detection and flow analysis.
                </p>
                <div style={{ display: 'flex', justifyContent: 'center', gap: '0.6rem' }}>
                  {onOpenUpload && (
                    <button type="button" className="btn-placeholder-primary" onClick={onOpenUpload}>
                      📤 Upload Video File
                    </button>
                  )}
                  {onQuickDemo && (
                    <button type="button" className="btn-placeholder-secondary" onClick={() => onQuickDemo(fps)}>
                      🚀 Quick Demo
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div>
                <div><strong>Live Stream Ingestion Active</strong></div>
                <div style={{ fontSize: '0.8rem', marginTop: '0.25rem', color: 'var(--text-muted)' }}>
                  {latestEvent
                    ? `Last Frame: #${latestEvent.frame_id} @ ${latestEvent.processing_time_ms}ms`
                    : 'Waiting for incoming frames...'}
                </div>
                {detections.length > 0 && (
                  <div style={{ marginTop: '0.5rem', color: 'var(--accent-green)' }}>
                    Active Bounding Boxes: {detections.length}
                  </div>
                )}
                <div style={{ marginTop: '1rem', fontSize: '0.75rem', color: 'var(--text-muted)', opacity: 0.7 }}>
                  Run a video demo or upload a video to inspect live inference here:<br />
                  <code style={{ fontSize: '0.7rem', color: 'var(--accent-green)' }}>
                    python -m demo.video_demo --video traffic.mp4
                  </code>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Neat Analysis Complete Summary Overlay */}
        {isUploadCam && isComplete && (
          <div className="analysis-summary-overlay">
            <div className="summary-card">
              <div className="summary-icon">✓</div>
              <h3 className="summary-title">Analysis Complete</h3>
              <p className="summary-subtitle">YOLOv8 Edge Traffic Tracking Finished</p>

              <div className="summary-stats-grid">
                <div className="summary-stat-box">
                  <span className="summary-stat-label">Total Vehicles Processed</span>
                  <span className="summary-stat-value">{totalVehicles || latestEvent?.vehicle_count || 0}</span>
                </div>
                <div className="summary-stat-box">
                  <span className="summary-stat-label">Frames Analyzed</span>
                  <span className="summary-stat-value">{totalFrames || currentFrame || latestEvent?.frame_id || 0}</span>
                </div>
                <div className="summary-stat-box">
                  <span className="summary-stat-label">Average Density</span>
                  <span className="summary-stat-value">{(latestEvent?.density ?? 0).toFixed(0)}%</span>
                </div>
              </div>

              <div className="summary-actions">
                {onReplay && (
                  <button type="button" className="summary-btn-replay" onClick={onReplay}>
                    🔄 Replay
                  </button>
                )}
                {onOpenUpload && (
                  <button type="button" className="summary-btn-new" onClick={onOpenUpload}>
                    📤 Upload Another Video
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
