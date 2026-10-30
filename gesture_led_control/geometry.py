"""Small geometry helpers for hand landmarks given as (x, y) pixel tuples."""
from __future__ import annotations

import numpy as np

from gesture_led_control.config import Config

Point = tuple[int, int]


def is_finger_bent(wrist: Point, base: Point, tip: Point) -> bool:
    """A finger is bent when its tip is closer to the wrist than its base joint."""
    dist_wrist_tip = (tip[0] - wrist[0]) ** 2 + (tip[1] - wrist[1]) ** 2
    dist_wrist_base = (base[0] - wrist[0]) ** 2 + (base[1] - wrist[1]) ** 2
    return dist_wrist_tip < dist_wrist_base


def is_in_control_area(point: Point) -> bool:
    return (Config.SQ_X1 < point[0] < Config.SQ_X2) and (Config.SQ_Y1 < point[1] < Config.SQ_Y2)


def get_distance(p1: Point, p2: Point) -> float:
    return float(np.linalg.norm(np.array(p1) - np.array(p2)))
