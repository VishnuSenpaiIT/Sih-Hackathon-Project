import React from 'react';
import HardwareBadge from './HardwareBadge';

export default function Dashboard({ latestEvent, hardwareState: propHardwareState }) {
  // Resolve hardware bridge state from props, latestEvent, or fallback
  const currentHardwareState = propHardwareState || latestEvent?.hardware_state || {
    connected: false,
    mode: 'simulated',
    last_command: latestEvent?.hardware_command || 'G',
    port: null,
  };

  const isOverrideActive =
    currentHardwareState.last_command === 'A' ||
    currentHardwareState.last_command === 'OVERRIDE' ||
    Boolean(latestEvent?.is_anomaly);

  const vehicleCount = latestEvent?.vehicle_count ?? 0;
  const density = latestEvent?.density ?? 0;
  const classCounts = latestEvent?.class_counts || {
    car: 0,
    bus: 0,
    truck: 0,
    bike: 0,
    pedestrian: 0
  };
  const latency = latestEvent?.processing_time_ms ?? 0;

  // Congestion Threshold Evaluation (>75 is critical warning)
  const isCongested = density >= 75;
  const isModerate = density >= 55 && density < 75;

  let densityColor = 'var(--accent-green)';
  let congestionStatus = 'FREE FLOW';
  let badgeClass = 'badge-flow-normal';

  if (isCongested) {
    densityColor = 'var(--accent-red)';
    congestionStatus = 'CONGESTION WARNING (>75)';
    badgeClass = 'badge-flow-critical';
  } else if (isModerate) {
    densityColor = 'var(--accent-amber)';
    congestionStatus = 'MODERATE FLOW';
    badgeClass = 'badge-flow-moderate';
  } else if (density >= 25) {
    densityColor = 'var(--accent-blue)';
    congestionStatus = 'NORMAL FLOW';
    badgeClass = 'badge-flow-normal';
  }

  return (
    <div className="stats-sidebar">
      {/* Emergency Incident / Accident Override Banner */}
      {isOverrideActive && (
        <div className="accident-override-banner">
          <div className="alert-header">
            <span className="pulse-dot-red" />
            <strong>🚨 HARDWARE OVERRIDE ACTIVE</strong>
          </div>
          <p>
            Emergency incident detected. Physical/simulated signal actuator locked into emergency override.
          </p>
        </div>
      )}

      {/* Hardware Actuation & Physical Bridge Card */}
      <div className="stat-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.65rem' }}>
          <h3>Hardware Bridge</h3>
          <HardwareBadge hardwareState={currentHardwareState} />
        </div>
        <div className="hw-kpi-grid">
          <div className="hw-kpi-item">
            <span className="hw-kpi-label">Mode</span>
            <span className="hw-kpi-val" style={{ textTransform: 'capitalize' }}>
              {currentHardwareState.mode || 'Simulated'}
            </span>
          </div>
          <div className="hw-kpi-item">
            <span className="hw-kpi-label">Actuation</span>
            <span className="hw-kpi-val" style={{ fontFamily: 'monospace' }}>
              '{currentHardwareState.last_command || 'G'}'
            </span>
          </div>
          <div className="hw-kpi-item">
            <span className="hw-kpi-label">Link</span>
            <span className="hw-kpi-val">
              {currentHardwareState.connected ? (currentHardwareState.port || 'USB Serial') : 'Virtual Bridge'}
            </span>
          </div>
        </div>
      </div>

      {/* Congestion Threshold Alert Banner */}
      {isCongested && (
        <div className="congestion-alert-banner">
          <div className="alert-header">
            <span className="pulse-dot-red" />
            <strong>⚠️ THRESHOLD EXCEEDED</strong>
          </div>
          <p>
            Density at <strong>{density.toFixed(1)}%</strong> exceeds 75% threshold. Adaptive green extension recommended.
          </p>
        </div>
      )}

      {/* Traffic Density Card */}
      <div className="stat-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <h3>Traffic Density</h3>
          <span style={{ fontWeight: 700, fontSize: '1.1rem', color: densityColor }}>
            {density.toFixed(1)} / 100
          </span>
        </div>

        {/* Dynamic Status Badge */}
        <div style={{ marginTop: '0.35rem', marginBottom: '0.5rem' }}>
          <span className={`badge ${badgeClass}`}>
            {congestionStatus}
          </span>
        </div>

        <div className="density-bar-container">
          <div
            className="density-bar-fill"
            style={{ width: `${Math.min(100, Math.max(0, density))}%`, backgroundColor: densityColor }}
          />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>
          <span>Queue Est: {latestEvent?.queue_length ?? 0}m</span>
          <span>Threshold: 75% Limit</span>
        </div>
      </div>

      {/* Total Vehicles Card */}
      <div className="stat-card">
        <h3>Live Vehicle Count</h3>
        <div className="stat-value-large">{vehicleCount}</div>
        <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
          Motorized units in field of view
        </p>
      </div>

      {/* Vehicle Classification Breakdown */}
      <div className="stat-card">
        <h3>Vehicle Classification</h3>
        <div className="class-grid">
          <div className="class-pill">
            <span>🚗 Car</span>
            <strong>{classCounts.car}</strong>
          </div>
          <div className="class-pill">
            <span>🚌 Bus</span>
            <strong>{classCounts.bus}</strong>
          </div>
          <div className="class-pill">
            <span>🚛 Truck</span>
            <strong>{classCounts.truck}</strong>
          </div>
          <div className="class-pill">
            <span>🏍️ Bike</span>
            <strong>{classCounts.bike}</strong>
          </div>
        </div>
        <div style={{ marginTop: '0.5rem' }}>
          <div className="class-pill">
            <span>🚶 Pedestrians</span>
            <strong>{classCounts.pedestrian}</strong>
          </div>
        </div>
      </div>

      {/* Edge Latency & Performance */}
      <div className="stat-card">
        <h3>Inference Latency</h3>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '1.25rem', fontWeight: 600 }}>{latency} ms</span>
          <span className="badge" style={{ backgroundColor: latency < 100 ? 'rgba(16,185,129,0.2)' : 'rgba(245,158,11,0.2)', color: latency < 100 ? 'var(--accent-green)' : 'var(--accent-amber)' }}>
            {latency < 100 ? 'Target Met (<100ms)' : 'Processing'}
          </span>
        </div>
      </div>
    </div>
  );
}
