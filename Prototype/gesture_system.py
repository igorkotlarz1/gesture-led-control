from HandsDetector import HandDetector
from config import Config
from utils import *
from mqtt_client import MQTTClient

import numpy as np
import cv2
import time

class SystemState:
    CALIBRATE_MIN = 0
    CALIBRATE_MAX = 1
    ACTIVE = 2

class GestureSystem:
    def __init__(self):
        self.STATE = SystemState.CALIBRATE_MIN

        self.DIST_MIN = 0
        self.DIST_MAX = 0

        self.was_pinky_bent = False
        self.was_thumb_bent = False

        self.last_bright = 0
        self.last_rgb = (0,0,0)

        self.msg = ''
        self.msg_time = 0.0

        self.frame_count = 0

        self.cap = cv2.VideoCapture(0)
        self.cap.set(3, Config.CAM_W)
        self.cap.set(4, Config.CAM_H)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) 

        self.detector = HandDetector(max_num_hands=1, min_detection_confidence=0.7, width=Config.CAM_W, height=Config.CAM_H)
        
        self.white = (255,255,255)
        self.yellow = (0,255,255)  
        self.grey = (100, 100, 100)
        self.green = (0,255,0) 
        self.red = (0,0,255)
        self.purple = (255,0,255)
        
        self.mqtt = MQTTClient()
        time.sleep(1)

        self.mqtt_enabled = self.mqtt.connected
        self.last_mqtt_check = 0
        self.publish_state(state='on')

        self.last_active = time.time()

    def _publish_current_state(self):
        """Publikuje aktualny stan systemu"""
        state = ""
        if self.STATE == SystemState.SLEEP:
            state = "sleep"
        elif self.STATE == SystemState.ACTIVE:
            state = "active"
        elif self.STATE == SystemState.CALIBRATE_MIN or self.STATE == SystemState.CALIBRATE_MAX:
            state = "calibrating"
        
        self.mqtt.publish_system_state(state)

    def publish_state(self, state):
        self.mqtt.publish_system_state(state)

    def calculate_brightness(self, distance):
        raw_val = np.interp(distance, [self.DIST_MIN, self.DIST_MAX], [0,100])
        return int(round(raw_val / Config.BRIGHT_STEP) * Config.BRIGHT_STEP) # /10 * 10
    
    def draw_text(self, frame, text, pos, scale, color):
        cv2.putText(frame, text, pos, Config.FONT, scale, (0,0,0), Config.TEXT_THICKNESS+3, cv2.LINE_AA)
        cv2.putText(frame, text, pos, Config.FONT, scale, color, Config.TEXT_THICKNESS, cv2.LINE_AA)

    def handle_right(self, frame, landmarks):
        if len(landmarks) != 5:
            return False
        
        wrist, thumb, index, pinky_18, pinky_20 = landmarks

        if (not in_square(thumb)) or (not in_square(pinky_20)):
            return False
        
        self.last_active = time.time()

        distance = get_distance(np.array(thumb), np.array(index))
        brightness = self.calculate_brightness(distance)

        pinky_bent = is_finger_bent(wrist, base=pinky_18, tip=pinky_20)

        if pinky_bent and not self.was_pinky_bent:
            self.was_pinky_bent = True
            self._approve_brightness(distance, brightness)
        elif not pinky_bent:
            self.was_pinky_bent = False

        cv2.line(frame, thumb, index, self.purple,3) #linia miedzy palcem wskazujacym a kciukiem
        cv2.circle(frame, index, 7, self.purple, cv2.FILLED) #punkt na palcu wskazujacym
        cv2.circle(frame, thumb, 7, self.purple, cv2.FILLED) #punkt na kciuku

        if self.STATE == SystemState.ACTIVE:
            text = f'Brightness: {brightness}%'
        else:
            text = f'Distance: {distance:.0f} px'
        self.draw_text(frame, text, (50,50), 0.6, self.white)

        return True

    def _approve_brightness(self, distance, brightness):
        t = time.time()

        if self.STATE == SystemState.CALIBRATE_MIN:
            self.DIST_MIN = int(distance)
            self.msg = f'MIN: {self.DIST_MIN } px'
            self.STATE = SystemState.CALIBRATE_MAX
            self.msg_time = t

        elif self.STATE == SystemState.CALIBRATE_MAX:
            self.DIST_MAX = int(distance)

            if self.DIST_MAX > self.DIST_MIN:
                self.msg = f'MAX: {self.DIST_MAX } px'
                self.STATE = SystemState.ACTIVE
            else:
                self.msg = 'ERROR: MIN>MAX'
                self.STATE = SystemState.CALIBRATE_MIN
            self.msg_time = t
        elif self.STATE == SystemState.ACTIVE and brightness != self.last_bright:
            success = self.mqtt.publish_brightness(brightness)
            self.last_bright = brightness
            if success:                                  
                self.msg = f'APPROVED {brightness}%'
            else:
                self.msg = f'OFFL APPROVED {brightness}%'
            self.msg_time = t

    def handle_left(self, frame, landmarks):
        if self.STATE != SystemState.ACTIVE:
            return False
        
        if len(landmarks) != 9:
            return False
        
        wrist, thumb_2, thumb_4, index_6, index_8, mid_10, mid_12, ring_14, ring_16 = landmarks

        if (not in_square(thumb_4)) or (not in_square(ring_16)):
            return False
        
        self.last_active = time.time()
        cx = (wrist[0] + ring_14[0]) // 2
        cy = (wrist[1] + ring_14[1]) // 2

        r = 0 if is_finger_bent(wrist, base=index_6, tip=index_8) else 255
        g = 0 if is_finger_bent(wrist, base=mid_10, tip=mid_12) else 255
        b = 0 if is_finger_bent(wrist, base=ring_14, tip=ring_16) else 255
        rgb = (r, g, b)

        thumb_bent = is_finger_bent((cx,cy), base=thumb_2, tip=thumb_4)

        if thumb_bent and not self.was_thumb_bent:
            self.was_thumb_bent = True
            if rgb != self.last_rgb:
                success = self.mqtt.publish_color(r,g,b)
                self.last_rgb = rgb
                if success:                      
                    self.msg = f'APPROVED {rgb}'
                else:
                    self.msg = f'OFFL APPROVED {rgb}'
                self.msg_time = time.time()
        elif not thumb_bent:
            self.was_thumb_bent = False

        self.draw_text(frame, f'RGB:{rgb}', (50,50), 0.6, (b, g, r))

        return True

    def cleanup(self):
        self.mqtt.disconnect()
        self.cap.release()
        cv2.destroyAllWindows()
        self.detector.close()

    def run(self):
        while True:
            success, frame = self.cap.read()

            if not success: break
            self.frame_count += 1

            t = time.time()
            inactive = t - self.last_active

            if inactive > Config.INACTIVITY_LIMIT:
                print('AUTO SHUTDOWN')
                self.publish_state('off')
                break

            frame = cv2.flip(frame, 1)

            frame, detected = self.detector.detect_hands(frame)
            hand_type = self.detector.get_handedness()

            square_color = self.yellow if self.STATE < 2 else self.grey
            active = False

            if detected and hand_type:
                if hand_type == "Right":
                    landmarks = self.detector.get_landmarks(Config.BRIGHTNESS_INDICES)
                    active = self.handle_right(frame, landmarks)
                elif hand_type == "Left":
                    landmarks = self.detector.get_landmarks(Config.COLOR_INDICES)
                    active = self.handle_left(frame, landmarks)

                if active:
                    square_color = self.green

            cv2.rectangle(frame, (Config.SQ_X1, Config.SQ_Y1), (Config.SQ_X2, Config.SQ_Y2), square_color, 2) #ramka 

            if self.STATE == SystemState.ACTIVE:
                info_msg = "[LEFT] COLOR, [RIGHT] BRIGHTNESS"
            elif self.STATE == SystemState.CALIBRATE_MAX:
                info_msg = "CALIBRATION: Stretch out, OK=Pinky"
            elif self.STATE == SystemState.CALIBRATE_MIN:
                info_msg = "CALIBRATION: Pinch, OK=Pinky"

            self.draw_text(frame, info_msg, (Config.SQ_X1, Config.SQ_Y1-25), 0.6, self.yellow)

            time_left = Config.INACTIVITY_LIMIT - inactive
            if time_left < 10 and not active:
                self.draw_text(frame, f'SHUTDOWN IN {time_left:.0f}', (Config.SQ_X1, Config.SQ_Y2+25), 0.6, self.red)

            if t - self.msg_time < Config.FEEDBACK_DURATION:
                self.draw_text(frame, self.msg, (Config.SQ_X1, Config.SQ_Y2+25), 0.6, self.green)

            if t -self.last_mqtt_check >= Config.MQTT_CHECK_INTERVAL:
                self.mqtt_enabled = self.mqtt.connected
                self.last_mqtt_check = t

            mqtt_text = "MQTT Enabled" if self.mqtt_enabled else "MQTT Disabled"
            mqtt_color = self.green if self.mqtt_enabled else self.red
            self.draw_text(frame, mqtt_text, (10, Config.CAM_H - 20), 0.5, mqtt_color)

            cv2.imshow('Gesture LED Control', frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.publish_state('off')
                break
        
        self.cleanup()

#if __name__ == "__main__":
#   GestureSystem.run()