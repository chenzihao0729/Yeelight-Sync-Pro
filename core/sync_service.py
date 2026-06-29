import threading
import time
import colorsys

from PySide6.QtCore import QObject, Signal

from core.config import DEFAULT_CONFIG, load_config, save_config
from core.screen_color import average_screen_color, hue_distance
from core.yeelight_client import LIGHT_STATE_PROPS, YeelightClient


MAX_RESEND_INTERVAL_MS = 3200
MIN_VISIBLE_DELTA = 2


def normalize_config(config: dict) -> dict:
    merged = DEFAULT_CONFIG.copy()
    merged.update(config or {})
    return merged


def rgb_int_to_tuple(value) -> tuple[int, int, int]:
    try:
        rgb_int = int(value or 0)
    except (TypeError, ValueError):
        return 0, 0, 0
    return (rgb_int >> 16) & 255, (rgb_int >> 8) & 255, rgb_int & 255


def average_rgb_to_hsv(r: int, g: int, b: int) -> tuple[int, int, int]:
    hue_float, saturation_float, value_float = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    hue = max(1, min(359, int(round(hue_float * 359))))
    saturation = max(0, min(100, int(round(saturation_float * 100))))
    brightness = max(1, min(100, int(round(value_float * 100))))
    return hue, saturation, brightness


def format_light_state(state: dict) -> str:
    power = "开" if state.get("power") == "on" else "关"
    bright = state.get("bright") or "-"
    color_mode = str(state.get("color_mode") or "-")
    mode_names = {"1": "RGB", "2": "色温", "3": "HSV"}
    mode_text = mode_names.get(color_mode, color_mode)

    if color_mode == "2":
        color_text = f"色温 {state.get('ct') or '-'}K"
    elif color_mode == "3":
        color_text = f"色相 {state.get('hue') or '-'} / 饱和 {state.get('sat') or '-'}%"
    else:
        r, g, b = rgb_int_to_tuple(state.get("rgb"))
        color_text = f"RGB {r}, {g}, {b}"

    name = state.get("name") or ""
    name_text = f" | 名称: {name}" if name else ""
    return f"电源: {power} | 亮度: {bright}% | 模式: {mode_text} | {color_text}{name_text}"


class YeelightSyncService(QObject):
    statusChanged = Signal(str)
    runningChanged = Signal(bool)
    colorChanged = Signal(int, int, int, int, int, int)
    sentChanged = Signal(str)
    lightStateChanged = Signal(dict, str)
    errorOccurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.client = YeelightClient()
        self.config = normalize_config(load_config())
        self.running = False
        self.stop_event = threading.Event()
        self.worker = None
        self.last_color = None
        self.last_sent_color = None
        self.last_sent_at = 0.0
        self.pre_sync_state = None
        self.refresh_lock = threading.Lock()
        self.restore_lock = threading.Lock()

    def update_config(self, config: dict):
        self.config = normalize_config(config)
        save_config(self.config)

    def refresh_state(self):
        if not self.refresh_lock.acquire(blocking=False):
            self.statusChanged.emit("状态刷新正在进行中...")
            return

        def worker():
            try:
                self._configure_client()
                state = self.capture_light_state_snapshot()
                self.lightStateChanged.emit(state, format_light_state(state))
                power = state.get("power") == "on"
                self.statusChanged.emit("状态已刷新" if power else "灯带当前为关闭状态")
            except Exception as exc:
                self.client.close()
                self.errorOccurred.emit(f"刷新状态失败: {exc}")
            finally:
                self.refresh_lock.release()

        threading.Thread(target=worker, daemon=True).start()

    def set_power(self, power_on: bool):
        def worker():
            try:
                self._configure_client()
                state = "on" if power_on else "off"
                self.client.send("set_power", [state, "smooth", 300])
                self.statusChanged.emit("已发送开灯命令" if power_on else "已发送关灯命令")
                time.sleep(0.25)
                self.refresh_state()
            except Exception as exc:
                self.client.close()
                self.errorOccurred.emit(f"设置电源失败: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def set_brightness(self, brightness: int):
        def worker():
            try:
                self._configure_client()
                value = max(1, min(100, int(brightness)))
                self.client.send("set_bright", [value, "smooth", 300])
                self.statusChanged.emit(f"已设置灯带亮度为 {value}%")
                time.sleep(0.25)
                self.refresh_state()
            except Exception as exc:
                self.client.close()
                self.errorOccurred.emit(f"设置亮度失败: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def start(self, config: dict):
        if self.running:
            return

        self.update_config(config)
        self.stop_event.clear()
        self.running = True
        self.last_color = None
        self.last_sent_color = None
        self.last_sent_at = 0.0
        self.pre_sync_state = None
        self.runningChanged.emit(True)
        self.statusChanged.emit("正在启动同步...")

        self.worker = threading.Thread(target=self._sync_worker, daemon=True)
        self.worker.start()

    def stop(self):
        if not self.running and not self.worker:
            return

        self.stop_event.set()
        self.statusChanged.emit("正在停止并恢复同步前状态...")
        threading.Thread(target=self._restore_after_stop, daemon=True).start()

    def close(self):
        self.stop_event.set()
        self.client.close()

    def _configure_client(self):
        host = str(self.config.get("Host", "")).strip()
        port = int(self.config.get("Port") or 55443)
        if not host:
            raise RuntimeError("请输入 Yeelight 设备 IP")
        self.client.configure(host, port)

    def capture_light_state_snapshot(self) -> dict:
        result = self.client.query_properties(LIGHT_STATE_PROPS)
        return dict(zip(LIGHT_STATE_PROPS, result))

    def restore_light_state(self, state: dict):
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
            r, g, b = rgb_int_to_tuple(state.get("rgb"))
            hue, saturation, _brightness = average_rgb_to_hsv(r, g, b)
            self.client.send("set_hsv", [hue, saturation, "smooth", duration])

        if bright:
            self.client.send("set_bright", [int(bright), "smooth", duration])

        self.client.send("set_power", [power, "smooth", duration])

    def _should_send_color(self, color_state: dict, config: dict, now: float) -> bool:
        if self.last_sent_color is None:
            return True

        interval_ms = max(30, int(config["IntervalMs"]))
        elapsed_ms = (now - self.last_sent_at) * 1000
        fade_ms = max(0, int(config["FadeMs"]))
        min_send_interval = max(90, min(450, int(fade_ms * 0.7)))
        if elapsed_ms < min_send_interval:
            return False

        resend_interval = max(MAX_RESEND_INTERVAL_MS, interval_ms * 8)
        if elapsed_ms >= resend_interval:
            return True

        threshold = max(MIN_VISIBLE_DELTA, int(config["Threshold"]))
        brightness_delta = abs(color_state["brightness"] - self.last_sent_color["brightness"])
        saturation_delta = abs(color_state["saturation"] - self.last_sent_color["saturation"])
        hue_delta = hue_distance(color_state["hue"], self.last_sent_color["hue"])

        if color_state.get("is_dark") or color_state.get("is_neutral"):
            return brightness_delta >= max(2, threshold // 3) or saturation_delta >= max(3, threshold // 2)

        hue_weight = max(color_state["saturation"], self.last_sent_color["saturation"]) / 100.0
        weighted_hue_delta = hue_delta * hue_weight
        visible_delta = max(weighted_hue_delta, saturation_delta, brightness_delta)
        return visible_delta >= threshold

    def _send_color_state(self, color_state: dict, duration: int):
        previous_brightness = None
        if self.last_sent_color is not None:
            previous_brightness = self.last_sent_color["brightness"]
        brightness = color_state["brightness"]
        should_send_brightness = (
            previous_brightness is None
            or abs(brightness - previous_brightness) >= 2
        )

        if should_send_brightness and previous_brightness is not None and brightness < previous_brightness:
            self.client.send("set_bright", [brightness, "smooth", duration])

        self.client.send(
            "set_hsv",
            [color_state["hue"], color_state["saturation"], "smooth", duration],
        )

        if should_send_brightness and not (
            previous_brightness is not None and brightness < previous_brightness
        ):
            self.client.send("set_bright", [brightness, "smooth", duration])

    def _sync_worker(self):
        try:
            self._configure_client()
            self.client.close()
            self._configure_client()
            self.pre_sync_state = self.capture_light_state_snapshot()
            self.statusChanged.emit("已保存同步前灯带状态，正在同步...")
            self.client.send("set_power", ["on", "smooth", 300])

            while not self.stop_event.is_set():
                config = normalize_config(self.config)
                color_state = average_screen_color(config, self.last_color)
                rgb = color_state["rgb"]

                self.colorChanged.emit(
                    rgb[0],
                    rgb[1],
                    rgb[2],
                    color_state["hue"],
                    color_state["saturation"],
                    color_state["brightness"],
                )
                now = time.monotonic()
                if self._should_send_color(color_state, config, now):
                    duration = int(config["FadeMs"])
                    self._send_color_state(color_state, duration)
                    self.last_sent_color = color_state
                    self.last_sent_at = now
                    self.sentChanged.emit("上次发送: " + time.strftime("%H:%M:%S"))

                self.last_color = color_state
                time.sleep(max(30, int(config["IntervalMs"])) / 1000.0)
        except Exception as exc:
            self.errorOccurred.emit(f"同步失败: {exc}")
            self.stop_event.set()
            self.running = False
            self.runningChanged.emit(False)
        finally:
            self.client.close()
            if not self.stop_event.is_set():
                self.running = False
                self.runningChanged.emit(False)

    def _restore_after_stop(self):
        if not self.restore_lock.acquire(blocking=False):
            return

        try:
            worker = self.worker
            if worker and worker.is_alive():
                worker.join(timeout=2.5)

            self.client.close()
            self._configure_client()
            if self.pre_sync_state:
                self.restore_light_state(self.pre_sync_state)
                self.statusChanged.emit("同步已停止，已恢复同步前灯带状态")
            else:
                self.statusChanged.emit("同步已停止，未找到同步前状态快照")
        except Exception as exc:
            self.errorOccurred.emit(f"同步已停止，但恢复状态失败: {exc}")
        finally:
            self.client.close()
            self.pre_sync_state = None
            self.worker = None
            self.running = False
            self.runningChanged.emit(False)
            self.refresh_state()
            self.restore_lock.release()
