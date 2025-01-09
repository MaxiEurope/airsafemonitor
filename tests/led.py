import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
LEDS = {'red': 22, 'yellow': 27, 'green': 17}

for pin in LEDS.values():
    GPIO.setup(pin, GPIO.OUT)

def all_lights_off():
    for pin in LEDS.values():
        GPIO.output(pin, False)

try:
    print('ctrl + c to end')
    while True:
        GPIO.output(LEDS['red'], True)  # red on
        time.sleep(3)

        GPIO.output(LEDS['yellow'], True)  # yellow on, red still on
        time.sleep(1)

        all_lights_off()
        GPIO.output(LEDS['green'], True)  # green on
        time.sleep(5)

        all_lights_off()
        GPIO.output(LEDS['yellow'], True)  # yellow on
        time.sleep(2)

        all_lights_off()
except KeyboardInterrupt:
    all_lights_off()
    GPIO.cleanup()
