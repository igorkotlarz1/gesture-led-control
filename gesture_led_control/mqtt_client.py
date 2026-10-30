"""MQTT publisher for LED color, brightness and system state."""
from __future__ import annotations

import logging

import paho.mqtt.client as mqtt

from gesture_led_control.config import Config

logger = logging.getLogger(__name__)


class MQTTClient:
    def __init__(self, broker: str = Config.MQTT_BROKER, port: int = Config.MQTT_PORT,
                 client_id: str = Config.MQTT_CLIENT_ID):
        self.broker = broker
        self.port = port
        self.connected = False
        self.last_brightness: int | None = None
        self.last_color: tuple[int, int, int] | None = None
        self.last_state: str | None = None

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self._connect()

    def _connect(self) -> None:
        # connect_async + loop_start: the network loop keeps retrying in the
        # background, so the app starts offline and goes online when the broker appears.
        try:
            logger.info("Connecting to %s:%s...", self.broker, self.port)
            self.client.connect_async(self.broker, self.port, keepalive=60)
            self.client.loop_start()
        except Exception as exc:  # noqa: BLE001 - e.g. an invalid host name
            logger.error("Error while connecting: %s. Running offline.", exc)
            self.connected = False

    def _publish(self, topic: str, payload: str) -> bool:
        try:
            result = self.client.publish(topic, payload)
        except Exception as exc:  # noqa: BLE001
            logger.error("Exception while publishing to %s: %s", topic, exc)
            return False
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.error("Error publishing to %s: rc=%s", topic, result.rc)
            return False
        return True

    def publish_brightness(self, value: int) -> bool:
        """Publish brightness 0..100. Returns False when offline or on error."""
        if not self.connected:
            return False
        if value == self.last_brightness:
            return True
        if self._publish(Config.MQTT_TOPIC_BRIGHTNESS, f"{value}"):
            self.last_brightness = value
            return True
        return False

    def publish_color(self, r: int, g: int, b: int) -> bool:
        """Publish an RGB color as "r,g,b". Returns False when offline or on error."""
        if not self.connected:
            return False
        rgb = (r, g, b)
        if rgb == self.last_color:
            return True
        if self._publish(Config.MQTT_TOPIC_COLOR, f"{r},{g},{b}"):
            self.last_color = rgb
            return True
        return False

    def publish_system_state(self, state: str) -> None:
        """Publish "on" / "off" (skipped when unchanged or offline)."""
        if state == self.last_state or not self.connected:
            return
        if self._publish(Config.MQTT_TOPIC_SYSTEM_STATE, state):
            self.last_state = state
            logger.info("Published system state: %s", state.upper())

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        self.connected = not reason_code.is_failure
        if self.connected:
            logger.info("Connected successfully")
        else:
            logger.error("Connection error: %s", reason_code)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        self.connected = False
        if reason_code.is_failure:
            logger.warning("Unexpected disconnect: %s", reason_code)

    def disconnect(self) -> None:
        if self.connected:
            self.client.disconnect()
            logger.info("Disconnected")
        self.client.loop_stop()
