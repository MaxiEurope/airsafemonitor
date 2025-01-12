import spidev
import time
import math

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000

RL = 10  # load resistance in kΩ
VC = 5.0  # circuit voltage in volts
CLEAN_AIR_RATIO = 9.8  # Rs/Ro ratio in clean air

def read_adc(channel):
    if channel < 0 or channel > 7:
        raise ValueError("Channel must be an integer between 0 and 7.")
    adc = spi.xfer2([1, (8 + channel) << 4, 0])
    data = ((adc[1] & 3) << 8) + adc[2]
    return data

# calculate Ro in clean air
def calibrate(sensor_channel, read_samples=50, delay=0.5):
    print("Calibrating sensor in clean air...")
    rs_sum = 0
    for _ in range(read_samples):
        sensor_value = read_adc(sensor_channel)
        if not (0 <= sensor_value <= 1023):
            raise ValueError("ADC value out of range. Check your hardware or connections.")

        vout = (sensor_value * 3.3) / 1023 # 10 bit ADC
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
    gas_curves = {
        "LPG": (-0.47, 1.7),
        "Methane": (-0.38, 1.3),
        "Hydrogen": (-0.35, 1.1),
        "Alcohol": (-0.30, 0.8)
    }
    if gas not in gas_curves:
        raise ValueError("Gas type not supported.")
    
    slope, intercept = gas_curves[gas]
    log_ppm = (math.log10(rs_ro_ratio) - intercept) / slope

    ppm = 10 ** log_ppm
    if ppm > 1e6:
        print("Warning: PPM value exceeds maximum detectable range.")
        ppm = 1e6
    elif ppm < 0:
        raise ValueError("PPM value cannot be negative.")

    return ppm

try:
    print("Initializing MQ-2 sensor...")

    sensor_channel = 0  # ADC channel (0 to 7)
    RO = calibrate(sensor_channel)
    
    print("Reading MQ-2 sensor data... Press Ctrl+C to stop.")
    while True:
        sensor_value = read_adc(sensor_channel)
        if not (0 <= sensor_value <= 1023):
            raise ValueError("ADC value out of range. Check your hardware or connections.")

        vout = (sensor_value * 3.3) / 1023  # convert ADC value to voltage
        if vout == 0:
            raise ValueError("Vout is 0. Check the sensor or connections.")

        rs = ((VC - vout) * RL) / vout

        rs_ro_ratio = rs / RO
        if rs_ro_ratio <= 0:
            raise ValueError("Rs/Ro ratio is invalid. Check the sensor readings.")

        lpg_ppm = calculate_ppm(rs_ro_ratio, gas="LPG")

        print(f"Raw ADC Value: {sensor_value} | Voltage: {vout:.2f}V | Rs/Ro: {rs_ro_ratio:.2f} | LPG PPM: {lpg_ppm:.2f}")
        
        time.sleep(1)
except KeyboardInterrupt:
    print("Exiting gracefully...")
    spi.close()
