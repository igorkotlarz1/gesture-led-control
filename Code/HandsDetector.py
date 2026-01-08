import mediapipe as mp
import cv2
import numpy as np

#mp_hands = mp.solutions.hands
#mp_drawing = mp.solutions.drawing_utils
#hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)

class HandDetector:
    def __init__(self, static_mode=False, max_num_hands=1, min_detection_confidence=0.5, min_tracking_confidence=0.5, width=640, height=480):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(static_mode, max_num_hands=max_num_hands, min_detection_confidence=min_detection_confidence, min_tracking_confidence=min_tracking_confidence)

        self.mp_drawing = mp.solutions.drawing_utils
        self.w = width
        self.h = height

    def detect_hands(self, img):
        img = cv2.flip(img, 1) 
        #frame = cv2.resize(frame, (CAM_W, CAM_H)) 
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
             
        self.results = self.hands.process(img_rgb)
        success = False 
        if self.results.multi_hand_landmarks:
            for hand_landmarks in self.results.multi_hand_landmarks:               
                self.mp_drawing.draw_landmarks(img, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
            success = True
        return img, success
    
    def get_landmarks(self, indices, hand_no=0):
        if len(indices) == 0:
            return []
        
        landmarks = []
        if self.results.multi_hand_landmarks:
            hand = self.results.multi_hand_landmarks[hand_no]

            #for landmark in hand.landmark:
            #    x,y = int(landmark.x * self.w), int(landmark.y * self.h)
            #    landmarks.append((x, y))

            for index in indices:
                x,y = int(hand.landmark[index].x * self.w), int(hand.landmark[index].y * self.h)
                landmarks.append((x, y))
            
        return landmarks
    
    def get_handedness(self,hand_no=0):
        if self.results.multi_handedness:
            classification = self.results.multi_handedness[hand_no].classification[0]
            return classification.label
        return None
    
    def close(self):
        self.hands.close()