import sys
import os
import time

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
import json
import logging
import argparse
import subprocess
import threading
import tempfile
import atexit
import socket
from pathlib import Path
from collections import deque
from typing import Optional, Tuple, Any, Dict

try:
    import psutil
except ImportError:
    psutil = None
try:
    import winsound
except ImportError:
    winsound = None

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None
    Image = None
    ImageDraw = None

try:
    import tkinter as tk
    from tkinter import messagebox
except ImportError:
    tk = None
    messagebox = None


BEEP_FREQUENCY = 1000
BEEP_DURATION = 700

tray_icon = None
current_battery_percent = 0
current_status = "Starting..."
last_error = None
verbose_logging = False

config_file: Optional[Path] = None
app_settings: Dict[str, Any] = {}
config_last_modified: float = 0.0

rate_samples = deque(maxlen=180)
ema_rate_per_min = 0.0
snooze_until_ts = 0.0
last_alert_percent = None

instance_socket = None
instance_lock_file = None
instance_mutex = None


def get_config_path() -> Path:
    """Determine the configuration file path with portable-first and user-dir fallback."""
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


config_file = get_config_path()


def create_single_instance_check() -> bool:
    """Create a single instance check using platform mutex/lockfile with socket fallback."""
    global instance_mutex, instance_lock_file, instance_socket
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            mutex_name = "Local\\HABatteryMonitor_SingleInstance_Mutex"
            instance_mutex = kernel32.CreateMutexW(None, False, mutex_name)
            last_err = kernel32.GetLastError()
            ERROR_ALREADY_EXISTS = 183
            if last_err == ERROR_ALREADY_EXISTS:
                return False
            atexit.register(cleanup_single_instance)
            return True
        except Exception:
            pass

    try:
        uid = getattr(os, 'getuid', lambda: 'default')()
        lock_path = Path(tempfile.gettempdir()) / f"ha_battery_monitor_{uid}.lock"
        try:
            import fcntl
            instance_lock_file = open(lock_path, "w")
            fcntl.flock(instance_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            instance_lock_file.write(str(os.getpid()))
            instance_lock_file.flush()
            atexit.register(cleanup_single_instance)
            return True
        except (ImportError, IOError, OSError):
            if instance_lock_file:
                try:
                    instance_lock_file.close()
                except Exception:
                    pass
    except Exception:
        pass

    try:
        instance_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        instance_socket.bind(("127.0.0.1", 54321))
        instance_socket.listen(1)
        atexit.register(cleanup_single_instance)
        return True
    except socket.error:
        return False


def cleanup_single_instance():
    """Clean up single instance handles."""
    global instance_mutex, instance_lock_file, instance_socket
    if instance_mutex and os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(instance_mutex)
        except Exception:
            pass
        instance_mutex = None

    if instance_lock_file:
        try:
            import fcntl
            fcntl.flock(instance_lock_file.fileno(), fcntl.LOCK_UN)
            instance_lock_file.close()
        except Exception:
            pass
        instance_lock_file = None

    if instance_socket:
        try:
            instance_socket.close()
        except Exception:
            pass
        instance_socket = None


def handle_already_running():
    """Handle the case when the application is already running."""
    try:
        if tk and messagebox:
            root = tk.Tk()
            root.withdraw()
            result = messagebox.askyesno(
                "HA Battery Monitor Already Running",
                "HA Battery Monitor is already running!\n\nYou can find it in the system tray (notification area).\nRight-click the battery icon to access Settings.\n\nWould you like to open the Settings GUI?",
                icon="info"
            )
            if result:
                open_settings_gui(None, None)
            root.destroy()
            return
    except Exception:
        pass
    print("[INFO] HA Battery Monitor is already running!")
    print("[INFO] Look for the battery icon in your system tray.")
    print("[INFO] Right-click the tray icon to access Settings.")


def check_config_changes() -> Tuple[bool, Optional[int]]:
    """Check if config file has been modified and reload if necessary."""
    global config_last_modified, app_settings
    try:
        if config_file and os.path.exists(config_file):
            current_modified = os.path.getmtime(config_file)
            if current_modified > config_last_modified:
                config_last_modified = current_modified
                log_message("🔄 Configuration file changed, reloading settings...", "INFO")
                old_settings = app_settings.copy()
                load_settings()

                interval_changed = False
                new_interval = None

                old_monitoring = old_settings.get("monitoring", {})
                new_monitoring = app_settings.get("monitoring", {})

                if old_monitoring != new_monitoring:
                    log_message("⚙️ Settings updated from GUI changes:", "INFO")
                    if old_monitoring.get("low_notice") != new_monitoring.get("low_notice"):
                        log_message(f"  • Low Notice Alert: {old_monitoring.get('low_notice')}% → {new_monitoring.get('low_notice')}%", "INFO")
                    if old_monitoring.get("check_interval") != new_monitoring.get("check_interval"):
                        old_interval = old_monitoring.get("check_interval")
                        new_interval = new_monitoring.get("check_interval")
                        log_message(f"  • Check Interval: {old_interval}s → {new_interval}s", "INFO")
                        interval_changed = True

                old_notifications = old_settings.get("notifications", {})
                new_notifications = app_settings.get("notifications", {})
                if old_notifications != new_notifications:
                    status = "Enabled" if new_notifications.get("enabled") else "Disabled"
                    log_message(f"  • Notifications: {status}", "INFO")

                old_audio = old_settings.get("audio", {})
                new_audio = app_settings.get("audio", {})
                if old_audio != new_audio:
                    status = "Enabled" if new_audio.get("enabled") else "Disabled"
                    log_message(f"  • Audio Alerts: {status}", "INFO")

                old_advanced = old_settings.get("advanced", {})
                new_advanced = app_settings.get("advanced", {})
                if old_advanced != new_advanced:
                    status = "Paused" if new_advanced.get("paused") else "Active"
                    log_message(f"  • Monitoring: {status}", "INFO")

                if hasattr(check_battery_alerts_v2, "last_level"):
                    delattr(check_battery_alerts_v2, "last_level")
                    log_message("  • Alert level tracking reset for immediate effect", "INFO")

                log_message("✅ Settings reloaded successfully - changes applied!", "INFO")
                return interval_changed, new_interval
            return False, None
    except Exception as e:
        log_message(f"Error checking config changes: {e}", "ERROR")
    return False, None


def load_settings() -> Dict[str, Any]:
    """Load settings from configuration file."""
    global app_settings, config_last_modified
    default_settings = {
        "monitoring": {
            "check_interval": 60,
            "smart_interval": True,
            "min_interval": 10,
            "hysteresis_band": 2,
            "smart_interval_v2": True,
            "ema_alpha": 0.3,
            "roc_alert_enabled": True,
            "roc_rate_percent_per_min": 0.7,
            "roc_min_window_min": 2,
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

    if config_file and os.path.exists(config_file):
        try:
            config_last_modified = os.path.getmtime(config_file)
            with open(config_file, "r") as f:
                loaded_settings = json.load(f)
                settings = default_settings.copy()
                for category in ["monitoring", "notifications", "audio", "advanced"]:
                    if category in loaded_settings and isinstance(loaded_settings[category], dict):
                        settings[category].update(loaded_settings[category])
                    elif category in loaded_settings:
                        settings[category] = loaded_settings[category]
                app_settings = settings
                log_message("Settings loaded from config file", "INFO")
                return app_settings
        except Exception as e:
            log_message(f"Error loading settings: {e}, using defaults", "ERROR")

    app_settings = default_settings.copy()
    log_message("Using default settings (no config file found)", "INFO")
    return app_settings


def save_settings():
    """Persist current app_settings to configuration file safely."""
    global config_file, app_settings
    try:
        if config_file:
            with open(config_file, "w") as f:
                json.dump(app_settings, f, indent=4)
            log_message("Settings saved to config file", "INFO")
    except Exception as e:
        log_message(f"Error saving settings: {e}", "ERROR")


def open_settings_gui(icon=None, item=None):
    """Open the Qt (PySide6) settings GUI only (no fallback)."""
    base_dir = Path(__file__).parent
    qt_script = base_dir / "qt_gui.py"
    try:
        import importlib.util
        pyside_spec = importlib.util.find_spec("PySide6")
        if not qt_script.exists() or pyside_spec is None:
            log_message("Qt GUI not available (qt_gui.py missing or PySide6 not installed)", "ERROR")
            show_notification("Settings GUI unavailable: Install PySide6 to use the Qt Settings.", alert_level="warning")
            return

        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
        subprocess.Popen([sys.executable, str(qt_script)], creationflags=creationflags)
        log_message("Qt Settings GUI launched", "INFO")
    except Exception as e:
        log_message(f"Error launching Qt settings GUI: {e}", "ERROR")


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def log_message(message: str, level: str = "INFO"):
    """Log message to console using logging module."""
    if not verbose_logging and level not in ("ERROR", "CRITICAL"):
        return
    log_func = getattr(logging, level.lower(), logging.info)
    if level == "WARNING":
        message = f"⚠️  {message}"
    elif level == "NOTIFICATION":
        message = f"🔔 {message.replace('NOTIFICATION: ', '')}"
    log_func(message)


def create_tray_image(percent: int, is_charging: bool, has_error: bool = False):
    """Create a system tray icon showing battery percentage."""
    if Image is None or ImageDraw is None:
        return None
    image = Image.new('RGB', (64, 64), color='white')
    draw = ImageDraw.Draw(image)

    if has_error:
        color = 'red'
    elif is_charging:
        color = 'green'
    elif percent <= 20:
        color = 'red'
    elif percent <= 30:
        color = 'orange'
    else:
        color = 'blue'

    draw.rectangle([10, 20, 50, 50], outline=color, width=2)
    draw.rectangle([50, 25, 54, 35], fill=color)

    fill_height = int((percent / 100) * 28)
    if fill_height > 0:
        draw.rectangle([12, 48 - fill_height, 48, 48], fill=color)

    text = f"{percent}%"
    draw.text((16, 52), text, fill='black')
    return image


def update_tray_icon():
    """Update the system tray icon with current battery status."""
    global tray_icon, current_battery_percent, current_status, last_error
    if tray_icon is None:
        return
    try:
        battery = psutil.sensors_battery()
        if battery:
            is_charging = battery.power_plugged
            has_error = last_error is not None
            icon_image = create_tray_image(current_battery_percent, is_charging, has_error)
            if icon_image:
                tray_icon.icon = icon_image
            status_text = f"Battery: {current_battery_percent}%"
            if is_charging:
                status_text += " (Charging)"
            else:
                status_text += " (Not Charging)"
            if last_error:
                status_text += f"\nError: {last_error}"
            tray_icon.title = status_text
    except Exception as e:
        log_message(f"Error updating tray icon: {e}", "ERROR")


def show_status():
    """Show current battery status in tray menu."""
    try:
        battery = psutil.sensors_battery()
        if battery:
            status_msg = f"Battery: {battery.percent}% ({'Charging' if battery.power_plugged else 'Not Charging'})"
            log_message(f"Tray status requested: {status_msg}", "INFO")
            show_notification(status_msg, alert_level="info")
        else:
            log_message("Tray status requested: No battery detected", "WARNING")
            show_notification("No battery detected on this system", alert_level="warning")
    except Exception as e:
        log_message(f"Error getting battery status: {e}", "ERROR")


def quit_app(icon=None, item=None):
    """Quit the application."""
    log_message("Application shutting down...", "INFO")
    if icon:
        icon.stop()
    os._exit(0)


def toggle_pause_state(icon=None, item=None):
    """Toggle advanced.paused in settings and refresh tray menu."""
    try:
        advanced = app_settings.setdefault("advanced", {})
        current = advanced.get("paused", False)
        advanced["paused"] = not current
        save_settings()
        msg = "Monitoring paused" if advanced["paused"] else "Monitoring resumed"
        log_message(msg, "INFO")
        refresh_tray_menu()
        show_notification(msg, alert_level="info")
    except Exception as e:
        log_message(f"Failed to toggle pause: {e}", "ERROR")


def check_now(icon=None, item=None):
    """Force an immediate battery check and show a notification (and optional sound)."""
    try:
        battery = check_battery_status()
        if not battery:
            show_notification("No battery detected on this system", alert_level="warning")
            return
        status_msg = f"Battery: {battery.percent}% ({'Charging' if battery.power_plugged else 'Not Charging'})"
        show_notification(status_msg, alert_level="info")
        if not app_settings.get("advanced", {}).get("paused", False):
            should_alert, alert_message, alert_level = check_battery_alerts_v2(battery)
            if should_alert:
                show_notification(alert_message, alert_level=alert_level)
                if app_settings.get("audio", {}).get("enabled", True):
                    play_sound(alert_level)
    except Exception as e:
        log_message(f"Check Now failed: {e}", "ERROR")


def refresh_tray_menu():
    """Rebuild the tray menu to reflect current state (e.g., pause/resume label)."""
    global tray_icon
    if tray_icon is None or pystray is None:
        return
    try:
        is_paused = app_settings.get("advanced", {}).get("paused", False)
        pause_label = "Resume Monitoring" if is_paused else "Pause Monitoring"
        new_menu = pystray.Menu(
            pystray.MenuItem("Check Now", check_now),
            pystray.MenuItem("Show Status", lambda icon, item: show_status()),
            pystray.MenuItem(pause_label, toggle_pause_state),
            pystray.MenuItem("Settings", open_settings_gui),
            pystray.MenuItem("Quit", quit_app)
        )
        tray_icon.menu = new_menu
    except Exception as e:
        log_message(f"Error updating tray menu: {e}", "ERROR")


def setup_tray():
    """Setup system tray icon with menu."""
    global tray_icon
    if pystray is None or Image is None:
        return
    icon_image = create_tray_image(0, False)
    if icon_image is None:
        return
    menu = pystray.Menu(
        pystray.MenuItem("Check Now", check_now),
        pystray.MenuItem("Show Status", lambda icon, item: show_status()),
        pystray.MenuItem("Pause Monitoring", toggle_pause_state),
        pystray.MenuItem("Settings", open_settings_gui),
        pystray.MenuItem("Quit", quit_app)
    )
    tray_icon = pystray.Icon("ha_battery_monitor", icon_image, "HA Battery Monitor - Starting...", menu)


def check_battery_status():
    """Check the battery status (plugged in or not)."""
    global last_error
    try:
        if psutil is None:
            log_message("psutil not available", "WARNING")
            last_error = "psutil not available"
            return None
        battery = psutil.sensors_battery()
        if battery is None:
            log_message("No battery detected!", "WARNING")
            last_error = "No battery detected"
            return None
        last_error = None
        return battery
    except Exception as e:
        log_message(f"Error checking battery status: {e}", "ERROR")
        last_error = str(e)
        return None


def get_notification_icon(alert_level: str) -> str:
    """Get appropriate icon for notification based on alert level."""
    lvl = alert_level.lower()
    if "critical" in lvl or "20%" in lvl:
        return "[system.windows.forms.tooltipicon]::Error"
    elif "warning" in lvl or "25%" in lvl:
        return "[system.windows.forms.tooltipicon]::Warning"
    elif "high" in lvl or "80%" in lvl:
        return "[system.windows.forms.tooltipicon]::Info"
    return "[system.windows.forms.tooltipicon]::Info"


def show_native_notification(title: str, message: str, alert_level: str = "info") -> bool:
    """Show Windows native toast notification using PowerShell with appropriate icon."""
    if os.name != "nt":
        return False
    try:
        icon_type = get_notification_icon(alert_level)

        def _ps_literal(s: str) -> str:
            """Return a PowerShell‑compatible literal string."""
            return s.replace("`", "``").replace('"', '`"').replace("$", "`$")

        ps_script = f"""
param(
    [string]$title,
    [string]$message,
    [string]$icon
)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Information
$notify.Visible = $true
$notify.BalloonTipTitle = $title
$notify.BalloonTipText = $message
$notify.BalloonTipIcon = $icon
$notify.ShowBalloonTip(8000)
Start-Sleep -Seconds 2
$notify.Dispose()
"""
        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        subprocess.Popen([
            "powershell.exe",
            "-WindowStyle", "Hidden",
            "-ExecutionPolicy", "Bypass",
            "-Command", ps_script,
            "-ArgumentList", f'"{_ps_literal(title)}"', f'"{_ps_literal(message)}"', icon_type
        ], creationflags=creationflags)
        return True
    except Exception as e:
        log_message(f"PowerShell notification failed: {e}", "ERROR")
        return False


def show_win10_toast_notification(title: str, message: str, alert_level: str = "info") -> bool:
    """Show Windows 10/11 style toast notification."""
    if os.name != "nt":
        return False
    try:
        import html
        lvl = alert_level.lower()
        if "critical" in lvl or "20%" in lvl:
            emoji = "🔴"
            urgency = "CRITICAL"
        elif "warning" in lvl or "25%" in lvl:
            emoji = "🟠"
            urgency = "WARNING"
        elif "notice" in lvl or "30%" in lvl:
            emoji = "🟡"
            urgency = "NOTICE"
        elif "high" in lvl or "80%" in lvl:
            emoji = "🟢"
            urgency = "FULL"
        else:
            emoji = "🔋"
            urgency = "INFO"

        enhanced_title = f"{emoji} HA Battery Monitor - {urgency}"
        enhanced_message = message

        xml_title = html.escape(enhanced_title)
        xml_message = html.escape(enhanced_message)

        safe_ps_title = enhanced_title.replace("`", "``").replace('"', '`"').replace("$", "`$")
        safe_ps_message = enhanced_message.replace("`", "``").replace('"', '`"').replace("$", "`$")

        toast_script = f"""
        $ErrorActionPreference = "SilentlyContinue"
        
        # Try modern toast notification
        try {{
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
            
            $template = @"
<toast>
    <visual>
        <binding template="ToastText02">
            <text id="1">{xml_title}</text>
            <text id="2">{xml_message}</text>
        </binding>
    </visual>
    <audio src="ms-winsoundevent:Notification.Default" />
</toast>
"@
            
            $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
            $xml.LoadXml($template)
            $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("HA Battery Monitor").Show($toast)
        }} catch {{
            # Fallback to balloon tip
            Add-Type -AssemblyName System.Windows.Forms
            $notify = New-Object System.Windows.Forms.NotifyIcon
            $notify.Icon = [System.Drawing.SystemIcons]::Information
            $notify.Visible = $true
            $notify.ShowBalloonTip(5000, "{safe_ps_title}", "{safe_ps_message}", [System.Windows.Forms.ToolTipIcon]::Info)
            Start-Sleep -Seconds 3
            $notify.Dispose()
        }}
        """
        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        subprocess.Popen([
            "powershell.exe",
            "-WindowStyle", "Hidden",
            "-ExecutionPolicy", "Bypass",
            "-Command", toast_script
        ], creationflags=creationflags)
        return True
    except Exception as e:
        log_message(f"Toast notification failed: {e}", "ERROR")
        return False


def show_simple_notification(title: str, message: str) -> bool:
    """Show simple message box notification as fallback."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        threading.Thread(
            target=lambda: ctypes.windll.user32.MessageBoxW(0, message, title, 4160),
            daemon=True
        ).start()
        return True
    except Exception as e:
        log_message(f"Simple notification failed: {e}", "ERROR")
        return False


def show_notification(message: str, alert_level: str = "info"):
    """Show a notification using multiple fallback methods with enhanced styling."""
    title = "🔋 HA Battery Monitor"
    try:
        if show_win10_toast_notification(title, message, alert_level):
            log_message(f"Toast notification sent: {message}", "INFO")
            return
        if show_native_notification(title, message, alert_level):
            log_message(f"Balloon notification sent: {message}", "INFO")
            return
        if show_simple_notification(title, message):
            log_message(f"MessageBox notification sent: {message}", "INFO")
            return
        log_message(f"🔔 NOTIFICATION: {message}", "WARNING")
    except Exception as e:
        log_message(f"All notification methods failed: {e}", "ERROR")


def detect_headphones_connected() -> Optional[bool]:
    """Attempt to detect if default audio render device is a headphone/headset."""
    if os.name != "nt":
        return None
    try:
        ps = """
        try {
            $de = New-Object -ComObject MMDeviceEnumerator
            $eRender = 0
            $eMultimedia = 1
            $dev = $de.GetDefaultAudioEndpoint($eRender, $eMultimedia)
            $name = $dev.FriendlyName
            $name
        } catch {
            # Fallback to empty
        }
        """
        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        proc = subprocess.Popen(
            ["powershell.exe", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-Command", ps],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags
        )
        out, _ = proc.communicate(timeout=3)
        name = out.decode("utf-8", errors="ignore").strip().lower()
        keywords = ("headphone", "headset", "earbud", "earphones")
        return any(k in name for k in keywords)
    except Exception:
        return None


def play_sound(alert_level: str = "info"):
    """Play a configurable beep sound based on settings and context."""
    audio_cfg = app_settings.get("audio", {})
    if not audio_cfg.get("enabled", True):
        return

    enabled_by_level = audio_cfg.get("enabled_by_level", {})
    if alert_level in enabled_by_level and not enabled_by_level[alert_level]:
        log_message(f"Audio suppressed for level {alert_level}", "INFO")
        return

    freq = int(audio_cfg.get("beep_frequency", BEEP_FREQUENCY))
    dur = int(audio_cfg.get("beep_duration", BEEP_DURATION))

    if audio_cfg.get("reduce_on_headphones", True):
        hp = detect_headphones_connected()
        if hp:
            factor = float(audio_cfg.get("headphones_reduction_factor", 0.6))
            freq = max(100, int(freq * 0.8))
            dur = max(200, int(dur * factor))
            log_message("Headphones detected: reducing beep intensity", "INFO")

    if winsound is None:
        log_message("Audio disabled: winsound module not available (not on Windows).", "WARNING")
        return

    try:
        winsound.Beep(freq, dur)
        log_message(f"Alert sound played ({freq}Hz, {dur}ms)", "INFO")
    except Exception as e:
        log_message(f"Error playing sound: {e}", "ERROR")


def check_battery_alerts(battery, last_alert_level: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """Check if the battery level meets low or high battery conditions."""
    percent = battery.percent
    plugged_in = battery.power_plugged

    if not plugged_in:
        if percent <= 20:
            log_message(f"CRITICAL: Battery at {percent}% - Immediate charging required!", "CRITICAL")
            return True, f"Battery is critically low ({percent}%)! Plug in your charger!", "critical_low"
        elif percent <= 25:
            log_message(f"WARNING: Battery at {percent}% - Charging recommended", "WARNING")
            return True, f"Battery is low ({percent}%)! Plug in your charger!", "low_warning"
        elif percent <= 30:
            log_message(f"NOTICE: Battery at {percent}% - Consider charging soon", "INFO")
            return True, f"Battery is getting low ({percent}%)! Plug in your charger.", "low_notice"
    else:
        if percent >= 90:
            log_message(f"CRITICAL: Battery at {percent}% - Consider unplugging to prevent overcharging", "CRITICAL")
            return True, f"Battery is almost full ({percent}%)! Consider unplugging the charger.", "high_critical"
        elif percent >= 85:
            log_message(f"INFO: Battery at {percent}% - Nearly full", "WARNING")
            return True, f"Battery is nearly full ({percent}%)! Consider unplugging charger.", "high_warning"
        elif percent >= 80:
            log_message(f"NOTICE: Battery at {percent}% - Approaching full charge", "INFO")
            return True, f"Battery is at {percent}%. Almost full, unplug to prevent overcharging.", "high_notice"

    return False, None, None


def check_battery_alerts_v2(battery) -> Tuple[bool, Optional[str], Optional[str]]:
    """Improved battery alert logic with better user experience using config settings."""
    percent = battery.percent
    plugged_in = battery.power_plugged

    monitoring_settings = app_settings.get("monitoring", {})
    low_critical = monitoring_settings.get("low_critical", 20)
    low_warning = monitoring_settings.get("low_warning", 25)
    low_notice = monitoring_settings.get("low_notice", 30)
    high_notice = monitoring_settings.get("high_notice", 80)
    high_warning = monitoring_settings.get("high_warning", 85)
    high_critical = monitoring_settings.get("high_critical", 90)

    if not plugged_in:
        if percent <= low_critical:
            log_message(f"CRITICAL: Battery at {percent}% - Immediate charging required!", "CRITICAL")
            return True, f"CRITICAL: Battery at {percent}%! Plug in charger immediately!", "critical_low"
        elif percent <= low_warning:
            log_message(f"WARNING: Battery at {percent}% - Charging recommended", "WARNING")
            return True, f"WARNING: Battery low at {percent}%! Please plug in charger.", "warning_low"
        elif percent <= low_notice:
            log_message(f"NOTICE: Battery at {percent}% - Consider charging soon", "INFO")
            return True, f"Battery getting low ({percent}%). Consider plugging in charger.", "notice_low"
    else:
        if percent >= high_critical:
            log_message(f"CRITICAL: Battery at {percent}% - Immediate charging required!", "CRITICAL")
            return True, f"Battery almost full ({percent}%)! Consider unplugging charger.", "high_critical"
        elif percent >= high_warning:
            log_message(f"WARNING: Battery at {percent}% - Charging recommended", "WARNING")
            return True, f"Battery nearly full ({percent}%)! Consider unplugging charger.", "high_warning"
        elif percent >= high_notice:
            log_message(f"NOTICE: Battery at {percent}% - Consider charging soon", "INFO")
            return True, f"Battery at {percent}%. Almost full, consider unplugging.", "high_notice"

    return False, None, None


def set_snooze(minutes: int = 60):
    """Snooze notifications and audio for given minutes."""
    global snooze_until_ts
    snooze_until_ts = time.time() + (minutes * 60)
    log_message(f"🔕 Alerts snoozed for {minutes} minutes", "INFO")


def run_monitoring(interval: int = 60):
    """Main monitoring loop."""
    global current_battery_percent, current_status, last_error, ema_rate_per_min, snooze_until_ts, last_alert_percent
    original_interval = interval
    min_interval = 10
    max_interval = interval
    check_count = 0
    last_config_check = 0
    config_check_interval = 5
    is_paused = False

    log_message(f"Starting battery monitoring with {interval}s interval", "INFO")
    log_message(f"User interval: {interval}s, Min: {min_interval}s", "INFO")

    while True:
        try:
            current_ts = time.time()
            check_count += 1

            if current_ts - last_config_check >= config_check_interval:
                last_config_check = current_ts
                interval_changed, new_interval = check_config_changes()
                if interval_changed and new_interval:
                    interval = new_interval
                    max_interval = interval
                    log_message(f"Monitoring interval updated to {interval}s due to configuration change", "INFO")

                new_pause_state = app_settings.get("advanced", {}).get("paused", False)
                if new_pause_state != is_paused:
                    is_paused = new_pause_state
                    if is_paused:
                        log_message("⏸️ Monitoring paused by user", "INFO")
                        current_status = "Paused"
                    else:
                        log_message("▶️ Monitoring resumed by user", "INFO")
                    update_tray_icon()

            battery = check_battery_status()
            if not battery:
                current_status = "No battery detected"
                update_tray_icon()
                time.sleep(min_interval)
                continue

            current_battery_percent = int(battery.percent)
            charging_status = "Charging" if battery.power_plugged else "Not Charging"
            current_status = f"Battery: {current_battery_percent}% ({charging_status})"
            rate_samples.append((current_ts, float(battery.percent)))

            if is_paused:
                update_tray_icon()
                time.sleep(interval)
                continue

            should_alert, alert_message, alert_level = check_battery_alerts_v2(battery)

            monitoring_cfg = app_settings.get("monitoring", {})
            if monitoring_cfg.get("roc_alert_enabled", True) and not battery.power_plugged and len(rate_samples) >= 2:
                window_min = monitoring_cfg.get("roc_min_window_min", 2)
                cutoff = current_ts - (window_min * 60)
                points = [(t, p) for (t, p) in rate_samples if t >= cutoff]
                if len(points) >= 2:
                    dt_min = (points[-1][0] - points[0][0]) / 60.0
                    if dt_min > 0.5:
                        rate_per_min = (points[0][1] - points[-1][1]) / dt_min
                        if rate_per_min >= monitoring_cfg.get("roc_rate_percent_per_min", 0.7):
                            should_alert = True
                            alert_level = "roc_warning"
                            alert_message = f"Rapid discharge detected (≈{rate_per_min:.2f}%/min). Consider plugging in."

            current_time = time.time()
            notifications_enabled = app_settings.get("notifications", {}).get("enabled", True)
            audio_enabled = app_settings.get("audio", {}).get("enabled", True)
            notification_frequency = app_settings.get("notifications", {}).get("frequency", "every")
            notification_cooldown_setting = app_settings.get("notifications", {}).get("cooldown", 300)

            if not hasattr(run_monitoring, "last_event_time_by_level"):
                run_monitoring.last_event_time_by_level = {}

            last_time_for_level = run_monitoring.last_event_time_by_level.get(alert_level, 0)
            hysteresis_band = monitoring_cfg.get("hysteresis_band", 2)

            allow_new_alert = True
            if notification_frequency == "cooldown":
                if current_time - last_time_for_level < notification_cooldown_setting:
                    allow_new_alert = False
            elif notification_frequency == "once":
                if hasattr(check_battery_alerts_v2, "last_level") and getattr(check_battery_alerts_v2, "last_level") == alert_level:
                    if last_alert_percent is not None and abs(current_battery_percent - last_alert_percent) < hysteresis_band:
                        allow_new_alert = False

            should_show_notification = should_alert and allow_new_alert and current_time >= snooze_until_ts

            if should_show_notification:
                if notifications_enabled:
                    show_notification(alert_message, alert_level=alert_level)
                if audio_enabled:
                    play_sound(alert_level)
                run_monitoring.last_event_time_by_level[alert_level] = current_time
                check_battery_alerts_v2.last_level = alert_level
                last_alert_percent = current_battery_percent

            # Smart interval adjustment
            if monitoring_cfg.get("smart_interval_v2", True):
                if not battery.power_plugged:
                    thresholds = [
                        monitoring_cfg.get("low_notice", 30),
                        monitoring_cfg.get("low_warning", 25),
                        monitoring_cfg.get("low_critical", 20)
                    ]
                    lows = [abs(current_battery_percent - t) for t in thresholds]
                    prox = min(lows) if lows else 100
                else:
                    thresholds = [
                        monitoring_cfg.get("high_notice", 80),
                        monitoring_cfg.get("high_warning", 85),
                        monitoring_cfg.get("high_critical", 90)
                    ]
                    highs = [abs(current_battery_percent - t) for t in thresholds]
                    prox = min(highs) if highs else 100

                if len(rate_samples) >= 2:
                    dt = rate_samples[-1][0] - rate_samples[-2][0]
                    if dt > 0:
                        inst_rate = abs(rate_samples[-1][1] - rate_samples[-2][1]) / (dt / 60.0)
                        alpha = monitoring_cfg.get("ema_alpha", 0.3)
                        ema_rate_per_min = alpha * inst_rate + (1 - alpha) * ema_rate_per_min

                base = max_interval
                if should_alert:
                    interval = min_interval
                elif prox <= 5 or ema_rate_per_min >= 0.8:
                    interval = max(min_interval, int(base * 0.5))
                elif prox <= 10 or ema_rate_per_min >= 0.6:
                    interval = max(min_interval, int(base * 0.8))
                else:
                    interval = max_interval
            elif should_alert:
                interval = min_interval
            else:
                interval = max_interval

            update_tray_icon()
            time.sleep(interval)

        except KeyboardInterrupt:
            log_message("Received interrupt signal, shutting down...", "INFO")
            break
        except Exception as e:
            error_msg = f"Unexpected error in monitoring loop: {e}"
            log_message(error_msg, "ERROR")
            last_error = str(e)
            time.sleep(10)


def main(interval: int = 60, debug_mode: bool = False):
    """Main application with system tray support."""
    global verbose_logging
    verbose_logging = debug_mode

    load_settings()
    configured_interval = app_settings.get("monitoring", {}).get("check_interval", interval)
    if configured_interval:
        interval = configured_interval

    if debug_mode:
        log_message("============================================================", "INFO")
        log_message("HA BATTERY MONITOR v2.2 - Enhanced Edition (DEBUG MODE)", "INFO")
        log_message("Features: Console Logging, System Tray, GUI Settings", "INFO")
        log_message(f"Monitoring interval: {interval} seconds", "INFO")
        notifications_enabled = app_settings.get("notifications", {}).get("enabled", True)
        log_message(f"Notifications: {'Enabled' if notifications_enabled else 'Disabled'}", "INFO")
        audio_enabled = app_settings.get("audio", {}).get("enabled", True)
        log_message(f"Audio alerts: {'Enabled' if audio_enabled else 'Disabled'}", "INFO")
        log_message("============================================================", "INFO")
    else:
        print("\n[BATTERY] HA Battery Monitor v2.2 - Startup Complete!")
        print(f"[INFO] Monitoring every {interval} seconds")
        notifications_enabled = app_settings.get("notifications", {}).get("enabled", True)
        print(f"[NOTIFY] Notifications: {'Enabled' if notifications_enabled else 'Disabled'}")
        audio_enabled = app_settings.get("audio", {}).get("enabled", True)
        print(f"[AUDIO] Audio: {'Enabled' if audio_enabled else 'Disabled'}")
        print("[TRAY] System Tray: Enabled")
        print("[CONFIG] Right-click tray icon for Settings")
        print("[CTRL] Press Ctrl+C to stop\n")

    if not create_single_instance_check():
        handle_already_running()
        return

    try:
        setup_tray()
        if tray_icon:
            tray_thread = threading.Thread(target=tray_icon.run, daemon=True)
            tray_thread.start()
            time.sleep(0.2)
            refresh_tray_menu()
            log_message("System tray initialized successfully", "INFO")
            log_message("Right-click tray icon for Settings and options", "INFO")
    except ImportError as e:
        log_message(f"Missing dependency: {e}", "ERROR")
        log_message("Please install required packages: pip install pystray pillow", "ERROR")
        sys.exit(1)
    except Exception as e:
        log_message(f"Failed to start application: {e}", "ERROR")
        sys.exit(1)

    try:
        run_monitoring(interval=interval)
    except KeyboardInterrupt:
        print("\n[DONE] Application stopped by user.")
        sys.exit(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='HA Battery Monitor - Enhanced with Console Logging and System Tray',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Features:
  - Real-time battery monitoring with visual alerts
  - System tray icon showing battery percentage
  - Smart notification system with fallbacks
  - User-friendly interface or debug mode

Usage Examples:
  BatteryMonitor.exe                    # User-friendly mode, 60s interval
  BatteryMonitor.exe --interval 30      # Check every 30 seconds
  BatteryMonitor.exe --debug            # Enable verbose logging
  BatteryMonitor.exe --settings         # Open settings GUI only
  BatteryMonitor.exe --interval 15 --debug  # Debug mode with custom interval

System Tray:
  - Right-click the tray icon for options
  - Icon color indicates battery status:
    * Blue: Normal (31-100%)
    * Orange: Low (21-30%)
    * Red: Critical (≤20%) or Error
    * Green: Charging

Modes:
  - Default: Clean, user-friendly output
  - Debug: Detailed logging for troubleshooting
  - Settings: Open GUI configuration without monitoring
"""
    )
    parser.add_argument('--interval', type=int, default=60, help='Interval in seconds between battery checks (default: 60, minimum: 10)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode with verbose logging (for troubleshooting)')
    parser.add_argument('--settings', action='store_true', help='Open settings GUI only (without starting monitoring service)')

    args = parser.parse_args()

    if args.settings:
        print("[BATTERY] HA Battery Monitor - Opening Settings GUI...")
        try:
            from pathlib import Path
            qt_path = Path(__file__).parent / "qt_gui.py"
            if not qt_path.exists():
                print(f"[ERROR] Error opening settings GUI: Qt GUI not found at {qt_path}")
                sys.exit(1)
            creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
            proc = subprocess.Popen([sys.executable, str(qt_path)], creationflags=creationflags)
            print("[SETTINGS] Settings GUI opened. Close the GUI window to exit.")
            proc.wait()
        except KeyboardInterrupt:
            print("\n[DONE] Settings mode stopped by user.")
        except Exception as e:
            print(f"[ERROR] Error opening settings GUI: {e}")
            sys.exit(1)
    else:
        if args.interval < 10:
            print("Error: Minimum interval is 10 seconds")
            sys.exit(1)
        try:
            main(interval=args.interval, debug_mode=args.debug)
        except KeyboardInterrupt:
            print("\n[DONE] Application stopped by user.")
            sys.exit(0)
