"""
Unit and Static Verification Tests for Hardware Integration (SIH26222)
Firmware: hardware/firmware/traffic_controller.ino
"""

import re
import os

def test_firmware_file_exists():
    path = os.path.join("hardware", "firmware", "traffic_controller.ino")
    assert os.path.exists(path), f"Firmware file not found at {path}"

def test_no_delay_calls():
    path = os.path.join("hardware", "firmware", "traffic_controller.ino")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Match any delay(...) or delayMicroseconds(...) not in comments
    lines = content.splitlines()
    for idx, line in enumerate(lines, 1):
        clean_line = line.strip()
        if clean_line.startswith("//") or clean_line.startswith("*") or clean_line.startswith("/*"):
            continue
        assert not re.search(r'\bdelay\s*\(', clean_line), f"Forbidden delay() call found at line {idx}: {line}"
        assert not re.search(r'\bdelayMicroseconds\s*\(', clean_line), f"Forbidden delayMicroseconds() found at line {idx}: {line}"

def test_required_pins():
    path = os.path.join("hardware", "firmware", "traffic_controller.ino")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    assert re.search(r'PIN_LED_GREEN\s*=\s*2\s*;', content), "PIN_LED_GREEN must be 2"
    assert re.search(r'PIN_LED_YELLOW\s*=\s*3\s*;', content), "PIN_LED_YELLOW must be 3"
    assert re.search(r'PIN_LED_RED\s*=\s*(?:8|4)\s*;', content), "PIN_LED_RED must be 8 or 4"
    assert re.search(r'PIN_BUZZER\s*=\s*5\s*;', content), "PIN_BUZZER must be 5"

    assert re.search(r'PIN_HEARTBEAT_LED\s*=\s*13\s*;', content), "PIN_HEARTBEAT_LED must be 13"

def test_command_protocol_handled():
    path = os.path.join("hardware", "firmware", "traffic_controller.ino")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    for cmd in ['G', 'Y', 'R', 'A', 'C', 'H']:
        assert f"case '{cmd}'" in content, f"Command '{cmd}' not handled in firmware switch"

def test_handshake_response():
    path = os.path.join("hardware", "firmware", "traffic_controller.ino")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    assert 'Serial.print("OK\\n");' in content or 'Serial.println("OK");' in content, "Handshake must reply with OK"

def test_baud_rate():
    path = os.path.join("hardware", "firmware", "traffic_controller.ino")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    assert 'Serial.begin(9600);' in content, "Baud rate must be 9600"

def test_accident_buzzer_timing_math():
    """Verify buzzer pulse math: 100ms ON / 100ms OFF / 100ms ON / 500ms OFF (total 800ms)"""
    def is_buzzer_active(t_ms):
        cycle = t_ms % 800
        return (cycle < 100) or (200 <= cycle < 300)

    # 0 to 99ms: ON
    for t in [0, 10, 50, 99]:
        assert is_buzzer_active(t) is True
    # 100 to 199ms: OFF
    for t in [100, 101, 150, 199]:
        assert is_buzzer_active(t) is False
    # 200 to 299ms: ON
    for t in [200, 201, 250, 299]:
        assert is_buzzer_active(t) is True
    # 300 to 799ms: OFF
    for t in [300, 400, 500, 600, 700, 799]:
        assert is_buzzer_active(t) is False
    # 800ms: Cycle resets -> ON
    assert is_buzzer_active(800) is True

def test_red_flash_timing_math():
    """Verify red flash: 250ms interval (250ms ON, 250ms OFF = 500ms cycle)"""
    def get_flash_state(t_ms, interval=250):
        # Toggles every 250ms
        return ((t_ms // interval) % 2) == 0

    assert get_flash_state(0) is True
    assert get_flash_state(249) is True
    assert get_flash_state(250) is False
    assert get_flash_state(499) is False
    assert get_flash_state(500) is True

if __name__ == "__main__":
    test_firmware_file_exists()
    test_no_delay_calls()
    test_required_pins()
    test_command_protocol_handled()
    test_handshake_response()
    test_baud_rate()
    test_accident_buzzer_timing_math()
    test_red_flash_timing_math()
    print("ALL TESTS PASSED SUCCESSFULLY!")
