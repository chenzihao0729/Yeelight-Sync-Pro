# -*- coding: utf-8 -*-
import json
import os
import socket
import threading
import time
import tkinter as tk
import colorsys
import ctypes
from tkinter import ttk

try:
    from PIL import ImageGrab, Image
except Exception:
    ImageGrab = None
    Image = None

try:
    import pystray
except Exception:
    pystray = None


APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
ICON_PATH = os.path.join(APP_DIR, "icon.ico")

DEFAULT_CONFIG = {
    "Host": "",
    "Port": "55443",
    "CaptureModeIndex": 0,
    "SampleGridIndex": 2,
    "SampleGrid": "64 x 36",
    "RegionPercent": 45,
    "IntervalMs": 300,
    "FadeMs": 200,
    "BrightnessCap": 85,
    "SaturationBoost": 20,
    "SmoothingPercent": 35,
    "Threshold": 10,
    "StartWithWindows": False,
}

LIGHT_STATE_PROPS = ["power", "bright", "color_mode", "ct", "rgb", "hue", "sat", "name", "fw_ver"]


def clamp(value, low, high):
    return max(low, min(high, value))


def rgb_to_int(r, g, b):
    return max(1, (int(r) << 16) | (int(g) << 8) | int(b))


def hsv_signature(hue, saturation, brightness):
    return (int(hue) << 16) | (int(saturation) << 8) | int(brightness)


def color_distance(a, b):
    if a is None or b is None:
        return 999
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def load_config():
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                config.update(loaded)
        except Exception:
            pass
    return config


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def screen_size():
    if ImageGrab is None:
        raise RuntimeError("当前 Python 缺少 Pillow，无法捕获屏幕。请运行：pip install pillow")
    image = ImageGrab.grab()
    size = image.size
    image.close()
    return size


def capture_rect(mode_index, region_percent):
    width, height = screen_size()
    if int(mode_index) == 0:
        return 0, 0, width, height

    scale = clamp(int(region_percent) / 100.0, 0.05, 1.0)
    rect_w = max(10, int(width * scale))
    rect_h = max(10, int(height * scale))
    return int((width - rect_w) / 2), int((height - rect_h) / 2), rect_w, rect_h


def average_screen_color(config, last_color):
    x, y, width, height = capture_rect(config["CaptureModeIndex"], config["RegionPercent"])
    image = ImageGrab.grab(bbox=(x, y, x + width, y + height))
    image = image.resize((64, 36)).convert("RGB")
    pixel_source = getattr(image, "get_flattened_data", image.getdata)
    pixels = list(pixel_source())
    image.close()

    count = len(pixels)
    r = sum(pixel[0] for pixel in pixels) / count
    g = sum(pixel[1] for pixel in pixels) / count
    b = sum(pixel[2] for pixel in pixels) / count

    hue_float, saturation_float, _value_float = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    hue = int(round(hue_float * 359))
    source_saturation = int(round(saturation_float * 100))
    saturation = source_saturation

    # Perceived image brightness drives the lamp brightness; the slider is a cap, not a fixed brightness.
    luminance = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
    is_dark = luminance < 4
    brightness = int(round((luminance / 255.0) * int(config["BrightnessCap"])))
    brightness = int(clamp(brightness, 1, 100))

    is_neutral = source_saturation < 8
    if is_neutral:
        saturation = 0
    else:
        saturation_boost = 1.0 + (int(config["SaturationBoost"]) / 100.0)
        saturation = int(clamp(round(saturation * saturation_boost), 1, 100))

    if not is_dark and saturation >= 25:
        brightness = max(brightness, 8)

    smoothing = int(config["SmoothingPercent"])
    if last_color is not None and smoothing > 0:
        alpha = clamp(smoothing / 100.0, 0.0, 0.95)
        if not is_neutral and last_color["saturation"] > 0:
            previous_hue = last_color["hue"]
            hue_delta = ((hue - previous_hue + 180) % 360) - 180
            hue = int(round((previous_hue + hue_delta * (1.0 - alpha)) % 360))
        saturation = int(round(last_color["saturation"] * alpha + saturation * (1.0 - alpha)))
        brightness = int(round(last_color["brightness"] * alpha + brightness * (1.0 - alpha)))
        if is_neutral:
            saturation = 0

    hue = int(clamp(hue, 1, 359))
    saturation = int(clamp(saturation, 0, 100))
    brightness = int(clamp(brightness, 1, 100))
    if saturation <= 3:
        gray = int(clamp(round((brightness / 100.0) * 255), 0, 255))
        rgb = (gray, gray, gray)
        hue = 1
        saturation = 0
    else:
        display_rgb = colorsys.hsv_to_rgb(hue / 359.0, saturation / 100.0, brightness / 100.0)
        rgb = tuple(int(clamp(round(channel * 255), 0, 255)) for channel in display_rgb)

    return {
        "rgb": rgb,
        "hue": hue,
        "saturation": saturation,
        "brightness": brightness,
        "is_dark": is_dark,
        "is_neutral": saturation <= 3,
    }


class YeelightClient:
    def __init__(self):
        self.host = ""
        self.port = 55443
        self.command_sock = None
        self.listener = None
        self.command_id = 1
        self.lock = threading.Lock()

    def configure(self, host, port):
        self.host = str(host).strip()
        self.port = int(port)

    def close(self):
        with self.lock:
            for sock in (self.command_sock,):
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass
            if self.listener:
                try:
                    self.listener.close()
                except Exception:
                    pass
            self.command_sock = None
            self.listener = None

    def command_socket(self):
        if self.command_sock is None:
            sock = socket.create_connection((self.host, self.port), timeout=1.5)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.command_sock = sock
        return self.command_sock

    def send(self, method, params):
        payload = json.dumps(
            {"id": self.command_id, "method": method, "params": params},
            separators=(",", ":"),
        ).encode("utf-8") + b"\r\n"
        self.command_id += 1

        with self.lock:
            sock = self.command_socket()
            try:
                sock.sendall(payload)
            except OSError:
                self.command_sock = None
                sock = self.command_socket()
                sock.sendall(payload)

    def query_properties(self, properties):
        with self.lock:
            command_id = self.command_id
            self.command_id += 1

        payload = json.dumps(
            {"id": command_id, "method": "get_prop", "params": list(properties)},
            separators=(",", ":"),
        ).encode("utf-8") + b"\r\n"

        with socket.create_connection((self.host, self.port), timeout=2.0) as sock:
            sock.settimeout(2.0)
            sock.sendall(payload)
            chunks = []
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
                if b"\n" in chunk:
                    break

        response = b"".join(chunks).decode("utf-8", "replace").strip()
        if not response:
            raise RuntimeError("灯带没有返回状态。")

        data = json.loads(response.splitlines()[0])
        if "error" in data:
            message = data["error"].get("message", "未知错误")
            raise RuntimeError(message)
        return data.get("result", [])


class YeelightSyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Yeelight 屏幕同步")
        self.window_width = 800
        self.window_height = 760
        self.root.geometry(f"{self.window_width}x{self.window_height}")
        self.root.resizable(False, False)

        self.client = YeelightClient()
        self.config_lock = threading.Lock()
        self.running = False
        self.stop_event = threading.Event()
        self.worker = None
        self.last_color = None
        self.last_rgb = -1
        self.loading = True
        self.tray_icon = None
        self.is_quitting = False
        self.state_refreshing = False
        self.pre_sync_state = None
        self.restore_running = False

        self.vars = {}
        self.value_labels = {}
        self.scale_ranges = {}
        self.scale_last_values = {}
        self.setup_icons_and_tray()
        self.build_ui()
        self.load_values(load_config())
        self.loading = False
        self.save_current_config()
        self.center_window()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(300, self.refresh_light_state)
        self.root.after(5000, self.auto_refresh_light_state)

    def setup_icons_and_tray(self):
        if os.path.exists(ICON_PATH):
            try:
                self.root.iconbitmap(ICON_PATH)
            except tk.TclError:
                pass

        if pystray is None or Image is None or not os.path.exists(ICON_PATH):
            return

        try:
            icon_image = Image.open(ICON_PATH)
            menu = pystray.Menu(
                pystray.MenuItem("显示窗口", self.show_from_tray, default=True),
                pystray.MenuItem("退出", self.exit_from_tray),
            )
            self.tray_icon = pystray.Icon("YeelightScreenSync", icon_image, "Yeelight 屏幕同步", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception:
            self.tray_icon = None

    def show_from_tray(self, _icon=None, _item=None):
        self.root.after(0, self.show_window)

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def exit_from_tray(self, _icon=None, _item=None):
        self.root.after(0, self.exit_app)

    def center_window(self):
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = max(0, int((screen_width - self.window_width) / 2))
        y = max(0, int((screen_height - self.window_height) / 2))
        self.root.geometry(f"{self.window_width}x{self.window_height}+{x}+{y}")

    def make_glass_panel(self, title, x, y, width, height):
        panel = tk.Frame(self.root, bg="#2b2b2e", highlightbackground="#4a4a50", highlightthickness=1)
        panel.place(x=x, y=y, width=width, height=height)
        tk.Label(
            panel,
            text=title,
            bg="#2b2b2e",
            fg="#dce7f7",
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).place(x=18, y=10, width=180, height=22)
        return panel

    def build_ui(self):
        self.root.configure(bg="#1d1d20")
        bg_canvas = tk.Canvas(self.root, bg="#1d1d20", highlightthickness=0, bd=0)
        bg_canvas.place(x=0, y=0, width=self.window_width, height=self.window_height)
        bg_canvas.create_oval(-100, -120, 280, 220, fill="#202a38", outline="")
        bg_canvas.create_oval(500, -100, 900, 280, fill="#251f35", outline="")
        bg_canvas.create_oval(420, 520, 900, 840, fill="#182b2f", outline="")
        bg_canvas.tk.call("lower", bg_canvas._w)
        tk.Label(self.root, text="Yeelight Sync Pro", bg="#1d1d20", fg="#ffffff", font=("Microsoft YaHei UI", 24, "bold"), anchor="w").place(x=28, y=34, width=420, height=42)
        tk.Label(self.root, text="Yeelight 环境光同步系统", bg="#1d1d20", fg="#9db7d9", font=("Microsoft YaHei UI", 10), anchor="w").place(x=30, y=78, width=420, height=24)
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Glass.TButton", background="#343438", foreground="#f4f7fb", bordercolor="#56565c", focusthickness=0, padding=(10, 6))
        style.map("Glass.TButton", background=[("active", "#3d3d42"), ("pressed", "#29292d")])
        style.configure("Accent.TButton", background="#168bff", foreground="#ffffff", bordercolor="#168bff", focusthickness=0, padding=(10, 6))
        style.map("Accent.TButton", background=[("active", "#2998ff"), ("pressed", "#0876dd")])
        style.configure("Glass.TEntry", fieldbackground="#1b1b1e", foreground="#ffffff", bordercolor="#57575f", lightcolor="#57575f", darkcolor="#57575f", padding=4)
        style.configure("Glass.TCombobox", fieldbackground="#1b1b1e", foreground="#ffffff", background="#2b2b2e", bordercolor="#57575f", arrowsize=14, padding=4)

        self.device_group = self.make_glass_panel("设备", 16, 116, 768, 145)

        tk.Label(self.device_group, text="设备 IP", bg="#2b2b2e", fg="#c5d0df", anchor="w").place(x=18, y=45, width=80)
        self.vars["Host"] = tk.StringVar()
        ttk.Entry(self.device_group, textvariable=self.vars["Host"], style="Glass.TEntry").place(x=118, y=41, width=240, height=30)

        self.vars["Port"] = tk.StringVar()

        ttk.Button(self.device_group, text="开灯", command=lambda: self.power("on"), style="Glass.TButton").place(x=388, y=40, width=86, height=32)
        ttk.Button(self.device_group, text="关灯", command=lambda: self.power("off"), style="Glass.TButton").place(x=486, y=40, width=86, height=32)
        self.refresh_button = ttk.Button(self.device_group, text="刷新状态", command=self.refresh_light_state, style="Glass.TButton")
        self.refresh_button.place(x=584, y=40, width=100, height=32)

        tk.Label(self.device_group, text="当前状态", bg="#2b2b2e", fg="#c5d0df", anchor="w").place(x=18, y=95, width=80)
        self.light_state_var = tk.StringVar(value="未获取")
        tk.Label(self.device_group, textvariable=self.light_state_var, bg="#2b2b2e", fg="#f4f7fb", anchor="w").place(x=118, y=95, width=500)

        self.start_button = ttk.Button(self.device_group, text="开始同步", command=self.toggle_sync, style="Accent.TButton")
        self.start_button.place(x=632, y=88, width=110, height=36)

        self.status_var = tk.StringVar(value="")

        self.sync_group = self.make_glass_panel("同步", 16, 276, 768, 330)

        tk.Label(self.sync_group, text="取色范围", bg="#2b2b2e", fg="#c5d0df", anchor="w").place(x=18, y=50, width=80)
        self.vars["CaptureModeIndex"] = tk.IntVar()
        self.mode_box = ttk.Combobox(self.sync_group, state="readonly", values=["全屏", "中心区域"], style="Glass.TCombobox")
        self.mode_box.place(x=118, y=46, width=170, height=30)
        self.mode_box.bind("<<ComboboxSelected>>", self.on_mode_changed)

        self.add_scale("RegionPercent", "采样区域大小", 390, 44, 5, 100, "%", 470, 180, 665)
        self.add_scale("IntervalMs", "同步间隔", 18, 105, 100, 1000, " ms", 118, 210, 345)
        self.add_scale("FadeMs", "渐变", 390, 105, 50, 1000, " ms", 470, 180, 665)
        self.add_scale("BrightnessCap", "亮度上限", 18, 166, 10, 100, "%", 118, 210, 345)
        self.add_scale("SaturationBoost", "饱和度上限", 390, 166, 0, 100, "%", 470, 180, 665)
        self.add_scale("SmoothingPercent", "平滑", 18, 227, 0, 90, "%", 118, 210, 345)
        self.add_scale("Threshold", "变化阈值", 390, 227, 0, 80, "", 470, 180, 665)

        self.preview_group = self.make_glass_panel("实时颜色", 16, 626, 768, 105)

        self.preview_card = tk.Frame(self.preview_group, bg="#111113", highlightbackground="#34343a", highlightthickness=1)
        self.preview_card.place(x=18, y=38, width=732, height=50)

        self.swatch = tk.Canvas(self.preview_card, width=104, height=32, highlightthickness=1, highlightbackground="#4d4d55", bg="#111113")
        self.swatch.place(x=16, y=9)
        self.swatch_rect = self.swatch.create_rectangle(0, 0, 104, 44, fill="#000000", outline="")

        tk.Label(self.preview_card, text="当前颜色", bg="#111113", fg="#9db7d9", anchor="w").place(x=140, y=5, width=80, height=16)

        self.color_var = tk.StringVar(value="RGB: 0, 0, 0")
        tk.Label(self.preview_card, textvariable=self.color_var, bg="#111113", fg="#ffffff", anchor="w").place(x=140, y=24, width=390, height=20)

        tk.Label(self.preview_card, text="运行状态", bg="#111113", fg="#9db7d9", anchor="w").place(x=550, y=5, width=80, height=16)
        self.run_var = tk.StringVar(value="已停止")
        tk.Label(self.preview_card, textvariable=self.run_var, bg="#111113", fg="#ffffff", anchor="w").place(x=550, y=24, width=160, height=20)

        self.vars["Host"].trace_add("write", lambda *_: self.save_current_config())

    def add_scale(self, key, text, label_x, y, low, high, suffix, scale_x, scale_width, value_x, prefix=""):
        tk.Label(self.sync_group, text=text, bg="#2b2b2e", fg="#c5d0df", anchor="w").place(x=label_x, y=y + 8, width=80)
        var = tk.IntVar()
        self.vars[key] = var
        self.scale_ranges[key] = (low, high)
        scale = tk.Scale(
            self.sync_group,
            from_=low,
            to=high,
            orient="horizontal",
            variable=var,
            resolution=10,
            showvalue=False,
            highlightthickness=0,
            bd=0,
            bg="#2b2b2e",
            fg="#ffffff",
            troughcolor="#17171a",
            activebackground="#168bff",
            command=lambda value, k=key: self.on_scale_changed(k, value),
        )
        scale.place(x=scale_x, y=y, width=scale_width, height=42)
        label = tk.Label(self.sync_group, text="", bg="#2b2b2e", fg="#168bff", anchor="w", font=("Microsoft YaHei UI", 9, "bold"))
        label.place(x=value_x, y=y + 8, width=76)
        self.value_labels[key] = (label, prefix, suffix)

    def snap_scale_value(self, key, value):
        low, high = self.scale_ranges[key]
        snapped = int(round(float(value) / 10.0) * 10)
        return int(clamp(snapped, low, high))

    def load_values(self, config):
        self.vars["Host"].set(str(config.get("Host", "")))
        self.vars["Port"].set(str(config.get("Port", "55443")))
        mode_index = clamp(int(config.get("CaptureModeIndex", 0)), 0, 1)
        self.vars["CaptureModeIndex"].set(mode_index)
        self.mode_box.current(mode_index)
        for key in (
            "RegionPercent",
            "IntervalMs",
            "FadeMs",
            "BrightnessCap",
            "SaturationBoost",
            "SmoothingPercent",
            "Threshold",
        ):
            self.vars[key].set(self.snap_scale_value(key, int(config.get(key, DEFAULT_CONFIG[key]))))
            self.scale_last_values[key] = int(self.vars[key].get())
        self.update_value_labels()

    def on_mode_changed(self, _event=None):
        index = self.mode_box.current()
        self.vars["CaptureModeIndex"].set(max(0, index))
        self.save_current_config()

    def on_scale_changed(self, key, value=None):
        snapped = self.snap_scale_value(key, self.vars[key].get() if value is None else value)
        if int(self.vars[key].get()) != snapped:
            self.vars[key].set(snapped)
        if self.scale_last_values.get(key) == snapped:
            return
        self.scale_last_values[key] = snapped
        self.update_value_labels()
        self.save_current_config()

    def update_value_labels(self):
        for key, (label, prefix, suffix) in self.value_labels.items():
            label.configure(text=f"{prefix}{int(self.vars[key].get())}{suffix}")

    def current_config(self):
        config = {
            "Host": self.vars["Host"].get().strip(),
            "Port": self.vars["Port"].get().strip() or "55443",
            "CaptureModeIndex": int(self.vars["CaptureModeIndex"].get()),
        }
        for key in (
            "RegionPercent",
            "IntervalMs",
            "FadeMs",
            "BrightnessCap",
            "SaturationBoost",
            "SmoothingPercent",
            "Threshold",
        ):
            config[key] = int(self.vars[key].get())
        return config

    def save_current_config(self):
        if self.loading:
            return
        self.update_value_labels()
        config = self.current_config()
        with self.config_lock:
            self.config = config
        try:
            save_config(config)
        except Exception:
            pass

    def config_snapshot(self):
        with self.config_lock:
            return dict(getattr(self, "config", self.current_config()))

    def set_status(self, text):
        self.root.after(0, lambda: self.status_var.set(text))

    def set_run(self, text):
        self.root.after(0, lambda: self.run_var.set(text))

    def set_color(self, color_state):
        def update():
            if isinstance(color_state, dict):
                color = color_state["rgb"]
                detail = f"RGB: {color[0]}, {color[1]}, {color[2]} | 亮度: {color_state['brightness']}% 饱和: {color_state['saturation']}%"
            else:
                color = color_state
                detail = f"RGB: {color[0]}, {color[1]}, {color[2]}"
            hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            self.swatch.itemconfig(self.swatch_rect, fill=hex_color)
            self.color_var.set(detail)
        self.root.after(0, update)

    def configure_client(self):
        config = self.config_snapshot()
        if not config["Host"]:
            raise RuntimeError("请先输入设备 IP。")
        self.client.configure(config["Host"], config["Port"])
        return config

    def refresh_light_state(self, manual=True):
        if self.state_refreshing:
            return
        self.save_current_config()
        try:
            self.configure_client()
        except Exception:
            if manual:
                self.light_state_var.set("请输入设备 IP 后刷新")
            return

        self.state_refreshing = True
        self.refresh_button.configure(state="disabled")
        self.light_state_var.set("正在获取...")

        def worker():
            try:
                props = LIGHT_STATE_PROPS
                result = self.client.query_properties(props)
                state_text = self.format_light_state(dict(zip(props, result)))
                self.root.after(0, lambda: self.finish_light_state_refresh(state_text))
            except Exception as exc:
                self.root.after(0, lambda e=exc: self.finish_light_state_refresh(f"获取失败：{e}"))

        threading.Thread(target=worker, daemon=True).start()

    def auto_refresh_light_state(self):
        if not self.is_quitting:
            self.refresh_light_state(manual=False)
            self.root.after(5000, self.auto_refresh_light_state)

    def finish_light_state_refresh(self, text):
        self.light_state_var.set(text)
        self.state_refreshing = False
        self.refresh_button.configure(state="normal")

    def format_light_state(self, state):
        power = "开" if state.get("power") == "on" else "关"
        bright = state.get("bright") or "-"
        color_mode = state.get("color_mode") or "-"
        mode_names = {
            "1": "RGB",
            "2": "色温",
            "3": "HSV",
        }
        mode_text = mode_names.get(str(color_mode), str(color_mode))

        if str(color_mode) == "2":
            color_text = f"色温 {state.get('ct') or '-'}K"
        elif str(color_mode) == "3":
            color_text = f"色相 {state.get('hue') or '-'} / 饱和 {state.get('sat') or '-'}%"
        else:
            rgb_value = state.get("rgb") or "0"
            try:
                rgb_int = int(rgb_value)
                r = (rgb_int >> 16) & 255
                g = (rgb_int >> 8) & 255
                b = rgb_int & 255
                color_text = f"RGB {r},{g},{b}"
            except ValueError:
                color_text = f"RGB {rgb_value}"

        name = state.get("name") or ""
        name_text = f" | 名称: {name}" if name else ""
        return f"电源: {power} | 亮度: {bright}% | 模式: {mode_text} | {color_text}{name_text}"

    def capture_light_state_snapshot(self):
        props = LIGHT_STATE_PROPS
        result = self.client.query_properties(props)
        return dict(zip(props, result))

    def restore_light_state(self, state):
        if not state:
            return

        duration = 300
        power = state.get("power") or "on"
        bright = state.get("bright")
        color_mode = str(state.get("color_mode") or "1")

        if color_mode == "2" and state.get("ct"):
            self.client.send("set_ct_abx", [int(state["ct"]), "smooth", duration])
        elif color_mode == "3" and state.get("hue") and state.get("sat"):
            self.client.send("set_hsv", [int(state["hue"]), int(state["sat"]), "smooth", duration])
        elif state.get("rgb"):
            self.client.send("set_rgb", [max(1, int(state["rgb"])), "smooth", duration])

        if bright:
            self.client.send("set_bright", [int(bright), "smooth", duration])

        self.client.send("set_power", [power, "smooth", duration])

    def power(self, state):
        self.save_current_config()

        def worker():
            try:
                self.configure_client()
                self.client.send("set_power", [state, "smooth", 300])
                self.set_status("已发送开灯命令。" if state == "on" else "已发送关灯命令。")
                time.sleep(0.2)
                self.root.after(0, self.refresh_light_state)
            except Exception as exc:
                self.client.close()
                prefix = "开灯失败：" if state == "on" else "关灯失败："
                self.set_status(prefix + str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def toggle_sync(self):
        if self.running:
            self.stop_sync()
        else:
            self.start_sync()

    def start_sync(self):
        self.save_current_config()
        try:
            self.configure_client()
        except Exception as exc:
            self.status_var.set(str(exc))
            return

        self.refresh_light_state()
        self.running = True
        self.stop_event.clear()
        self.last_color = None
        self.last_rgb = -1
        self.pre_sync_state = None
        self.start_button.configure(text="停止同步", state="disabled")
        self.run_var.set("正在启动")
        self.status_var.set("正在启动同步...")

        self.worker = threading.Thread(target=self.sync_worker, daemon=True)
        self.worker.start()

    def stop_sync(self):
        self.stop_event.set()
        self.running = False
        self.start_button.configure(text="开始同步", state="disabled")
        self.run_var.set("正在恢复")
        self.status_var.set("正在恢复同步前灯带状态...")
        threading.Thread(target=self.restore_after_stop, daemon=True).start()

    def restore_after_stop(self):
        if self.restore_running:
            return
        self.restore_running = True
        try:
            if self.worker and self.worker.is_alive():
                self.worker.join(timeout=2.0)
            self.client.close()
            config = self.config_snapshot()
            self.client.configure(config["Host"], config["Port"])
            if self.pre_sync_state:
                self.restore_light_state(self.pre_sync_state)
                self.root.after(0, lambda: self.status_var.set("同步已停止，已恢复同步前状态。"))
            else:
                self.root.after(0, lambda: self.status_var.set("同步已停止。未找到同步前状态快照。"))
        except Exception as exc:
            self.root.after(0, lambda e=exc: self.status_var.set(f"同步已停止，但恢复状态失败：{e}"))
        finally:
            self.client.close()
            self.pre_sync_state = None
            self.restore_running = False
            self.root.after(0, lambda: self.start_button.configure(text="开始同步", state="normal"))
            self.root.after(0, lambda: self.run_var.set("已停止"))
            self.root.after(0, self.refresh_light_state)

    def finish_start(self, status):
        self.start_button.configure(text="停止同步", state="normal")
        self.status_var.set(status)

    def effective_interval(self, config):
        return max(int(config["IntervalMs"]), 1000)

    def sync_worker(self):
        try:
            config = self.config_snapshot()
            self.client.close()
            self.client.configure(config["Host"], config["Port"])
            self.pre_sync_state = self.capture_light_state_snapshot()
            self.set_status("已保存同步前灯带状态，正在开始同步...")
            self.client.send("set_power", ["on", "smooth", 300])
            self.root.after(0, lambda: self.finish_start(f"同步运行中，间隔 {self.effective_interval(config)} ms。"))

            while not self.stop_event.is_set():
                config = self.config_snapshot()
                color_state = average_screen_color(config, self.last_color)
                color = color_state["rgb"]
                previous_rgb = self.last_color["rgb"] if self.last_color is not None else None
                signature = hsv_signature(color_state["hue"], color_state["saturation"], color_state["brightness"])
                distance = color_distance(previous_rgb, color)
                self.set_color(color_state)

                if distance >= int(config["Threshold"]) and signature != self.last_rgb:
                    duration = int(config["FadeMs"])
                    if color_state.get("is_dark"):
                        self.client.send("set_rgb", [1, "smooth", duration])
                    else:
                        self.client.send(
                            "set_hsv",
                            [color_state["hue"], color_state["saturation"], "smooth", duration],
                        )
                    self.client.send(
                        "set_bright",
                        [color_state["brightness"], "smooth", duration],
                    )
                    self.last_rgb = signature
                    self.set_run("上次发送：" + time.strftime("%H:%M:%S"))

                self.last_color = color_state
                time.sleep(self.effective_interval(config) / 1000.0)
        except Exception as exc:
            self.root.after(0, lambda e=exc: self.handle_sync_error(e))
        finally:
            self.running = False
            self.client.close()

    def handle_sync_error(self, error):
        self.stop_event.set()
        self.start_button.configure(text="开始同步", state="disabled")
        self.run_var.set("出错后恢复中")
        self.status_var.set(f"同步错误：{error}。正在恢复同步前状态...")
        threading.Thread(target=self.restore_after_stop, daemon=True).start()

    def on_close(self):
        if self.is_quitting:
            return
        self.save_current_config()
        if self.tray_icon is not None:
            self.root.withdraw()
            return
        self.exit_app()

    def exit_app(self):
        self.is_quitting = True
        self.save_current_config()
        self.stop_event.set()
        if self.running and self.pre_sync_state:
            try:
                if self.worker and self.worker.is_alive():
                    self.worker.join(timeout=2.0)
                self.client.close()
                config = self.config_snapshot()
                self.client.configure(config["Host"], config["Port"])
                self.restore_light_state(self.pre_sync_state)
            except Exception:
                pass
        self.running = False
        self.client.close()
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None
        self.root.destroy()


def main():
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Yeelight.ScreenSync")
    except Exception:
        pass
    root = tk.Tk()
    YeelightSyncApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
