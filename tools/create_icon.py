"""
Create a simple battery icon for the HA Battery Monitor
"""
from PIL import Image, ImageDraw
import pathlib
from pathlib import Path


def create_battery_icon():
    """Create a simple battery icon"""
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Body
    draw.rectangle([10, 20, 50, 50], outline=(0, 100, 200, 255), width=3)
    # Terminal
    draw.rectangle([50, 25, 54, 35], fill=(0, 100, 200, 255))
    # Charge fill
    fill_width = int(30.0)
    draw.rectangle([12, 22, 12 + fill_width, 48], fill=(0, 200, 100, 255))
    return img


def main():
    """Create and save the icon"""
    try:
        icon = create_battery_icon()
        from pathlib import Path
        output_path = Path(__file__).parent.parent / 'src' / 'ha_battery_icon.ico'
        output_path.parent.mkdir(parents=True, exist_ok=True)
        icon.save(str(output_path), format='ICO')
        print(f"✅ Icon created successfully: {output_path}")
    except Exception as e:
        print(f"❌ Error creating icon: {e}")


if __name__ == '__main__':
    main()
