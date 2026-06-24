# Yeelight Sync Pro

[中文](README.md) | English

Yeelight Sync Pro is a Windows desktop ambient-light app that syncs the dominant color of your screen to Yeelight devices over the local LAN Control protocol.

## Features

- Real-time screen color sampling for monitors, TVs, desks, and gaming setups.
- Full-screen and centered-region capture modes.
- Adjustable sync interval, fade duration, brightness cap, saturation boost, smoothing, and change threshold.
- Device status refresh, power control, and brightness control.
- Restores the previous light state after sync stops.
- System tray support.
- Automatic light/dark theme matching on Windows.

## Requirements

- Windows 10 or later.
- Python 3.10 or later for source builds.
- A Yeelight device that supports `LAN Control`.
- The PC and Yeelight device must be on the same local network.

Before using the app, enable `LAN Control` for the target device in the Yeelight or Mi Home app.

Yeelight LAN Control uses port `55443` by default.

## Quick Start

Install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the app:

```powershell
python main.py
```

Enter your Yeelight device IP address in the app, then refresh the device status or start syncing.

## Configuration

To create a config file manually:

```powershell
Copy-Item config.example.json config.json
```

Common settings:

- Device IP Address: local IP address of the Yeelight device, stored as `Host`.
- Capture Range: `Full Screen` or `Screen Center`, stored as `CaptureModeIndex`.
- Sample Grid: screen sampling density, stored as `SampleGrid`.
- Sample Region Size: size of the centered capture region, stored as `RegionPercent`.
- Sync Interval: delay between color sync updates, stored as `IntervalMs`.
- Fade Duration: light transition duration, stored as `FadeMs`.
- Brightness Cap: maximum output brightness, stored as `BrightnessCap`.
- Saturation Cap: adjusts color saturation output, stored as `SaturationBoost`.
- Smoothing: color smoothing strength, stored as `SmoothingPercent`.

## Build

Create a Windows distribution with PyInstaller:

```powershell
pip install pyinstaller
pyinstaller "Yeelight Sync Pro.spec"
```

The packaged app is written to:

```text
dist/Yeelight Sync Pro/Yeelight Sync Pro.exe
```

## Project Structure

```text
.
|-- core/                  # configuration, screen sampling, Yeelight client, sync service
|-- ui/                    # PySide6 windows, panels, and theme helpers
|-- widgets/               # reusable UI widgets
|-- main.py                # application entry point
|-- icon.ico               # application icon
`-- Yeelight Sync Pro.spec # PyInstaller build config
```

## Troubleshooting

### The app cannot connect to the device

- Make sure LAN Control is enabled for the Yeelight device.
- Make sure the PC and device are on the same network.
- Verify the device IP address and port `55443`.
- Check whether Windows Firewall is blocking local network access.

### The light does not react strongly enough

- Increase `Brightness Cap`.
- Increase `Saturation Cap`.
- Reduce `Sync Interval` for faster updates.
- Lower `Smoothing` to make color changes more responsive.

### Dependencies are missing

Reinstall dependencies:

```powershell
pip install -r requirements.txt
```
