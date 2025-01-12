import time
import math
import threading
import sys
import signal

import RPi.GPIO as GPIO
import spidev

import board
from adafruit_dht import DHT11

import requests

# config
API_URL = "https://api.maxi-script.com/airsafe"
API_INTERVAL = 5.0
DHT_READ_INTERVAL = 2.0
MQ2_READ_INTERVAL = 0.5

readings_lock = threading.Lock()
readings = {
    "temperature": None,
    "humidity": None,
    "lpg_ppm": None
}

stop_event = threading.Event()

# dht11 setup
DHT_PIN = board.D5  # gpio 5
dht_sensor = DHT11(DHT_PIN)

def read_dht11():
    """
    reads temperature and humidity from the DHT11 sensor
    returns (temperature, humidity) or (None, None) if reading fails
    """
    try:
        temperature = dht_sensor.temperature
        humidity = dht_sensor.humidity
        return (temperature, humidity)
    except RuntimeError as error:
        print(f"DHT RuntimeError: {error}")
        return (None, None)
    except Exception as error:
        print(f"An unexpected error occurred with DHT: {error}")
        dht_sensor.exit()
        raise

# led setup
GPIO.setmode(GPIO.BCM)
GREEN_LED = 17
YELLOW_LED = 27
RED_LED = 22

GPIO.setup(GREEN_LED, GPIO.OUT)
GPIO.setup(YELLOW_LED, GPIO.OUT)
GPIO.setup(RED_LED, GPIO.OUT)

def all_lights_off(*args, **kwargs):
    """turn off all lights"""
    global blinking_red
    blinking_red = False  # stop blinking thread
    GPIO.output(GREEN_LED, False)
    GPIO.output(YELLOW_LED, False)
    GPIO.output(RED_LED, False)

def cleanup_and_exit(signal_received=None, frame=None):
    """cleanup GPIO, SPI, threads and exit gracefully"""
    try:
        stop_event.set()
        if api_thread and api_thread.is_alive():
            api_thread.join(timeout=2)

        all_lights_off()
        GPIO.cleanup()
        spi.close()
        dht_sensor.exit()
    except Exception as e:
        print(f"Cleanup error: {e}")
    finally:
        print("Exiting program...")
        sys.exit(0)

# exit on ctrl + c
signal.signal(signal.SIGINT, cleanup_and_exit)

# led in separate thread
blinking_red = False
blink_thread = None

def blink_red_led():
    """blink the red LED in a separate thread"""
    global blinking_red
    while blinking_red:
        GPIO.output(RED_LED, True)
        time.sleep(0.2)
        GPIO.output(RED_LED, False)
        time.sleep(0.2)

def start_blinking_red():
    """start blinking the red LED using a thread"""
    global blinking_red, blink_thread
    if not blinking_red:
        blinking_red = True
        blink_thread = threading.Thread(target=blink_red_led)
        blink_thread.start()

def stop_blinking_red():
    """stop blinking the red LED"""
    global blinking_red, blink_thread
    if blinking_red:
        blinking_red = False
        if blink_thread:
            blink_thread.join()
        GPIO.output(RED_LED, False)

# mq2 setup
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000

RL = 10.0 # load resistance in kΩ
VC = 5.0 # circuit voltage in volts
CLEAN_AIR_RATIO = 9.8 # Rs/Ro ratio in clean air

def read_adc(channel):
    """
    reads the analog value from a specified channel (0-7) on the MCP3008 (10 bit)
    returns ADC value (0 to 1023)
    """
    if channel < 0 or channel > 7:
        raise ValueError("Channel must be an integer between 0 and 7.")

    adc = spi.xfer2([1, (8 + channel) << 4, 0])
    data = ((adc[1] & 3) << 8) + adc[2]
    return data

def calibrate(sensor_channel, read_samples=50, delay=0.5):
    """
    calibrate sensor in clean air to find Ro
    returns the calculated Ro value
    """
    print("Calibrating MQ-2 sensor in clean air. Please ensure the sensor is in clean air...")
    rs_sum = 0.0
    for _ in range(read_samples):
        sensor_value = read_adc(sensor_channel)
        if not (0 <= sensor_value <= 1023):
            raise ValueError("ADC value out of range. Check your hardware or connections.")

        vout = (sensor_value * 3.3) / 1023.0  # 10-bit ADC => range 0-3.3V
        if vout == 0:
            raise ValueError("Vout is 0. Check the sensor or connections.")

        rs = ((VC - vout) * RL) / vout
        rs_sum += rs

        time.sleep(delay)

    rs_avg = rs_sum / read_samples
    ro = rs_avg / CLEAN_AIR_RATIO
    print(f"Calibration complete. Ro = {ro:.2f} kΩ")
    return ro

def calculate_ppm(rs_ro_ratio, gas="LPG"):
    """
    estimate the gas PPM using the provided Rs/Ro ratio and the gas type
    """
    gas_curves = {
        "LPG": (-0.47, 1.7),
        "Methane": (-0.38, 1.3),
        "Hydrogen": (-0.35, 1.1),
        "Alcohol": (-0.30, 0.8)
    }

    if gas not in gas_curves:
        raise ValueError(f"Gas type '{gas}' not supported. Choose from: {list(gas_curves.keys())}")

    slope, intercept = gas_curves[gas]
    log_ppm = (math.log10(rs_ro_ratio) - intercept) / slope
    ppm = 10 ** log_ppm

    if ppm > 1e6:
        print("Warning: PPM value exceeds maximum readable range, set to 1e6.")
        ppm = 1e6
    elif ppm < 0:
        ppm = 0

    return ppm

# api thread
def api_thread_func():
    """
    threaded function to send data to the API at regular intervals
    """
    while not stop_event.is_set():
        time.sleep(API_INTERVAL)
        with readings_lock:
            temp = readings["temperature"]
            hum = readings["humidity"]
            lpg = readings["lpg_ppm"]

        # no data
        if temp is None or hum is None or lpg is None:
            continue

        payload = {
            "timestamp": time.time(),
            "temperature": temp,
            "humidity": hum,
            "lpg_ppm": lpg
        }
        try:
            print(f"Sending data to API: {payload}")
            response = requests.post(API_URL, json=payload, timeout=5)
            response.raise_for_status()
            print("API POST successful:", response.status_code)
        except requests.exceptions.RequestException as ex:
            print(f"API POST error: {ex}")

# main
def main():
    global api_thread

    # start API thread
    api_thread = threading.Thread(target=api_thread_func, daemon=True)
    api_thread.start()

    try:
        sensor_channel = 0
        RO = calibrate(sensor_channel)
        print("\nReading MQ-2 sensor data... Press Ctrl+C to stop.\n")

        last_dht_read_time = 0 # track time since we can only read every 2 seconds

        while True:
            sensor_value = read_adc(sensor_channel)
            if not (0 <= sensor_value <= 1023):
                raise ValueError("ADC value out of range. Check your hardware or connections.")

            vout = (sensor_value * 3.3) / 1023.0
            if vout == 0:
                raise ValueError("Vout is 0. Check the sensor or connections.")

            rs = ((VC - vout) * RL) / vout
            rs_ro_ratio = rs / RO
            if rs_ro_ratio <= 0:
                raise ValueError("Rs/Ro ratio is invalid. Check the sensor readings.")

            lpg_ppm = calculate_ppm(rs_ro_ratio, gas="LPG")

            print(f"MQ-2 -> ADC: {sensor_value} | Vout: {vout:.2f} V | Rs/Ro: {rs_ro_ratio:.2f} | LPG: {lpg_ppm:.2f} ppm")

            # update readings for API
            with readings_lock:
                readings["lpg_ppm"] = lpg_ppm

            # control LEDs based on LPG PPM
            if lpg_ppm < 50:
                # safe
                stop_blinking_red()
                GPIO.output(GREEN_LED, True)
                GPIO.output(YELLOW_LED, False)
                GPIO.output(RED_LED, False)
            elif lpg_ppm < 100:
                # warning
                stop_blinking_red()
                GPIO.output(GREEN_LED, False)
                GPIO.output(YELLOW_LED, True)
                GPIO.output(RED_LED, False)
            elif lpg_ppm < 200:
                # dangerous
                stop_blinking_red()
                GPIO.output(GREEN_LED, False)
                GPIO.output(YELLOW_LED, False)
                GPIO.output(RED_LED, True)
            else:
                # very high => blink red
                GPIO.output(GREEN_LED, False)
                GPIO.output(YELLOW_LED, False)
                start_blinking_red()

            # read DHT11 every 2 seconds (default)
            now = time.time()
            if now - last_dht_read_time >= DHT_READ_INTERVAL:
                temperature, humidity = read_dht11()
                if temperature is not None and humidity is not None:
                    print(f"DHT11 -> Temperature: {temperature:.1f} °C, Humidity: {humidity:.1f} %")
                    with readings_lock:
                        readings["temperature"] = temperature
                        readings["humidity"] = humidity
                else:
                    print("DHT11 reading failed or returned None.")
                last_dht_read_time = now

            time.sleep(MQ2_READ_INTERVAL)

    except KeyboardInterrupt:
        print("KeyboardInterrupt: Exiting program...")
    finally:
        cleanup_and_exit()

if __name__ == "__main__":
    main()
