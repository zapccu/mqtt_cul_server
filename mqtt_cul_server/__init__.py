import logging
import sys
import signal
import threading
import paho.mqtt.client as mqtt
from . import cul
from .protocols import somfy_shutter, intertechno, lacrosse


class MQTT_CUL_Server:
    components = {}

    def __init__(self, config={}):
        culdev = config.get("DEFAULT", "CUL", fallback="/dev/ttyACM0")
        baudrate = config.get("DEFAULT", "baud_rate", fallback="115200")
        self.cul = cul.Cul(culdev, int(baudrate))
        self.mqtt_client = self.get_mqtt_client(config)

        # prefix for all MQTT topics
        self.prefix = config.get("DEFAULT", "prefix", fallback="homeassistant")

        if config["intertechno"].getboolean("enabled"):
            self.components["intertechno"] = intertechno.Intertechno(self.cul, self.mqtt_client, self.prefix, config["intertechno"])
        if config["somfy"].getboolean("enabled"):
            statedir = config.get("DEFAULT", "statedir", fallback="state")
            self.components["somfy"] = somfy_shutter.SomfyShutter(self.cul, self.mqtt_client, self.prefix, statedir)
        if config["lacrosse"].getboolean("enabled"):
            self.components["lacrosse"] = lacrosse.LaCrosse(self.cul, self.mqtt_client, self.prefix)

    def get_mqtt_client(self, config):
        mqtt_client = mqtt.Client()
        mqtt_client.enable_logger()
        if config.has_option("mqtt", "username") and config.has_option("mqtt", "password"):
            mqtt_client.username_pw_set(
                config.get("mqtt", "username"), config.get("mqtt", "password")
            )
        mqtt_client.on_connect = self.on_mqtt_connect
        mqtt_client.on_message = self.on_mqtt_message
        try:
            mqtt_client.connect(
                config.get("mqtt", "host", fallback="127.0.0.1"), int(config.get("mqtt", "port", fallback="1883")), keepalive=60
            )
        except Exception as e:
            logging.error("Could not connect to MQTT broker: %s", e)
            sys.exit(1)
        return mqtt_client

    def on_mqtt_connect(self, mqtt_client, _userdata, _flags, _rc):
        """The callback for when the MQTT client receives a CONNACK response"""
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        mqtt_client.subscribe(self.prefix + "/#")

    def on_mqtt_message(self, _client, _userdata, msg):
        """The callback for when a message is received"""
        try:
            _, _, component, _ = msg.topic.split("/", 3)
        except ValueError:
            logging.error("cannot parse topic: %s", msg.topic)
            return

        if component in self.components:
            self.components[component].on_message(msg)
        """
        The following log statement will generate warnings for each unknown component under
        "prefix". This makes no sense => commented it out
        else:
            logging.warning("component %s unknown (topic %s)", component, msg.topic)
        """

    def on_rf_message(self, message):
        """
        Handle message received via RF
        SOMFY: This function is also called when a command has been send to a device
        with the acknowledge message (same enc_key and rolling code)
        => Added a dummy message handler for Somfy.
        """
        if not message: return
        if message[0:3] == "N01":
            self.components["lacrosse"].on_rf_message(message)
        elif message[0:3] == "YsA":
            self.components["somfy"].on_rf_message(message)
        else:
            logging.error("Can't handle RF message: %s", message)

    def start(self):
        """Start multiple threads to listen for MQTT and RF messages"""
        # thread to listen for MQTT command messages
        self.mqtt_listener = threading.Thread(target=self.mqtt_client.loop_forever)
        self.mqtt_listener.start()
        # thread to listen for received RF messages
        self.cul_listener = threading.Thread(target=self.cul.listen, args=[self.on_rf_message])
        self.cul_listener.start()
        