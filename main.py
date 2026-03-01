import network # type: ignore
import espnow # type: ignore
import machine # type: ignore
import struct
import time

# --- KONFIGURACJA PINÓW I KANAŁÓW RC ---
# Mapowanie standardu AETR (Aileron, Elevator, Throttle, Rudder)
# oraz przycisków pomocniczych (AUX) i potencjometru.
#                   ESP32-C3 Zero
#                      TOP VIEW
#                ____________________
#               |    USB-C           |
#               |_____________ ______|
#               | [ ] 5V      21 [ ] |
#               | [ ] GND     20 [ ] |
#               | [ ] 3.3v    19 [ ] |
#               | [ ] 0       18 [ ] | 
#               | [ ] 1       10 [ ] | 
#     (PWM) CH4 | [ ] 2        9 [ ] |
#     (PWM) CH3 | [ ] 3        8 [ ] | CH7 (Toggle Button) (DIGITAL)
#     (PWM) CH2 | [ ] 4        7 [ ] | CH6 (Potencjometr) (PWM)
#     (PWM) CH1 | [ ] 5        6 [ ] | CH5 (Toggle Button) (PWM)
#               |____________________|
#                  
# RAMKA DANYCH Z NADAJNKA:
# 
#    0: map_to_rc(joy_data[1]),           # LY
#    1: map_to_rc(joy_data[0]),           # LX
#    2: map_to_rc(joy_data[3]),           # RY
#    3: map_to_rc(joy_data[2]),           # RX
#    4: 2000 if btns['sw3'] else 1000,    # SW3
#    5: 2000 if btns['sw4'] else 1000,    # SW4
#    6: map_to_rc(pots['pot1'], True)     # POT1
# 




# PWM_CHANNELS: 
PWM_CHANNELS = {
    0: 5,  # CH1: Aileron (Lotki) - prawy drążek (lewo/prawo)
    1: 4,  # CH2: Elevator (Wysokość) - prawy drążek (góra/dół)
    2: 3,  # CH3: Throttle (Gaz/Przepustnica) - lewy drążek (góra/dół)
    3: 2,  # CH4: Rudder (Kierunek) - lewy drążek (lewo/prawo)
    4: 6,  # CH5: Toggle Button 1 (Przełącznik dwupozycyjny)
    6: 7   # CH6: Potencjometr (Sterowanie płynne dodatkowe)
}

# DIGITAL_CHANNELS: 
DIGITAL_CHANNELS = {
    5: 8  # CH7: Toggle Button 2 (Przełącznik dwupozycyjny)
}

pwms = {}
for ch, pin_num in PWM_CHANNELS.items():
    pwm = machine.PWM(machine.Pin(pin_num))
    pwm.freq(50)
    pwms[ch] = pwm

digitals = {}
for ch, pin_num in DIGITAL_CHANNELS.items():
    digitals[ch] = machine.Pin(pin_num, machine.Pin.OUT)

def set_servo_us(pwm_obj, us):
    pwm_obj.duty_ns(us * 1000)

def apply_failsafe():
    for pwm in pwms.values():
        set_servo_us(pwm, 1500)
    for pin in digitals.values():
        pin.value(0)
    print("\n[!] STATUS: UTRATA SYGNAŁU - FAILSAFE AKTYWNY")

# --- ESP-NOW ---
sta = network.WLAN(network.STA_IF)
sta.active(True)
e = espnow.ESPNow()
e.active(True)

# Zmienne do monitorowania statusu
last_packet_time = time.ticks_ms()
packet_count = 0
last_info_time = time.ticks_ms()
is_connected = False

print("\n=== ODBIORNIK RC URUCHOMIONY ===")
print(f"MAC: {sta.config('mac')}")
print("Oczekiwanie na nadajnik...")

last_data = None  # Przechowuje poprzedni stan kanałów
DEADZONE = 10     # Ignoruj minimalne drgania potencjometrów (szumy)

while True:
    host, msg = e.recv(50)
    current_time = time.ticks_ms()

    if msg:
        if not is_connected:
            print("\n[+] POŁĄCZONO Z NADAJNIKIEM")
            is_connected = True
            
        try:
            data = struct.unpack('7h', msg)
            
            # --- SEKCJA LOGOWANIA RUCHU ---
            if last_data is not None:
                for i in range(len(data)):
                    # Sprawdzamy czy zmiana jest większa niż DEADZONE (dla płynnych kanałów)
                    if abs(data[i] - last_data[i]) > DEADZONE:
                        nazwa = f"CH{i+1}"
                        # Specjalne opisy dla konkretnych kanałów
                        if i == 2: nazwa = "THROTTLE (CH3)"
                        if i == 4 or i == 5: nazwa = f"PRZEŁĄCZNIK (CH{i+1})"
                        
                        print(f"[*] Ruch na {nazwa}: {data[i]} us")
            
            last_data = data # Zapamiętaj obecny stan
            # ------------------------------

            # Aktualizacja wyjść PWM i Digital
            for ch, pwm_obj in pwms.items():
                set_servo_us(pwm_obj, data[ch])
            for ch, pin_obj in digitals.items():
                pin_obj.value(1 if data[ch] > 1500 else 0)
            
            packet_count += 1
            last_packet_time = current_time
            
        except Exception as err:
            print(f"[-] Błąd: {err}")