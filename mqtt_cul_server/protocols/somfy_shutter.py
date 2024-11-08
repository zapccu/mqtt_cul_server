"""
Control Somfy RTS blinds via CUL RF USB stick

This module implements the serial protocol of culfw for the Somfy
wireless communication protocol.
"""

import json
import logging
import os
import time

from threading import Timer

class SomfyShutter:
    """
    Control Somfy RTS blinds via CUL RF USB stick

    This module implements the serial protocol of culfw for the Somfy
    wireless communication protocol.
    """

    class SomfyShutterState:
        def __init__(self, mqtt_client, prefix, statedir, statefile):
            self.mqtt_client = mqtt_client
            
            self.statefile = statedir + "/somfy/" + statefile
            with open(self.statefile, "r", encoding='utf8') as file_handle:
                self.state = json.loads(file_handle.read())

            """
            Up and down timers

            Add up_time and down_time entries to .json state file of your Somfy device to enable up/down timers
            """
            self.otimer = None    # Timer for opening the shutter
            self.ctimer = None    # Timer for closing the shutter
            self.cmd_time = 0     # Timestamp of last open or close command. Used to calculate stop position
            self.direction = 0    # 1 = opening, -1 = closing, 0 = stopped
            
            self.base_path = prefix + "/cover/somfy/" + self.state["address"]

            """
            Send Home Assistant - compatible discovery messages

            for more information about MQTT-discovery and MQTT switches, see
            https://www.home-assistant.io/docs/mqtt/discovery/
            https://www.home-assistant.io/integrations/cover.mqtt/

            Somfy is fire-and-forget with no feedback about the state.
			Anyway state and position are simulated by calculating position based
			on up_time and down_time or as a result of OPEN/CLOSE commands
            """

            configuration = {
                "~": self.base_path,
                "command_topic": "~/set",
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "position_topic": self.base_path + "/position",
                "state_topic": self.base_path + "/state",
                "optimistic": True,
                "device_class": self.state["device_class"],
                "name": self.state["name"],
                "unique_id": "somfy_" + self.state["address"],
            }

            self.mqtt_client.publish(self.base_path + "/config", payload=json.dumps(configuration), retain=True)
                  
        def save(self):
            """Save state to JSON file"""
            with open(self.statefile, "w", encoding='utf8') as file_handle:
                json.dump(self.state, file_handle)

        def increase_rolling_code(self):
            """
            Increment rolling_code, roll over when crossing the 16 bit boundary.
            Increment enc_key, roll over when crossing the 4 bit boundary.
            Save updated state to statefile
            """
            self.state["rolling_code"] = (self.state["rolling_code"] + 1) % 0x10000
            self.state["enc_key"]      = (self.state["enc_key"] + 1) % 0x10
            self.save()

            """ don't loose the code during testing ;) """
            print("next rolling code for device", self.state["address"], " is", self.state["rolling_code"])
            logging.info("next rolling code for device %s is %d", self.state["address"], self.state["rolling_code"])

        def publish_devstate(self, devstate, position = None):
            """ Publish state and position of shutter """
            self.mqtt_client.publish(self.base_path + "/state", payload=devstate, retain=True)
            if position is not None:
                self.state["current_pos"] = position
                self.mqtt_client.publish(self.base_path + "/position", payload=position, retain=True)
                self.save()

        def reset_timers(self):
            """ Reset timer functions """
            if self.otimer is not None:
                self.otimer.cancel()
                self.otimer = None
            if self.ctimer is not None:
                self.ctimer.cancel()
                self.ctimer = None
            self.cmd_timer = 0

        def timer_open(self):
            """ Timer function called when shutter has been opened """
            self.publish_devstate("open", position=100)

        def timer_closed(self):
            """ Timer function called when shutter has been closed """
            self.publish_devstate("closed", position=0)

        def update_state(self, cmd):
            """ calculate position, publish state and position """
            if cmd == "OPEN":
                if "up_time" in self.state:
                    self.publish_devstate("opening")
                    self.reset_timers()
                    self.cmd_time = time.time()
                    self.direction = 1
                    self.otimer = Timer(self.state["up_time"], self.timer_open)
                else:
                    self.publish_devstate("open", position=100)
                    
            elif cmd == "CLOSE":
                if "down_time" in self.state:
                    self.publish_devstate("closing")
                    self.reset_timers()
                    self.cmd_time = time.time()
                    self.direction = -1
                    self.ctimer = Timer(self.state["down_time"], self.timer_close)
                else:
                    self.publish_devstate("closed", position=0)
                    
            elif cmd == "STOP":
                current_pos = 100 if "current_pos" not in self.state else self.state["current_pos"]               
                pos = 50    # Default position, if exact position cannot be calculated
                current_time = time.time()
                
                if self.otimer is not None:
                    self.otimer.cancel()
                    self.otimer = None
                    if self.cmd_time > 0:
                        ti = current_time - self.cmd_time
                        pos = current_pos + int(ti / self.state["up_time"] * 100) * self.direction
                elif self.ctimer is not None:
                    self.ctimer.cancel()
                    self.ctimer = None
                    if self.cmd_time > 0:
                        ti = current_time - self.cmd_time
                        pos = current_pos + int(ti / self.state["down_time"] * 100) * self.direction

                pos = max(min(pos,100), 0)    # Make sure that pos is in range 0..100

                """ publish stopped state and calculated position """
                self.publish_devstate("stopped", position=pos)
                self.cmd_time = 0
                self.direction = 0                

        def calculate_checksum(self, command):
            """
            Calculate checksum for command string

            From https://pushstack.wordpress.com/somfy-rts-protocol/ :
            The checksum is calculated by doing a XOR of all nibbles of the frame.
            To generate a checksum for a frame set the 'cks' field to 0 before
            calculating the checksum.
            """
            cmd = bytearray(command, "utf-8")
            checksum = 0
            for char in cmd:
                checksum = checksum ^ char ^ (char >> 4)
            checksum = checksum & 0xF
            return "{:01X}".format(checksum)

        def command_string(self, command):
            """
            A Somfy command is a hex string of the following form: KKC0RRRRSSSSSS

            KK - Encryption key: First byte always 'A', second byte varies
            C - Command (1 = My, 2 = Up, 4 = Down, 8 = Prog)
            0 - Checksum (set to 0 for calculating checksum)
            RRRR - Rolling code
            SSSSSS - Address (= remote channel)
            """
            commands = {
                "my": 1,
                "up": 2,
                "my-up": 3,
                "down": 4,
                "my-down": 5,
                "up-down": 6,
                "my-up-down": 7,
                "prog": 8,
                "enable-sun": 9,
                "disable-sun": 10,
            }
            if command in commands:
                command_string = "A{:01X}{:01X}0{:04X}{}".format(
                    self.state["enc_key"],
                    commands[command],
                    self.state["rolling_code"],
                    self.state["address"],
                )
            else:
                raise NameError("unknown command")
            command_string = (
                command_string[:3]
                + self.calculate_checksum(command_string)
                + command_string[4:]
            )
            command_string = "Ys" + command_string + "\n"
            return command_string.encode()

    """
    Implementation of class SomfyShutter
    """
    def __init__(self, cul, mqtt_client, prefix, statedir):
        self.cul = cul
        self.prefix = prefix
        self.calibrate = 0
        self.cal_start = 0

        self.devices = []
        for statefile in os.listdir(statedir + "/somfy/"):
            if ".json" in statefile:
                self.devices.append(self.SomfyShutterState(mqtt_client, prefix, statedir, statefile))

    @classmethod
    def get_component_name(cls):
        return "somfy"

    def send_command(self, command, device):
        """Send command string via CUL device"""
        command_string = device.command_string(command)
        logging.info("sending command string %s to %s", command_string, device.state["name"])
        self.cul.send_command(command_string)
        device.increase_rolling_code()

    def on_message(self, message):
        prefix, devicetype, component, address, topic = message.topic.rsplit("/", 4)
        command = message.payload.decode()

        if prefix != self.prefix:
            logging.info("Ignoring message due to prefix")
            return
        if devicetype != "cover":
            raise ValueError("Somfy can only handle covers")
        if component != "somfy":
            raise ValueError("Received command for different component")

        device = None
        for d in self.devices:
            if d.state["address"] == address:
                device = d
                break
        if not device:
            raise ValueError("Device not found: %s", address)

        if topic == "set":
            cmd_lookup = { "OPEN": "up", "CLOSE": "down", "STOP": "my", "PROG": "prog" }
            
            if command == "CALIBRATE":
                if self.calibrate > 0:
                    """ interrupt calibration """
                    self.calibrate = 0
                    self.cal_start = 0
                    device.publish_devstate("stopped")
                else:
                    """ start calibration, measure up and down time """
                    self.calibrate = 1
                    self.cal_start = time.time()
                    self.send_command("down", device)
                    device.publish_devstate("calibrating")
                    
            elif command == "STOP" and self.calibrate == 1:
                """ measure down_time """
                self.calibrate = 2
                device.state["down_time"] = time.time() - self.cal_start
                self.send_command("my", device)    # also save state to file incl. down_time
                time.sleep(2)
                self.cal_start = time.time()
                self.send_command("up", device)
                
            elif command == "STOP" and self.calibrate == 2:
                """ measure up_time and stop calibration """
                self.calibrate = 0
                self.cal_start = 0
                device.state["up_time"] = time.time() - self.cal_start
                self.send_command("my", device)    # also save state to file incl. up_time
                device.publish_devstate("open", 100)
                
            elif command in cmd_lookup:
                self.send_command(cmd_lookup[command], device)
                device.update_state(command)
                
            else:
                raise ValueError("Command %s is not supported", command)
        else:
            logging.debug("ignoring topic %s", topic)
