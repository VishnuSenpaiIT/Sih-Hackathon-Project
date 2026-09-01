"""
Sample Video Generator (demo/generate_sample_video.py)
Smart Traffic Monitoring & Prediction System (SIH26222)

Generates a realistic 15-second synthetic traffic video (traffic_sample_01.mp4)
featuring multi-lane roads, lane dividers, and moving vehicles (cars, buses, bikes)
with bounding indicators. This ensures cam_01 in edge/config.json has a valid,
reproducible offline video source ready out of the box.
"""

import os
import cv2
import numpy as np


class Vehicle:
    def __init__(self, v_type: str, x: float, y: float, speed: float, color: tuple, size: tuple, lane: int):
        self.v_type = v_type
        self.x = x
        self.y = y
        self.speed = speed
        self.color = color      # BGR
        self.width, self.height = size
        self.lane = lane

    def update(self, frame_height: int):
        self.y += self.speed
        # Loop around when vehicle leaves frame
        if self.speed > 0 and self.y > frame_height + 50:
            self.y = -self.height - np.random.randint(20, 150)
        elif self.speed < 0 and self.y < -self.height - 50:
            self.y = frame_height + np.random.randint(20, 150)


def create_traffic_video(
    output_path: str = "demo/sample_videos/traffic_sample_01.mp4",
    duration_sec: int = 15,
    fps: int = 20,
    width: int = 640,
    height: int = 480
):
    """
    Generates a 15-second traffic video rendered directly into output_path.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    total_frames = duration_sec * fps

    # Try mp4v fourcc first, with fallbacks if needed
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    if not out.isOpened():
        fourcc = cv2.VideoWriter_fourcc(*"avc1")
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    if not out.isOpened():
        raise RuntimeError(f"Failed to open VideoWriter for {output_path}")

    print(f"[+] Generating {total_frames} frames ({duration_sec}s @ {fps}fps) -> {output_path}...")

    # Lane coordinates (4 vertical lanes)
    lane_width = 75
    road_left = (width - 4 * lane_width) // 2
    lanes_x = [road_left + i * lane_width + lane_width // 2 for i in range(4)]

    # Initial vehicles: Mix of cars, buses, bikes
    vehicles = [
        # Southbound (lanes 0, 1 -> downwards)
        Vehicle("car", lanes_x[0], 50, 4.5, (40, 40, 200), (38, 65), lane=0),
        Vehicle("bus", lanes_x[1], -80, 3.2, (20, 180, 240), (46, 120), lane=1),
        Vehicle("bike", lanes_x[0] + 15, 260, 5.2, (180, 50, 50), (18, 32), lane=0),
        Vehicle("car", lanes_x[1], 380, 4.0, (200, 200, 200), (38, 62), lane=1),
        Vehicle("bike", lanes_x[0] - 10, -180, 5.0, (50, 180, 50), (18, 30), lane=0),

        # Northbound (lanes 2, 3 -> upwards)
        Vehicle("car", lanes_x[2], height - 60, -4.8, (220, 100, 30), (38, 64), lane=2),
        Vehicle("bus", lanes_x[3], height + 100, -3.0, (30, 150, 230), (46, 125), lane=3),
        Vehicle("car", lanes_x[2], height - 320, -4.2, (60, 60, 60), (38, 62), lane=2),
        Vehicle("bike", lanes_x[3] - 12, height - 180, -5.5, (0, 140, 255), (18, 32), lane=3),
        Vehicle("car", lanes_x[3] + 8, height + 300, -4.0, (190, 40, 140), (36, 60), lane=3),
    ]

    for frame_idx in range(total_frames):
        # 1. Background: road and surroundings
        frame = np.full((height, width, 3), (70, 110, 60), dtype=np.uint8)  # Grass

        # Sidewalks
        cv2.rectangle(frame, (road_left - 18, 0), (road_left, height), (170, 170, 170), -1)
        cv2.rectangle(frame, (road_left + 4 * lane_width, 0), (road_left + 4 * lane_width + 18, height), (170, 170, 170), -1)

        # Asphalt roadway
        cv2.rectangle(frame, (road_left, 0), (road_left + 4 * lane_width, height), (48, 48, 48), -1)

        # Center double yellow dividing line
        center_x = road_left + 2 * lane_width
        cv2.line(frame, (center_x - 3, 0), (center_x - 3, height), (0, 215, 255), 2)
        cv2.line(frame, (center_x + 3, 0), (center_x + 3, height), (0, 215, 255), 2)

        # Dashed lane dividers
        dash_length = 20
        gap_length = 20
        for l_idx in [1, 3]:
            div_x = road_left + l_idx * lane_width
            y_offset = (frame_idx * 3) % (dash_length + gap_length)
            y = -y_offset
            while y < height:
                cv2.line(frame, (div_x, int(max(0, y))), (div_x, int(min(height, y + dash_length))), (220, 220, 220), 2)
                y += dash_length + gap_length

        # 2. Render Vehicles
        for v in vehicles:
            v.update(height)
            vx, vy = int(v.x), int(v.y)
            vw, vh = v.width, v.height

            top_left = (vx - vw // 2, vy - vh // 2)
            bottom_right = (vx + vw // 2, vy + vh // 2)

            # Skip rendering if fully outside screen
            if bottom_right[1] < 0 or top_left[1] > height:
                continue

            # Vehicle body shadow
            shadow_tl = (top_left[0] + 3, top_left[1] + 3)
            shadow_br = (bottom_right[0] + 3, bottom_right[1] + 3)
            cv2.rectangle(frame, shadow_tl, shadow_br, (20, 20, 20), -1)

            # Vehicle chassis
            cv2.rectangle(frame, top_left, bottom_right, v.color, -1)
            cv2.rectangle(frame, top_left, bottom_right, (20, 20, 20), 1)

            # Details based on vehicle type
            if v.v_type == "bus":
                # Front windshield
                wf_y1 = top_left[1] + (6 if v.speed > 0 else vh - 18)
                wf_y2 = wf_y1 + 12
                cv2.rectangle(frame, (top_left[0] + 4, wf_y1), (bottom_right[0] - 4, wf_y2), (180, 210, 220), -1)
                # Passenger side windows
                for wy in range(top_left[1] + 24, bottom_right[1] - 24, 16):
                    cv2.rectangle(frame, (top_left[0] + 3, wy), (top_left[0] + 7, wy + 10), (140, 170, 180), -1)
                    cv2.rectangle(frame, (bottom_right[0] - 7, wy), (bottom_right[0] - 3, wy + 10), (140, 170, 180), -1)
            elif v.v_type == "car":
                # Windshield & rear window
                ws_y1 = top_left[1] + (10 if v.speed > 0 else vh - 22)
                ws_y2 = ws_y1 + 12
                cv2.rectangle(frame, (top_left[0] + 4, ws_y1), (bottom_right[0] - 4, ws_y2), (160, 200, 220), -1)
                # Roof
                roof_y1 = top_left[1] + 20
                roof_y2 = bottom_right[1] - 20
                cv2.rectangle(frame, (top_left[0] + 5, roof_y1), (bottom_right[0] - 5, roof_y2), tuple(int(c * 0.8) for c in v.color), -1)
            elif v.v_type == "bike":
                # Rider helmet
                cv2.circle(frame, (vx, vy), 5, (230, 220, 40), -1)
                # Handlebars
                cv2.line(frame, (vx - 7, vy - 4 if v.speed > 0 else vy + 4), (vx + 7, vy - 4 if v.speed > 0 else vy + 4), (30, 30, 30), 2)

            # Headlights / Taillights
            if v.speed > 0:
                # Southbound: headlights at bottom, taillights at top
                cv2.circle(frame, (top_left[0] + 5, bottom_right[1] - 2), 3, (200, 255, 255), -1)
                cv2.circle(frame, (bottom_right[0] - 5, bottom_right[1] - 2), 3, (200, 255, 255), -1)
                cv2.circle(frame, (top_left[0] + 5, top_left[1] + 2), 2, (0, 0, 220), -1)
                cv2.circle(frame, (bottom_right[0] - 5, top_left[1] + 2), 2, (0, 0, 220), -1)
            else:
                # Northbound: headlights at top, taillights at bottom
                cv2.circle(frame, (top_left[0] + 5, top_left[1] + 2), 3, (200, 255, 255), -1)
                cv2.circle(frame, (bottom_right[0] - 5, top_left[1] + 2), 3, (200, 255, 255), -1)
                cv2.circle(frame, (top_left[0] + 5, bottom_right[1] - 2), 2, (0, 0, 220), -1)
                cv2.circle(frame, (bottom_right[0] - 5, bottom_right[1] - 2), 2, (0, 0, 220), -1)

        # 3. Telemetry Overlay (Simulating CCTV camera OSD)
        osd_text = f"CAM-01 [CONNAUGHT PLACE] | REC | FPS: {fps} | FRM: {frame_idx:04d}/{total_frames}"
        cv2.putText(frame, osd_text, (16, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)

        time_str = f"2026-09-01 10:20:{frame_idx // fps:02d} IST"
        cv2.putText(frame, time_str, (width - 220, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 255), 1, cv2.LINE_AA)

        out.write(frame)

    out.release()
    print(f"[OK] Generated {output_path} ({os.path.getsize(output_path)} bytes)")


if __name__ == "__main__":
    create_traffic_video()
