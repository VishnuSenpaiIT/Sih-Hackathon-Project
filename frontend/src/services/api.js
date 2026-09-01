/**
 * API & WebSocket Client Service (frontend/src/services/api.js)
 * Smart Traffic Monitoring & Prediction System (SIH26222)
 */

const API_BASE = '/api';

export async function fetchStreams() {
  const res = await fetch(`${API_BASE}/streams`);
  if (!res.ok) {
    throw new Error(`Failed to fetch streams: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
    throw new Error(`Failed to fetch health: ${res.statusText}`);
  }
  return res.json();
}

/**
 * Fetch current hardware actuation bridge status (Arduino Uno / Simulated).
 * Gracefully returns simulated defaults if backend endpoint is unavailable.
 */
export async function fetchHardwareStatus() {
  try {
    const res = await fetch(`${API_BASE}/hardware/status`);
    if (!res.ok) {
      return {
        connected: false,
        mode: 'simulated',
        last_command: 'G',
        port: null,
      };
    }
    return await res.json();
  } catch (err) {
    return {
      connected: false,
      mode: 'simulated',
      last_command: 'G',
      port: null,
    };
  }
}

export async function fetchPredictions(cameraId, horizonHours = 6) {
  const res = await fetch(`${API_BASE}/predictions/${encodeURIComponent(cameraId)}?horizon_hours=${horizonHours}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch predictions: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchDetections(cameraId = null, limit = 20) {
  const url = cameraId
    ? `${API_BASE}/detections?camera_id=${encodeURIComponent(cameraId)}&limit=${limit}`
    : `${API_BASE}/detections?limit=${limit}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch detections: ${res.statusText}`);
  }
  return res.json();
}

export function connectTrafficWebSocket(onMessage, onStatusChange, cameraId = null) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  const url = `${protocol}//${host}/ws${cameraId ? `?camera_id=${encodeURIComponent(cameraId)}` : ''}`;

  let ws = null;
  let isClosedManually = false;
  let reconnectTimer = null;

  function connect() {
    onStatusChange('CONNECTING');
    ws = new WebSocket(url);

    ws.onopen = () => {
      onStatusChange('CONNECTED');
    };

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        onMessage(payload);
      } catch (err) {
        console.error('Error parsing WebSocket frame:', err);
      }
    };

    ws.onerror = (err) => {
      console.warn('WebSocket error encountered:', err);
      onStatusChange('ERROR');
    };

    ws.onclose = () => {
      if (!isClosedManually) {
        onStatusChange('DISCONNECTED');
        reconnectTimer = setTimeout(connect, 3000);
      }
    };
  }

  connect();

  return () => {
    isClosedManually = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    if (ws) ws.close();
  };
}

/**
 * Upload a traffic video file for YOLOv8 analysis.
 * Uses XMLHttpRequest to provide precise upload progress callbacks.
 */
export function uploadTrafficVideo(file, targetFps = 10, onProgress = null) {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('target_fps', targetFps);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API_BASE}/video-analysis/upload`);
    xhr.timeout = 180000; // 3-minute timeout for larger video uploads

    if (xhr.upload && onProgress) {
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percent = Math.round((event.loaded / event.total) * 100);
          onProgress(percent);
        }
      };
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText);
          resolve(data);
        } catch {
          resolve({ status: 'ok' });
        }
      } else {
        try {
          const errData = JSON.parse(xhr.responseText);
          reject(new Error(errData.detail || `Upload failed (status ${xhr.status})`));
        } catch {
          reject(new Error(`Upload failed with status ${xhr.status}: ${xhr.statusText}`));
        }
      }
    };

    xhr.ontimeout = () => {
      reject(new Error('Upload timed out after 3 minutes. Please try again.'));
    };

    xhr.onerror = () => {
      reject(new Error('Connection error during upload. Ensure backend server is reachable.'));
    };

    xhr.send(formData);
  });
}


/**
 * Start instant demo analysis using server-side sample traffic video.
 */
export async function triggerSampleAnalysis(targetFps = 10) {
  const res = await fetch(`${API_BASE}/video-analysis/sample`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_fps: targetFps })
  });
  if (!res.ok) {
    let errorDetail = res.statusText;
    try {
      const err = await res.json();
      if (err.detail) errorDetail = err.detail;
    } catch {
      // ignore json parse error
    }
    throw new Error(`Sample analysis failed: ${errorDetail}`);
  }
  return res.json();
}

/**
 * Request stopping/canceling active video analysis.
 */
export async function stopVideoAnalysis() {
  const res = await fetch(`${API_BASE}/video-analysis/stop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });
  if (!res.ok) {
    throw new Error(`Failed to stop video analysis: ${res.statusText}`);
  }
  return res.json();
}

/**
 * Fetch current video analysis job status.
 */
export async function fetchAnalysisStatus() {
  const res = await fetch(`${API_BASE}/video-analysis/status`);
  if (!res.ok) {
    throw new Error(`Failed to fetch status: ${res.statusText}`);
  }
  return res.json();
}
