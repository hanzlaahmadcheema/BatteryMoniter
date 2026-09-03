from __future__ import annotations

import sys
import os
import json
import pathlib
from pathlib import Path
from typing import Any, Dict

import psutil
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QPalette, QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QTabWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QCheckBox, QSpinBox, QGroupBox,
    QFileDialog, QMessageBox, QComboBox, QGridLayout,
    QProgressBar, QFrame
)

APP_TITLE = "HA Battery Monitor - Settings"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "ui": {
        "theme": "qt_dark",
    },
    "monitoring": {
        "check_interval": 60,
        "smart_interval": True,
        "min_interval": 10,
        "low_critical": 20,
        "low_warning": 25,
        "low_notice": 30,
        "high_notice": 80,
        "high_warning": 85,
        "high_critical": 90,
    },
    "notifications": {
        "enabled": True,
        "frequency": "every",
        "cooldown": 300,
    },
    "audio": {
        "enabled": True,
        "frequency": "every",
        "cooldown": 300,
        "beep_frequency": 1000,
        "beep_duration": 700,
        "enabled_by_level": {
            "notice_low": True,
            "warning_low": True,
            "critical_low": True,
            "high_notice": True,
            "high_warning": True,
            "high_critical": True,
        },
        "reduce_on_headphones": True,
        "headphones_reduction_factor": 0.6,
    },
    "advanced": {
        "paused": False,
    }
}


def config_path() -> Path:
    base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    local_cfg = base_dir / "battery_config.json"
    try:
        test_file = base_dir / ".write_test.tmp"
        test_file.touch()
        test_file.unlink()
        return local_cfg
    except (PermissionError, OSError):
        pass

    if os.name == "nt":
        user_dir = Path(os.environ.get("APPDATA", Path.home())) / "HABatteryMonitor"
    else:
        user_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "ha_battery_monitor"

    try:
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir / "battery_config.json"
    except Exception:
        return local_cfg


def load_settings() -> Dict[str, Any]:
    path = config_path()
    data = DEFAULT_SETTINGS.copy()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                for k, v in loaded.items():
                    if k in data and isinstance(data[k], dict) and isinstance(v, dict):
                        data[k].update(v)
                    else:
                        data[k] = v
        except Exception:
            pass
    return data


def save_settings(settings: Dict[str, Any]) -> None:
    path = config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        QMessageBox.critical(None, "Error", f"Failed to save settings: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.settings = load_settings()
        self.apply_theme(self.settings.get("ui", {}).get("theme", "qt_dark"))

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.dashboard_tab = QWidget()
        self.monitoring_tab = QWidget()
        self.notifications_tab = QWidget()
        self.audio_tab = QWidget()

        self.tabs.addTab(self.dashboard_tab, "Dashboard")
        self.tabs.addTab(self.monitoring_tab, "Monitoring")
        self.tabs.addTab(self.notifications_tab, "Notifications")
        self.tabs.addTab(self.audio_tab, "Audio")

        self._init_dashboard()
        self._init_monitoring()
        self._init_notifications()
        self._init_audio()

        toolbar = self.addToolBar("Main")
        save_act = QAction("Save", self)
        save_act.triggered.connect(self.on_save)
        toolbar.addAction(save_act)

        export_act = QAction("Export", self)
        export_act.triggered.connect(self.on_export)
        toolbar.addAction(export_act)

        import_act = QAction("Import", self)
        import_act.triggered.connect(self.on_import)
        toolbar.addAction(import_act)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_dashboard)
        self.timer.start(2000)

        self.resize(920, 700)

    def _init_dashboard(self):
        self.dashboard_tab.setStyleSheet("""
            QWidget { background-color: #1f1f1f; color: #dddddd; }
            QLabel { selection-background-color: transparent; selection-color: #dddddd; }
            *:focus { outline: 0; }
            QTabBar::tab { background: #2b2b2b; color: #cccccc; padding: 6px 10px; }
            QTabBar::tab:selected { background: #323232; color: #ffffff; }
            QFrame#Card { background-color: #262626; border: 1px solid #3a3a3a; border-radius: 8px; }
            QLabel#CardTitle { background-color: #262626; color: #a0a6ac; font-size: 10pt; }
            QLabel#KPI { background-color: #262626; color: #eaeaea; font-size: 18pt; font-weight: 600; }
            QLabel#SubKPI { background-color: #262626; color: #b7bcc1; font-size: 9pt; }
            QProgressBar { border: 1px solid #3a3a3a; border-radius: 6px; background: #151515; height: 12px; }
            QProgressBar::chunk { background-color: #2e7d32; border-radius: 6px; }
            QPushButton { padding: 6px 12px; background: #2f2f2f; border: 1px solid #444; border-radius: 6px; }
            QPushButton:hover { background: #3a3a3a; }\n            QPushButton:pressed { background: #262626; }
            QGroupBox { border: 1px solid #3a3a3a; border-radius: 8px; margin-top: 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; color: #a0a6ac; }
            """)

        def make_card(title_text: str, center_widget: QWidget) -> QWidget:
            card = QFrame()
            card.setObjectName("Card")
            v = QVBoxLayout(card)
            title = QLabel(title_text)
            title.setObjectName("CardTitle")
            title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            title.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            v.addWidget(title)
            v.addWidget(center_widget)
            v.addStretch(1)
            return card

        def make_kpi_label(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setObjectName("KPI")
            lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            lbl.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            return lbl

        def make_subkpi_label(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setObjectName("SubKPI")
            lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            lbl.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            return lbl

        root = QVBoxLayout(self.dashboard_tab)

        header = QHBoxLayout()
        header_left = QVBoxLayout()
        title_lbl = QLabel("HA Battery Monitor")
        tfont = title_lbl.font()
        tfont.setPointSize(13)
        tfont.setBold(True)
        title_lbl.setFont(tfont)
        title_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        title_lbl.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        subtitle = QLabel("Dashboard")
        sfont = subtitle.font()
        sfont.setPointSize(9)
        subtitle.setFont(sfont)
        subtitle.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        subtitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        header_left.addWidget(title_lbl)
        header_left.addWidget(subtitle)
        header.addLayout(header_left)
        header.addStretch(1)

        btn_check = QPushButton("Check Now")
        btn_check.clicked.connect(self.test_notification)
        header.addWidget(btn_check)

        btn_sound = QPushButton("Test Sound")
        btn_sound.clicked.connect(self.test_sound)
        header.addWidget(btn_sound)

        self.pause_checkbox = QCheckBox("Pause Monitoring")
        self.pause_checkbox.setChecked(bool(self.settings.get("advanced", {}).get("paused", False)))
        self.pause_checkbox.toggled.connect(self.on_toggle_pause)
        header.addWidget(self.pause_checkbox)

        root.addLayout(header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        self.battery_percent_lbl = make_kpi_label("--%")
        self.battery_bar = QProgressBar()
        self.battery_bar.setRange(0, 100)
        self.battery_bar.setValue(0)
        self.battery_bar.setTextVisible(False)

        battery_card_content = QWidget()
        v1 = QVBoxLayout(battery_card_content)
        v1.addWidget(self.battery_percent_lbl)
        v1.addWidget(self.battery_bar)
        v1.addWidget(make_subkpi_label("Current charge"))

        grid.addWidget(make_card("🔋 Battery", battery_card_content), 0, 0)

        self.status_value_lbl = make_kpi_label("Unknown")
        grid.addWidget(make_card("⚡ Status", self.status_value_lbl), 0, 1)

        self.time_value_lbl = make_kpi_label("--")
        grid.addWidget(make_card("⏱️ Time Estimate", self.time_value_lbl), 0, 2)

        self.power_value_lbl = make_kpi_label("Unknown")
        grid.addWidget(make_card("🔌 Power Source", self.power_value_lbl), 1, 0)

        self.monitor_state_lbl = make_kpi_label("Active")
        grid.addWidget(make_card("🖥️ Monitoring", self.monitor_state_lbl), 1, 1)

        interval_val = self.settings.get("monitoring", {}).get("check_interval", 60)
        self.interval_lbl = make_kpi_label(f"{interval_val}s")
        grid.addWidget(make_card("⏰ Check Interval", self.interval_lbl), 1, 2)

        root.addLayout(grid)
        root.addStretch(1)
        self.update_dashboard()

    def update_dashboard(self):
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                self.battery_percent_lbl.setText("N/A")
                self.battery_bar.setValue(0)
                self.status_value_lbl.setText("No battery")
                self.time_value_lbl.setText("--")
                self.power_value_lbl.setText("--")
            else:
                pct = int(battery.percent)
                self.battery_percent_lbl.setText(f"{pct}%")
                self.battery_bar.setValue(pct)

                if pct <= 20:
                    self.battery_bar.setStyleSheet("QProgressBar::chunk{background-color:#c62828;border-radius:6px}")
                elif pct <= 30:
                    self.battery_bar.setStyleSheet("QProgressBar::chunk{background-color:#ef6c00;border-radius:6px}")
                elif pct >= 80:
                    self.battery_bar.setStyleSheet("QProgressBar::chunk{background-color:#2e7d32;border-radius:6px}")
                else:
                    self.battery_bar.setStyleSheet("QProgressBar::chunk{background-color:#1976d2;border-radius:6px}")

                if battery.power_plugged:
                    self.power_value_lbl.setText("AC Power Connected")
                    if pct >= 99:
                        self.status_value_lbl.setText("Fully Charged")
                        self.time_value_lbl.setText("100%")
                    else:
                        self.status_value_lbl.setText("Charging")
                        remaining_percent = 100 - pct
                        hours = remaining_percent / 50
                        self.time_value_lbl.setText(f"~{int(hours)}h {int((hours % 1) * 60)}m to full")
                else:
                    self.power_value_lbl.setText("Running on Battery")
                    self.status_value_lbl.setText("On Battery")
                    if battery.secsleft > 0 and battery.secsleft != psutil.POWER_TIME_UNLIMITED:
                        hours = battery.secsleft / 3600
                        mins = int((battery.secsleft % 3600) / 60)
                        self.time_value_lbl.setText(f"{int(hours)}h {mins}m remaining")
                    else:
                        self.time_value_lbl.setText("--")

            paused = bool(self.settings.get("advanced", {}).get("paused", False))
            self.monitor_state_lbl.setText("Paused" if paused else "Active")
        except Exception:
            self.status_value_lbl.setText("Error")

    def _init_monitoring(self):
        layout = QVBoxLayout(self.monitoring_tab)

        gb_interval = QGroupBox("Check Intervals")
        ly_interval = QVBoxLayout(gb_interval)

        self.interval_slider = QSlider(Qt.Orientation.Horizontal)
        self.interval_slider.setRange(10, 300)
        self.interval_slider.setValue(int(self.settings.get("monitoring", {}).get("check_interval", 60)))

        self.interval_value = QLabel(f"{self.interval_slider.value()} seconds")
        self.interval_slider.valueChanged.connect(lambda v: self.interval_value.setText(f"{v} seconds"))

        ly_interval.addWidget(QLabel("Check Interval (seconds):"))
        ly_interval.addWidget(self.interval_slider)
        ly_interval.addWidget(self.interval_value)

        self.smart_checkbox = QCheckBox("Smart Interval (Auto-adjust during alerts)")
        self.smart_checkbox.setChecked(bool(self.settings.get("monitoring", {}).get("smart_interval", True)))
        ly_interval.addWidget(self.smart_checkbox)

        gb_interval.setLayout(ly_interval)
        layout.addWidget(gb_interval)

        gb_th = QGroupBox("Alert Thresholds")
        ly_th = QHBoxLayout(gb_th)

        low_box = QGroupBox("Low Battery Alerts (%)")
        low_ly = QVBoxLayout(low_box)

        self.low_critical = QSpinBox()
        self.low_critical.setRange(5, 30)
        self.low_critical.setValue(int(self.settings.get("monitoring", {}).get("low_critical", 20)))

        self.low_warning = QSpinBox()
        self.low_warning.setRange(5, 40)
        self.low_warning.setValue(int(self.settings.get("monitoring", {}).get("low_warning", 25)))

        self.low_notice = QSpinBox()
        self.low_notice.setRange(15, 50)
        self.low_notice.setValue(int(self.settings.get("monitoring", {}).get("low_notice", 30)))

        low_ly.addWidget(QLabel("Critical (≤):"))
        low_ly.addWidget(self.low_critical)
        low_ly.addWidget(QLabel("Warning (≤):"))
        low_ly.addWidget(self.low_warning)
        low_ly.addWidget(QLabel("Notice (≤):"))
        low_ly.addWidget(self.low_notice)
        low_box.setLayout(low_ly)

        high_box = QGroupBox("High Battery Alerts (%)")
        high_ly = QVBoxLayout(high_box)

        self.high_notice = QSpinBox()
        self.high_notice.setRange(70, 95)
        self.high_notice.setValue(int(self.settings.get("monitoring", {}).get("high_notice", 80)))

        self.high_warning = QSpinBox()
        self.high_warning.setRange(70, 99)
        self.high_warning.setValue(int(self.settings.get("monitoring", {}).get("high_warning", 85)))

        self.high_critical = QSpinBox()
        self.high_critical.setRange(70, 100)
        self.high_critical.setValue(int(self.settings.get("monitoring", {}).get("high_critical", 90)))

        high_ly.addWidget(QLabel("Notice (≥):"))
        high_ly.addWidget(self.high_notice)
        high_ly.addWidget(QLabel("Warning (≥):"))
        high_ly.addWidget(self.high_warning)
        high_ly.addWidget(QLabel("Critical (≥):"))
        high_ly.addWidget(self.high_critical)
        high_box.setLayout(high_ly)

        ly_th.addWidget(low_box)
        ly_th.addWidget(high_box)
        gb_th.setLayout(ly_th)

        layout.addWidget(gb_th)
        layout.addStretch(1)

    def _init_notifications(self):
        layout = QVBoxLayout(self.notifications_tab)

        self.notif_enabled = QCheckBox("Enable Notifications")
        self.notif_enabled.setChecked(bool(self.settings.get("notifications", {}).get("enabled", True)))
        layout.addWidget(self.notif_enabled)

        gb_freq = QGroupBox("Notification Frequency")
        lyf = QHBoxLayout(gb_freq)

        self.notif_freq = QComboBox()
        self.notif_freq.addItems(["every", "cooldown"])
        self.notif_freq.setCurrentText(self.settings.get("notifications", {}).get("frequency", "every"))

        self.notif_cooldown = QSpinBox()
        self.notif_cooldown.setRange(60, 1800)
        self.notif_cooldown.setValue(int(self.settings.get("notifications", {}).get("cooldown", 300)))

        lyf.addWidget(QLabel("Mode:"))
        lyf.addWidget(self.notif_freq)
        lyf.addWidget(QLabel("Cooldown (s):"))
        lyf.addWidget(self.notif_cooldown)
        gb_freq.setLayout(lyf)

        layout.addWidget(gb_freq)
        layout.addStretch(1)

    def _init_audio(self):
        layout = QVBoxLayout(self.audio_tab)

        self.audio_enabled = QCheckBox("Enable Audio Alerts")
        self.audio_enabled.setChecked(bool(self.settings.get("audio", {}).get("enabled", True)))
        layout.addWidget(self.audio_enabled)

        gb_af = QGroupBox("Audio Frequency")
        laf = QHBoxLayout(gb_af)

        self.audio_freq = QComboBox()
        self.audio_freq.addItems(["every", "once", "cooldown"])
        self.audio_freq.setCurrentText(self.settings.get("audio", {}).get("frequency", "every"))

        self.audio_cooldown = QSpinBox()
        self.audio_cooldown.setRange(60, 1800)
        self.audio_cooldown.setValue(int(self.settings.get("audio", {}).get("cooldown", 300)))

        laf.addWidget(QLabel("Mode:"))
        laf.addWidget(self.audio_freq)
        laf.addWidget(QLabel("Cooldown (s):"))
        laf.addWidget(self.audio_cooldown)
        gb_af.setLayout(laf)
        layout.addWidget(gb_af)

        gb_beep = QGroupBox("Beep Customization")
        lbeep = QHBoxLayout(gb_beep)

        self.beep_freq = QSpinBox()
        self.beep_freq.setRange(200, 5000)
        self.beep_freq.setValue(int(self.settings.get("audio", {}).get("beep_frequency", 1000)))

        self.beep_dur = QSpinBox()
        self.beep_dur.setRange(100, 5000)
        self.beep_dur.setValue(int(self.settings.get("audio", {}).get("beep_duration", 700)))

        lbeep.addWidget(QLabel("Frequency (Hz):"))
        lbeep.addWidget(self.beep_freq)
        lbeep.addWidget(QLabel("Duration (ms):"))
        lbeep.addWidget(self.beep_dur)
        gb_beep.setLayout(lbeep)
        layout.addWidget(gb_beep)

        gb_hp = QGroupBox("Headphone Reduction")
        lhp = QHBoxLayout(gb_hp)

        self.reduce_hp = QCheckBox("Reduce when headphones detected")
        self.reduce_hp.setChecked(bool(self.settings.get("audio", {}).get("reduce_on_headphones", True)))

        self.hp_factor = QSpinBox()
        self.hp_factor.setRange(20, 100)
        self.hp_factor.setValue(int(float(self.settings.get("audio", {}).get("headphones_reduction_factor", 0.6)) * 100))

        lhp.addWidget(self.reduce_hp)
        lhp.addWidget(QLabel("Reduction (% duration):"))
        lhp.addWidget(self.hp_factor)
        gb_hp.setLayout(lhp)
        layout.addWidget(gb_hp)

        gb_levels = QGroupBox("Per-Level Audio Enable")
        ll = QVBoxLayout(gb_levels)

        ebl = self.settings.get("audio", {}).get("enabled_by_level", {})
        self.chk_notice_low = QCheckBox("Low Notice")
        self.chk_notice_low.setChecked(bool(ebl.get("notice_low", True)))
        self.chk_warning_low = QCheckBox("Low Warning")
        self.chk_warning_low.setChecked(bool(ebl.get("warning_low", True)))
        self.chk_critical_low = QCheckBox("Low Critical")
        self.chk_critical_low.setChecked(bool(ebl.get("critical_low", True)))
        self.chk_high_notice = QCheckBox("High Notice")
        self.chk_high_notice.setChecked(bool(ebl.get("high_notice", True)))
        self.chk_high_warning = QCheckBox("High Warning")
        self.chk_high_warning.setChecked(bool(ebl.get("high_warning", True)))
        self.chk_high_critical = QCheckBox("High Critical")
        self.chk_high_critical.setChecked(bool(ebl.get("high_critical", True)))

        for w in (self.chk_notice_low, self.chk_warning_low, self.chk_critical_low,
                  self.chk_high_notice, self.chk_high_warning, self.chk_high_critical):
            ll.addWidget(w)
        gb_levels.setLayout(ll)
        layout.addWidget(gb_levels)

        layout.addStretch(1)

    def on_save(self):
        self.settings.setdefault("ui", {})["theme"] = "qt_dark"
        mon = self.settings.setdefault("monitoring", {})
        mon["check_interval"] = int(self.interval_slider.value())
        mon["smart_interval"] = bool(self.smart_checkbox.isChecked())
        mon["low_critical"] = int(self.low_critical.value())
        mon["low_warning"] = int(self.low_warning.value())
        mon["low_notice"] = int(self.low_notice.value())
        mon["high_notice"] = int(self.high_notice.value())
        mon["high_warning"] = int(self.high_warning.value())
        mon["high_critical"] = int(self.high_critical.value())

        notif = self.settings.setdefault("notifications", {})
        notif["enabled"] = bool(self.notif_enabled.isChecked())
        notif["frequency"] = self.notif_freq.currentText()
        notif["cooldown"] = int(self.notif_cooldown.value())

        aud = self.settings.setdefault("audio", {})
        aud["enabled"] = bool(self.audio_enabled.isChecked())
        aud["frequency"] = self.audio_freq.currentText()
        aud["cooldown"] = int(self.audio_cooldown.value())
        aud["beep_frequency"] = int(self.beep_freq.value())
        aud["beep_duration"] = int(self.beep_dur.value())
        aud["reduce_on_headphones"] = bool(self.reduce_hp.isChecked())
        aud["headphones_reduction_factor"] = max(0.2, min(1.0, float(self.hp_factor.value()) / 100.0))

        aud["enabled_by_level"] = {
            "notice_low": bool(self.chk_notice_low.isChecked()),
            "warning_low": bool(self.chk_warning_low.isChecked()),
            "critical_low": bool(self.chk_critical_low.isChecked()),
            "high_notice": bool(self.chk_high_notice.isChecked()),
            "high_warning": bool(self.chk_high_warning.isChecked()),
            "high_critical": bool(self.chk_high_critical.isChecked()),
        }

        save_settings(self.settings)
        QMessageBox.information(self, "Saved", "Settings saved successfully.")

    def on_export(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Export Settings", str(Path.home() / "settings.json"), "JSON Files (*.json)")
        if fn:
            try:
                with open(fn, "w", encoding="utf-8") as f:
                    json.dump(self.settings, f, indent=4)
                QMessageBox.information(self, "Export", "Settings exported successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export: {e}")

    def on_import(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Import Settings", str(Path.home()), "JSON Files (*.json)")
        if fn:
            try:
                with open(fn, "r", encoding="utf-8") as f:
                    imported = json.load(f)
                merged = load_settings()
                for k, v in imported.items():
                    if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
                        merged[k].update(v)
                    else:
                        merged[k] = v
                self.settings = merged
                save_settings(self.settings)
                QMessageBox.information(self, "Import", "Settings imported. Restart this window to reload UI values.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import: {e}")

    def on_toggle_pause(self, checked: bool):
        self.settings.setdefault("advanced", {})["paused"] = bool(checked)
        save_settings(self.settings)

    def apply_theme(self, theme_key: str):
        QFont = PySide6.QtGui.QFont if hasattr(PySide6.QtGui, 'QFont') else QFont
        QApplication.setStyle("Fusion")
        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window, QColor(31, 31, 31))
        pal.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        pal.setColor(QPalette.ColorRole.Base, QColor(23, 23, 23))
        pal.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 45))
        pal.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        pal.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        pal.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        pal.setColor(QPalette.ColorRole.Button, QColor(33, 33, 33))
        pal.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        pal.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        pal.setColor(QPalette.ColorRole.Highlight, QColor(150, 150, 243))
        pal.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        self.setPalette(pal)
        self.setFont(QFont("Segoe UI", 9))

    def test_notification(self):
        try:
            from battery_monitor import show_notification
            show_notification("This is a test notification from Qt GUI.", alert_level="info")
        except Exception:
            QMessageBox.information(self, "Notification", "Test notification requested.")

    def test_sound(self):
        freq = int(self.beep_freq.value()) if hasattr(self, 'beep_freq') else 1000
        dur = int(self.beep_dur.value()) if hasattr(self, 'beep_dur') else 300
        try:
            import winsound
            winsound.Beep(freq, dur)
        except ImportError:
            QMessageBox.information(self, "Audio Test", "Audio test beep is supported on Windows (winsound).")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to play sound: {e}")


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
