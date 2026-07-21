from machine import Pin, ADC, I2C
import time
import dht
from pico_i2c_lcd import I2cLcd

# ==================== ПИНЫ СЕНСОРОВ ====================
sensor_light = ADC(Pin(28))
sensor_water = ADC(Pin(27))
d = dht.DHT11(Pin(11))  

# Пиновка энкодера
clk_pin = Pin(15, Pin.IN, Pin.PULL_UP)
dt_pin  = Pin(14, Pin.IN, Pin.PULL_UP)
sw_pin  = Pin(16, Pin.IN, Pin.PULL_UP)

# Пиновка дисплея
i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=10000)
time.sleep_ms(2000) # Ждем инициализации I2C
lcd = I2cLcd(i2c, 0x27, 4, 20)
lcd.backlight_on()
lcd.clear()

# ==================== ПИНЫ ИСПОЛНИТЕЛЬНЫХ УСТРОЙСТВ ====================
fan_pin   = Pin(3, Pin.OUT)   # Вентилятор
lamp_pin  = Pin(2, Pin.OUT)   # Лампа
pump_pin  = Pin(4, Pin.OUT)   # Насос
uv_pin    = Pin(5, Pin.OUT)   # УФ лампа

# ==================== КАЛИБРОВКА ДАТЧИКА ВОДЫ ====================
RAW_DRY = 512      
RAW_WET = 17100    
MAX_CM = 4.0
RANGE_VAL = RAW_WET - RAW_DRY  

# ==================== ТАЙМИНГИ В МИЛЛИСЕКУНДАХ (как millis) ====================
CYCLE_TOTAL_MS = 180000   # 3 минуты
PUMP_TIME_MS   = 15000    # 15 секунд
FAN_TIME_MS    = 15000    # 15 секунд

LAMP_ON_MS     = 57600000 # 16 часов
LAMP_OFF_MS    = 28800000 # 8 часов

DISPLAY_UPDATE_MS = 5000  # 5 секунд

# ==================== ПЕРЕМЕННЫЕ СОСТОЯНИЯ ====================
current_page = 1
last_page = 0
last_clk = clk_pin.value()

temp = 0
hum = 0

# Стартовые метки времени
system_start_ms = time.ticks_ms()
lamp_start_ms = time.ticks_ms()
last_update_ms = time.ticks_ms()

lamp_state = True

# ==================== ФУНКЦИИ ====================
def get_smooth_water(samples=10):
    total = 0
    for _ in range(samples):
        total += sensor_water.read_u16()
        time.sleep_ms(5)
    raw_val = total // samples
    if raw_val < RAW_DRY: raw_val = RAW_DRY
    if raw_val > RAW_WET: raw_val = RAW_WET
    
    cm = (raw_val - RAW_DRY) * MAX_CM / RANGE_VAL
    return round(cm, 2)

# ==================== СТАРТ ====================
print("Система запущена (millis mode).")
uv_pin.on()      
pump_pin.off()   
fan_pin.off()
lamp_pin.on()    

# ==================== ОСНОВНОЙ ЦИКЛ ====================
while True:
    now_ms = time.ticks_ms()

    # --- 1. ЛОГИКА НАСОСА И ВЕНТИЛЯТОРА ---
    # ticks_diff корректно обрабатывает переполнение счетчика
    elapsed_cycle = time.ticks_diff(now_ms, system_start_ms) % CYCLE_TOTAL_MS

    if elapsed_cycle < PUMP_TIME_MS:
        # Фаза 1: 0 - 15 сек -> Насос ВКЛ
        pump_pin.on()
        fan_pin.off()
    elif elapsed_cycle < (PUMP_TIME_MS + FAN_TIME_MS):
        # Фаза 2: 15 - 30 сек -> Вентилятор ВКЛ
        pump_pin.off()
        fan_pin.on()
    else:
        # Фаза 3: 30 - 180 сек -> Пауза
        pump_pin.off()
        fan_pin.off()

    # --- 2. ЛОГИКА ЛАМПЫ ---
    elapsed_lamp = time.ticks_diff(now_ms, lamp_start_ms)
    
    if lamp_state:
        if elapsed_lamp >= LAMP_ON_MS:
            lamp_pin.off()
            lamp_state = False
            lamp_start_ms = now_ms
            print("[Лампа] ВЫКЛ")
    else:
        if elapsed_lamp >= LAMP_OFF_MS:
            lamp_pin.on()
            lamp_state = True
            lamp_start_ms = now_ms
            print("[Лампа] ВКЛ")

    # --- 3. ЛОГИКА ЭНКОДЕРА ---
    current_clk = clk_pin.value()
    if current_clk != last_clk:
        if current_clk == 0:  # Спад сигнала (поворот)
            if dt_pin.value() != current_clk:
                current_page += 1
            else:
                current_page -= 1
            
            if current_page > 3: current_page = 1
            if current_page < 1: current_page = 3
            
            last_page = 0  # Форсируем обновление экрана
            last_update_ms = now_ms
            
        last_clk = current_clk

    # Кнопка энкодера -> возврат на Page 1
    if sw_pin.value() == 0:
        current_page = 1
        last_page = 0
        time.sleep_ms(300)  # Антидребезг в миллисекундах

    # --- 4. ЧТЕНИЕ СЕНСОРОВ ---
    value_sensor = sensor_light.read_u16()
    water_cm = get_smooth_water()

    try:
        d.measure()
        temp = d.temperature()
        hum = d.humidity()
    except OSError:
        pass 

    # --- 5. ОБНОВЛЕНИЕ ДИСПЛЕЯ ---
    if (current_page != last_page) or (time.ticks_diff(now_ms, last_update_ms) >= DISPLAY_UPDATE_MS):
        lcd.clear()
        last_page = current_page
        last_update_ms = now_ms

        if current_page == 1:
            lcd.move_to(0, 0)
            lcd.putstr("--- Sensors 1 ---")
            lcd.move_to(0, 1)
            lcd.putstr(f"Light: {value_sensor}")
            lcd.move_to(0, 2)
            lcd.putstr(f"Water: {water_cm:.1f} cm")
            
        elif current_page == 2:
            lcd.move_to(0, 0)
            lcd.putstr("--- Climate ---")
            lcd.move_to(0, 1)
            lcd.putstr(f"Temp: {temp} C")
            lcd.move_to(0, 2)
            lcd.putstr(f"Hum: {hum} %")
            
        elif current_page == 3:
            lcd.move_to(0, 0)
            lcd.putstr("--- Status ---")
            lcd.move_to(0, 1)
            p_s = "ON " if pump_pin.value() else "OFF"
            f_s = "ON " if fan_pin.value() else "OFF"
            l_s = "ON " if lamp_pin.value() else "OFF"
            lcd.putstr(f"P:{p_s} F:{f_s}")
            lcd.move_to(0, 2)
            lcd.putstr(f"L:{l_s} UV: ON")

    # Неблокирующая задержка цикла
    time.sleep_ms(50)



