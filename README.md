# 🔋 Battery Monitor Pro (HA Battery Monitor)

A comprehensive, lightweight battery monitoring solution for Windows with system tray integration, configurable toast/balloon notifications, audio alerts, and a modern Qt-based settings dashboard.

---

## 🌟 Features

- **Real-time Monitoring**: Tracks battery percentage, charging state, remaining run/charge time estimates, and discharge rates.
- **Smart System Tray Integration**: Color-coded battery level indicator in the system tray with quick action menu (*Check Now*, *Pause/Resume*, *Snooze*, *Settings*, *Quit*).
- **Multi-tiered Alerts**: Configurable notice, warning, and critical thresholds for both discharging (low battery) and charging (high charge / overcharge prevention).
- **Multi-modal Notifications**: Windows 10/11 modern toast notifications with fallback to system balloon tips and dialogs.
- **Audio Alerts & Headphone Protection**: Customizable frequency and duration beeps, with automatic audio intensity reduction when headphones are connected.
- **Modern Qt Settings GUI**: PySide6 dashboard with dark mode theme, live battery KPI gauges, and persistent JSON configuration management.
- **Single-Instance Protection**: Prevents multiple background instances from running simultaneously.

---

## 📁 Project Structure

```text
BatteryMoniter/
├── src/
│   ├── app_launcher.py       # Main CLI & entry point launcher
│   ├── battery_monitor.py    # Core battery monitoring engine & background service
│   ├── qt_gui.py             # PySide6 settings & dashboard interface
│   ├── qt_tray.py            # Qt-based system tray runner
│   └── splash_screen.py      # Tkinter animated splash screen
├── tests/
│   ├── test_battery_monitor.py # Unit tests for monitoring, config, and alerts
│   ├── test_executable.py      # Binary smoke & execution tests
│   └── final_test.py           # Verification script
├── tools/
│   ├── create_icon.py        # Generates default battery icons
│   └── convert_png_to_ico.py # Converts PNG assets to ICO
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+ (recommended 3.12+)
- Windows OS (for native Windows notifications and winsound audio)

### Installation
```bash
pip install -r requirements.txt
```

### Usage

#### Start Background Monitoring
```bash
python src/app_launcher.py
```

#### Open Settings GUI Directly
```bash
python src/app_launcher.py --settings
```

#### Custom Interval & Debug Logging
```bash
python src/app_launcher.py --interval 30 --debug
```

---

## 🧪 Running Tests

Run the test suite with unittest:

```bash
python -m unittest discover tests
```

---

## 📄 License
MIT License
