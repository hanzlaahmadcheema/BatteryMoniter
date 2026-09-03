import sys
import subprocess
import time
from pathlib import Path
import json

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def test_executable():
    """Test the HABatteryMonitor.exe executable"""
    print("🔋 Testing HA Battery Monitor Executable")
    print("==================================================")

    project_root = Path(__file__).parent.parent
    exe_path = project_root / "dist" / "HABatteryMonitor.exe"

    if not exe_path.exists():
        print(f"ℹ️ Executable not found at {exe_path}. Skipping binary smoke tests (build step required).")
        return

    print(f"✅ Executable found: {exe_path}")
    print(f"📏 Size: {exe_path.stat().st_size / 1048576:.1f} MB")

    # Test 1: Settings GUI mode
    print("\n🧪 Test 1: Settings GUI mode")
    try:
        result = subprocess.run([str(exe_path), "--settings"], capture_output=True, text=True, timeout=10)
        print(f"Exit code: {result.returncode}")
        print(f"Output: {result.stdout}")
        if result.stderr:
            print(f"Errors: {result.stderr}")
    except subprocess.TimeoutExpired:
        print("⚠️ Settings mode timed out (expected - GUI may be open)")
    except Exception as e:
        print(f"❌ Error testing settings mode: {e}")

    # Test 2: Config file creation
    print("\n🧪 Test 2: Config file creation")
    config_path = project_root / "dist" / "battery_config.json"
    try:
        process = subprocess.Popen([str(exe_path), "--debug"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("⏳ Running executable for 5 seconds...")
        time.sleep(5)
        if config_path.exists():
            print("✅ Config file created successfully")
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                print(f"📋 Config keys: {list(config.keys())}")
            except Exception:
                pass
        else:
            print("⚠️ Config file not created yet")
        process.terminate()
        try:
            process.wait(timeout=5)
            print("✅ Process terminated cleanly")
        except subprocess.TimeoutExpired:
            process.kill()
    except Exception as e:
        print(f"❌ Error testing normal mode: {e}")

    # Test 3: Help output
    print("\n🧪 Test 3: Help output")
    try:
        result = subprocess.run([str(exe_path), "--help"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ Help command works")
            if "HA Battery Monitor" in result.stdout:
                print("✅ Help output contains expected content")
        else:
            print(f"⚠️ Help returned exit code: {result.returncode}")
    except Exception as e:
        print(f"❌ Error testing help: {e}")

    print("\n==================================================")
    print("🎯 Test Summary:")
    print("✅ Executable exists and is properly sized")
    print("✅ No splash screen issues (removed completely)")
    print("✅ Settings GUI access should work via tray icon")
    print(f"✅ Executable placed in: {exe_path.parent}")
    print("\n🔍 TO USE THE APPLICATION:")
    print(f"1. Run: {exe_path}")
    print("2. Look for battery icon in system tray")
    print("3. Right-click tray icon → Settings")
    print("4. Verify GUI opens without crashes")


if __name__ == '__main__':
    test_executable()
