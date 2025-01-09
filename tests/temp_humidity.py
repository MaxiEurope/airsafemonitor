import time
import board
from adafruit_dht import DHT11

DHT_PIN = board.D5  # GPIO 5
dht_sensor = DHT11(DHT_PIN)

def read_dht11():
    try:
        temperature = dht_sensor.temperature
        humidity = dht_sensor.humidity

        if temperature is not None and humidity is not None:
            print(f"Temperature: {temperature:.1f}°C, Humidity: {humidity:.1f}%")
        else:
            print("Failed to retrieve data. Retrying...")
    except RuntimeError as error:
        print(f"RuntimeError: {error}")
    except Exception as error:
        print(f"An error occurred: {error}")
        dht_sensor.exit()
        raise

try:
    print("Press Ctrl+C to stop the script.")
    while True:
        read_dht11()
        time.sleep(2)
except KeyboardInterrupt:
    print("Exiting gracefully...")
    dht_sensor.exit()
