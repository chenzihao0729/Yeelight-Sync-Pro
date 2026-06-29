from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSlider, QVBoxLayout
from qfluentwidgets import BodyLabel, CaptionLabel, StrongBodyLabel

from ui.theme import DARK_THEME, AppTheme, slider_style


class DeviceCard(QFrame):
    """Clickable Yeelight device summary card."""

    clicked = Signal()
    brightnessRequested = Signal(int)

    def __init__(
        self,
        name: str,
        ip_address: str,
        power_on: bool = False,
        brightness: int = 0,
        selected: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.name = name
        self.ip_address = ip_address
        self.connected = False
        self.power_on = power_on
        self.brightness = brightness
        self.selected = selected
        self.freeze_brightness_ui = False
        self.brightness_control_allowed = True
        self.state_summary = "等待刷新"
        self.app_theme = DARK_THEME
        self.setObjectName("DeviceCard")
        self.setCursor(Qt.ArrowCursor)
        self.setFixedHeight(148)
        self._build_ui()
        self._apply_style()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(8)

        self.status_dot = QFrame()
        self.status_dot.setObjectName("StatusDot")
        self.status_dot.setFixedSize(10, 10)

        self.name_label = StrongBodyLabel(self._display_name())

        top.addWidget(self.status_dot, 0, Qt.AlignVCenter)
        top.addWidget(self.name_label, 1)

        state_row = QHBoxLayout()
        state_row.setSpacing(10)

        self.state_label = BodyLabel("同步已停止")
        self.state_label.setObjectName("CardStateText")
        self.ip_label = CaptionLabel(self.ip_address)
        self.ip_label.setObjectName("CardMutedText")
        self.ip_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        state_row.addWidget(self.state_label)
        state_row.addStretch(1)
        state_row.addWidget(self.ip_label)

        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(1, 5)
        self.brightness_slider.setSingleStep(1)
        self.brightness_slider.setPageStep(1)
        self.brightness_slider.setTickInterval(1)
        self.brightness_slider.setFixedHeight(22)
        self.brightness_slider.setValue(self._brightness_to_level(self.brightness))
        self.brightness_slider.sliderReleased.connect(self._emit_brightness_request)
        self._apply_brightness_slider_state()

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self.brightness_label = CaptionLabel(
            f"亮度：{self._level_to_brightness(self._brightness_to_level(self.brightness))}%"
        )
        self.brightness_label.setObjectName("CardMutedText")
        self.extra_label = CaptionLabel(self.state_summary)
        self.extra_label.setObjectName("CardMutedText")
        self.extra_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bottom.addWidget(self.brightness_label)
        bottom.addWidget(self.extra_label, 1)

        layout.addLayout(top)
        layout.addLayout(state_row)
        layout.addWidget(self.brightness_slider)
        layout.addLayout(bottom)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def _apply_style(self):
        theme = self.app_theme
        dot_color = "#34C759" if self.connected else "#FF5C5C"
        self.setStyleSheet(
            f"""
            QFrame#DeviceCard {{
                background: {theme.card_bg};
                border: 1px solid {theme.card_border};
                border-radius: 8px;
            }}
            QFrame#StatusDot {{
                background: {dot_color};
                border-radius: 5px;
            }}
            QLabel#CardMutedText {{
                color: {theme.text_muted};
                font-size: 12px;
            }}
            QLabel#CardStateText {{
                color: {theme.text_soft};
                font-size: 13px;
            }}
            """
        )
        self._apply_brightness_slider_state()

    def apply_theme(self, theme: AppTheme):
        self.app_theme = theme
        self._apply_style()

    def set_ip(self, ip_address: str):
        self.ip_address = ip_address
        self.ip_label.setText(ip_address)

    def set_brightness_control_enabled(self, enabled: bool):
        self.brightness_control_allowed = enabled
        self.freeze_brightness_ui = not enabled
        self._apply_brightness_slider_state()

    def update_device(
        self,
        name: str,
        ip_address: str,
        power_on: bool,
        brightness: int,
        connected: bool = True,
        state_summary: str = "",
    ):
        self.name = name
        self.ip_address = ip_address
        self.connected = connected
        self.power_on = power_on
        self.brightness = max(0, min(100, int(brightness)))
        self.state_summary = state_summary or ("电源开" if self.power_on else "电源关")

        self.name_label.setText(self._display_name())
        self.ip_label.setText(self.ip_address)
        if not self.power_on:
            self.brightness_label.setText("亮度：--")
        elif not self.freeze_brightness_ui:
            level = self._brightness_to_level(self.brightness)
            self.brightness_slider.blockSignals(True)
            self.brightness_slider.setValue(level)
            self.brightness_slider.blockSignals(False)
            self.brightness_label.setText(f"亮度：{self._level_to_brightness(level)}%")
        self.extra_label.setText(self.state_summary)
        self._apply_style()

    def update_live_color(self, h: int, s: int, v: int):
        self.connected = True
        self.power_on = True
        self.state_summary = "实时同步中"
        self.name_label.setText(self._display_name())
        self.extra_label.setText(self.state_summary)
        self._apply_style()

    def set_sync_state(self, running: bool):
        self.state_label.setText("已开启同步" if running else "同步已停止")

    def _brightness_to_level(self, brightness: int) -> int:
        return max(1, min(5, int(round(max(1, brightness) / 20.0))))

    def _display_name(self) -> str:
        status = "已连接" if self.connected else "未连接"
        return f"{status} · {self.name}"

    def _level_to_brightness(self, level: int) -> int:
        return max(1, min(100, int(level) * 20))

    def _apply_brightness_slider_state(self):
        enabled = self.brightness_control_allowed and self.power_on
        self.brightness_slider.setEnabled(enabled)
        disabled_style = f"""
            QSlider::groove:horizontal:disabled {{
                height: 4px;
                border-radius: 2px;
                background: {self.app_theme.groove};
            }}
            QSlider::sub-page:horizontal:disabled {{
                height: 4px;
                border-radius: 2px;
                background: {self.app_theme.groove};
            }}
            QSlider::add-page:horizontal:disabled {{
                height: 4px;
                border-radius: 2px;
                background: {self.app_theme.groove};
            }}
            QSlider::handle:horizontal:disabled {{
                width: 0px;
                height: 0px;
                margin: 0;
                background: transparent;
                border: none;
            }}
        """
        self.brightness_slider.setStyleSheet(slider_style(self.app_theme, handle_size=16) + disabled_style)

    def _emit_brightness_request(self):
        if not self.power_on:
            return
        level = self.brightness_slider.value()
        brightness = self._level_to_brightness(level)
        self.brightness = brightness
        self.brightness_label.setText(f"亮度：{brightness}%")
        self.brightnessRequested.emit(brightness)
