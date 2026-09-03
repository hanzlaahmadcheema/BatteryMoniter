from __future__ import annotations

import sys
import os
import threading
from pathlib import Path

from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

import battery_monitor as bm


class TrayApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.tray = QSystemTrayIcon()
        self.menu = QMenu()
        self.is_running = False
        self.monitor_thread = None

        self.action_check = QAction("Check Now")
        self.action_pause = QAction("Pause Monitoring")
        self.action_startup = QAction("Start with Windows")
        self.action_startup.setCheckable(True)
        self.action_startup.setChecked(bm.is_startup_enabled())
        self.action_snooze_30 = QAction("Snooze 30 min")
        self.action_snooze_60 = QAction("Snooze 60 min")
        self.action_snooze_120 = QAction("Snooze 120 min")
        self.action_settings = QAction("Settings")
        self.action_quit = QAction("Quit")

        self.action_check.triggered.connect(self.check_now)
        self.action_pause.triggered.connect(self.toggle_pause)
        self.action_startup.triggered.connect(self.toggle_startup)
        self.action_settings.triggered.connect(self.open_settings)
        self.action_quit.triggered.connect(self.quit)

        self.action_snooze_30.triggered.connect(lambda: self.snooze(30))
        self.action_snooze_60.triggered.connect(lambda: self.snooze(60))
        self.action_snooze_120.triggered.connect(lambda: self.snooze(120))

        snooze_menu = QMenu("Snooze", self.menu)
        snooze_menu.addAction(self.action_snooze_30)
        snooze_menu.addAction(self.action_snooze_60)
        snooze_menu.addAction(self.action_snooze_120)

        self.menu.addAction(self.action_check)
        self.menu.addAction(self.action_pause)
        self.menu.addAction(self.action_startup)
        self.menu.addMenu(snooze_menu)
        self.menu.addSeparator()
        self.menu.addAction(self.action_settings)
        self.menu.addSeparator()
        self.menu.addAction(self.action_quit)

        self.tray.setContextMenu(self.menu)
        self.tray.setToolTip("HA Battery Monitor")

        # Set default icon
        try:
            self.tray.setIcon(QIcon.fromTheme("battery", self.app.style().standardIcon(getattr(self.app.style().StandardPixmap, 'SP_ComputerIcon', 0))))
        except Exception:
            pass

        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

        bm.load_settings()

        if not bm.create_single_instance_check():
            try:
                self.tray.showMessage("HA Battery Monitor", "Already running.", QSystemTrayIcon.MessageIcon.Information, 3000)
            except Exception:
                pass
            sys.exit(0)

        try:
            bm.update_tray_icon = lambda: None
            bm.setup_tray = lambda: None
        except Exception:
            pass

        self.is_running = True
        self.monitor_thread = threading.Thread(
            target=bm.run_monitoring,
            args=(bm.app_settings.get("monitoring", {}).get("check_interval", 60),),
            daemon=True
        )
        self.monitor_thread.start()
        self.refresh_pause_label()

    def refresh_pause_label(self):
        paused = bm.app_settings.get("advanced", {}).get("paused", False)
        self.action_pause.setText("Resume Monitoring" if paused else "Pause Monitoring")

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            try:
                battery = bm.check_battery_status()
                if battery:
                    msg = f"Battery: {battery.percent}% ({'Charging' if battery.power_plugged else 'Not Charging'})"
                else:
                    msg = "No battery detected"
                self.tray.showMessage("HA Battery Monitor", msg, QSystemTrayIcon.MessageIcon.Information, 3000)
            except Exception:
                pass

    def check_now(self):
        try:
            battery = bm.check_battery_status()
            if not battery:
                bm.show_notification("No battery detected on this system", alert_level="warning")
                return
            status_msg = f"Battery: {battery.percent}% ({'Charging' if battery.power_plugged else 'Not Charging'})"
            bm.show_notification(status_msg, alert_level="info")

            if not bm.app_settings.get("advanced", {}).get("paused", False):
                should_alert, alert_message, alert_level = bm.check_battery_alerts_v2(battery)
                if should_alert:
                    bm.show_notification(alert_message, alert_level=alert_level)
                    if bm.app_settings.get("audio", {}).get("enabled", True):
                        bm.play_sound(alert_level)
        except Exception as e:
            self.tray.showMessage("HA Battery Monitor", f"Check failed: {e}", QSystemTrayIcon.MessageIcon.Critical, 3000)

    def snooze(self, minutes: int):
        try:
            bm.set_snooze(minutes)
            self.tray.showMessage("HA Battery Monitor", f"Alerts snoozed for {minutes} minutes", QSystemTrayIcon.MessageIcon.Information, 3000)
        except Exception as e:
            self.tray.showMessage("HA Battery Monitor", f"Failed to snooze: {e}", QSystemTrayIcon.MessageIcon.Critical, 3000)

    def toggle_pause(self):
        try:
            adv = bm.app_settings.setdefault("advanced", {})
            adv["paused"] = not adv.get("paused", False)
            bm.save_settings()
            self.refresh_pause_label()
            bm.show_notification("Monitoring paused" if adv["paused"] else "Monitoring resumed", alert_level="info")
        except Exception as e:
            self.tray.showMessage("HA Battery Monitor", f"Pause toggle failed: {e}", QSystemTrayIcon.MessageIcon.Critical, 3000)

    def toggle_startup(self, checked: bool):
        try:
            bm.set_startup_enabled(checked)
            adv = bm.app_settings.setdefault("advanced", {})
            adv["start_with_windows"] = checked
            bm.save_settings()
            msg = "Start with Windows enabled" if checked else "Start with Windows disabled"
            self.tray.showMessage("HA Battery Monitor", msg, QSystemTrayIcon.MessageIcon.Information, 3000)
        except Exception as e:
            self.tray.showMessage("HA Battery Monitor", f"Failed to toggle startup: {e}", QSystemTrayIcon.MessageIcon.Critical, 3000)

    def open_settings(self):
        try:
            import subprocess
            creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
            subprocess.Popen([sys.executable, str(BASE_DIR / "qt_gui.py")], creationflags=creationflags)
        except Exception as e:
            self.tray.showMessage("HA Battery Monitor", f"Failed to open Settings: {e}", QSystemTrayIcon.MessageIcon.Critical, 3000)

    def quit(self):
        self.is_running = False
        self.tray.hide()
        QApplication.quit()

    def run(self):
        sys.exit(self.app.exec())


def main():
    app = TrayApp()
    app.run()


if __name__ == '__main__':
    main()
