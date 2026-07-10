from machine import Pin, ADC, I2C
import time
import dht
from pico_i2c_lcd import I2cLcd

# Пины датчиков
sensor_light = ADC(Pin(28))
THRESHOLD_light = 3200
sensor_water = ADC(Pin(27))
THRESHOLD_water = 10000
d = dht.DHT11(Pin(17))

# Пиновка энкодера
clk_pin = Pin(15, Pin.IN, Pin.PULL_UP)
dt_pin = Pin(14, Pin.IN, Pin.PULL_UP)
sw_pin = Pin(16, Pin.IN, Pin.PULL_UP)

# пиновка дисплея
i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=10000)
time.sleep(2)
lcd = I2cLcd(i2c, 0x27, 4, 20)
lcd.backlight_on()
lcd.clear()

# переменные для калибровки дв
RAW_DRY = 512      # Значение при 0 см
RAW_WET = 17100    # Значение при 4 см
MAX_CM = 4.0       # длина датчика
RANGE_VAL = 16588

# переключение дисплея
current_page = 1
last_page = 0
last_clk = clk_pin.value()
last_update = time.ticks_ms()

# Инициализируем переменные температуры и влажности базовыми значениями
temp = 0
hum = 0

#калибровка дв
def get_smooth_water(samples=10):
    total = 0
    for _ in range(samples):
        total += sensor_water.read_u16()
        time.sleep_ms(5)
    raw_val = total // samples
    raw_val = max(RAW_DRY, min(raw_val, RAW_WET))

    cm = (raw_val - RAW_DRY) * MAX_CM / RANGE_VAL
    return round(cm, 2) 
while True:
    # работа экрана
    current_clk = clk_pin.value()
    if current_clk != last_clk:
        if current_clk == 0:
            if dt_pin.value() != current_clk:
                current_page += 1
            else:
                current_page -= 1
            if current_page > 2:
                current_page = 1
            if current_page < 1:
                current_page = 2
        last_clk = current_clk

    #возврат на страницу 1
    if sw_pin.value() == 0:
        current_page = 1
        time.sleep(0.3)

    value_sensor = sensor_light.read_u16()
    

    water_cm = get_smooth_water()

    try:
        d.measure()
        temp = d.temperature()
        hum = d.humidity()
    except:
        pass

    print(f"Стр {current_page} -> Light: {value_sensor}, Water: {water_cm} cm, Temp: {temp}, Hum: {hum}")
    
    if (current_page != last_page) or (time.ticks_ms() - last_update >= 5000):
        lcd.clear()
        last_page = current_page
        last_update = time.ticks_ms() 

        if current_page == 1:
            lcd.move_to(0, 0)
            lcd.putstr("=== Page 1 ===")
            lcd.move_to(0, 1)
            lcd.putstr(f"Light: {value_sensor}")
            lcd.move_to(0, 2)
            lcd.putstr(f"Water: {(water_cm):.2f} cm")
        else:
            lcd.move_to(0, 0)
            lcd.putstr("=== Page 2 ===")
            lcd.move_to(0, 1)
            lcd.putstr(f"Temp: {temp} C")
            lcd.move_to(0, 2)
            lcd.putstr(f"Hum: {hum} %")
    time.sleep(0.01)
