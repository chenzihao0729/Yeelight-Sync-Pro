# Yeelight Sync Pro

中文 | [English](README.en.md)

Yeelight Sync Pro 是一款 Windows 桌面氛围光同步工具，可以采集屏幕主色，并通过 Yeelight 局域网控制协议将颜色实时同步到支持 LAN Control 的 Yeelight 灯带或灯泡。

## 功能特性

- 实时采集屏幕颜色，适合显示器、电视、桌面和游戏氛围光场景。
- 支持全屏取色和中心区域取色。
- 可调节同步间隔、渐变时间、亮度上限、饱和度增强、平滑强度和变化阈值。
- 支持设备状态刷新、开关灯和亮度调节。
- 开始同步前保存灯具状态，停止同步后自动恢复。
- 支持系统托盘，关闭窗口后可继续驻留后台。
- 自动跟随 Windows 深色/浅色主题。

## 环境要求

- Windows 10 或更高版本。
- 从源码运行需要 Python 3.10 或更高版本。
- 一台支持 `LAN Control` 的 Yeelight 设备。
- 电脑和 Yeelight 设备需要处于同一个局域网。

使用前请先在 Yeelight 或米家 App 中为目标设备开启 `局域网控制 / LAN Control`。

Yeelight 局域网控制默认端口为 `55443`。

## 快速开始

安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

启动应用：

```powershell
python main.py
```

首次运行后，在界面中输入 Yeelight 设备 IP，然后刷新设备状态或开始同步。

## 配置说明

如需手动创建配置文件，可以复制示例配置：

```powershell
Copy-Item config.example.json config.json
```

常用配置项：

- 设备 IP 地址：Yeelight 设备的局域网 IP，对应 `Host`。
- 取色范围：可选择 `全屏` 或 `屏幕中央`，对应 `CaptureModeIndex`。
- 采样网格：屏幕取色采样密度，对应 `SampleGrid`。
- 采样区域大小：中心区域取色范围，对应 `RegionPercent`。
- 同步间隔：两次颜色同步之间的时间间隔，对应 `IntervalMs`。
- 渐变时间：灯光颜色过渡时长，对应 `FadeMs`。
- 亮度上限：限制输出到灯具的最高亮度，对应 `BrightnessCap`。
- 饱和度上限：调节灯光颜色饱和表现，对应 `SaturationBoost`。
- 平滑：控制颜色变化的平滑程度，对应 `SmoothingPercent`。

## 打包构建

使用 PyInstaller 构建 Windows 可执行程序：

```powershell
pip install pyinstaller
pyinstaller "Yeelight Sync Pro.spec"
```

构建结果位于：

```text
dist/Yeelight Sync Pro/Yeelight Sync Pro.exe
```

## 项目结构

```text
.
|-- core/                  # 配置、屏幕取色、Yeelight 客户端和同步服务
|-- ui/                    # PySide6 界面、面板和主题辅助
|-- widgets/               # 可复用 UI 组件
|-- main.py                # 应用入口
|-- icon.ico               # 应用图标
`-- Yeelight Sync Pro.spec # PyInstaller 打包配置
```

## 常见问题

### 无法连接设备

- 确认目标设备已经开启 `LAN Control`。
- 确认电脑和设备在同一个局域网。
- 确认设备 IP 地址正确，端口为 `55443`。
- 检查 Windows 防火墙是否阻止应用访问局域网。

### 灯光变化不明显

- 提高「亮度上限」。
- 提高「饱和度上限」。
- 缩短「同步间隔」以提升更新频率。
- 适当降低「平滑」，让颜色变化更灵敏。

### 提示缺少依赖

重新安装依赖：

```powershell
pip install -r requirements.txt
```
