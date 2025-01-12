# airsafemonitor

This is a raspberry pi-based air quality monitoring system that measures the temperature, humidity, and LPG gas levels using the DHT11 and MQ2 sensor, and LED indicators. The data is processed and sent to an API for real-time monitoring.

## features

- measures temperature and humidity using the DHT11 sensor
- measures LPG gas levels using the MQ2 sensor
- LED indicators for the status of the sensors
    - green: safe
    - yellow: warning
    - red: dangerous (blinks for very high levels)
- sends data to an API for real-time monitoring

## components

- raspberry pi 4
- DHT11 temperature and humidity sensor
- MQ2 gas sensor
- LED module (green, yellow, red)
- MCP3008 ADC (10 bit analog to digital converter)
- breadboard
- jumper wires
- resistors:
    - 1k ohm and 560 ohm for voltage divider (converting 5V MQ2 output to 3.3V)
- power supply for the raspberry pi
- (optional) LAN cable for SSH access/debugging

## wiring

### DHT11 sensor

- VCC: 5V
- GND: GND
- DATA: GPIO 5

### MQ2 sensor

- VCC: 5V
- GND: GND
- AOUT: MCP3008 CH0

### LED module

- green: GPIO 17
- yellow: GPIO 27
- red: GPIO 22
- GND: GND

### MCP3008 ADC

The MCP3008 ADC communicates with the raspberry pi via SPI, but since it operates at 5V due to the MQ2 sensor and the raspberry pi operates at 3.3V, we need a voltage divider on the DOUT (MISO) line (this reduces the 5V signal to ~3.2V).

- DGND: GND
- CS: GPIO 8 (CE0)
- DIN: GPIO 10 (MOSI)
- DOUT: connected to a voltage divider to GPIO 9 (MISO)
- CLK: GPIO 11 (SCLK)
- AGND: GND
- VREF: 3.3V
- VDD: 3.3V

### voltage divider

- attach one leg of a 560 ohm resistor to the DOUT pin of the MCP3008
- connect the second leg of the 560 ohm resistor to a row on the breadboard
- use a jumper wire to connect this row the GPIO 9 (MISO) pin of the raspberry pi
- in the same row, connect a 1k ohm resistor to GND

```
MCP3008 DOUT --- [560 Ω] ---+--- GPIO 9 (MISO)
                            |
                         [1 kΩ]
                            |
                           GND
```

## installation

You need to have python3 installed on your system.

```sh
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

Note: using the circuitpython version as it is actively maintained and integrates better with modern raspberry pi's.

## testing

you can run the testing scripts in the `/tests` directory to test the functionality of the modules (DHT11, MQ2, LEDs)
