import colorsys
import math

from PySide6.QtCore import QEasingCurve, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CheckBox, LineEdit, PushButton, SpinBox, StrongBodyLabel, SubtitleLabel, SwitchButton, TitleLabel

from ui.theme import DARK_THEME, AppTheme
from widgets.device_card import DeviceCard


class PreviewPanel(QFrame):
    """Center panel with device status, sync buttons, and live metrics."""

    refreshRequested = Signal()
    CARD_SPACING = 18

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PreviewPanel")
        self.metric_cards = {}
        self.metric_labels = {}
        self.metric_values = {}
        self.metric_swatches = {}
        self.current_color = QColor(16, 16, 16)
        self.last_light_state = None
        self.app_theme = DARK_THEME
        self.is_running = False
        self.color_animation = QVariantAnimation(self)
        self.color_animation.setDuration(220)
        self.color_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.color_animation.valueChanged.connect(self._apply_color_card_color)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(self.CARD_SPACING)

        title_row = QWidget()
        title_row_layout = QHBoxLayout(title_row)
        title_row_layout.setContentsMargins(0, 0, 0, 0)
        title_row_layout.setSpacing(12)

        title_box = QWidget()
        title_layout = QVBoxLayout(title_box)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(8)
        title_layout.addWidget(TitleLabel("Yeelight  Sync Pro"))
        hint = BodyLabel("易来动态光效映射系统")
        hint.setObjectName("SubtleLabel")
        title_layout.addWidget(hint)

        self.power_switch = SwitchButton()
        self.power_switch.setOnText("已开启")
        self.power_switch.setOffText("已关闭")
        self.power_switch.setChecked(False)
        power_box = QWidget()
        power_layout = QHBoxLayout(power_box)
        power_layout.setContentsMargins(0, 0, 0, 0)
        power_layout.setSpacing(10)
        power_label = StrongBodyLabel("灯带电源")
        power_layout.addWidget(power_label)
        power_layout.addWidget(self.power_switch)
        title_row_layout.addWidget(title_box, 1)
        title_row_layout.addWidget(power_box, 0, Qt.AlignRight | Qt.AlignVCenter)

        device_box = QWidget()
        device_layout = QVBoxLayout(device_box)
        device_layout.setContentsMargins(0, 0, 0, 0)
        device_layout.setSpacing(self.CARD_SPACING)

        device_label = BodyLabel("设备 IP 地址")
        device_label.setObjectName("SubtleLabel")
        self.ip_edit = LineEdit()
        self.ip_edit.setPlaceholderText("192.168.31.175")
        self.ip_edit.setFixedHeight(38)

        self.refresh_button = PushButton("刷新状态")
        self.refresh_button.setMinimumHeight(40)
        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        self.device_card = DeviceCard(
            name="Yeelight 灯带",
            ip_address="未配置",
            power_on=False,
            brightness=0,
            selected=False,
        )
        self.device_card.setFixedHeight(148)

        device_layout.addWidget(device_label)
        device_layout.addWidget(self.ip_edit)
        device_layout.addWidget(self.device_card)

        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)

        self.start_button = PushButton("开始同步")
        self.start_button.setMinimumHeight(40)
        self.start_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.refresh_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._apply_start_button_style()

        button_layout.addWidget(self.refresh_button, 1)
        button_layout.addWidget(self.start_button, 1)

        metrics = QWidget()
        metrics_layout = QVBoxLayout(metrics)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(0)
        metrics_layout.addWidget(self._metric_card("color", "当前颜色", "RGB 0, 0, 0", "#101010", 0))

        self.output_card = self._output_card()

        layout.addWidget(title_row)
        layout.addWidget(button_row)
        layout.addWidget(device_box)
        layout.addWidget(metrics)
        layout.addWidget(self.output_card)
        layout.addStretch(1)

        self.apply_theme(self.app_theme)

    def apply_theme(self, theme: AppTheme):
        self.app_theme = theme
        self.setStyleSheet(
            f"""
            QFrame#PreviewPanel {{
                background: {theme.panel_bg};
                border: 1px solid {theme.panel_border};
                border-radius: 8px;
            }}
            QLabel#SubtleLabel {{
                color: {theme.text_muted};
                font-size: 13px;
            }}
            QFrame#MetricCard {{
                background: {theme.card_bg};
                border: 1px solid {theme.card_border};
                border-radius: 8px;
            }}
            QFrame#OutputCard {{
                background: {theme.card_bg};
                border: 1px solid {theme.card_border};
                border-radius: 8px;
            }}
            QLabel#MetricLabel {{
                color: {theme.text_muted};
                font-size: 12px;
            }}
            QLabel#MetricValue {{
                color: {theme.text};
                font-size: 18px;
                font-weight: 700;
            }}
            """
        )
        self.device_card.apply_theme(theme)
        self._apply_sync_button_style(self.is_running)
        if not self.is_running:
            self._apply_standby_color_card()
        else:
            self._apply_color_card_color(self.current_color)

    def _metric_card(self, key: str, label: str, value: str, color: str, swatch_size: int) -> QFrame:
        card = QFrame()
        card.setObjectName("MetricCard")
        card.setFixedHeight(112 if key == "color" else 62)
        self.metric_cards[key] = card

        layout = QHBoxLayout(card)
        layout.setContentsMargins(18 if key == "color" else 14, 14 if key == "color" else 8, 18 if key == "color" else 14, 14 if key == "color" else 8)
        layout.setSpacing(12)

        label_widget = BodyLabel(label)
        label_widget.setObjectName("MetricLabel")
        value_widget = SubtitleLabel(value)
        value_widget.setObjectName("MetricValue")

        self.metric_labels[key] = label_widget
        self.metric_values[key] = value_widget

        if key == "color":
            card.setStyleSheet(
                "background: #101010; border: 1px solid rgba(255,255,255,24); border-radius: 8px;"
            )
            label_widget.setStyleSheet(
                "background: transparent; border: none; color: #FFFFFF; font-size: 15px; font-weight: 700;"
            )
            value_widget.setStyleSheet(
                "background: transparent; border: none; color: rgba(255, 255, 255, 125); font-size: 17px; font-weight: 700;"
            )
            layout.addWidget(label_widget)
            layout.addStretch(1)
            layout.addWidget(value_widget)
            return card

        swatch = QFrame()
        swatch.setFixedSize(swatch_size, swatch_size)
        self._set_swatch_color(swatch, color, swatch_size)
        self.metric_swatches[key] = swatch

        text_box = QWidget()
        text_layout = QVBoxLayout(text_box)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)
        text_layout.addWidget(label_widget)
        text_layout.addWidget(value_widget)
        layout.addWidget(swatch)
        layout.addWidget(text_box, 1)
        return card

    def _output_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("OutputCard")
        card.setFixedHeight(152)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(0)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 2)

        self.interval_spin = SpinBox()
        self.interval_spin.setRange(30, 2000)
        self.interval_spin.setSingleStep(10)
        self.interval_spin.setValue(170)
        self.interval_spin.setSuffix(" ms")
        self.interval_spin.setFixedHeight(34)
        self.interval_spin.setKeyboardTracking(False)

        self.fade_spin = SpinBox()
        self.fade_spin.setRange(0, 1000)
        self.fade_spin.setSingleStep(10)
        self.fade_spin.setValue(290)
        self.fade_spin.setSuffix(" ms")
        self.fade_spin.setFixedHeight(34)
        self.fade_spin.setKeyboardTracking(False)

        self.restore_check = CheckBox("停止后恢复同步前状态")
        self.restore_check.setChecked(True)
        self.startup_check = CheckBox("允许随 Windows 开机自动启动")

        grid.addWidget(BodyLabel("同步间隔"), 0, 0, Qt.AlignVCenter)
        grid.addWidget(self.interval_spin, 0, 1, Qt.AlignVCenter)
        grid.addWidget(BodyLabel("渐变时间"), 1, 0, Qt.AlignVCenter)
        grid.addWidget(self.fade_spin, 1, 1, Qt.AlignVCenter)
        checks = QWidget()
        checks_layout = QHBoxLayout(checks)
        checks_layout.setContentsMargins(0, 0, 0, 0)
        checks_layout.setSpacing(12)
        checks_layout.addWidget(self.restore_check)
        checks_layout.addStretch(1)
        checks_layout.addWidget(self.startup_check)
        grid.addWidget(checks, 2, 0, 1, 2, Qt.AlignVCenter)
        layout.addStretch(1)
        layout.addLayout(grid)
        layout.addStretch(1)
        return card

    def host(self) -> str:
        return self.ip_edit.text().strip()

    def set_host(self, host: str):
        self.ip_edit.setText(host or "")
        self.device_card.set_ip(host or "未配置")

    def set_refreshing(self, refreshing: bool):
        self.refresh_button.setEnabled(not refreshing)
        self.refresh_button.setText("刷新中..." if refreshing else "刷新状态")

    def update_device_state(self, state: dict):
        if self.is_running:
            self.last_light_state = dict(state)
            return

        power_on = state.get("power") == "on"
        try:
            brightness = int(state.get("bright") or 0)
        except ValueError:
            brightness = 0
        name = state.get("name") or "Yeelight 灯带"
        state_summary = self._format_device_details(state, brightness)
        self.device_card.update_device(
            name=name,
            ip_address=self.host() or "未配置",
            power_on=power_on,
            brightness=brightness,
            connected=True,
            state_summary=state_summary,
        )
        self.last_light_state = dict(state)
        if not self.is_running:
            self._apply_standby_color_card()

    def _format_device_details(self, state: dict, brightness: int) -> str:
        if state.get("power") != "on":
            return "RGB：-- · 色温：-- · 版本号：--"

        color_mode = str(state.get("color_mode") or "")
        if color_mode == "2":
            detail = f"色温 {state.get('ct') or '-'}K"
        elif color_mode == "3":
            detail = f"H {state.get('hue') or '-'} / S {state.get('sat') or '-'}%"
        elif color_mode == "1":
            detail = f"RGB {self._format_rgb_value(state.get('rgb'))}"
        else:
            detail = "模式 -"
        firmware = state.get("fw_ver") or "-"
        return f"{detail} · 亮度 {brightness}% · 版本号 {firmware}"

    def _format_rgb_value(self, value) -> str:
        try:
            rgb_int = int(value or 0)
        except (TypeError, ValueError):
            return str(value or "-")
        r = (rgb_int >> 16) & 255
        g = (rgb_int >> 8) & 255
        b = rgb_int & 255
        return f"{r}, {g}, {b}"

    def set_running(self, running: bool):
        self.is_running = running
        self.start_button.setEnabled(True)
        self.start_button.setText("停止同步" if running else "开始同步")
        self.ip_edit.setEnabled(not running)
        self.refresh_button.setEnabled(not running)
        self.power_switch.setEnabled(not running)
        self.device_card.set_brightness_control_enabled(not running)
        self.device_card.set_sync_state(running)
        self._apply_sync_button_style(running)
        if not running and self.last_light_state:
            self.update_device_state(self.last_light_state)

    def set_power_checked(self, checked: bool):
        self.power_switch.blockSignals(True)
        self.power_switch.setChecked(checked)
        self.power_switch.blockSignals(False)

    def set_disconnected(self):
        self.device_card.update_device(
            name=self.device_card.name,
            ip_address=self.host() or "未配置",
            power_on=False,
            brightness=0,
            connected=False,
            state_summary="RGB：-- · 色温：-- · 版本号：--",
        )
        if not self.is_running:
            self.last_light_state = None
            self._apply_standby_color_card()

    def set_config_metrics(self, region_percent: int, interval_ms: int):
        return

    def update_color(self, r: int, g: int, b: int, h: int | None = None, s: int | None = None, v: int | None = None):
        if h is not None and s is not None and v is not None:
            self.metric_values["color"].setText(f"HSV {h}, {s}%, {v}%")
        else:
            self.metric_values["color"].setText(f"RGB {r}, {g}, {b}")
        target = QColor(int(r), int(g), int(b))
        self._animate_color_card(target)
        if self.is_running:
            self.device_card.update_live_color(int(h or 0), int(s or 0), int(v or 0))

    def _animate_color_card(self, target: QColor):
        if self.color_animation.state() == QVariantAnimation.Running:
            self.color_animation.stop()
        self.color_animation.setStartValue(self.current_color)
        self.color_animation.setEndValue(target)
        self.color_animation.start()

    def _apply_standby_color_card(self):
        if self.last_light_state and self.last_light_state.get("power") == "on":
            color = self._light_state_to_qcolor(self.last_light_state)
            self.metric_values["color"].setText(f"RGB {color.red()}, {color.green()}, {color.blue()}")
            self._animate_color_card(color)
            return

        color = QColor(16, 18, 23) if self.app_theme.dark else QColor(243, 247, 251)
        self.metric_values["color"].setText("")
        self._animate_color_card(color)

    def _light_state_to_qcolor(self, state: dict) -> QColor:
        brightness = self._bounded_int(state.get("bright"), 100, 0, 100) / 100.0
        color_mode = str(state.get("color_mode") or "1")

        if color_mode == "3":
            hue = self._bounded_int(state.get("hue"), 0, 0, 359) / 359.0
            saturation = self._bounded_int(state.get("sat"), 0, 0, 100) / 100.0
            r, g, b = colorsys.hsv_to_rgb(hue, saturation, brightness)
            return QColor(round(r * 255), round(g * 255), round(b * 255))

        if color_mode == "2":
            r, g, b = self._color_temperature_to_rgb(self._bounded_int(state.get("ct"), 4000, 1700, 6500))
            return QColor(round(r * brightness), round(g * brightness), round(b * brightness))

        r, g, b = self._rgb_int_to_tuple(state.get("rgb"))
        return QColor(round(r * brightness), round(g * brightness), round(b * brightness))

    def _bounded_int(self, value, fallback: int, minimum: int, maximum: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = fallback
        return max(minimum, min(maximum, number))

    def _rgb_int_to_tuple(self, value) -> tuple[int, int, int]:
        try:
            rgb_int = int(value or 0)
        except (TypeError, ValueError):
            return 0, 0, 0
        return (rgb_int >> 16) & 255, (rgb_int >> 8) & 255, rgb_int & 255

    def _color_temperature_to_rgb(self, kelvin: int) -> tuple[int, int, int]:
        temperature = kelvin / 100.0
        if temperature <= 66:
            red = 255
            green = 99.4708025861 * math.log(temperature) - 161.1195681661
            blue = 0 if temperature <= 19 else 138.5177312231 * math.log(temperature - 10) - 305.0447927307
        else:
            red = 329.698727446 * ((temperature - 60) ** -0.1332047592)
            green = 288.1221695283 * ((temperature - 60) ** -0.0755148492)
            blue = 255
        return tuple(max(0, min(255, round(channel))) for channel in (red, green, blue))

    def _apply_color_card_color(self, qcolor: QColor):
        self.current_color = QColor(qcolor)
        r, g, b = qcolor.red(), qcolor.green(), qcolor.blue()
        color = f"#{r:02X}{g:02X}{b:02X}"
        text_color = "#111827" if (r * 0.299 + g * 0.587 + b * 0.114) > 150 else "#FFFFFF"
        self.metric_cards["color"].setStyleSheet(
            f"background: {color}; border: 1px solid {self.app_theme.card_border}; border-radius: 8px;"
        )
        self.metric_labels["color"].setStyleSheet(
            f"background: transparent; border: none; color: {text_color}; font-size: 15px; font-weight: 700;"
        )
        alpha_color = "rgba(17, 24, 39, 130)" if text_color == "#111827" else "rgba(255, 255, 255, 125)"
        self.metric_values["color"].setStyleSheet(
            f"background: transparent; border: none; color: {alpha_color}; font-size: 17px; font-weight: 700;"
        )

    def set_output_config(self, config: dict):
        self.interval_spin.setValue(int(config.get("IntervalMs", 170)))
        self.fade_spin.setValue(int(config.get("FadeMs", 290)))
        self.startup_check.setChecked(bool(config.get("StartWithWindows", False)))

    def output_values(self) -> dict:
        return {
            "IntervalMs": self.interval_spin.value(),
            "FadeMs": self.fade_spin.value(),
            "StartWithWindows": self.startup_check.isChecked(),
        }

    def _set_swatch_color(self, swatch: QFrame, color: str, size: int = 44):
        radius = max(10, int(size * 0.24))
        swatch.setStyleSheet(
            f"background: {color}; border: 1px solid rgba(255,255,255,45); border-radius: {radius}px;"
        )

    def _apply_start_button_style(self):
        self._apply_sync_button_style(False)

    def _apply_sync_button_style(self, running: bool):
        background = "#FF3B30" if running else "#2F9BFF"
        hover = "#FF5148" if running else "#45A8FF"
        pressed = "#D92D25" if running else "#167FE0"
        theme = self.app_theme
        self.start_button.setStyleSheet(
            f"""
            PushButton {{
                min-height: 40px;
                max-height: 40px;
                background: {background};
                color: white;
                border: 1px solid rgba(255, 255, 255, 38);
                border-radius: 6px;
                font-weight: 700;
                padding: 0;
            }}
            PushButton:hover {{
                background: {hover};
            }}
            PushButton:pressed {{
                background: {pressed};
            }}
            PushButton:disabled {{
                background: {theme.disabled_bg};
                color: {theme.disabled_text};
                border: 1px solid {theme.card_border};
            }}
            """
        )
