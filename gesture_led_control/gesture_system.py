"""Main loop: camera -> hand landmarks -> gesture state machine -> MQTT."""
from __future__ import annotations

import logging
import time
from enum import IntEnum

import cv2
import numpy as np

from gesture_led_control.config import Config
from gesture_led_control.geometry import get_distance, is_finger_bent, is_in_control_area
from gesture_led_control.mqtt_client import MQTTClient

logger = logging.getLogger(__name__)

# BGR colors for the overlay
WHITE = (255, 255, 255)
YELLOW = (0, 255, 255)
GREY = (100, 100, 100)
GREEN = (0, 255, 0)
RED = (0, 0, 255)
PURPLE = (255, 0, 255)


class SystemState(IntEnum):
    CALIBRATE_MIN = 0   # pinch thumb and index, confirm with the pinky
    CALIBRATE_MAX = 1   # spread thumb and index, confirm with the pinky
    ACTIVE = 2          # right hand sets brightness, left hand sets color


class GestureSystem:
    def __init__(self, capture=None, detector=None, mqtt: MQTTClient | None = None):
        self.state = SystemState.CALIBRATE_MIN
        self.dist_min = 0
        self.dist_max = 0

        # edge detection for the "confirm" gestures
        self.was_pinky_bent = False
        self.was_thumb_bent = False

        self.last_brightness = 0
        self.last_rgb = (0, 0, 0)

        self.message = ""
        self.message_time = 0.0

        if capture is None:
            capture = cv2.VideoCapture(Config.CAMERA_INDEX)
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, Config.CAM_W)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, Config.CAM_H)
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.capture = capture

        if detector is None:
            from gesture_led_control.hand_detector import HandDetector  # imports MediaPipe
            detector = HandDetector(max_num_hands=1,
                                    min_detection_confidence=Config.MIN_DETECTION_CONFIDENCE,
                                    width=Config.CAM_W, height=Config.CAM_H)
        self.detector = detector

        if mqtt is None:
            mqtt = MQTTClient()
            time.sleep(Config.MQTT_CONNECT_WAIT_S)
        self.mqtt = mqtt

        self.mqtt_enabled = self.mqtt.connected
        self.last_mqtt_check = 0.0
        self.mqtt.publish_system_state("on")
        self.last_active = time.time()

    # ---- gesture logic -------------------------------------------------

    def calculate_brightness(self, distance: float) -> int:
        """Map the pinch distance onto 0..100 % using the calibrated range, snapped to 10 %."""
        raw = np.interp(distance, [self.dist_min, self.dist_max], [0, 100])
        return int(round(raw / Config.BRIGHTNESS_STEP) * Config.BRIGHTNESS_STEP)

    def handle_right_hand(self, frame, landmarks) -> bool:
        """Brightness hand. Returns True when the hand is inside the control area."""
        if len(landmarks) != 5:
            return False
        wrist, thumb_tip, index_tip, pinky_pip, pinky_tip = landmarks
        if not is_in_control_area(thumb_tip) or not is_in_control_area(pinky_tip):
            return False

        self.last_active = time.time()
        distance = get_distance(thumb_tip, index_tip)
        brightness = self.calculate_brightness(distance)

        pinky_bent = is_finger_bent(wrist, base=pinky_pip, tip=pinky_tip)
        if pinky_bent and not self.was_pinky_bent:
            self.was_pinky_bent = True
            self.confirm_brightness(distance, brightness)
        elif not pinky_bent:
            self.was_pinky_bent = False

        if frame is not None:
            cv2.line(frame, thumb_tip, index_tip, PURPLE, 3)
            cv2.circle(frame, index_tip, 7, PURPLE, cv2.FILLED)
            cv2.circle(frame, thumb_tip, 7, PURPLE, cv2.FILLED)
            text = f"Brightness: {brightness}%" if self.state == SystemState.ACTIVE else f"Distance: {distance:.0f} px"
            self.draw_text(frame, text, (50, 50), 0.6, WHITE)
        return True

    def confirm_brightness(self, distance: float, brightness: int) -> None:
        """Pinky bend: store a calibration point, or publish the brightness when active."""
        now = time.time()
        if self.state == SystemState.CALIBRATE_MIN:
            self.dist_min = int(distance)
            self._show(f"MIN: {self.dist_min} px", now)
            self.state = SystemState.CALIBRATE_MAX

        elif self.state == SystemState.CALIBRATE_MAX:
            self.dist_max = int(distance)
            if self.dist_max > self.dist_min:
                self._show(f"MAX: {self.dist_max} px", now)
                self.state = SystemState.ACTIVE
            else:
                self._show("ERROR: MIN>MAX", now)
                self.state = SystemState.CALIBRATE_MIN

        elif self.state == SystemState.ACTIVE and brightness != self.last_brightness:
            published = self.mqtt.publish_brightness(brightness)
            self.last_brightness = brightness
            self._show(f"APPROVED {brightness}%" if published else f"OFFL APPROVED {brightness}%", now)

    def handle_left_hand(self, frame, landmarks) -> bool:
        """Color hand: index/middle/ring finger up = R/G/B on; thumb bend confirms."""
        if self.state != SystemState.ACTIVE or len(landmarks) != 9:
            return False
        (wrist, thumb_mcp, thumb_tip, index_pip, index_tip,
         middle_pip, middle_tip, ring_pip, ring_tip) = landmarks
        if not is_in_control_area(thumb_tip) or not is_in_control_area(ring_tip):
            return False

        self.last_active = time.time()
        palm_center = ((wrist[0] + ring_pip[0]) // 2, (wrist[1] + ring_pip[1]) // 2)

        r = 0 if is_finger_bent(wrist, base=index_pip, tip=index_tip) else 255
        g = 0 if is_finger_bent(wrist, base=middle_pip, tip=middle_tip) else 255
        b = 0 if is_finger_bent(wrist, base=ring_pip, tip=ring_tip) else 255
        rgb = (r, g, b)

        thumb_bent = is_finger_bent(palm_center, base=thumb_mcp, tip=thumb_tip)
        if thumb_bent and not self.was_thumb_bent:
            self.was_thumb_bent = True
            if rgb != self.last_rgb:
                published = self.mqtt.publish_color(r, g, b)
                self.last_rgb = rgb
                self._show(f"APPROVED {rgb}" if published else f"OFFL APPROVED {rgb}", time.time())
        elif not thumb_bent:
            self.was_thumb_bent = False

        if frame is not None:
            self.draw_text(frame, f"RGB:{rgb}", (50, 50), 0.6, (b, g, r))
        return True

    # ---- drawing -------------------------------------------------------

    def _show(self, message: str, now: float) -> None:
        self.message = message
        self.message_time = now

    @staticmethod
    def draw_text(frame, text, pos, scale, color) -> None:
        """Text with a black outline so it stays readable on any background."""
        cv2.putText(frame, text, pos, Config.FONT, scale, (0, 0, 0), Config.TEXT_THICKNESS + 3, cv2.LINE_AA)
        cv2.putText(frame, text, pos, Config.FONT, scale, color, Config.TEXT_THICKNESS, cv2.LINE_AA)

    def _instruction(self) -> str:
        if self.state == SystemState.ACTIVE:
            return "[LEFT] COLOR, [RIGHT] BRIGHTNESS"
        if self.state == SystemState.CALIBRATE_MAX:
            return "CALIBRATION: Stretch out, OK=Pinky"
        return "CALIBRATION: Pinch, OK=Pinky"

    def draw_overlay(self, frame, hand_active: bool, now: float, inactive_s: float) -> None:
        if hand_active:
            square_color = GREEN
        else:
            square_color = YELLOW if self.state < SystemState.ACTIVE else GREY
        cv2.rectangle(frame, (Config.SQ_X1, Config.SQ_Y1), (Config.SQ_X2, Config.SQ_Y2), square_color, 2)
        self.draw_text(frame, self._instruction(), (Config.SQ_X1, Config.SQ_Y1 - 25), 0.6, YELLOW)

        time_left = Config.INACTIVITY_LIMIT_S - inactive_s
        if time_left < 10 and not hand_active:
            self.draw_text(frame, f"SHUTDOWN IN {time_left:.0f}", (Config.SQ_X1, Config.SQ_Y2 + 25), 0.6, RED)
        if now - self.message_time < Config.FEEDBACK_DURATION_S:
            self.draw_text(frame, self.message, (Config.SQ_X1, Config.SQ_Y2 + 25), 0.6, GREEN)

        mqtt_text = "MQTT Enabled" if self.mqtt_enabled else "MQTT Disabled"
        self.draw_text(frame, mqtt_text, (10, Config.CAM_H - 20), 0.5, GREEN if self.mqtt_enabled else RED)

    # ---- main loop -----------------------------------------------------

    def process_frame(self, frame) -> bool:
        """Detect a hand and run the matching handler. Returns True if a gesture was active."""
        frame, detected = self.detector.detect_hands(frame)
        handedness = self.detector.get_handedness()
        if not detected or not handedness:
            return False
        if handedness == "Right":
            return self.handle_right_hand(frame, self.detector.get_landmarks(Config.BRIGHTNESS_LANDMARKS))
        if handedness == "Left":
            return self.handle_left_hand(frame, self.detector.get_landmarks(Config.COLOR_LANDMARKS))
        return False

    def run(self) -> None:
        try:
            while True:
                ok, frame = self.capture.read()
                if not ok:
                    break

                now = time.time()
                inactive_s = now - self.last_active
                if inactive_s > Config.INACTIVITY_LIMIT_S:
                    logger.info("Auto shutdown after %.0f s of inactivity", Config.INACTIVITY_LIMIT_S)
                    self.mqtt.publish_system_state("off")
                    break

                frame = cv2.flip(frame, 1)  # mirror view; MediaPipe handedness assumes it
                hand_active = self.process_frame(frame)

                if now - self.last_mqtt_check >= Config.MQTT_CHECK_INTERVAL_S:
                    self.mqtt_enabled = self.mqtt.connected
                    self.last_mqtt_check = now

                self.draw_overlay(frame, hand_active, now, inactive_s)
                cv2.imshow("Gesture LED Control", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    self.mqtt.publish_system_state("off")
                    break
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        self.mqtt.disconnect()
        self.capture.release()
        cv2.destroyAllWindows()
        self.detector.close()
