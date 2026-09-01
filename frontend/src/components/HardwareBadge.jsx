import React from 'react';

/**
 * HardwareStatusBadge Component (frontend/src/components/HardwareBadge.jsx)
 * Smart Traffic Monitoring & Prediction System (SIH26222)
 *
 * Implements Sections 7 & 11 of Hardware Integration Specification:
 * - Minimalist, pure CSS status badge & actuation pill
 * - Operational states: SIMULATED (default), CONNECTED (real), OFFLINE
 * - Active actuation pill displaying physical/simulated LED color: GREEN, YELLOW, RED, OVERRIDE
 */

export default function HardwareBadge({ hardwareState = null, showActuation = true, className = '' }) {
  // Normalize state safely with fallback defaults
  const state = hardwareState || {
    connected: false,
    mode: 'simulated',
    last_command: 'G',
    port: null,
  };

  const mode = (state.mode || (state.connected ? 'real' : 'simulated')).toLowerCase();
  const rawCommand = (state.last_command || 'G').toString().trim().toUpperCase();

  // Resolve 3 distinct operational states per spec
  let opState = 'SIMULATED';
  let badgeIcon = '⚡';
  let badgeLabel = 'HW: SIMULATED';
  let badgeTooltip = 'Hardware Bridge Active (Simulated Arduino Uno)';
  let badgeClass = 'hw-badge-simulated';

  if (mode === 'real' || (state.connected && mode !== 'offline' && mode !== 'simulated')) {
    opState = 'CONNECTED';
    const portName = state.port || 'COM3';
    badgeIcon = '🟢';
    badgeLabel = `HW: CONNECTED (${portName})`;
    badgeTooltip = 'Physical Arduino Uno Linked & Responding';
    badgeClass = 'hw-badge-connected';
  } else if (mode === 'offline') {
    opState = 'OFFLINE';
    badgeIcon = '⚠️';
    badgeLabel = 'HW: OFFLINE';
    badgeTooltip = 'Arduino Disconnected — Falling back to Simulated';
    badgeClass = 'hw-badge-offline';
  } else {
    // Default SIMULATED
    opState = 'SIMULATED';
    badgeIcon = '⚡';
    badgeLabel = 'HW: SIMULATED';
    badgeTooltip = 'Hardware Bridge Active (Simulated Arduino Uno)';
    badgeClass = 'hw-badge-simulated';
  }

  // Resolve active actuation pill (LED color / Override)
  let actuationIcon = '🟢';
  let actuationLabel = 'GREEN';
  let actuationClass = 'actuation-pill-green';
  let actuationTitle = 'Signal Actuation: Green Light (Normal Flow)';

  if (rawCommand === 'Y' || rawCommand === 'YELLOW') {
    actuationIcon = '🟡';
    actuationLabel = 'YELLOW';
    actuationClass = 'actuation-pill-yellow';
    actuationTitle = 'Signal Actuation: Yellow Caution (Moderate Flow)';
  } else if (rawCommand === 'R' || rawCommand === 'RED') {
    actuationIcon = '🔴';
    actuationLabel = 'RED';
    actuationClass = 'actuation-pill-red';
    actuationTitle = 'Signal Actuation: Red Stop (Congestion Hold)';
  } else if (rawCommand === 'A' || rawCommand === 'OVERRIDE' || rawCommand === 'ACCIDENT') {
    actuationIcon = '🚨';
    actuationLabel = 'OVERRIDE';
    actuationClass = 'actuation-pill-override';
    actuationTitle = 'Emergency Actuation: Accident/Incident Override Active';
  } else if (rawCommand === 'G' || rawCommand === 'GREEN') {
    actuationIcon = '🟢';
    actuationLabel = 'GREEN';
    actuationClass = 'actuation-pill-green';
    actuationTitle = 'Signal Actuation: Green Light (Normal Flow)';
  }

  return (
    <div className={`hw-status-container ${className}`} role="status" aria-label="Hardware Status">
      {/* Operational State Badge */}
      <span
        className={`hw-badge ${badgeClass}`}
        title={badgeTooltip}
        aria-label={badgeTooltip}
      >
        <span className="hw-badge-icon" aria-hidden="true">{badgeIcon}</span>
        <span className="hw-badge-label">{badgeLabel}</span>
      </span>

      {/* Active Actuation Pill */}
      {showActuation && (
        <span
          className={`hw-actuation-pill ${actuationClass}`}
          title={actuationTitle}
          aria-label={actuationTitle}
        >
          <span className="hw-actuation-icon" aria-hidden="true">{actuationIcon}</span>
          <span className="hw-actuation-label">{actuationLabel}</span>
        </span>
      )}
    </div>
  );
}
