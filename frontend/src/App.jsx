import React, { useState, useEffect } from 'react';
import CameraFeed from './components/CameraFeed';
import Dashboard from './components/Dashboard';
import PredictionChart from './components/PredictionChart';
import VideoUploadModal from './components/VideoUploadModal';
import {
  fetchStreams,
  connectTrafficWebSocket,
  uploadTrafficVideo,
  triggerSampleAnalysis,
  stopVideoAnalysis,
} from './services/api';

const DEFAULT_STREAMS = [
  {
    id: 'cam_01',
    name: 'Connaught Place Junction',
    junction_name: 'Outer Circle Junction',
    fps: 5,
    enabled: true
  },
  {
    id: 'cam_02',
    name: 'Silk Board Intersection',
    junction_name: 'Corridor Node 4',
    fps: 5,
    enabled: true
  },
  {
    id: 'cam_mobile_demo',
    name: 'Mobile Live Stream',
    junction_name: 'Mobile Field Unit',
    fps: 5,
    enabled: true
  }
];

export default function App() {
  const [streams, setStreams] = useState(DEFAULT_STREAMS);
  const [selectedCameraId, setSelectedCameraId] = useState('cam_01');
  const [latestEvent, setLatestEvent] = useState(null);
  const [cameraEvents, setCameraEvents] = useState({});
  const [wsStatus, setWsStatus] = useState('CONNECTING');

  // Video Analysis & Ingestion State
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [hasUploadedCamera, setHasUploadedCamera] = useState(false);
  const [targetFps, setTargetFps] = useState(10);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [analysisState, setAnalysisState] = useState({
    status: 'idle', // 'idle' | 'uploading' | 'analyzing' | 'completed' | 'stopped'
    currentFrame: 0,
    totalFrames: 0,
    progressPercent: 0,
    fps: 10,
    latencyMs: 28,
    totalVehicles: 0,
    fileName: '',
    error: '',
    replayCount: 0,
  });

  useEffect(() => {
    // Load configured camera sources from backend
    fetchStreams()
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setStreams(data);
          setSelectedCameraId((prev) => {
            if (prev === 'cam_upload') return prev;
            const exists = data.some((c) => c.id === prev);
            return exists ? prev : data[0].id;
          });
        }
      })
      .catch((err) => {
        console.warn('Using default camera configurations (API offline):', err);
      });
  }, []);

  useEffect(() => {
    // Establish WebSocket stream subscription
    const disconnect = connectTrafficWebSocket(
      (payload) => {
        // 1. Handle live analysis progress updates (10-15 Hz)
        if (payload.type === 'analysis_progress') {
          const data = payload.data || payload;
          const current_frame = data.current_frame ?? data.frame_id ?? 0;
          const total_frames = data.total_frames ?? 0;
          const progress_percent =
            data.progress_percent ??
            (total_frames > 0 ? (current_frame / total_frames) * 100 : 0);
          const fps = data.fps ?? data.current_fps ?? targetFps;
          const status = data.status || 'analyzing';
          const latency_ms = data.processing_time_ms ?? data.latency_ms ?? 28;
          const total_vehicles = data.total_vehicles ?? data.vehicle_count ?? 0;

          setAnalysisState((prev) => ({
            ...prev,
            status,
            currentFrame: current_frame,
            totalFrames: total_frames,
            progressPercent: Math.min(100, Math.max(0, progress_percent)),
            fps,
            latencyMs: latency_ms,
            totalVehicles: total_vehicles,
            fileName: data.file_name || prev.fileName || 'traffic_video.mp4',
          }));

          // Dynamically reveal cam_upload tab and switch to it
          setHasUploadedCamera(true);
          if (status === 'analyzing') {
            setSelectedCameraId('cam_upload');
          }
        }

        // 2. Handle detection updates per frame
        if (payload.type === 'traffic_update' && payload.data) {
          const eventData = payload.data;
          const camId = eventData.camera_id;

          if (camId === 'cam_upload') {
            setHasUploadedCamera(true);
          }

          // Track latest event per camera
          setCameraEvents((prev) => ({
            ...prev,
            [camId]: eventData
          }));

          // Update main event if it belongs to selected camera or global subscription
          if (!selectedCameraId || camId === selectedCameraId) {
            setLatestEvent(eventData);
          }
        }
      },
      (status) => setWsStatus(status),
      selectedCameraId || null
    );

    return () => disconnect();
  }, [selectedCameraId, targetFps]);

  // Upload Video File Handler
  const handleUploadFile = async (file, fpsRate) => {
    setIsUploading(true);
    setUploadProgress(0);
    setHasUploadedCamera(true);
    setSelectedCameraId('cam_upload');
    setAnalysisState((prev) => ({
      ...prev,
      status: 'uploading',
      fileName: file.name,
      error: '',
    }));

    try {
      await uploadTrafficVideo(file, fpsRate, (percent) => {
        setUploadProgress(percent);
      });
      setIsUploading(false);
      setUploadProgress(null);
      setAnalysisState((prev) => ({
        ...prev,
        status: 'analyzing',
        currentFrame: 0,
        progressPercent: 0,
        fps: fpsRate,
      }));
    } catch (err) {
      console.error('Upload failed:', err);
      setIsUploading(false);
      setUploadProgress(null);
      setAnalysisState((prev) => ({
        ...prev,
        status: 'idle',
        error: err.message || 'Failed to upload video',
      }));
    }
  };

  // Quick Demo (Sample Video) Trigger
  const handleQuickDemo = async (fpsRate) => {
    setHasUploadedCamera(true);
    setSelectedCameraId('cam_upload');
    setAnalysisState((prev) => ({
      ...prev,
      status: 'analyzing',
      fileName: 'sample_junction_traffic.mp4',
      currentFrame: 0,
      progressPercent: 0,
      fps: fpsRate,
      error: '',
      replayCount: prev.replayCount + 1,
    }));

    try {
      await triggerSampleAnalysis(fpsRate);
    } catch (err) {
      console.warn('Quick demo endpoint response:', err);
      setAnalysisState((prev) => ({
        ...prev,
        error: err.message || 'Failed to trigger sample video analysis',
      }));
    }
  };

  // Stop / Cancel Active Video Analysis
  const handleStopAnalysis = async () => {
    try {
      await stopVideoAnalysis();
    } catch (err) {
      console.warn('Stop analysis error:', err);
    }
    setAnalysisState((prev) => ({
      ...prev,
      status: 'stopped',
    }));
  };

  // Replay Completed Video
  const handleReplayAnalysis = () => {
    setAnalysisState((prev) => ({
      ...prev,
      status: 'analyzing',
      currentFrame: 0,
      progressPercent: 0,
      replayCount: prev.replayCount + 1,
    }));
    handleQuickDemo(targetFps);
  };

  // Dynamic Upload Camera Definition
  const UPLOAD_CAMERA = {
    id: 'cam_upload',
    name: 'Uploaded Video',
    junction_name: 'Custom Video Ingestion',
    fps: targetFps,
    enabled: true,
    isUploadedVideo: true,
  };

  // Build stream array including dynamic cam_upload when active
  const allStreams = hasUploadedCamera && !streams.some((s) => s.id === 'cam_upload')
    ? [...streams, UPLOAD_CAMERA]
    : streams;

  const activeCamera = allStreams.find((s) => s.id === selectedCameraId) || allStreams[0];
  const activeEvent = (selectedCameraId && cameraEvents[selectedCameraId]) || latestEvent;
  const activeDensity = activeEvent?.density ?? 0;
  const isHighCongestion = activeDensity >= 75;

  return (
    <div className="app-container">
      {/* Brand Header */}
      <header className="header">
        <div className="brand">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="6" y="2" width="12" height="20" rx="3" />
            <circle cx="12" cy="6" r="2" fill="var(--accent-red)" stroke="none" />
            <circle cx="12" cy="12" r="2" fill="var(--accent-amber)" stroke="none" />
            <circle cx="12" cy="18" r="2" fill="var(--accent-green)" stroke="none" />
          </svg>
          <div>
            <h1 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Smart Traffic Intelligence</h1>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              SIH26222 &bull; Software-First Monitoring & Prediction
            </span>
          </div>
        </div>

        {/* Header Alert, Upload Button & System Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {/* Upload Video Button in Header */}
          <button
            type="button"
            className="header-upload-btn"
            onClick={() => setIsUploadModalOpen(true)}
            aria-label="Upload traffic video"
          >
            <span style={{ fontSize: '1rem' }}>📤</span>
            <span>Upload Video</span>
            {analysisState.status === 'analyzing' && (
              <span className="status-dot status-dot-active" style={{ width: '7px', height: '7px' }} />
            )}
          </button>

          {isHighCongestion && (
            <span className="badge badge-warning-pulse" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span className="pulse-dot-red" />
              <span>ALERT: DENSITY &gt; 75%</span>
            </span>
          )}
          <span className={`badge ${wsStatus === 'CONNECTED' ? 'badge-connected' : 'badge-disconnected'}`}>
            {wsStatus}
          </span>
        </div>
      </header>

      {/* Multi-Camera Switcher Tabs with Dynamic cam_upload Tab */}
      <nav className="camera-switcher-container" aria-label="Camera Switcher">
        <div className="camera-switcher-label">CCTV Feeds:</div>
        <div className="camera-tabs-list">
          {allStreams.map((cam) => {
            const isSelected = cam.id === selectedCameraId;
            const camEvent = cameraEvents[cam.id];
            const camDensity = camEvent?.density;
            const isCamAlert = camDensity != null && camDensity >= 75;
            const isUploadCam = cam.id === 'cam_upload';
            const isAnalyzingThisCam = isUploadCam && analysisState.status === 'analyzing';

            return (
              <button
                key={cam.id}
                type="button"
                className={`camera-tab-btn ${isSelected ? 'active' : ''} ${isUploadCam ? 'camera-tab-upload' : ''}`}
                onClick={() => setSelectedCameraId(cam.id)}
              >
                {/* Status Dot: Pulsing green during active video analysis */}
                <span
                  className={`status-dot ${
                    isAnalyzingThisCam
                      ? 'status-dot-active'
                      : wsStatus === 'CONNECTED'
                        ? isCamAlert
                          ? 'status-dot-alert'
                          : 'status-dot-active'
                        : 'status-dot-offline'
                  }`}
                />

                <div className="camera-tab-info">
                  <div className="camera-tab-title">
                    {isUploadCam ? '📹 Uploaded Video' : cam.name}
                  </div>
                  <div className="camera-tab-subtitle">
                    {isUploadCam
                      ? isAnalyzingThisCam
                        ? `Analyzing • ${analysisState.fps || targetFps} FPS`
                        : 'Custom Ingestion'
                      : `${cam.junction_name || cam.id} • ${cam.fps || 5} FPS`}
                  </div>
                </div>

                {/* Camera Congestion Mini-Badge */}
                {camDensity != null && (
                  <span
                    className={`badge ${isCamAlert ? 'badge-flow-critical' : 'badge-flow-normal'}`}
                    style={{ fontSize: '0.7rem', padding: '0.15rem 0.35rem' }}
                  >
                    {camDensity.toFixed(0)}%
                  </span>
                )}
              </button>
            );
          })}

          {/* Quick Upload Video Tab Button */}
          <button
            type="button"
            className="camera-tab-btn camera-tab-upload-action"
            onClick={() => setIsUploadModalOpen(true)}
            title="Upload a new traffic video or launch demo"
          >
            <span style={{ fontSize: '1rem' }}>📤</span>
            <div className="camera-tab-info">
              <div className="camera-tab-title">Upload Video</div>
              <div className="camera-tab-subtitle">Inference Demo</div>
            </div>
          </button>
        </div>
      </nav>

      {/* Main Content Layout */}
      <main className="main-content">
        {/* Left Column: Live Feed + Prediction Chart */}
        <div className="feed-column">
          <CameraFeed
            activeCamera={activeCamera}
            latestEvent={activeEvent}
            wsStatus={wsStatus}
            analysisState={analysisState}
            onReplay={handleReplayAnalysis}
            onOpenUpload={() => setIsUploadModalOpen(true)}
            onQuickDemo={handleQuickDemo}
          />

          <PredictionChart
            cameraId={selectedCameraId}
            currentDensity={activeDensity}
          />
        </div>

        {/* Right Column: Key Stats & Live Breakdown Sidebar */}
        <Dashboard latestEvent={activeEvent} />
      </main>

      {/* Video Upload & Real-Time Analysis Progress Modal */}
      <VideoUploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUploadFile={handleUploadFile}
        onQuickDemo={handleQuickDemo}
        onStopAnalysis={handleStopAnalysis}
        onReplayAnalysis={handleReplayAnalysis}
        onViewFeed={() => setSelectedCameraId('cam_upload')}
        analysisState={analysisState}
        targetFps={targetFps}
        setTargetFps={setTargetFps}
        uploadProgress={uploadProgress}
        isUploading={isUploading}
      />
    </div>
  );
}
