
# Installation on Debian / Raspbian
## Prerequisits
* MQTT broker is already setup and running anywhere in your network
* Python is installed on the target system
* You are connected as user root to the target system

## Create directories and clone files from repository

```
# Binaries
mkdir /opt/mqtt_cul_server
# Configuration
mkdir /etc/mqtt_cul_server
# Device states
mkdir -p /var/lib/mqtt_cul_server/state/somfy
# Logfile
mkdir /var/log/mqtt_cul_server

cd /opt
git clone https://github.com/zapccu/mqtt_cul_server
cp /opt/mqtt_cul_server/mqtt_cul_server.ini /etc/mqtt_cul_server/.
```

## Change settings in configuration file

```
vi /etc/mqtt_cul_server/mqtt_cul_server.ini
```

* Set `CUL` to the device file of your CUL device
* Set `statedir` to `/var/lib/mqtt_cul_server/state`
* Set `logfile` to `/var/log/mqtt_cul_server/mqtt_cul_server.log`
* Configure MQTT broker parameters in section `mqtt`


## Create state file(s) for your Somfy devices

```
cd /var/lib/mqtt_cul_server/state
vi myshutter.json    # example
```

For syntax of Somfy state file see [somfy.md](/doc/somfy.md)

## Create user and set rights

```
useradd -d /var/lib/mqtt_cul_server mqttcul
chown -R mqttcul:mqttcul /opt/mqtt_cul_server
chown -R mqttcul:mqttcul /etc/mqtt_cul_server
chown -R mqttcul:mqttcul /var/lib/mqtt_cul_server
chown mqttcul:mqttcul /var/log/mqtt_cul_server
```

## Add service to system daemon

```
cd /etc/systemd/system
```
Create a new file `mqtt-cul-server.service` with the following content:
```
[Unit]
Description=MQTT CUL Gateway
After=network.target

[Service]
Type=idle
Restart=on-failure
User=mqttcul
ExecStart=/bin/bash -c 'cd /opt/mqtt_cul_server/ && python3 mqtt_cul_server.py --config /etc/mqtt_cul_server/mqtt_cul_server.ini'

[Install]
WantedBy=multi-user.target
```
Enable and start the new service:
```
systemctl daemon-reload
systemctl start mqtt-cul-server
systemctl enable mqtt-cul-server
```