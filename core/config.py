import json
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = APP_DIR / "config.json"

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


def load_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open("r", encoding="utf-8-sig") as file:
                loaded = json.load(file)
            if isinstance(loaded, dict):
                config.update(loaded)
        except Exception:
            pass
    return config


def save_config(config: dict):
    with CONFIG_PATH.open("w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=2)
