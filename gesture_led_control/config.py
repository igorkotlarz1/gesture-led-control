"""Application settings. MQTT and camera settings can be overridden with environment variables."""
from __future__ import annotations

import os

import cv2


class Config:
    # Camera
    CAMERA_INDEX = int(os.getenv("GLC_CAMERA_INDEX", "0"))
    CAM_W, CAM_H = 640, 480

    # Control area: gestures only count when the key landmarks are inside this square
    SQUARE_SIZE = 250
    SQ_X1 = (CAM_W - SQUARE_SIZE) // 2
    SQ_Y1 = (CAM_H - SQUARE_SIZE) // 2
    SQ_X2 = SQ_X1 + SQUARE_SIZE
    SQ_Y2 = SQ_Y1 + SQUARE_SIZE

    # Overlay text
    FONT = cv2.FONT_HERSHEY_SIMPLEX
    TEXT_THICKNESS = 2

    # Behaviour
    BRIGHTNESS_STEP = 10          # brightness snaps to multiples of 10 %
    INACTIVITY_LIMIT_S = 30.0     # no gesture for this long -> lights off and exit
    FEEDBACK_DURATION_S = 1.5     # how long confirmation messages stay on screen
    MIN_DETECTION_CONFIDENCE = 0.7

    # MediaPipe hand landmark indices
    # right hand (brightness): wrist, thumb tip, index tip, pinky PIP, pinky tip
    BRIGHTNESS_LANDMARKS = [0, 4, 8, 18, 20]
    # left hand (color): wrist, thumb MCP, thumb tip, index PIP, index tip,
    # middle PIP, middle tip, ring PIP, ring tip
    COLOR_LANDMARKS = [0, 2, 4, 6, 8, 10, 12, 14, 16]

    # MQTT (10.42.0.1 is the default address of a NetworkManager Wi-Fi hotspot)
    MQTT_BROKER = os.getenv("GLC_MQTT_BROKER", "10.42.0.1")
    MQTT_PORT = int(os.getenv("GLC_MQTT_PORT", "1883"))
    MQTT_CLIENT_ID = os.getenv("GLC_MQTT_CLIENT_ID", "GestureAPP")
    MQTT_CHECK_INTERVAL_S = 1.0
    MQTT_CONNECT_WAIT_S = 1.0     # give the client a moment to connect at startup

    MQTT_TOPIC_COLOR = "project/led/color"              # payload "r,g,b" (0 or 255 each)
    MQTT_TOPIC_BRIGHTNESS = "project/led/brightness"    # payload "0".."100"
    MQTT_TOPIC_SYSTEM_STATE = "project/system/state"    # payload "on" / "off"
