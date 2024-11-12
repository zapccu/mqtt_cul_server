#!/usr/bin/env python3

import sys
import argparse
import configparser
import logging
import signal

from mqtt_cul_server import MQTT_CUL_Server

def signal_handler(sig, frame):
    """ called when SIGTERM received """
    logging.info("Received SIGTERM. Terminating")
    sys.exit(0)
        
if __name__ == "__main__":
    """Control devices via MQTT and CUL RF USB stick"""
    
    parser = argparse.ArgumentParser(
        prog="mqtt_cul_server",
        description="Bidrectional CUL2MQTT Gateway"
    )
    parser.add_argument('--config', default='mqtt_cul_server.ini')
    args = parser.parse_args()
    
    config = configparser.ConfigParser()
    fcount = config.read(args.config)
    if len(fcount) == 0:
        print(f"ERROR: Cannot read config file {args.config}")
        sys.exit(1)

    level = logging.ERROR
    logger = logging.getLogger()
    if config.getboolean("DEFAULT", "verbose", fallback=False):
        level = logging.INFO
    if config.getboolean("DEFAULT", "debug", fallback=False):
        level = logging.DEBUG
        
    logfile = config.get("DEFAULT", "logfile", fallback='')
    if logfile != '':
        logging.basicConfig(filename=logfile, encoding='utf-8', level=level)
    else:
        logger.setLevel(level)
        
    signal.signal(signal.SIGTERM, signal_handler)

    mcs = MQTT_CUL_Server(config=config)
    mcs.start()
    
    sys.exit(0)
