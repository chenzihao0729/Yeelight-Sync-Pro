# Yeelight Sync Pro

Yeelight Sync Pro 是一个 Windows 桌面工具，可以采集屏幕平均颜色，并通过 Yeelight 局域网控制协议把颜色同步到支持 LAN Control 的 Yeelight 灯带或灯泡。

## 功能特性

- 实时采集全屏或中心区域颜色。
- 支持同步间隔、渐变时间、亮度上限、饱和度增强、平滑程度和变化阈值调节。
- 支持开灯、关灯、亮度调节和设备状态刷新。
- 开始同步前保存灯具状态，停止同步后自动恢复。
- 支持系统托盘，关闭窗口时最小化到托盘。
- 自动跟随 Windows 深色/浅色主题。

## 使用前准备

1. 在 Yeelight 或米家 App 中打开目标设备的 `局域网控制 / LAN Control`。
2. 确保电脑和 Yeelight 设备在同一个局域网内。
3. 获取设备的局域网 IP 地址，通常可以在路由器后台、App 设备信息或局域网扫描工具中查看。

Yeelight 局域网控制默认端口是 `55443`。

## 安装依赖

建议使用 Python 3.10 或更高版本。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 运行

```powershell
python main.py
```

首次运行后，在界面中输入 Yeelight 设备 IP，然后点击刷新状态或开始同步。

## 配置

程序会在项目根目录读取并保存 `config.json`。该文件用于记录本机设备 IP 和界面参数，属于个人运行配置，默认已被 `.gitignore` 忽略。

可以参考 `config.example.json` 创建自己的配置：

```powershell
Copy-Item config.example.json config.json
```

主要配置项：

- `Host`：Yeelight 设备 IP。
- `Port`：Yeelight 控制端口，默认 `55443`。
- `CaptureModeIndex`：取色模式，`0` 为全屏，`1` 为中心区域。
- `RegionPercent`：中心区域采样范围。
- `IntervalMs`：同步间隔。
- `FadeMs`：灯光渐变时间。
- `BrightnessCap`：亮度上限。
- `SaturationBoost`：饱和度增强。
- `SmoothingPercent`：颜色平滑程度。
- `Threshold`：颜色变化阈值。

## 打包

项目包含 PyInstaller spec 文件，可用于生成 Windows 可执行程序：

```powershell
pip install pyinstaller
pyinstaller "Yeelight Sync Pro.spec"
```

打包产物会输出到 `dist/`，该目录默认不提交到 Git。

## 项目结构

```text
.
├── core/                  # 配置、屏幕取色、Yeelight 客户端和同步服务
├── ui/                    # PySide6 主界面、控制面板、预览面板和主题
├── widgets/               # 可复用界面组件
├── main.py                # 应用入口
├── icon.ico               # 应用图标
└── Yeelight Sync Pro.spec # PyInstaller 打包配置
```

## 常见问题

### 无法连接设备

- 确认设备已开启 `LAN Control`。
- 确认电脑和设备在同一个局域网。
- 确认设备 IP 正确，端口为 `55443`。
- 检查系统防火墙是否阻止 Python 或打包后的程序访问局域网。

### 启动时报缺少模块

重新安装依赖：

```powershell
pip install -r requirements.txt
```

### 屏幕颜色变化但灯光不明显

可以尝试降低 `Threshold`，提高 `BrightnessCap` 或 `SaturationBoost`，并适当缩短 `IntervalMs`。

## 开源协议

本项目建议使用 MIT License。请在发布前确认依赖、图标和相关素材的授权均允许开源分发。
