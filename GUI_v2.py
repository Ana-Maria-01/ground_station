import tkinter as tk
import serial
import threading
import re
import time
import queue
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# === Serial Setup ===
ser = serial.Serial('COM21', 115200, timeout=0.1)

# === Command Definitions ===
commands_info = {
    "batt":       {"label": "Battery (V)",      "keyword": "batt:"},
    "rssi":       {"label": "RSSI (dB)",        "keyword": "rssi:"},
    "uptime":     {"label": "Uptime (s)",       "keyword": "uptime:"},
    "power=5":    {"label": "Power (dB)",       "keyword": "power:"},
    "coord":      {"label": "GPS Coordinates",  "keyword": "coord:"},
    "cartesian":  {"label": "Cartesian Coord",  "keyword": "cart:"},
    "acc":        {"label": "Accel (mg)",       "keyword": "acc:"},
    "ang_vel":    {"label": "Angular Vel (dps)","keyword": "vel:"},
    "magn_field": {"label": "Mag Field (uT)",   "keyword": "field:"},
    "adcs":       {"label": "Roll/Pitch/Head",  "keyword": "roll:"},
    "temp_C":     {"label": "Temp (°C)",        "keyword": "temp_C:"},
    "temp_K":     {"label": "Temp (K)",         "keyword": "temp_K:"},
    "track":    {"label": "Position (X,Y,Z)", "keyword": "mg"},
    "calibrate":  {"label": "Accel Offset (mg)","keyword": "offset:"}
}

value_fields = {}
known_prefixes = [v["keyword"] for v in commands_info.values()]

# === Mission state ===
velocity = [0.0, 0.0, 0.0]   # m/s
position = [0.0, 0.0, 0.0]   # mm

positions_x = []
positions_y = []
positions_z = []
HISTORY_MAX = 5000  # keep last N points (tune to your liking)

# Thread-safe queue from serial thread -> UI thread
evt_q = queue.Queue()

# === GUI Setup ===
root = tk.Tk()
root.title("Telemetry Dashboard + 3D Mission Tracker")
root.geometry("2200x1500")

dashboard_frame = tk.Frame(root)
dashboard_frame.pack(padx=10, pady=10, fill='x')

def send_command(command):
    try:
        ser.write((command + "\n").encode())
        print(f"Sent: {command}")
    except Exception as e:
        print("Serial write error:", e)

for cmd, info in commands_info.items():
    row = tk.Frame(dashboard_frame)
    row.pack(fill='x', pady=3)

    btn = tk.Button(row, text=cmd, width=15, command=lambda c=cmd: send_command(c))
    btn.pack(side='left', padx=5)

    label = tk.Label(row, text=info["label"], width=20, anchor='w')
    label.pack(side='left')

    value_label = tk.Label(row, text="(no data)", width=45, anchor='w', bg='white',
                           relief='sunken', font=("Courier", 10))
    value_label.pack(side='left', padx=5, expand=True, fill='x')

    value_fields[cmd] = value_label

# === 3D Plot Setup ===
fig = plt.figure(figsize=(6, 5))
ax = fig.add_subplot(111, projection='3d')
ax.set_title("3D Position Tracker")
ax.set_xlabel("X (cm)")
ax.set_ylabel("Y (cm)")
ax.set_zlabel("Z (cm)")

plot_canvas = FigureCanvasTkAgg(fig, master=root)
plot_canvas.get_tk_widget().pack()

trajectory, = ax.plot([], [], [], 'o-', markersize=3)

def autoscale_3d():
    if not positions_x:
        return
    minx, maxx = min(positions_x), max(positions_x)
    miny, maxy = min(positions_y), max(positions_y)
    minz, maxz = min(positions_z), max(positions_z)

    # Handle flat ranges gracefully
    def pad_bounds(lo, hi):
        if lo == hi:
            lo -= 1.0
            hi += 1.0
        pad = 0.1 * (hi - lo)
        return lo - pad, hi + pad

    xlo, xhi = pad_bounds(minx, maxx)
    ylo, yhi = pad_bounds(miny, maxy)
    zlo, zhi = pad_bounds(minz, maxz)

    ax.set_xlim(xlo, xhi)
    ax.set_ylim(ylo, yhi)
    ax.set_zlim(zlo, zhi)

def update_3d_plot():
    trajectory.set_data(positions_x, positions_y)
    trajectory.set_3d_properties(positions_z)
    autoscale_3d()
    plot_canvas.draw_idle()  # non-blocking redraw

# === Parsing helpers ===
def extract_numerical_value(raw):
    cleaned = raw
    for prefix in known_prefixes:
        cleaned = cleaned.replace(prefix, '')
    return cleaned.strip()

mission_re = re.compile(r'(\d+):\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)')

def integrate_mission_sample(dt_ms, ax_g, ay_g, az_g):
    global velocity, position
    dt = dt_ms / 1000.0  #ms -> s

    # g → m/s²
    ax_ms2 = ax_g * 9.81
    ay_ms2 = ay_g * 9.81
    az_ms2 = az_g * 9.81

    velocity[0] += ax_ms2 * dt  # m/s
    velocity[1] += ay_ms2 * dt
    velocity[2] += az_ms2 * dt
    print("velocity: ")
    print(velocity[0], velocity[1], velocity[2])
    position[0] += velocity[0] * dt * 100.0  # m -> cm
    position[1] += velocity[1] * dt * 100.0
    position[2] += velocity[2] * dt * 100.0

    return tuple(int(x) for x in position)

# === Serial Thread ===
def read_serial_data():
    buf = b""
    while True:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    # parse and enqueue results for UI thread
                    handled = False
                    for cmd, info in commands_info.items():
                        if info["keyword"] in line:
                            if cmd == "track":
                                print(f"[RAW MISSION] {line}")
                                m = mission_re.search(line)
                                if m:
                                    dt_ms = int(m.group(1))
                                    ax_mg = int(m.group(2))
                                    ay_mg = int(m.group(3))
                                    az_mg = int(m.group(4))

                                    # Convert mg → g and round to 1 decimal
                                    ax_g = round(ax_mg / 1000.0, 1)
                                    ay_g = round(ay_mg / 1000.0, 1)
                                    az_g = round(az_mg / 1000.0, 1) - 1.0
                                    print(ax_g, ay_g, az_g)
                                    evt_q.put(("track", (dt_ms, ax_g, ay_g, az_g)))
                            else:
                                cleaned = extract_numerical_value(line)
                                evt_q.put(("field", (cmd, cleaned)))
                            handled = True
                            break
                    if not handled:
                        # Unknown line; ignore or log
                        pass
            else:
                time.sleep(0.01)
        except Exception as e:
            # Avoid crashing the thread
            print("Serial read error:", e)
            time.sleep(0.1)

# === UI thread: process queue & update plot/labels ===
def process_events():
    updated_plot = False
    try:
        while True:
            evt, payload = evt_q.get_nowait()
            if evt == "field":
                cmd, text = payload
                if cmd in value_fields:
                    value_fields[cmd].config(text=text)
            elif evt == "track":
                dt_ms, ax_mg, ay_mg, az_mg = payload
                x_mm, y_mm, z_mm = integrate_mission_sample(dt_ms, ax_mg, ay_mg, az_mg)

                # Convert to centimeters for UI and plotting
                x_cm = position[0] / 10.0
                y_cm = position[1] / 10.0
                z_cm = position[2] / 10.0

                # Update label (in cm)
                value_fields["track"].config(text=f"{x_cm:.1f}, {y_cm:.1f}, {z_cm:.1f} cm")

                # Append cm values for plotting/history
                positions_x.append(x_cm)
                positions_y.append(y_cm)
                positions_z.append(z_cm)

                if len(positions_x) > HISTORY_MAX:
                    del positions_x[:-HISTORY_MAX]
                    del positions_y[:-HISTORY_MAX]
                    del positions_z[:-HISTORY_MAX]

                updated_plot = True
    except queue.Empty:
        pass

    if updated_plot:
        update_3d_plot()

    # schedule next poll
    root.after(30, process_events)  # ~33 FPS max

# === Launch threads and UI loop ===
threading.Thread(target=read_serial_data, daemon=True).start()
root.after(30, process_events)
root.mainloop()
