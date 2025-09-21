import tkinter as tk
import serial
import threading
import time
import queue

# === Serial Setup ===
ser = serial.Serial('COM21', 115200, timeout=0.1)

# === Command Definitions ===
# id = number sent on click, keyword = what we expect at the start of incoming lines
# For adcs, per your rule, keyword is ":" (just a leading colon).
commands_info = {
    "batt":       {"id": 1,  "label": "Battery [V]",             "keyword": "1:"},
    "rssi":       {"id": 2,  "label": "RSSI [dB]",               "keyword": "2:"},
    "uptime":     {"id": 3,  "label": "Uptime [s]",              "keyword": "3:"},
    "power=5":    {"id": 4,  "label": "Power [dB]",              "keyword": "4:"},
    "coord":      {"id": 5,  "label": "GPS Coordinates",         "keyword": "5:"},
    "cartesian":  {"id": 6,  "label": "Cartesian Coordinates",   "keyword": "6:"},
    "acc":        {"id": 7,  "label": "Acceleration [mg]",       "keyword": "7:"},
    "ang_vel":    {"id": 8,  "label": "Angular Velocity [dps]",  "keyword": "8:"},
    "magn_field": {"id": 9,  "label": "Magnetic Field [uT]",     "keyword": "9:"},
    "adcs":       {"id": 10, "label": "Roll/Pitch/Yaw [deg]",    "keyword": ":"},   # special
    "temp_C":     {"id": 11, "label": "Temperature [°C]",        "keyword": "11:"},
    "temp_K":     {"id": 12, "label": "Temperature [K]",         "keyword": "12:"},
}

value_fields = {}
evt_q = queue.Queue()

# === GUI Setup ===
root = tk.Tk()
root.title("Telemetry Dashboard")
root.geometry("1200x800")

dashboard_frame = tk.Frame(root)
dashboard_frame.pack(padx=10, pady=10, fill='x')

def send_numeric(code: int):
    try:
        ser.write((str(code) + "\n").encode())
        print(f"Sent code: {code}")
    except Exception as e:
        print("Serial write error:", e)

# Build rows
for cmd_name, info in commands_info.items():
    row = tk.Frame(dashboard_frame)
    row.pack(fill='x', pady=3)

    btn = tk.Button(row, text=cmd_name, width=15,
                    command=lambda c=info["id"]: send_numeric(c))
    btn.pack(side='left', padx=5)

    label = tk.Label(row, text=info["label"], width=24, anchor='w')
    label.pack(side='left')

    value_label = tk.Label(
        row, text="(no data)", width=48, anchor='w',
        bg='white', relief='sunken', font=("Courier", 10)
    )
    value_label.pack(side='left', padx=5, expand=True, fill='x')

    value_fields[cmd_name] = value_label

# === Parsing helper ===
def value_after_first_colon(line: str) -> str:
    """Return substring after the first ':'; if none, return whole line."""
    i = line.find(':')
    return line[i+1:].strip() if i >= 0 else line.strip()

# === Serial Thread ===
def read_serial_data():
    while True:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if not line:
                    continue

                # Match by keyword; for adcs we expect the line to START with ':'
                handled = False
                for cmd_name, info in commands_info.items():
                    kw = info["keyword"]
                    if kw == ":":
                        if line.startswith(":"):
                            cleaned = value_after_first_colon(line)
                            evt_q.put(("field", (cmd_name, cleaned)))
                            handled = True
                            break
                    else:
                        if line.startswith(kw):
                            cleaned = value_after_first_colon(line)
                            evt_q.put(("field", (cmd_name, cleaned)))
                            handled = True
                            break

                if not handled:
                    # Unrecognized line; ignore or print for debug
                    # print(f"[UNPARSED] {line}")
                    pass
            else:
                time.sleep(0.01)
        except Exception as e:
            print("Serial read error:", e)
            time.sleep(0.1)

# === UI thread: process queue & update labels ===
def process_events():
    try:
        while True:
            evt, payload = evt_q.get_nowait()
            if evt == "field":
                cmd_name, text = payload
                if cmd_name in value_fields:
                    value_fields[cmd_name].config(text=text)
    except queue.Empty:
        pass

    root.after(30, process_events)  # ~33 FPS max

# === Launch threads and UI loop ===
threading.Thread(target=read_serial_data, daemon=True).start()
root.after(30, process_events)
root.mainloop()
