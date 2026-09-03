import tkinter as tk
from tkinter import ttk
import threading
import time
import math
from datetime import datetime


class BatteryMonitorSplash:
    def __init__(self):
        self.root = tk.Tk()
        self.setup_window()
        self.setup_styles()
        self.create_widgets()
        self.setup_animations()

    def setup_window(self):
        """Configure the splash screen window."""
        self.root.title("HA Battery Monitor")
        self.root.geometry("600x400")
        self.root.resizable(False, False)
        self.root.overrideredirect(True)
        self.center_window()
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.0)
        self.root.configure(bg="#1a1a2e")

    def center_window(self):
        """Center the splash screen on the screen."""
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = 600
        window_height = 400
        x = int((screen_width - window_width) / 2)
        y = int((screen_height - window_height) / 2)
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

    def setup_styles(self):
        """Configure modern styles."""
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure(
            "Modern.Horizontal.TProgressbar",
            background="#00d4ff",
            troughcolor="#2d2d44",
            borderwidth=0,
            lightcolor="#00d4ff",
            darkcolor="#00d4ff"
        )

    def create_widgets(self):
        """Create all the splash screen widgets."""
        self.main_frame = tk.Frame(self.root, bg="#1a1a2e", width=600, height=400)
        self.main_frame.pack(fill="both", expand=True)
        self.main_frame.pack_propagate(False)

        self.top_frame = tk.Frame(self.main_frame, bg="#1a1a2e", height=120)
        self.top_frame.pack(fill="x", pady=(30, 0))

        self.title_label = tk.Label(
            self.top_frame,
            text="🔋 HA BATTERY MONITOR",
            font=("Segoe UI", 24, "bold"),
            fg="#00d4ff",
            bg="#1a1a2e"
        )
        self.title_label.pack(pady=(10, 5))

        self.version_label = tk.Label(
            self.top_frame,
            text="v2.2 ENHANCED EDITION",
            font=("Segoe UI", 12, "normal"),
            fg="#16c79a",
            bg="#1a1a2e"
        )
        self.version_label.pack(pady=5)

        self.subtitle_label = tk.Label(
            self.top_frame,
            text="⚡ INTELLIGENT POWER MANAGEMENT ⚡",
            font=("Segoe UI", 11, "normal"),
            fg="#f39c12",
            bg="#1a1a2e"
        )
        self.subtitle_label.pack(pady=(5, 0))

        self.middle_frame = tk.Frame(self.main_frame, bg="#1a1a2e", height=150)
        self.middle_frame.pack(fill="x", pady=(20, 0))

        self.dev_card = tk.Frame(self.middle_frame, bg="#2d2d44", relief="flat", bd=0)
        self.dev_card.pack(pady=10, padx=50, fill="x")

        self.dev_title = tk.Label(
            self.dev_card,
            text="👨‍💻 DEVELOPED BY 👨‍💻",
            font=("Segoe UI", 14, "bold"),
            fg="#e74c3c",
            bg="#2d2d44"
        )
        self.dev_title.pack(pady=(15, 5))

        self.dev_name = tk.Label(
            self.dev_card,
            text="🌟 HANZLA AHMAD 🌟",
            font=("Segoe UI", 18, "bold"),
            fg="#ffd700",
            bg="#2d2d44"
        )
        self.dev_name.pack(pady=5)

        self.github_label = tk.Label(
            self.dev_card,
            text="🐙 GitHub: @hanzlaahmadcheema",
            font=("Segoe UI", 10, "normal"),
            fg="#3498db",
            bg="#2d2d44"
        )
        self.github_label.pack(pady=(2, 15))

        self.bottom_frame = tk.Frame(self.main_frame, bg="#1a1a2e", height=130)
        self.bottom_frame.pack(fill="x", side="bottom")

        self.features_label = tk.Label(
            self.bottom_frame,
            text="✨ Real-time Monitoring | Smart Notifications | GUI Settings | System Tray ✨",
            font=("Segoe UI", 9, "normal"),
            fg="#95a5a6",
            bg="#1a1a2e"
        )
        self.features_label.pack(pady=(10, 15))

        self.loading_label = tk.Label(
            self.bottom_frame,
            text="🚀 Initializing HA Battery Monitor...",
            font=("Segoe UI", 12, "bold"),
            fg="#00d4ff",
            bg="#1a1a2e"
        )
        self.loading_label.pack(pady=(0, 10))

        self.progress = ttk.Progressbar(
            self.bottom_frame,
            style="Modern.Horizontal.TProgressbar",
            length=400,
            mode="determinate"
        )
        self.progress.pack(pady=5)

        self.status_label = tk.Label(
            self.bottom_frame,
            text="Loading components...",
            font=("Segoe UI", 9, "normal"),
            fg="#7f8c8d",
            bg="#1a1a2e"
        )
        self.status_label.pack(pady=5)

        self.signature_label = tk.Label(
            self.bottom_frame,
            text="💖 Crafted with Love & Code by Hanzla Ahmad 💖",
            font=("Segoe UI", 8, "italic"),
            fg="#e91e63",
            bg="#1a1a2e"
        )
        self.signature_label.pack(side="bottom", pady=(5, 10))

    def setup_animations(self):
        """Setup various animations for the splash screen."""
        self.animation_running = True
        self.progress_value = 0
        self.fade_in()
        self.animate_title()
        self.animate_progress()
        self.pulse_developer_name()

    def fade_in(self):
        """Fade in the entire window."""
        def fade():
            alpha = 0.0
            while self.animation_running and alpha < 1.0:
                alpha += 0.05
                try:
                    self.root.attributes("-alpha", alpha)
                except Exception:
                    break
                time.sleep(0.03)

        threading.Thread(target=fade, daemon=True).start()

    def animate_title(self):
        """Animate the title with color cycling."""
        colors = ("#00d4ff", "#16c79a", "#f39c12", "#e74c3c", "#9b59b6", "#3498db")
        color_idx = 0

        def cycle_colors():
            nonlocal color_idx
            while self.animation_running:
                try:
                    self.title_label.config(fg=colors[color_idx % len(colors)])
                    color_idx += 1
                except Exception:
                    break
                time.sleep(0.5)

        threading.Thread(target=cycle_colors, daemon=True).start()

    def pulse_developer_name(self):
        """Pulse effect for developer name."""
        def pulse():
            scale = 1.0
            direction = 1
            while self.animation_running:
                try:
                    font_size = int(16 + 4 * abs(math.sin(scale)))
                    scale += 0.1 * direction
                    self.dev_name.config(font=("Segoe UI", font_size, "bold"))
                except Exception:
                    break
                time.sleep(0.1)

        threading.Thread(target=pulse, daemon=True).start()

    def animate_progress(self):
        """Animate the progress bar with realistic loading steps."""
        steps = (
            (10, "Loading configuration..."),
            (25, "Initializing system tray..."),
            (40, "Setting up notifications..."),
            (55, "Loading GUI components..."),
            (70, "Configuring battery monitoring..."),
            (85, "Preparing audio alerts..."),
            (95, "Finalizing startup..."),
            (100, "Ready! 🎉"),
        )

        def progress_animation():
            for progress_val, status_text in steps:
                if not self.animation_running:
                    break
                current_val = self.progress["value"]
                while current_val < progress_val and self.animation_running:
                    current_val += 1
                    self.progress["value"] = current_val
                    try:
                        self.root.update_idletasks()
                    except Exception:
                        pass
                    time.sleep(0.02)
                if not self.animation_running:
                    break
                try:
                    self.status_label.config(text=status_text)
                except Exception:
                    pass
                time.sleep(0.5)

            if self.animation_running:
                self.complete_loading()

        threading.Thread(target=progress_animation, daemon=True).start()

    def complete_loading(self):
        """Complete the loading and show success."""
        try:
            self.loading_label.config(text="🎉 HA Battery Monitor Ready!", fg="#16c79a")
            self.status_label.config(text="Starting application...")
        except Exception:
            pass

        def flash():
            for i in range(3):
                if not self.animation_running:
                    break
                try:
                    self.dev_card.config(bg="#16c79a")
                    time.sleep(0.2)
                    self.dev_card.config(bg="#2d2d44")
                    time.sleep(0.2)
                except Exception:
                    break
            time.sleep(1)
            self.fade_out()

        threading.Thread(target=flash, daemon=True).start()

    def fade_out(self):
        """Fade out and close the splash screen."""
        def fade():
            self.animation_running = False
            alpha = 1.0
            while alpha > 0.0:
                alpha -= 0.15
                try:
                    self.root.attributes("-alpha", alpha)
                except Exception:
                    break
                time.sleep(0.03)
            self.root.after(0, self._force_close)

        threading.Thread(target=fade, daemon=True).start()

    def _force_close(self):
        """Force close the splash screen window."""
        self.animation_running = False
        try:
            self.root.withdraw()
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def show(self, duration=5):
        """Show the splash screen for specified duration."""
        def auto_close():
            time.sleep(duration)
            if self.animation_running:
                self.fade_out()

        def emergency_close():
            time.sleep(duration + 2)
            if self.animation_running:
                self._force_close()

        threading.Thread(target=auto_close, daemon=True).start()
        threading.Thread(target=emergency_close, daemon=True).start()

        try:
            self.root.protocol("WM_DELETE_WINDOW", self._force_close)
            self.root.mainloop()
        except Exception:
            self._force_close()


def show_splash_screen(duration=5):
    """Show the splash screen for the specified duration."""
    try:
        splash = BatteryMonitorSplash()
        splash.show(duration)
    except Exception as e:
        print("🔋 HA Battery Monitor v2.2")
        print("👨‍💻 Developed by: Hanzla Ahmad")
        print("🐙 GitHub: @hanzlaahmadcheema")
        print("💖 Crafted with Love & Code")
        print(f"Note: GUI splash error: {e}")


if __name__ == '__main__':
    show_splash_screen(5)
