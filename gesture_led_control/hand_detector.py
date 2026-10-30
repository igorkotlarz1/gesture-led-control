"""Thin wrapper around MediaPipe Hands."""
from __future__ import annotations

import cv2
import mediapipe as mp


class HandDetector:
    def __init__(self, static_mode: bool = False, max_num_hands: int = 1,
                 min_detection_confidence: float = 0.5, min_tracking_confidence: float = 0.5,
                 width: int = 640, height: int = 480):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(static_mode, max_num_hands=max_num_hands,
                                         min_detection_confidence=min_detection_confidence,
                                         min_tracking_confidence=min_tracking_confidence)
        self.mp_drawing = mp.solutions.drawing_utils
        self.width = width
        self.height = height
        self.results = None

    def detect_hands(self, frame):
        """Run detection on a BGR frame and draw the hand skeleton on it."""
        self.results = self.hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        detected = bool(self.results.multi_hand_landmarks)
        if detected:
            for hand_landmarks in self.results.multi_hand_landmarks:
                self.mp_drawing.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
        return frame, detected

    def get_landmarks(self, indices: list[int], hand_no: int = 0) -> list[tuple[int, int]]:
        """Pixel coordinates of the selected landmarks, in the order given."""
        if not indices or not self.results or not self.results.multi_hand_landmarks:
            return []
        hand = self.results.multi_hand_landmarks[hand_no]
        return [(int(hand.landmark[i].x * self.width), int(hand.landmark[i].y * self.height))
                for i in indices]

    def get_handedness(self, hand_no: int = 0) -> str | None:
        """'Left' or 'Right' (for a mirrored, selfie-style frame), or None."""
        if self.results and self.results.multi_handedness:
            return self.results.multi_handedness[hand_no].classification[0].label
        return None

    def close(self) -> None:
        self.hands.close()
