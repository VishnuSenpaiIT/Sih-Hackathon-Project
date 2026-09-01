/**
 * ============================================================================
 * Smart Traffic Monitoring & Prediction System (SIH26222)
 * Hardware Integration Layer — Physical Signal Controller Firmware
 * ============================================================================
 *
 * Target Board: Arduino Uno (ATmega328P) / Compatible
 * Communication: Serial over USB (9600 baud, 8-N-1)
 *
 * ARCHITECTURAL ROLE:
 * Actuation "Hands" for the laptop/edge AI "Brain".
 * Listens for single-byte state change commands and controls physical traffic
 * lights (LEDs) and audible emergency indicators (Active Buzzer).
 *
 * HARD CONCURRENCY RULE (NON-NEGOTIABLE):
 * ZERO delay() or blocking calls anywhere in this codebase!
 * All timing is orchestrated through asynchronous, non-blocking millis()
 * state machines. Every iteration of loop() executes in microseconds,
 * guaranteeing zero missed serial bytes and instantaneous preemption.
 *
 * PIN ASSIGNMENTS:
 *   - PIN 2  : Green LED  (Low traffic / Go)
 *   - PIN 3  : Yellow LED (Medium traffic / Caution)
 *   - PIN 4  : Red LED    (High congestion / Stop)
 *   - PIN 5  : 5V Active Buzzer (Accident acoustic alarm)
 *   - PIN 13 : Heartbeat LED (Built-in onboard LED, gentle periodic pulse)
 *
 * COMMAND PROTOCOL:
 *   'G' / 'g' : State NORMAL -> Green ON, Yellow/Red/Buzzer OFF
 *   'Y' / 'y' : State NORMAL -> Yellow ON, Green/Red/Buzzer OFF
 *   'R' / 'r' : State NORMAL -> Red ON, Green/Yellow/Buzzer OFF
 *   'A' / 'a' : State ACCIDENT_OVERRIDE (Highest priority preemption)
 *               - Red flashes at 250ms interval
 *               - Buzzer pattern: 100ms ON, 100ms OFF, 100ms ON, 500ms OFF
 *               - Normal traffic updates ('G','Y','R') are ignored
 *   'C' / 'c' : Clear ACCIDENT_OVERRIDE -> Restores last commanded NORMAL state
 *   'H' / 'h' : Handshake / Heartbeat ping -> Responds immediately with "OK\n"
 * ============================================================================
 */

#include <Arduino.h>

// ============================================================================
// HARDWARE PIN DEFINITIONS
// ============================================================================
const uint8_t PIN_LED_GREEN     = 2;
const uint8_t PIN_LED_YELLOW    = 3;
const uint8_t PIN_LED_RED       = 4;
const uint8_t PIN_BUZZER        = 5;
const uint8_t PIN_HEARTBEAT_LED = 13;

// ============================================================================
// TIMING CONSTANTS (Milliseconds)
// ============================================================================
// Heartbeat LED pulse (Gentle 150ms beacon pulse every 1000ms)
const unsigned long HEARTBEAT_PERIOD_MS = 1000;
const unsigned long HEARTBEAT_ON_MS     = 150;

// Accident Override Red LED flash interval (250ms ON / 250ms OFF = 2 Hz)
const unsigned long ACCIDENT_FLASH_INTERVAL_MS = 250;

// Accident Override Buzzer pattern:
// 100ms ON -> 100ms OFF -> 100ms ON -> 500ms OFF (Total period: 800ms)
const unsigned long BUZZER_CYCLE_PERIOD_MS = 800;
const unsigned long BUZZER_PULSE_1_END_MS  = 100;
const unsigned long BUZZER_PAUSE_1_END_MS  = 200;
const unsigned long BUZZER_PULSE_2_END_MS  = 300;
// Remainder (300ms to 800ms = 500ms) is silent pause

// ============================================================================
// SYSTEM STATES & ENUMS
// ============================================================================
enum SystemState {
  STATE_NORMAL,
  STATE_ACCIDENT_OVERRIDE
};

enum NormalSignal {
  SIGNAL_GREEN,
  SIGNAL_YELLOW,
  SIGNAL_RED
};

// ============================================================================
// GLOBAL STATE VARIABLES
// ============================================================================
static SystemState currentState = STATE_NORMAL;
static NormalSignal lastNormalSignal = SIGNAL_RED; // Safe default state on boot

// Non-blocking timer timestamps
static unsigned long overrideStartTime = 0;
static unsigned long lastRedFlashTime  = 0;
static bool redFlashState             = false;

// ============================================================================
// FUNCTION DECLARATIONS
// ============================================================================
void applyNormalSignal(NormalSignal signal);
void enterAccidentOverride();
void clearAccidentOverride();
void processSerialCommand(char cmd);
void updateHeartbeat(unsigned long currentMillis);
void updateAccidentActuation(unsigned long currentMillis);

// ============================================================================
// ARDUINO SETUP ROUTINE
// ============================================================================
void setup() {
  // Initialize GPIO pins as outputs
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_YELLOW, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_HEARTBEAT_LED, OUTPUT);

  // Default fail-safe state: Buzzer off, LEDs safe
  digitalWrite(PIN_BUZZER, LOW);
  digitalWrite(PIN_HEARTBEAT_LED, LOW);

  // Initialize in NORMAL state with safe default (Red signal)
  applyNormalSignal(lastNormalSignal);

  // Initialize hardware serial interface
  Serial.begin(9600);
}

// ============================================================================
// ARDUINO MAIN LOOP ROUTINE (STRICTLY NON-BLOCKING)
// ============================================================================
void loop() {
  const unsigned long currentMillis = millis();

  // 1. Service Serial Interface (Non-blocking character ingestion)
  while (Serial.available() > 0) {
    char incomingByte = (char)Serial.read();
    processSerialCommand(incomingByte);
  }

  // 2. Service Gentle Heartbeat LED Pulse (Pin 13)
  updateHeartbeat(currentMillis);

  // 3. Service Accident Actuation Timers (LED Flash & Pulsed Buzzer)
  if (currentState == STATE_ACCIDENT_OVERRIDE) {
    updateAccidentActuation(currentMillis);
  }
}

// ============================================================================
// SERIAL COMMAND PROCESSOR
// ============================================================================
void processSerialCommand(char cmd) {
  // Ignore whitespace and line delimiter characters
  if (cmd == '\r' || cmd == '\n' || cmd == ' ' || cmd == '\t') {
    return;
  }

  switch (cmd) {
    // ------------------------------------------------------------------------
    // Handshake / Heartbeat Ping
    // ------------------------------------------------------------------------
    case 'H':
    case 'h':
      // Immediately reply with handshake confirmation
      Serial.print("OK\n");
      break;

    // ------------------------------------------------------------------------
    // Normal Traffic Density Signals
    // ------------------------------------------------------------------------
    case 'G':
    case 'g':
      if (currentState == STATE_NORMAL) {
        lastNormalSignal = SIGNAL_GREEN;
        applyNormalSignal(SIGNAL_GREEN);
      }
      // Note: If in ACCIDENT_OVERRIDE, traffic updates are ignored per spec.
      break;

    case 'Y':
    case 'y':
      if (currentState == STATE_NORMAL) {
        lastNormalSignal = SIGNAL_YELLOW;
        applyNormalSignal(SIGNAL_YELLOW);
      }
      break;

    case 'R':
    case 'r':
      if (currentState == STATE_NORMAL) {
        lastNormalSignal = SIGNAL_RED;
        applyNormalSignal(SIGNAL_RED);
      }
      break;

    // ------------------------------------------------------------------------
    // Accident / Emergency Override
    // ------------------------------------------------------------------------
    case 'A':
    case 'a':
      enterAccidentOverride();
      break;

    // ------------------------------------------------------------------------
    // Clear Override
    // ------------------------------------------------------------------------
    case 'C':
    case 'c':
      clearAccidentOverride();
      break;

    // ------------------------------------------------------------------------
    // Unknown Command Guard
    // ------------------------------------------------------------------------
    default:
      // Unknown command: silently discard without blocking
      break;
  }
}

// ============================================================================
// ACTUATION CONTROLLERS
// ============================================================================

/**
 * Applies the specified solid traffic signal state.
 * Ensures mutual exclusion across Green, Yellow, Red and silences the buzzer.
 */
void applyNormalSignal(NormalSignal signal) {
  // Silence buzzer in normal operation
  digitalWrite(PIN_BUZZER, LOW);

  switch (signal) {
    case SIGNAL_GREEN:
      digitalWrite(PIN_LED_GREEN, HIGH);
      digitalWrite(PIN_LED_YELLOW, LOW);
      digitalWrite(PIN_LED_RED, LOW);
      break;

    case SIGNAL_YELLOW:
      digitalWrite(PIN_LED_GREEN, LOW);
      digitalWrite(PIN_LED_YELLOW, HIGH);
      digitalWrite(PIN_LED_RED, LOW);
      break;

    case SIGNAL_RED:
      digitalWrite(PIN_LED_GREEN, LOW);
      digitalWrite(PIN_LED_YELLOW, LOW);
      digitalWrite(PIN_LED_RED, HIGH);
      break;
  }
}

/**
 * Transitions system into ACCIDENT_OVERRIDE state.
 * Preempts normal traffic signals immediately.
 */
void enterAccidentOverride() {
  currentState = STATE_ACCIDENT_OVERRIDE;
  overrideStartTime = millis();
  lastRedFlashTime  = overrideStartTime;

  // Turn off Green and Yellow immediately
  digitalWrite(PIN_LED_GREEN, LOW);
  digitalWrite(PIN_LED_YELLOW, LOW);

  // Initialize Red LED ON for first flash half-cycle
  redFlashState = true;
  digitalWrite(PIN_LED_RED, HIGH);
}

/**
 * Clears accident override and restores the last commanded normal signal.
 */
void clearAccidentOverride() {
  currentState = STATE_NORMAL;

  // Ensure buzzer is silenced immediately
  digitalWrite(PIN_BUZZER, LOW);

  // Restore the traffic signal that was active prior to override
  applyNormalSignal(lastNormalSignal);
}

/**
 * Updates the gentle heartbeat beacon on built-in Pin 13.
 * Non-blocking: computes phase from current millis.
 */
void updateHeartbeat(unsigned long currentMillis) {
  unsigned long cyclePhase = currentMillis % HEARTBEAT_PERIOD_MS;
  bool heartbeatState = (cyclePhase < HEARTBEAT_ON_MS);
  digitalWrite(PIN_HEARTBEAT_LED, heartbeatState ? HIGH : LOW);
}

/**
 * Asynchronously drives Red LED 250ms flashing and 800ms pulsed buzzer pattern.
 * Non-blocking: relies strictly on elapsed millis math.
 */
void updateAccidentActuation(unsigned long currentMillis) {
  // 1. Red LED 250ms Square-wave Flash
  if (currentMillis - lastRedFlashTime >= ACCIDENT_FLASH_INTERVAL_MS) {
    lastRedFlashTime = currentMillis;
    redFlashState = !redFlashState;
    digitalWrite(PIN_LED_RED, redFlashState ? HIGH : LOW);
  }

  // 2. Buzzer Pulsed Alert Pattern (800ms periodic cycle):
  //    0ms   - 100ms : ON  (Pulse 1)
  //    100ms - 200ms : OFF (Inter-pulse silence)
  //    200ms - 300ms : ON  (Pulse 2)
  //    300ms - 800ms : OFF (Long 500ms silence)
  unsigned long cycleOffset = (currentMillis - overrideStartTime) % BUZZER_CYCLE_PERIOD_MS;
  bool buzzerActive = (cycleOffset < BUZZER_PULSE_1_END_MS) ||
                      (cycleOffset >= BUZZER_PAUSE_1_END_MS && cycleOffset < BUZZER_PULSE_2_END_MS);

  digitalWrite(PIN_BUZZER, buzzerActive ? HIGH : LOW);
}
