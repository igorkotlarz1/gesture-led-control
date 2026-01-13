import paho.mqtt.client as mqtt 
from config import Config

class MQTTClient:
    
    def __init__(self):
        self.client = mqtt.Client(client_id=Config.MQTT_CLIENT_ID)
        self.connected = False
        self.last_brightness = None
        self.last_color = None

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

        self._connect()
    
    def _connect(self):
        try:
            print(f'[MQTT] Connecting to {Config.MQTT_BROKER}:{Config.MQTT_PORT}...')
            self.client.connect(Config.MQTT_BROKER, Config.MQTT_PORT, keepalive=60)
            self.client.loop_start()  
        except Exception as e:
            print(f'[MQTT] Error while connecting: {e}')
            print('[MQTT] System will be running offline')
            self.connected = False
    
    def publish_brightness(self, value: int) -> bool:
        if not self.connected:
            print(f'[MQTT] OFFLINE - brightness: {value}%')
            return False
        
        if value == self.last_brightness:
            return True
        
        try:
            payload = f'{value}'
            result = self.client.publish(
                Config.MQTT_TOPIC_BRIGHTNESS,
                payload,
            )
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.last_brightness = value
                print(f'[MQTT] Sent brightness: {value}%')
                return True
            else:
                print(f'[MQTT] Error sending brightness: {result.rc}')
                return False
                
        except Exception as e:
            print(f'[MQTT] Exception while sending brightness: {e}')
            return False
    
    def publish_color(self, r: int, g: int, b: int) -> bool:
        if not self.connected:
            print(f'[MQTT] OFFLINE - RGB: ({r},{g},{b})')
            return False
        
        rgb = (r, g, b)
        if rgb == self.last_color:
            return True
        
        try:
            payload = f'{r},{g},{b}'
            result = self.client.publish(Config.MQTT_TOPIC_COLOR, payload)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.last_color = rgb
                print(f'[MQTT] Sent RGB: ({r},{g},{b})')
                return True
            else:
                print(f'[MQTT] Error sending color: {result.rc}')
                return False
                
        except Exception as e:
            print(f"[MQTT] Exception while sending color: {e}")
            return False
        
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            print("[MQTT] Connected succesfully")

        else:
            self.connected = False
            print(f"[MQTT] Connection error: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        if rc != 0:
            print(f"[MQTT] Unexpected disconnect rc: {rc}")

    def disconnect(self):
        if self.connected:
            self.client.loop_stop()
            self.client.disconnect()
            print("[MQTT] Successfully disconnected")