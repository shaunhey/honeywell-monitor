#!/usr/bin/env python3

import base64
from configparser import ConfigParser
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import http.client
from influxdb_client import InfluxDBClient;
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client import Point
import logging
import requests
import sys
import time

Verbose = False

def get_token(authorization: str):
    print("Obtaining token...")

    response = requests.post(
        "https://api.honeywell.com/oauth2/accesstoken",
        headers = {
            "Authorization": authorization
        },
        data = {
            "grant_type": "client_credentials"
        }
    )

    if Verbose: print(response.content)
    response.raise_for_status()
    token = response.json()

    token_expiration = datetime.now(timezone.utc) + timedelta(seconds = int(token["expires_in"]))
    print("Token obtained, expires at", token_expiration)

    return token, token_expiration

def get_locations(client_id: str, token_type: str, token: str, user_ref_id: str) -> list:
    print("Obtaining location information...    ")

    response = requests.get(
        "https://api.honeywell.com/v2/locations?apikey=" + client_id,
        headers = {
            "Authorization": token_type + " " + token,
            "UserRefID": user_ref_id
        }
    )

    if Verbose: print(response.content)
    response.raise_for_status()
    locations = response.json()
    print("Location information obtained")

    return locations

def compare_locations(previous_locations: list, locations: list):
    if len(previous_locations) > 0:
            for location in locations:
                for previous_location in previous_locations:
                    if location["locationID"] == previous_location["locationID"]:
                        for device in location["devices"]:
                            for previous_device in previous_location["devices"]:
                                if device["deviceID"] == previous_device["deviceID"]:
                                    device_name = device["userDefinedDeviceName"]

                                    mode = device["operationStatus"]["mode"]
                                    previous_mode = previous_device["operationStatus"]["mode"]
                                    mode_changed = mode != previous_mode

                                    if mode_changed:
                                        print(device_name, "mode changed from", previous_mode, "to", mode)

                                    fan_mode = device["settings"]["fan"]["changeableValues"]["mode"]
                                    previous_fan_mode = previous_device["settings"]["fan"]["changeableValues"]["mode"]
                                    fan_mode_changed = fan_mode != previous_fan_mode

                                    if fan_mode_changed:
                                        print(device_name, "fan mode changed from", previous_fan_mode, "to", fan_mode)

                                    heat_setpoint = device["changeableValues"]["heatSetpoint"]
                                    previous_heat_setpoint = previous_device["changeableValues"]["heatSetpoint"]
                                    heat_setpoint_changed = heat_setpoint != previous_heat_setpoint

                                    if heat_setpoint_changed:
                                        print(device_name, "heat setpoint changed from", previous_heat_setpoint, "to", heat_setpoint)


                                    cool_setpoint = device["changeableValues"]["coolSetpoint"]
                                    previous_cool_setpoint = previous_device["changeableValues"]["coolSetpoint"]
                                    cool_setpoint_changed = cool_setpoint != previous_cool_setpoint

                                    if cool_setpoint_changed:
                                        print(device_name, "cool setpoint changed from", previous_heat_setpoint, "to", heat_setpoint)

def process_locations(locations, influxdb_bucket, influxdb_org, write_api):
    for location in locations:
        for device in location["devices"]:
            device_name = device["userDefinedDeviceName"]
            write_api.write(
                influxdb_bucket, 
                influxdb_org, 
                Point("status")
                    .tag("device_name", device_name)
                    .field("set_mode", device["changeableValues"]["mode"])
                    .field("operation_mode", device["operationStatus"]["mode"])
                    .field("fan_mode", device["settings"]["fan"]["changeableValues"]["mode"])
                    .field("heat_setpoint", device["changeableValues"]["heatSetpoint"])
                    .field("cool_setpoint", device["changeableValues"]["coolSetpoint"])
                    .field("indoor_temperature", device["indoorTemperature"]))

def main():

    if "-v" in sys.argv:
        VERBOSE = True
        logging.basicConfig(level=logging.DEBUG)
        http.client.HTTPConnection.debuglevel = 1

    config = ConfigParser()
    config.read("/etc/honeywell-monitor.conf")

    client_id = config.get("config", "client_id")
    client_secret = config.get("config", "client_secret")
    user_ref_id = config.get("config", "user_ref_id")

    authorization = base64.b64encode((client_id + ":" + client_secret).encode("ascii")).decode("ascii")
    
    token_expiration = datetime.now(timezone.utc)
    previous_locations = []

    influxdb_url = config.get("config", "influxdb_url")
    influxdb_token = config.get("config", "influxdb_token")
    influxdb_org = config.get("config", "influxdb_org")
    influxdb_bucket = config.get("config", "influxdb_bucket")

    client = InfluxDBClient(url=influxdb_url, token=influxdb_token, org=influxdb_org)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    while True:
        if datetime.now(timezone.utc) + timedelta(seconds = 10) >= token_expiration:
            token, token_expiration = get_token(authorization)
        
        locations = get_locations(client_id, token["token_type"], token["access_token"], user_ref_id)
        process_locations(locations, influxdb_bucket, influxdb_org, write_api)
        compare_locations(previous_locations, locations)
        previous_locations = locations
        print("Sleeping...")
        time.sleep(60)

if __name__ == "__main__":
    main()
