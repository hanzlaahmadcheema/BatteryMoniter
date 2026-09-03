"""
Build script to package Battery Monitor Pro into a standalone Windows executable using PyInstaller.
"""
import sys
import os
import shutil
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def build():
    root_dir = Path(__file__).parent.parent
    src_dir = root_dir / "src"
    icon_path = src_dir / "ha_battery_icon.ico"
    tools_dir = root_dir / "tools"

    print("🚀 Starting Battery Monitor Pro Build Process...")

    # Step 1: Ensure icon exists
    if not icon_path.exists():
        print("🎨 Generating application icon...")
        create_icon_script = tools_dir / "create_icon.py"
        if create_icon_script.exists():
            subprocess.run([sys.executable, str(create_icon_script)], check=True)

    # Step 2: Ensure PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("📦 Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    # Step 3: Run PyInstaller
    app_launcher = src_dir / "app_launcher.py"
    data_separator = ";" if os.name == "nt" else ":"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=BatteryMonitor",
        "--noconsole",
        "--onedir",
        "--clean",
        "--noconfirm",
        f"--add-data={src_dir}{data_separator}src",
        f"--distpath={root_dir / 'dist'}",
        f"--workpath={root_dir / 'build'}",
        f"--specpath={root_dir}",
    ]

    if icon_path.exists():
        cmd.append(f"--icon={icon_path}")

    cmd.append(str(app_launcher))

    print(f"🔨 Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        exe_path = root_dir / "dist" / "BatteryMonitor" / ("BatteryMonitor.exe" if os.name == "nt" else "BatteryMonitor")
        print("=" * 60)
        print("🎉 Build Successful!")
        print(f"📁 Output directory: {root_dir / 'dist' / 'BatteryMonitor'}")
        if exe_path.exists():
            print(f"✨ Executable binary: {exe_path}")
            print(f"📏 Size: {exe_path.stat().st_size / (1024 * 1024):.1f} MB")
        print("=" * 60)
    else:
        print("❌ Build failed with exit code:", result.returncode)
        sys.exit(result.returncode)


if __name__ == "__main__":
    build()
