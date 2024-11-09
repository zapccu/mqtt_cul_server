#!/usr/bin/env python3

import argparse
import configparser
import logging

from mqtt_cul_server import MQTT_CUL_Server

if __name__ == "__main__":
    """Control devices via MQTT and CUL RF USB stick"""
    
    parser = argparse.ArgumentParser(
        prog="mqtt_cul_server",
        description="Bidrectional CUL2MQTT Gateway"
    )
    parser.add_argument('--config', default='mqtt_cul_server.ini')
    args = parser.parse_args()
    
    print(f"reading config from {args.config}")
    config = configparser.ConfigParser()
    config.read(args.config)

    level = logging.ERROR
    logger = logging.getLogger()
    if config["DEFAULT"].getboolean("verbose"):
        level = logging.INFO
        
    logfile = config["DEFAULT"].get("logfile", '')
    if logfile != '':
        logging.basicConfig(filename=logfile, encoding='utf-8', level=level)
    else:
        logger.setLevel(level)

    mcs = MQTT_CUL_Server(config=config)
    mcs.start()
