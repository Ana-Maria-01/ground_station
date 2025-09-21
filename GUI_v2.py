import tkinter as tk
import serial
import threading
import time
import queue
import re
import math
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# === Serial Setup ===
ser = serial.Serial('COM21', 115200, timeout=0.1)

# === Command Definitions ===
# Numeric IDs are sent; incoming lines start with "<id>:" except ADCS (id 10) which starts with ":".
commands_info = {
    "BATTERY":   {"id": 1,  "label": "Battery [V]",             "keyword": "1:"},
    "RSSI":      {"id": 2,  "label": "RSSI [dB]",               "keyword": "2:"},
    "UPTIME":    {"id": 3,  "label": "Uptime [s]",              "keyword": "3:"},
    "POWER":     {"id": 4,  "label": "Power [dB]",              "keyword": "4:"},
    "COORDS":    {"id": 5,  "label": "GPS Coordinates",         "keyword": "5:"},
    "CARTESIAN": {"id": 6,  "label": "Cartesian Coordinates",   "keyword": "6:"},
    "ACC":       {"id": 7,  "label": "Acceleration [mg]",       "keyword": "7:"},
    "GYRO":      {"id": 8,  "label": "Angular Velocity [dps]",  "keyword": "8:"},
    "MAGNETIC":  {"id": 9,  "label": "Magnetic Field [uT]",     "keyword": "9:"},
    "ADCS":      {"id": 10, "label": "Roll/Pitch/Yaw [deg]",    "keyword": ":"},   # special
    "TEMP":      {"id": 11, "label": "Temperature [°C]",        "keyword": "11:"},
    "TEMP_K":    {"id": 12, "label": "Temperature [K]",         "keyword": "12:"},
}

value_fields = {}
indicator_labels = {}     # cmd_name -> dot label

# --- Single-select indicator state (send-only) ---
active_cmd = None
DOT_ACTIVE = "●"
DOT_IDLE   = "○"
COLOR_ACTIVE = "#22c55e"  # green
COLOR_IDLE   = "#9aa0a6"  # gray

def set_active(cmd_name: str | None):
    """Make exactly one command active (green). None -> all gray."""
    global active_cmd
    active_cmd = cmd_name
    for name, lbl in indicator_labels.items():
        if name == active_cmd:
            lbl.config(text=DOT_ACTIVE, fg=COLOR_ACTIVE)
        else:
            lbl.config(text=DOT_IDLE, fg=COLOR_IDLE)

evt_q = queue.Queue()

# ---------------- Cube math ----------------
def rot_x(r_deg):
    th = math.radians(-r_deg)
    c, s = math.cos(th), math.sin(th)
    return np.array([[1, 0, 0],[0,  c,  s],[0, -s,  c]], dtype=float)

def rot_y(p_deg):
    th = math.radians(-p_deg)
    c, s = math.cos(th), math.sin(th)
    return np.array([[ c, 0, -s],[ 0, 1,  0],[ s, 0,  c]], dtype=float)

def rot_z(y_deg):
    th = math.radians(y_deg)
    c, s = math.cos(th), math.sin(th)
    return np.array([[c, -s, 0],[s,  c, 0],[0,  0, 1]], dtype=float)

def apply_rotation(pts, r, p, y):
    R = rot_z(y) @ rot_y(p) @ rot_x(r)
    return (R @ pts.T).T

def make_cube(edge=1.0):
    a = edge / 2.0
    V = np.array([[-a,-a,-a],[ a,-a,-a],[ a, a,-a],[-a, a,-a],
                  [-a,-a, a],[ a,-a, a],[ a, a, a],[-a, a, a]], dtype=float)
    faces = [[0,1,2,3],[4,5,6,7],[0,1,5,4],[2,3,7,6],[1,2,6,5],[0,3,7,4]]
    return V, faces

# ---------------- Tk GUI ----------------
root = tk.Tk()
root.title("Telemetry Dashboard + ADCS Cube")
root.geometry("1600x900")

# Left: dashboard
left_frame = tk.Frame(root)
left_frame.pack(side='left', padx=10, pady=10, fill='y')

dashboard_frame = tk.Frame(left_frame)
dashboard_frame.pack(padx=10, pady=10, fill='x')

def send_numeric(cmd_name: str, code: int):
    try:
        ser.write((str(code) + "\n").encode())
        print(f"Sent code: {code} ({cmd_name})")
        set_active(cmd_name)  # highlight ONLY on send
    except Exception as e:
        print("Serial write error:", e)

# Build rows of buttons + status dot + label + value
for cmd_name, info in commands_info.items():
    row = tk.Frame(dashboard_frame)
    row.pack(fill='x', pady=3)

    btn = tk.Button(row, text=cmd_name, width=15,
                    command=lambda n=cmd_name, c=info["id"]: send_numeric(n, c))
    btn.pack(side='left', padx=5)

    dot = tk.Label(row, text=DOT_IDLE, fg=COLOR_IDLE, font=("Arial", 12), width=2, anchor='e')
    dot.pack(side='left', padx=(0, 6))
    indicator_labels[cmd_name] = dot

    label = tk.Label(row, text=info["label"], width=24, anchor='w')
    label.pack(side='left')

    value_label = tk.Label(
        row, text="(no data)", width=48, anchor='w',
        bg='white', relief='sunken', font=("Courier", 10)
    )
    value_label.pack(side='left', padx=5, expand=True, fill='x')

    value_fields[cmd_name] = value_label

# Right: 3D cube
right_frame = tk.Frame(root)
right_frame.pack(side='left', padx=10, pady=10, fill='both', expand=True)

fig = plt.Figure(figsize=(7,6))
ax = fig.add_subplot(111, projection='3d')
ax.set_box_aspect([1,1,1])

edge = 1.0
lim = 0.8 * edge
ax.set_xlim3d(-lim, lim)
ax.set_ylim3d(-lim, lim)
ax.set_zlim3d(-lim, lim)
ax.set_xlabel("X")
ax.set_ylabel("Y")
ax.set_zlabel("Z")

axes_len = edge * 0.8
ax.quiver(0,0,0, axes_len,0,0)
ax.quiver(0,0,0, 0,axes_len,0)
ax.quiver(0,0,0, 0,0,axes_len)

V0, faces = make_cube(edge)
poly3d = Poly3DCollection([V0[f] for f in faces], alpha=0.35, edgecolor='k')
ax.add_collection3d(poly3d)

front_idx = [1,2,6,5]
front_marker = Poly3DCollection([V0[front_idx]], alpha=0.4)
ax.add_collection3d(front_marker)

canvas = FigureCanvasTkAgg(fig, master=right_frame)
canvas.get_tk_widget().pack(fill='both', expand=True)

# latest RPY from ADCS
latest_rpy = [0.0, 0.0, 0.0]

def update_cube():
    r, p, y = latest_rpy
    V_rot = apply_rotation(V0, r, p, y)
    poly3d.set_verts([V_rot[f] for f in faces])
    front_marker.set_verts([V_rot[front_idx]])
    canvas.draw_idle()

# ---------------- Parsing helpers ----------------
_re_csv3 = re.compile(r'^\s*([-+]?\d+(?:\.\d+)?)\s*,\s*([-+]?\d+(?:\.\d+)?)\s*,\s*([-+]?\d+(?:\.\d+)?)\s*$')

def value_after_first_colon(line: str) -> str:
    i = line.find(':')
    return line[i+1:].strip() if i >= 0 else line.strip()

def parse_rpy(text: str):
    s = text.strip()
    if not s:
        return None
    m = _re_csv3.match(s)
    if m:
        return float(m.group(1)), float(m.group(2)), float(m.group(3))
    nums = re.findall(r'[-+]?\d+(?:\.\d+)?', s)
    if len(nums) >= 3:
        return float(nums[0]), float(nums[1]), float(nums[2])
    return None

# ---------------- Serial Thread ----------------
def read_serial_data():
    while True:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if not line:
                    continue

                handled = False
                for cmd_name, info in commands_info.items():
                    kw = info["keyword"]
                    if kw == ":":
                        if line.startswith(":"):
                            payload = value_after_first_colon(line)
                            rpy = parse_rpy(payload)
                            if rpy:
                                evt_q.put(("field", (cmd_name, payload)))
                                evt_q.put(("rpy", rpy))
                            else:
                                evt_q.put(("field", (cmd_name, payload or "(parse error)")))
                            handled = True
                            break
                    else:
                        if line.startswith(kw):
                            cleaned = value_after_first_colon(line)
                            evt_q.put(("field", (cmd_name, cleaned)))
                            handled = True
                            break

                if not handled:
                    pass
            else:
                time.sleep(0.01)
        except Exception as e:
            print("Serial read error:", e)
            time.sleep(0.1)

# ---------------- UI event pump ----------------
def process_events():
    global latest_rpy
    cube_needs_update = False

    try:
        while True:
            evt, payload = evt_q.get_nowait()
            if evt == "field":
                cmd_name, text = payload
                if cmd_name in value_fields:
                    value_fields[cmd_name].config(text=text)
            elif evt == "rpy":
                r, p, y = payload
                latest_rpy = [r, p, y]
                cube_needs_update = True
    except queue.Empty:
        pass

    if cube_needs_update:
        update_cube()

    root.after(20, process_events)  # ~50 FPS UI pump

# === Launch threads and UI loop ===
threading.Thread(target=read_serial_data, daemon=True).start()
root.after(30, process_events)
root.mainloop()
