import ctypes
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMenu, QSystemTrayIcon, QVBoxLayout, QWidget
from qfluentwidgets import InfoBar, InfoBarPosition, Theme, setTheme, setThemeColor

from core.sync_service import YeelightSyncService
from ui.control_panel import ControlPanel
from ui.preview_panel import PreviewPanel
from ui.theme import ACCENT, current_app_theme


class MainWindow(QWidget):
    """Modern PySide6 + QFluentWidgets shell connected to Yeelight sync logic."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Yeelight Sync Pro")
        self.setFixedSize(960, 760)

        self.icon_path = Path(__file__).resolve().parent.parent / "icon.ico"
        self.tray_icon = None
        self.is_quitting = False
        self.service = YeelightSyncService(self)
        self.app_theme = current_app_theme()

        self._set_window_icon()
        self._build_ui()
        self._apply_theme()
        self._bind_events()
        self._load_config_to_ui()
        self._setup_tray()
        self._center_on_screen()

        self.auto_refresh_timer = QTimer(self)
        self.auto_refresh_timer.setInterval(5000)
        self.auto_refresh_timer.timeout.connect(self.refresh_state)
        self.auto_refresh_timer.start()
        self.theme_timer = QTimer(self)
        self.theme_timer.setInterval(1200)
        self.theme_timer.timeout.connect(self._sync_windows_theme)
        self.theme_timer.start()
        QTimer.singleShot(350, self.refresh_state)

    def _set_window_icon(self):
        if self.icon_path.exists():
            self.setWindowIcon(QIcon(str(self.icon_path)))

    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(str(self.icon_path)) if self.icon_path.exists() else self.windowIcon())
        self.tray_icon.setToolTip("Yeelight Sync Pro")

        menu = QMenu(self)
        show_action = menu.addAction("显示窗口")
        quit_action = menu.addAction("退出")
        show_action.triggered.connect(self.show_from_tray)
        quit_action.triggered.connect(self.quit_app)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _center_on_screen(self):
        screen = self.screen()
        if not screen:
            return
        geo = screen.availableGeometry()
        self.move(geo.center().x() - self.width() // 2, geo.center().y() - self.height() // 2)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        main_area = QWidget()
        main_area.setObjectName("MainArea")
        main_layout = QHBoxLayout(main_area)
        main_layout.setContentsMargins(20, 20, 20, 18)
        main_layout.setSpacing(20)

        self.preview_panel = PreviewPanel()
        self.control_panel = ControlPanel()

        main_layout.addWidget(self.preview_panel, 1)
        main_layout.addWidget(self.control_panel)

        root.addWidget(main_area, 1)

    def _apply_theme(self):
        theme = self.app_theme
        setTheme(Theme.DARK if theme.dark else Theme.LIGHT)
        setThemeColor(ACCENT)
        self.setStyleSheet(
            f"""
            QWidget {{
                font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
                color: {theme.text};
            }}
            QWidget#MainArea {{
                background: {theme.main_background};
            }}
            """
        )
        self.preview_panel.apply_theme(theme)
        self.control_panel.apply_theme(theme)
        self._apply_window_title_bar_theme()

    def _sync_windows_theme(self):
        next_theme = current_app_theme()
        if next_theme.dark == self.app_theme.dark:
            return
        self.app_theme = next_theme
        self._apply_theme()

    def _apply_window_title_bar_theme(self):
        if sys.platform != "win32":
            return
        try:
            hwnd = int(self.winId())
            value = ctypes.c_int(1 if self.app_theme.dark else 0)
            for attribute in (20, 19):
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    attribute,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                ) == 0:
                    break
        except Exception:
            pass

    def _bind_events(self):
        self.preview_panel.refreshRequested.connect(self.refresh_state)
        self.preview_panel.ip_edit.editingFinished.connect(self.save_config_from_ui)
        self.preview_panel.start_button.clicked.connect(self.toggle_sync)
        self.preview_panel.device_card.brightnessRequested.connect(self.set_light_brightness)
        self.preview_panel.power_switch.checkedChanged.connect(self.service.set_power)

        self.control_panel.region_combo.currentIndexChanged.connect(self._config_changed)
        self.control_panel.grid_combo.currentIndexChanged.connect(self._config_changed)
        self.preview_panel.interval_spin.lineEdit().returnPressed.connect(self._config_changed)
        self.preview_panel.fade_spin.lineEdit().returnPressed.connect(self._config_changed)
        self.preview_panel.startup_check.stateChanged.connect(self._config_changed)
        for slider in self.control_panel.sliders.values():
            slider.valueChanged.connect(self._config_changed)

        self.service.statusChanged.connect(self.set_status)
        self.service.runningChanged.connect(self.on_running_changed)
        self.service.colorChanged.connect(self.on_color_changed)
        self.service.lightStateChanged.connect(self.on_light_state_changed)
        self.service.errorOccurred.connect(self.on_error)

    def _load_config_to_ui(self):
        config = self.service.config
        self.preview_panel.set_host(str(config.get("Host", "")))
        self.preview_panel.set_output_config(config)
        self.control_panel.set_config(config)
        self._update_static_status()

    def collect_config(self) -> dict:
        config = self.service.config.copy()
        config.update(self.control_panel.config_values())
        config.update(self.preview_panel.output_values())
        config["Host"] = self.preview_panel.host()
        config["Port"] = str(config.get("Port", "55443") or "55443")
        return config

    def save_config_from_ui(self):
        self.service.update_config(self.collect_config())
        self.preview_panel.device_card.set_ip(self.preview_panel.host() or "未配置")
        self._update_static_status()

    def _config_changed(self, *_args):
        self.save_config_from_ui()

    def _update_static_status(self):
        config = self.collect_config()
        self.preview_panel.set_config_metrics(int(config["RegionPercent"]), int(config["IntervalMs"]))

    def refresh_state(self):
        self.save_config_from_ui()
        self.preview_panel.set_refreshing(True)
        self.service.refresh_state()

    def start_sync(self):
        self.save_config_from_ui()
        self.service.start(self.collect_config())

    def stop_sync(self):
        self.service.stop()

    def toggle_sync(self):
        if self.service.running:
            self.stop_sync()
        else:
            self.start_sync()

    def set_light_brightness(self, brightness: int):
        if self.service.running:
            return
        self.save_config_from_ui()
        self.service.set_brightness(brightness)

    def set_status(self, text: str):
        return

    def on_running_changed(self, running: bool):
        self.preview_panel.set_running(running)

    def on_color_changed(self, r: int, g: int, b: int, h: int, s: int, v: int):
        self.preview_panel.update_color(r, g, b, h, s, v)

    def on_light_state_changed(self, state: dict, text: str):
        self.preview_panel.set_refreshing(False)
        self.preview_panel.update_device_state(state)
        self.preview_panel.set_power_checked(state.get("power") == "on")

    def on_error(self, text: str):
        self.preview_panel.set_refreshing(False)
        if text.startswith("刷新状态失败"):
            self.preview_panel.set_disconnected()
        InfoBar.error(
            title="Yeelight Sync",
            content=text,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=4500,
            parent=self,
        )

    def show_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def quit_app(self):
        self.is_quitting = True
        self.auto_refresh_timer.stop()
        self.theme_timer.stop()
        if self.service.running:
            self.service.stop()
        self.service.close()
        if self.tray_icon:
            self.tray_icon.hide()
        QApplication.quit()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_from_tray()

    def closeEvent(self, event: QCloseEvent):
        if self.is_quitting:
            event.accept()
            return
        event.ignore()
        self.hide()
        if self.tray_icon:
            self.tray_icon.showMessage(
                "Yeelight Sync Pro",
                "程序已最小化到托盘，右键托盘图标可退出。",
                QSystemTrayIcon.Information,
                2500,
            )
