"""
Convert PNG to ICO format for the HA Battery Monitor executable
"""
from PIL import Image
import os
import pathlib
from pathlib import Path


def convert_png_to_ico():
    """Convert the PNG file to ICO format"""
    try:
        from pathlib import Path
        base_dir = Path(__file__).parent.parent
        png_path = base_dir / 'dist' / 'HABatteryMonitor' / 'HABatteryMonitor.png'
        ico_path = base_dir / 'src' / 'ha_battery_icon.ico'

        if not png_path.exists():
            print(f"⚠️ Source PNG not found at {png_path}. Please provide a PNG icon before converting.")
            return False

        img = Image.open(str(png_path))
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        img.save(str(ico_path), format='ICO', sizes=sizes)

        png_size = os.path.getsize(str(png_path)) / 1024
        ico_size = os.path.getsize(str(ico_path)) / 1024

        print(f"✅ Successfully converted PNG to ICO: {ico_path}")
        print(f"📁 Source: {png_path}")
        print(f"📁 Output: {ico_path}")
        print(f"📏 PNG size: {png_size:.1f} KB")
        print(f"📏 ICO size: {ico_size:.1f} KB")
        return True
    except Exception as e:
        print(f"❌ Error converting PNG to ICO: {e}")
        return False


def main():
    """Main function"""
    print("🔄 Converting HABatteryMonitor.png to ICO format...")
    success = convert_png_to_ico()
    if success:
        print("🎯 Ready to build executable with custom icon!")
    else:
        print("❌ Failed to convert icon")


if __name__ == '__main__':
    main()
