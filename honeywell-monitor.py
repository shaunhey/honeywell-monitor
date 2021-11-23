#!/usr/bin/env python3

import base64
from configparser import ConfigParser
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import http.client
import logging
import requests
import sys
import time

def main():
    verbose = False
    config = ConfigParser()

    if "-v" in sys.argv:
        verbose = True
        logging.basicConfig(level=logging.DEBUG)
        http.client.HTTPConnection.debuglevel = 1

    config_file = "/etc/honeywell-monitor.conf"
    config.read(config_file)

    client_id = config.get("config", "client_id")
    client_secret = config.get("config", "client_secret")
    authorization = base64.b64encode((client_id + ":" + client_secret).encode("ascii")).decode("ascii")

    user_ref_id = config.get("config", "user_ref_id")
    
    token_expiration = datetime.now(timezone.utc)
    previous_locations = []

    while True:
        if datetime.now(timezone.utc) + timedelta(seconds = 10) >= token_expiration:
            print("Obtaining token...")
            token_response = requests.post(
                "https://api.honeywell.com/oauth2/accesstoken",
                headers={
                    "Authorization": authorization
                },
                data={
                    "grant_type": "client_credentials"
                }
            )

            if verbose: print(token_response.content)
            token_response.raise_for_status()
            token = token_response.json()

            token_expiration = datetime.now(timezone.utc) + timedelta(seconds = int(token["expires_in"]))
            print("Token obtained, expires at", token_expiration)
        

        print("Obtaining location information...    ")
        location_response = requests.get(
            "https://api.honeywell.com/v2/locations?apikey=" + client_id,
            headers={
                "Authorization": token["token_type"] + " " + token["access_token"],
                "UserRefID": user_ref_id
            }
        )

        if verbose: print(location_response.content)
        location_response.raise_for_status()
        locations = location_response.json()

        print("Location information obtained, checking for changes...")

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
        
        previous_locations = locations

        print("Sleeping...")
        time.sleep(60)


                                    
                                    
                                    




if __name__ == "__main__":
    main()
