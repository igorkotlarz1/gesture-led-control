"""Entry point: python -m gesture_led_control [--broker HOST] [--port N] [--camera N]"""
from __future__ import annotations

import argparse
import logging
import time

from gesture_led_control.config import Config
from gesture_led_control.gesture_system import GestureSystem
from gesture_led_control.mqtt_client import MQTTClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Control LED color and brightness with hand gestures over MQTT")
    parser.add_argument("--broker", default=Config.MQTT_BROKER, help=f"MQTT broker host (default {Config.MQTT_BROKER})")
    parser.add_argument("--port", type=int, default=Config.MQTT_PORT, help=f"MQTT port (default {Config.MQTT_PORT})")
    parser.add_argument("--camera", type=int, default=Config.CAMERA_INDEX, help="camera index (default 0)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    Config.CAMERA_INDEX = args.camera

    mqtt = MQTTClient(broker=args.broker, port=args.port)
    time.sleep(Config.MQTT_CONNECT_WAIT_S)  # let the first connection attempt finish
    GestureSystem(mqtt=mqtt).run()


if __name__ == "__main__":
    main()
