import React, { useState, useRef, useEffect } from 'react';

/**
 * VideoUploadModal.jsx
 * Cyberpunk Dark-Themed Traffic Video Upload & Real-Time Telemetry Modal
 * Smart Traffic Monitoring & Prediction System (SIH26222)
 */
export default function VideoUploadModal({
  isOpen,
  onClose,
  onUploadFile,
  onQuickDemo,
  onStopAnalysis,
  onReplayAnalysis,
  onViewFeed,
  analysisState = {},
  targetFps = 10,
  setTargetFps,
  uploadProgress = null,
  isUploading = false,
}) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [localError, setLocalError] = useState('');
  const fileInputRef = useRef(null);

  // Close on ESC key
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const {
    status = 'idle',
    currentFrame = 0,
    totalFrames = 0,
    progressPercent = 0,
    fps = targetFps || 10,
    latencyMs = 28,
    totalVehicles = 0,
    fileName = '',
    error = '',
  } = analysisState;

  const isAnalyzing = status === 'analyzing';
  const isCompleted = status === 'completed';
  const isStopped = status === 'stopped';

  // Allowed MIME types / extensions
  const ALLOWED_TYPES = ['video/mp4', 'video/avi', 'video/quicktime', 'video/x-matroska', 'video/webm', 'video/mkv'];

  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const validateAndSetFile = (file) => {
    setLocalError('');
    if (!file) return;

    const ext = file.name.split('.').pop()?.toLowerCase();
    const validExts = ['mp4', 'avi', 'mov', 'mkv', 'webm'];

    if (!ALLOWED_TYPES.includes(file.type) && !validExts.includes(ext)) {
      setLocalError(`Unsupported video format (.${ext}). Please upload MP4, AVI, MOV, MKV, or WEBM.`);
      return;
    }

    setSelectedFile(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileInputChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const handleStartUpload = () => {
    if (!selectedFile) {
      setLocalError('Please select or drop a traffic video file first.');
      return;
    }
    setLocalError('');
    onUploadFile(selectedFile, targetFps);
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return '0 B';
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(1)} MB`;
  };

  return (
    <div className="video-modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div
        className="video-modal-card"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="video-modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <span className="video-modal-cyber-icon">📹</span>
            <div>
              <h2 className="video-modal-title">Traffic Video Analysis Ingestion</h2>
              <p className="video-modal-subtitle">
                Feed footage directly into YOLOv8 Edge Inference &amp; Real-Time Density Tracker
              </p>
            </div>
          </div>
          <button
            type="button"
            className="video-modal-close-btn"
            onClick={onClose}
            aria-label="Close dialog"
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="video-modal-body">
          {/* Quick Demo Banner */}
          <div className="quick-demo-banner">
            <div className="quick-demo-info">
              <div className="quick-demo-badge">ONE-CLICK DEMO</div>
              <div className="quick-demo-title">Want to test without uploading your own file?</div>
              <div className="quick-demo-desc">
                Launch the built-in urban traffic junction video with full vehicle tracking &amp; flow metrics instantly.
              </div>
            </div>
            <button
              type="button"
              className="quick-demo-btn"
              disabled={isUploading || isAnalyzing}
              onClick={() => {
                setLocalError('');
                onQuickDemo(targetFps);
              }}
            >
              🚀 Quick Demo (Sample Video)
            </button>
          </div>

          {/* Target Analysis FPS Selector */}
          <div className="fps-selector-section">
            <label className="fps-label">
              <span className="fps-label-text">Target Analysis FPS:</span>
              <span className="fps-label-hint">(Controls edge inferencing throughput &amp; frame skip rate)</span>
            </label>
            <div className="fps-pill-group">
              {[5, 10, 15].map((rate) => (
                <button
                  key={rate}
                  type="button"
                  disabled={isAnalyzing || isUploading}
                  className={`fps-pill ${targetFps === rate ? 'active' : ''}`}
                  onClick={() => setTargetFps && setTargetFps(rate)}
                >
                  <span className="fps-value">{rate} FPS</span>
                  {rate === 10 && <span className="fps-recommended-tag">Recommended</span>}
                </button>
              ))}
            </div>
          </div>

          {/* Drag and Drop Zone */}
          <div
            className={`video-dropzone ${isDragOver ? 'drag-over' : ''} ${selectedFile ? 'has-file' : ''}`}
            onDragEnter={handleDragEnter}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="video/mp4,video/avi,video/quicktime,video/mkv,video/webm"
              style={{ display: 'none' }}
              onChange={handleFileInputChange}
            />

            <div className="dropzone-inner">
              <div className="dropzone-icon-wrapper">
                <svg
                  width="36"
                  height="36"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.75"
                  className="dropzone-svg"
                >
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              </div>

              {selectedFile ? (
                <div className="file-info-box">
                  <div className="file-name" title={selectedFile.name}>
                    📄 {selectedFile.name}
                  </div>
                  <div className="file-meta">
                    Size: {formatFileSize(selectedFile.size)} &bull; Format: {selectedFile.name.split('.').pop()?.toUpperCase()}
                  </div>
                  <div className="change-file-hint">Click or drop another video to replace</div>
                </div>
              ) : (
                <div className="dropzone-text-group">
                  <div className="dropzone-primary-text">
                    Drag &amp; drop your traffic video here, or <span className="browse-link">browse</span>
                  </div>
                  <div className="dropzone-secondary-text">
                    Supports MP4, AVI, MOV, MKV, WEBM (up to 500MB)
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Upload Button */}
          {selectedFile && !isAnalyzing && (
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.75rem' }}>
              <button
                type="button"
                className="analyze-upload-btn"
                disabled={isUploading}
                onClick={handleStartUpload}
              >
                {isUploading ? 'Uploading Video...' : '⚡ Upload & Start YOLOv8 Analysis'}
              </button>
            </div>
          )}

          {/* Error notice */}
          {(localError || error) && (
            <div className="modal-error-banner">
              ⚠️ {localError || error}
            </div>
          )}

          {/* Upload Progress Indicator */}
          {isUploading && uploadProgress !== null && (
            <div className="upload-progress-card">
              <div className="progress-header">
                <span className="progress-title">Uploading Video Footage to Edge Buffer...</span>
                <span className="progress-percent-badge">{uploadProgress}%</span>
              </div>
              <div className="progress-track">
                <div
                  className="progress-fill upload-fill"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <div className="progress-subtext">
                Transmitting bytes to inference pipeline. Analysis will begin automatically.
              </div>
            </div>
          )}

          {/* Live Analysis Progress Card */}
          {(isAnalyzing || isCompleted || isStopped) && (
            <div className="live-analysis-card">
              <div className="live-analysis-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <span className="live-analysis-title">Live Analysis Progress</span>
                  {fileName && (
                    <span className="live-analysis-filename" title={fileName}>
                      ({fileName})
                    </span>
                  )}
                </div>

                {/* Status Pill */}
                <div>
                  {isAnalyzing && (
                    <span className="status-pill status-pill-analyzing">
                      <span className="status-pulse-dot" />
                      ANALYZING LIVE
                    </span>
                  )}
                  {isCompleted && (
                    <span className="status-pill status-pill-completed">
                      ✓ COMPLETED
                    </span>
                  )}
                  {isStopped && (
                    <span className="status-pill status-pill-stopped">
                      ⏹ STOPPED
                    </span>
                  )}
                </div>
              </div>

              {/* Progress Bar with Percentage */}
              <div className="analysis-progress-bar-container">
                <div className="progress-bar-label-row">
                  <span className="progress-bar-label">
                    [{progressPercent >= 10 ? '='.repeat(Math.min(20, Math.floor(progressPercent / 5))) + '>' : '>'}{' '.repeat(Math.max(0, 20 - Math.floor(progressPercent / 5)))}]
                  </span>
                  <span className="progress-bar-percent">
                    {progressPercent.toFixed(1)}%
                  </span>
                </div>
                <div className="progress-track">
                  <div
                    className={`progress-fill ${isCompleted ? 'progress-fill-completed' : 'progress-fill-active'}`}
                    style={{ width: `${Math.min(100, Math.max(0, progressPercent))}%` }}
                  />
                </div>
              </div>

              {/* Live Stats Ticker */}
              <div className="live-stats-ticker">
                <span className="ticker-item">
                  <strong>Frame</strong> {currentFrame} {totalFrames > 0 ? `/ ${totalFrames}` : ''}
                </span>
                <span className="ticker-dot">&bull;</span>
                <span className="ticker-item">
                  <strong>{fps.toFixed(1)}</strong> FPS
                </span>
                <span className="ticker-dot">&bull;</span>
                <span className="ticker-item">
                  <strong>{latencyMs}ms</strong> latency
                </span>
                {totalVehicles > 0 && (
                  <>
                    <span className="ticker-dot">&bull;</span>
                    <span className="ticker-item" style={{ color: 'var(--accent-green)' }}>
                      <strong>{totalVehicles}</strong> vehicles detected
                    </span>
                  </>
                )}
              </div>

              {/* Action Controls */}
              <div className="analysis-actions-row">
                <button
                  type="button"
                  className="view-feed-btn"
                  onClick={() => {
                    if (onViewFeed) onViewFeed();
                    onClose();
                  }}
                >
                  👁 Switch to Camera Feed View
                </button>

                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  {isAnalyzing && (
                    <button
                      type="button"
                      className="stop-analysis-btn"
                      onClick={onStopAnalysis}
                    >
                      ⏹ Stop Analysis
                    </button>
                  )}

                  {isCompleted && (
                    <button
                      type="button"
                      className="replay-btn"
                      onClick={onReplayAnalysis}
                    >
                      🔄 Replay Analysis
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="video-modal-footer">
          <div className="cyber-footer-note">
            <span className="cyber-dot" />
            YOLOv8 nano edge pipeline &bull; Real-time IoU / ByteTrack vehicle tracing
          </div>
          <button type="button" className="video-modal-dismiss-btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
