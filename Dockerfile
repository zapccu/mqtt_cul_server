FROM python:3.10-slim

LABEL org.opencontainers.image.url="https://github.com/zapccu/mqtt_cul_server"
LABEL org.opencontainers.image.authors="Bernhard Bock <bernhard@bock.nu>, Dirk Braner (zapccu) <d.braner@gmx.net>"
LABEL org.opencontainers.image.licenses="GPL-3.0"
LABEL org.opencontainers.image.title="MQTT CUL server"
LABEL org.opencontainers.image.description="Bridge to connect a CUL wireless transceiver with an MQTT broker"

WORKDIR /mqtt_cul_server

COPY . .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir .

VOLUME /state

ENTRYPOINT [ "python", "mqtt_cul_server.py" ]
