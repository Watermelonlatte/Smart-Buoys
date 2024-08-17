import time
import math
import json
import requests
import numpy as np
import RPi.GPIO as GPIO
import smbus
from gps3 import gps3

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
TRIG = 23
ECHO = 24
GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)

bus = smbus.SMBus(1)
address = 0x53
bus.write_byte_data(address, 0x2D, 0x08)

gps_socket = gps3.GPSDSocket()
data_stream = gps3.DataStream()
gps_socket.connect()
gps_socket.watch()

prev_lat, prev_lon = None, None

CSE_URL = "http://RPI_IP_ADDRESS:3000/TinyIoT"
AE_NAME = "WaveMonitoringApp"
CNT_NAME = "WaveData"

def get_distance():
    GPIO.output(TRIG, False)
    time.sleep(0.1)
    GPIO.output(TRIG, True)
    time.sleep(0.00001)
    GPIO.output(TRIG, False)

    while GPIO.input(ECHO) == 0:
        pulse_start = time.time()

    while GPIO.input(ECHO) == 1:
        pulse_end = time.time()

    pulse_duration = pulse_end - pulse_start
    distance = pulse_duration * 17150
    distance = round(distance, 2)

    return distance

def read_accel():
    data = bus.read_i2c_block_data(address, 0x32, 6)
    x = (data[1] << 8) | data[0]
    y = (data[3] << 8) | data[2]
    z = (data[5] << 8) | data[4]

    if x & (1 << 15):
        x -= 1 << 16
    if y & (1 << 15):
        y -= 1 << 16
    if z & (1 << 15):
        z -= 1 << 16

    return x, y, z

def get_gps_data():
    latitude, longitude, altitude = None, None, None
    for new_data in gps_socket:
        if new_data:
            data_stream.unpack(new_data)
            latitude = data_stream.TPV['lat']
            longitude = data_stream.TPV['lon']
            altitude = data_stream.TPV['alt']
            if latitude is not None and longitude is not None and altitude is not None:
                return latitude, longitude, altitude
        break
    return latitude, longitude, altitude

def calculate_wave_period(accelerometer_data, sampling_rate):
    z_values = [data[2] for data in accelerometer_data]
    threshold = 10.0
    peaks = []
    for i in range(1, len(z_values) - 1):
        if z_values[i - 1] < z_values[i] > z_values[i + 1] and z_values[i] > threshold:
            peaks.append(i)
    if len(peaks) >= 2:
        period = (peaks[-1] - peaks[-2]) / sampling_rate
        return period
    else:
        return 0

def get_wave_condition(wave_height, wave_period):
    if wave_height >= 4 and wave_period > 11.0:
        return "Hazard"
    elif wave_height >= 2 and 8.0 <= wave_period <= 11.0:
        return "Caution"
    elif wave_height > 2 and wave_period <= 8.0:
        return "Notice"
    elif wave_height <= 2 and wave_period > 8.0:
        return "Attention"
    elif wave_height < 2 and wave_period <= 8.0:
        return "Normal"
    else:
        return "Unknown"

def send_wave_condition_to_tinyiot(wave_condition):
    url = f"{CSE_URL}/{AE_NAME}/{CNT_NAME}"
    headers = {
        'X-M2M-Origin': 'CAdmin',
        'X-M2M-RVI': '3',
        'Content-Type': 'application/vnd.onem2m-res+json;ty=4'
    }
    data = {
        "m2m:cin": {
            "cnf": "application/json",
            "con": json.dumps({"wave_condition": wave_condition})
        }
    }
    response = requests.post(url, json=data, headers=headers, verify = False)
    return response.status_code

def create_ae():
    url = CSE_URL
    headers = {
        'X-M2M-Origin': 'CAdmin',
        'X-M2M-RVI': '3',
        'Content-Type': 'application/vnd.onem2m-res+json;ty=2',
    }
    data = {
        "m2m:ae": {
            "rn": AE_NAME,
            "api": "NWaveMonitoring",
            "rr": True,
        }
    }
    response = requests.post(url, json=data, headers=headers)
    return response.status_code

def create_cnt():
    url = f"{CSE_URL}/{AE_NAME}"
    headers = {
        'X-M2M-Origin': 'CAdmin',
        'X-M2M-RVI': '3',
        'Content-Type': 'application/vnd.onem2m-res+json;ty=3'
    }
    data = {
        "m2m:cnt": {
            "rn": CNT_NAME
        }
    }
    response = requests.post(url, json=data, headers=headers)
    return response.status_code

create_ae()
create_cnt()

sampling_rate = 1
wave_heights = []
accelerometer_data = []

while True:
    ultrasonic = get_distance()
    accel_x, accel_y, accel_z = read_accel()
    lat, lon, alt = get_gps_data()

    wave_heights.append(ultrasonic)
    accelerometer_data.append((accel_x, accel_y, accel_z))

    wave_period = calculate_wave_period(accelerometer_data, sampling_rate)

    wave_condition = get_wave_condition(ultrasonic, wave_period)

    print(f"Ultrasonic Data (Wave Height): {ultrasonic:.2f}m, Wave Period: {wave_period:.2f}s")
    print(f"Accelerometer Data: x={accel_x:.2f}, y={accel_y:.2f}, z={accel_z:.2f}")
    print(f"GPS Data: Latitude={lat}, Longitude={lon}, Altitude={alt}")
    print(f"----------Wave Condition: {wave_condition}------------")

    status_code = send_wave_condition_to_tinyiot(wave_condition)
    
    if status_code == 201:
        print(f"Wave condition sent successfully")
    else:
        print(f"Failed to send data")
    
    time.sleep(2)
