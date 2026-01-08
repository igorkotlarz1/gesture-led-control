
import cv2 

class Config:    
    CAM_W, CAM_H = 640, 480
    SQUARE_SIZE = 250

    SQ_X1 = (CAM_W - SQUARE_SIZE) //2
    SQ_Y1 = (CAM_H - SQUARE_SIZE) //2

    SQ_X2 = SQ_X1 + SQUARE_SIZE
    SQ_Y2 = SQ_Y1 + SQUARE_SIZE

    BRIGHT_X, BRIGHT_Y = 50, 50
    FONT = cv2.FONT_HERSHEY_SIMPLEX #FONT_HERSHEY_PLAIN
    FONT_SCALE = 0.6
    TEXT_THICKNESS = 2

    BRIGHT_STEP = 10

    INACTIVITY_LIMIT = 30.0
    FEEDBACK_DURATION = 1.5

    PROCESS_EV_N_FRAMES = 2 

    BRIGHTNESS_INDICES = [0, 4, 8, 18, 20] #wrist, thumb_tip, index_tip, pinky_pip, piky_tip
    COLOR_INDICES = [0, 2, 4, 6, 8, 10, 12, 14, 16] #wrist, thumb_tip, index_tip, pinky_pip, piky_tip
 
    