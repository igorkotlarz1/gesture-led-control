from config import Config
import numpy as np

def send_mqtt_brightness(value):
    print(f'[MQTT] set LED brightness to:{value}%\n')

def send_mqtt_color(r, g, b):
    print(f'[MQTT] RGB color: ({r}, {g}, {b}).\n')

def is_finger_bent(wrist, base, tip):
    dist_wrist_tip = (tip[0]-wrist[0])**2 + (tip[1]-wrist[1])**2
    dist_wrist_base = (base[0]-wrist[0])**2 + (base[1]-wrist[1])**2
    return dist_wrist_tip < dist_wrist_base

def in_square(point: tuple):
    return (Config.SQ_X1 < point[0] < Config.SQ_X2) and (Config.SQ_Y1 < point[1] < Config.SQ_Y2) 

def get_distance(p1, p2):
    return np.linalg.norm(p1 - p2)