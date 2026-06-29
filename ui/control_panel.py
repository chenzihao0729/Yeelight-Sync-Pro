from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QSlider, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, ComboBox, ScrollArea, StrongBodyLabel, TitleLabel

from ui.theme import ACCENT, DARK_THEME, AppTheme, slider_style


class ControlPanel(QFrame):
    """Right-side sync controls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ControlPanel")
        self.setFixedWidth(320)
        self.sliders = {}
        self.slider_values = {}
        self.app_theme = DARK_THEME
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = TitleLabel("控制")
        subtitle = BodyLabel("Control Panel")
        subtitle.setObjectName("SubtleLabel")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(4)

        scroll = ScrollArea()
        scroll.setObjectName("ControlScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("ControlScrollContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(22)
        content_layout.addWidget(self._section("画面采样", self._sampling_controls(), 276))
        content_layout.addWidget(self._section("颜色算法", self._color_controls(), 260))
        content_layout.addStretch(1)
        scroll.setWidget(content)

        layout.addSpacing(2)
        layout.addWidget(scroll, 1)

        self.apply_theme(self.app_theme)

    def apply_theme(self, theme: AppTheme):
        self.app_theme = theme
        self.setStyleSheet(
            f"""
            QFrame#ControlPanel {{
                background: {theme.panel_bg};
                border: 1px solid {theme.panel_border};
                border-radius: 8px;
            }}
            QScrollArea#ControlScroll {{
                background: transparent;
                border: none;
            }}
            QWidget#ControlScrollContent {{
                background: transparent;
            }}
            QLabel#SubtleLabel {{
                color: {theme.text_muted};
                font-size: 13px;
            }}
            QFrame#ControlSection {{
                background: {theme.card_bg};
                border: 1px solid {theme.card_border};
                border-radius: 8px;
            }}
            QLabel#ControlLabel {{
                color: {theme.text_soft};
                font-size: 12px;
            }}
            QLabel#SliderValue {{
                color: {ACCENT};
                font-size: 12px;
                font-weight: 700;
            }}
            QLabel#PowerLabel {{
                color: {theme.text};
                font-size: 14px;
                font-weight: 700;
            }}
            """
        )
        for slider in self.sliders.values():
            slider.setStyleSheet(slider_style(theme))

    def _section(self, title: str, content: QWidget, min_height: int) -> QFrame:
        section = QFrame()
        section.setObjectName("ControlSection")
        section.setFixedHeight(min_height)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(9)
        layout.addWidget(StrongBodyLabel(title))
        layout.addWidget(content)
        return section

    def _sampling_controls(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.region_combo = ComboBox()
        self.region_combo.addItems(["全屏", "屏幕中央"])

        self.grid_combo = ComboBox()
        self.grid_combo.addItems(["16 x 9", "32 x 18", "64 x 36", "128 x 72"])
        self.grid_combo.setCurrentText("64 x 36")

        layout.addWidget(self._combo_row("取色范围", self.region_combo))
        layout.addWidget(self._combo_row("采样网格", self.grid_combo))
        layout.addWidget(self._slider_row("RegionPercent", "采样区域大小", 70, "%"))
        return panel

    def _color_controls(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._slider_row("BrightnessCap", "亮度上限", 95, "%"))
        layout.addWidget(self._slider_row("SaturationBoost", "饱和度增强", 90, "%"))
        layout.addWidget(self._slider_row("SmoothingPercent", "平滑", 50, "%"))
        return panel

    def _slider_row(self, key: str, label: str, value: int, suffix: str) -> QWidget:
        row = QWidget()
        row.setFixedHeight(68)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QWidget()
        header.setFixedHeight(20)
        header_layout = QGridLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setHorizontalSpacing(8)

        label_widget = self._label(label)
        value_widget = BodyLabel(f"{value}{suffix}")
        value_widget.setObjectName("SliderValue")

        slider = QSlider(Qt.Horizontal)
        slider.setFixedHeight(30)
        slider.setMouseTracking(False)
        slider.setTracking(True)
        slider.setRange(0, 100)
        slider.setSingleStep(5)
        slider.setPageStep(5)
        slider.setValue(value)
        slider.valueChanged.connect(
            lambda v, key=key, w=value_widget, s=suffix: self._snap_slider_value(key, v, w, s)
        )
        slider.setStyleSheet(slider_style(self.app_theme))

        self.sliders[key] = slider
        self.slider_values[key] = value_widget

        header_layout.addWidget(label_widget, 0, 0)
        header_layout.addWidget(value_widget, 0, 1, Qt.AlignRight)
        layout.addWidget(header)
        layout.addWidget(slider)
        return row

    def _combo_row(self, label: str, combo: ComboBox) -> QWidget:
        row = QWidget()
        row.setFixedHeight(68)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QWidget()
        header.setFixedHeight(20)
        header_layout = QGridLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addWidget(self._label(label), 0, 0)

        combo.setFixedHeight(32)
        layout.addWidget(header)
        layout.addWidget(combo)
        return row

    def _snap_slider_value(self, key: str, value: int, value_widget: BodyLabel, suffix: str):
        slider = self.sliders[key]
        snapped = int(round(value / 5) * 5)
        snapped = max(slider.minimum(), min(slider.maximum(), snapped))
        if value != snapped:
            slider.blockSignals(True)
            slider.setValue(snapped)
            slider.blockSignals(False)
        value_widget.setText(f"{snapped}{suffix}")

    def _label(self, text: str) -> BodyLabel:
        label = BodyLabel(text)
        label.setObjectName("ControlLabel")
        return label

    def set_config(self, config: dict):
        mode_index = int(config.get("CaptureModeIndex", 0))
        self.region_combo.setCurrentIndex(max(0, min(mode_index, self.region_combo.count() - 1)))
        grid_index = int(config.get("SampleGridIndex", 2))
        if "SampleGrid" in config:
            text = str(config.get("SampleGrid") or "")
            found = self.grid_combo.findText(text)
            if found >= 0:
                grid_index = found
        self.grid_combo.setCurrentIndex(max(0, min(grid_index, self.grid_combo.count() - 1)))
        for key, slider in self.sliders.items():
            slider.setValue(int(config.get(key, slider.value())))

    def config_values(self) -> dict:
        return {
            "CaptureModeIndex": self.region_combo.currentIndex(),
            "SampleGridIndex": self.grid_combo.currentIndex(),
            "SampleGrid": self.grid_combo.currentText(),
            "RegionPercent": self.sliders["RegionPercent"].value(),
            "BrightnessCap": self.sliders["BrightnessCap"].value(),
            "SaturationBoost": self.sliders["SaturationBoost"].value(),
            "SmoothingPercent": self.sliders["SmoothingPercent"].value(),
        }
