import sys
import os
import argparse
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add current directory to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))


def main():
    """Main application launcher."""
    parser = argparse.ArgumentParser(
        description='Battery Monitor Pro - Complete Battery Management Solution',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
🔋 Battery Monitor Pro v2.0 🔋

A comprehensive battery monitoring solution with:
  • Real-time battery monitoring and alerts
  • System tray integration with visual indicators
  • Configurable notification system
  • Professional GUI for settings management
  • Smart power management recommendations

Usage Examples:
  BatteryMonitor.exe                    # Start monitoring (default settings)
  BatteryMonitor.exe --settings         # Open settings GUI only
  BatteryMonitor.exe --interval 30      # Monitor every 30 seconds
  BatteryMonitor.exe --debug            # Enable verbose logging

System Tray Features:
  • Right-click for quick access to settings and status
  • Visual battery percentage display
  • Color-coded status indicators:
    🔵 Blue: Normal battery level (31-100%)
    🟠 Orange: Low battery warning (21-30%)
    🔴 Red: Critical battery level (≤20%) or system error
    🟢 Green: Charging in progress

Author: Battery Monitor Pro Team
Version: 2.0 Enhanced Edition
"""
    )
    parser.add_argument('--settings', action='store_true', help='Open settings GUI only (does not start monitoring)')
    parser.add_argument('--interval', type=int, default=60, help='Battery check interval in seconds (default: 60, minimum: 10)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode with verbose console logging')
    parser.add_argument('--version', action='version', version='Battery Monitor Pro v2.0 Enhanced Edition')

    args = parser.parse_args()

    if args.settings:
        print("🔋 Battery Monitor Pro - Opening Settings (Qt)...")
        try:
            from pathlib import Path as _Path
            import subprocess as _subprocess
            import sys as _sys

            qt_path = _Path(__file__).parent / "qt_gui.py"
            if not qt_path.exists():
                print("❌ Qt GUI not found: qt_gui.py")
                _sys.exit(1)

            creationflags = getattr(_subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
            proc = _subprocess.Popen([_sys.executable, str(qt_path)], creationflags=creationflags)
            print("✅ Qt Settings launched. Close the window to exit.")
            proc.wait()
        except KeyboardInterrupt:
            print("\n✅ Settings closed by user.")
        except Exception as e:
            print(f"❌ Error launching Qt Settings: {e}")
            sys.exit(1)
    else:
        print("🔋 Battery Monitor Pro - Starting...")
        if args.interval < 10:
            print("❌ Error: Minimum monitoring interval is 10 seconds")
            sys.exit(1)
        try:
            from battery_monitor import main as monitor_main
            monitor_main(interval=args.interval, debug_mode=args.debug)
        except KeyboardInterrupt:
            print("\n✅ Battery Monitor Pro stopped by user.")
            sys.exit(0)
        except ImportError as e:
            print(f"❌ Error: Missing required component - {e}")
            print("Please ensure all application files are present.")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error: Failed to start Battery Monitor Pro - {e}")
            sys.exit(1)


if __name__ == '__main__':
    main()
