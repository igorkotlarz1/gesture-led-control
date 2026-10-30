"""Gesture logic and MQTT client tests: no camera, MediaPipe or broker needed."""
from types import SimpleNamespace

import paho.mqtt.client as mqtt
import pytest

from gesture_led_control.config import Config
from gesture_led_control.geometry import get_distance, is_finger_bent, is_in_control_area
from gesture_led_control.gesture_system import GestureSystem, SystemState
from gesture_led_control.mqtt_client import MQTTClient

CX, CY = (Config.SQ_X1 + Config.SQ_X2) // 2, (Config.SQ_Y1 + Config.SQ_Y2) // 2


class FakeMQTT:
    def __init__(self, connected=True):
        self.connected = connected
        self.sent = []

    def publish_brightness(self, value):
        self.sent.append(("brightness", value))
        return self.connected

    def publish_color(self, r, g, b):
        self.sent.append(("color", (r, g, b)))
        return self.connected

    def publish_system_state(self, state):
        self.sent.append(("state", state))

    def disconnect(self):
        pass


@pytest.fixture
def system():
    return GestureSystem(capture=SimpleNamespace(), detector=SimpleNamespace(), mqtt=FakeMQTT())


def right_hand(pinch_px, pinky_bent):
    """wrist, thumb tip, index tip, pinky PIP, pinky tip (all inside the control area)."""
    wrist = (CX, CY + 100)
    pinky_pip = (CX + 40, CY + 20)
    pinky_tip = (CX + 40, CY + 50) if pinky_bent else (CX + 40, CY - 20)
    return [wrist, (CX - 60, CY), (CX - 60 + pinch_px, CY), pinky_pip, pinky_tip]


def left_hand(r_up, g_up, b_up, thumb_bent):
    """wrist, thumb MCP, thumb tip, index PIP/tip, middle PIP/tip, ring PIP/tip."""
    wrist = (CX, CY + 100)

    def finger(x, up):
        return (x, CY), ((x, CY - 40) if up else (x, CY + 60))

    index_pip, index_tip = finger(CX - 30, r_up)
    middle_pip, middle_tip = finger(CX, g_up)
    ring_pip, ring_tip = finger(CX + 30, b_up)
    thumb_mcp = (CX - 60, CY + 60)
    thumb_tip = (CX - 20, CY + 55) if thumb_bent else (CX - 100, CY + 50)
    return [wrist, thumb_mcp, thumb_tip, index_pip, index_tip, middle_pip, middle_tip, ring_pip, ring_tip]


def gesture(system, hand, *frames):
    handler = system.handle_right_hand if hand == "right" else system.handle_left_hand
    return [handler(None, f) for f in frames]


def calibrate(system, min_px=20, max_px=120):
    gesture(system, "right", right_hand(min_px, False), right_hand(min_px, True), right_hand(min_px, False))
    gesture(system, "right", right_hand(max_px, False), right_hand(max_px, True), right_hand(max_px, False))


def test_geometry():
    assert is_finger_bent((0, 0), base=(0, 50), tip=(0, 30))
    assert not is_finger_bent((0, 0), base=(0, 50), tip=(0, 90))
    assert is_in_control_area((CX, CY))
    assert not is_in_control_area((0, 0))
    assert get_distance((0, 0), (3, 4)) == 5.0


def test_starts_in_calibration_and_announces_on(system):
    assert system.state == SystemState.CALIBRATE_MIN
    assert system.mqtt.sent == [("state", "on")]


def test_calibration_then_brightness(system):
    calibrate(system)
    assert (system.state, system.dist_min, system.dist_max) == (SystemState.ACTIVE, 20, 120)
    assert system.calculate_brightness(20) == 0
    assert system.calculate_brightness(120) == 100
    assert system.calculate_brightness(68) == 50  # 48 % snaps to 50 %

    gesture(system, "right", right_hand(70, False), right_hand(70, True))
    assert system.mqtt.sent[-1] == ("brightness", 50)
    assert system.message == "APPROVED 50%"


def test_confirm_fires_once_per_bend(system):
    calibrate(system)
    gesture(system, "right", right_hand(120, True), right_hand(120, True), right_hand(120, True))
    assert [s for s in system.mqtt.sent if s[0] == "brightness"] == [("brightness", 100)]


def test_invalid_calibration_restarts(system):
    calibrate(system, min_px=100, max_px=40)
    assert system.state == SystemState.CALIBRATE_MIN
    assert system.message == "ERROR: MIN>MAX"


def test_left_hand_ignored_until_calibrated(system):
    assert gesture(system, "left", left_hand(True, False, True, True)) == [False]


def test_color_from_raised_fingers(system):
    calibrate(system)
    gesture(system, "left", left_hand(True, False, True, False), left_hand(True, False, True, True))
    assert system.mqtt.sent[-1] == ("color", (255, 0, 255))


def test_hand_outside_control_area_is_ignored(system):
    calibrate(system)
    outside = [(5, 5)] * 5
    assert gesture(system, "right", outside) == [False]


def test_offline_publish_is_flagged():
    system = GestureSystem(capture=SimpleNamespace(), detector=SimpleNamespace(), mqtt=FakeMQTT(connected=False))
    calibrate(system)
    gesture(system, "right", right_hand(120, False), right_hand(120, True))
    assert system.message == "OFFL APPROVED 100%"


class FakePahoClient:
    def __init__(self, *args, **kwargs):
        self.published = []

    def connect_async(self, *a, **k): pass
    def loop_start(self): pass
    def loop_stop(self): pass
    def disconnect(self): pass

    def publish(self, topic, payload):
        self.published.append((topic, payload))
        return SimpleNamespace(rc=mqtt.MQTT_ERR_SUCCESS)


def test_mqtt_client_payloads_and_deduplication(monkeypatch):
    monkeypatch.setattr(mqtt, "Client", FakePahoClient)
    client = MQTTClient(broker="test", port=1883)
    assert client.publish_brightness(40) is False  # offline until on_connect

    client.connected = True
    assert client.publish_brightness(40) and client.publish_brightness(40)
    assert client.publish_color(255, 0, 0)
    client.publish_system_state("on")
    client.publish_system_state("on")
    assert client.client.published == [
        (Config.MQTT_TOPIC_BRIGHTNESS, "40"),
        (Config.MQTT_TOPIC_COLOR, "255,0,0"),
        (Config.MQTT_TOPIC_SYSTEM_STATE, "on"),
    ]
