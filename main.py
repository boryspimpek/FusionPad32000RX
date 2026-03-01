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
#           CH4 | [ ] 2        9 [ ] |
#           CH3 | [ ] 3        8 [ ] | CH7 (Potencjometr)
#           CH2 | [ ] 4        7 [ ] | CH6 (Toggle Button)
#           CH1 | [ ] 5        6 [ ] | CH5  (Toggle Button)
#               |____________________|
#                  



# PWM_CHANNELS: 
PWM_CHANNELS = {
    0: 5,  # CH1: Aileron (Lotki) - prawy drążek (lewo/prawo)
    1: 4,  # CH2: Elevator (Wysokość) - prawy drążek (góra/dół)
    2: 3,  # CH3: Throttle (Gaz/Przepustnica) - lewy drążek (góra/dół)
    3: 2,  # CH4: Rudder (Kierunek) - lewy drążek (lewo/prawo)
    6: 8   # CH5: Potencjometr (Sterowanie płynne dodatkowe)
}

# DIGITAL_CHANNELS: 
DIGITAL_CHANNELS = {
    4: 6,  # CH6: Toggle Button 1 (Przełącznik dwupozycyjny)
    5: 7   # CH7: Toggle Button 2 (Przełącznik dwupozycyjny)
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

while True:
    host, msg = e.recv(50) # Krótki timeout dla lepszej reakcji
    
    current_time = time.ticks_ms()

    if msg:
        if not is_connected:
            print("\n[+] POŁĄCZONO Z NADAJNIKIEM")
            is_connected = True
            
        try:
            data = struct.unpack('7h', msg)
            
            # Aktualizacja wyjść
            for ch, pwm_obj in pwms.items():
                set_servo_us(pwm_obj, data[ch])
            for ch, pin_obj in digitals.items():
                pin_obj.value(1 if data[ch] > 1500 else 0)
            
            packet_count += 1
            last_packet_time = current_time
            
        except:
            print("[-] Błąd dekodowania ramki")
    
    # Statystyki co 2 sekundy (aby nie śmiecić w konsoli)
    if time.ticks_diff(current_time, last_info_time) > 2000:
        if is_connected:
            # Obliczamy pakiety na sekundę (PPS)
            pps = packet_count / 2
            print(f"[OK] Sygnał stabilny | Otrzymano: {packet_count} pkt | ~{pps} pkt/s")
        
        packet_count = 0
        last_info_time = current_time

    # Fail-safe
    if time.ticks_diff(current_time, last_packet_time) > 1000:
        if is_connected:
            apply_failsafe()
            is_connected = False
        last_packet_time = current_time