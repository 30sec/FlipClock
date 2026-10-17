import ctypes
import math
import os
import sys
import time
import tkinter as tk
from ctypes import wintypes
from datetime import datetime

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageTk


BACKGROUND = "#202020"
CARD_COLOR = "#2c292c"
TIME_COLOR = "#f5f5f5"
DATE_COLOR = "#ffd400"
SEAM_COLOR = "#120f12"
FLIP_DURATION = 0.6
FRAME_INTERVAL = 30
TITLE_BAR_HEIGHT = 38
CLIENT_WIDTH = 431
CLIENT_HEIGHT = 144
APP_VERSION = "V1.0"
RESOURCE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
ICON_PATH = os.path.join(RESOURCE_DIR, "clock.ico")


class Clock:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Flip Clock {APP_VERSION}")
        self.root.iconbitmap(ICON_PATH)
        self.root.overrideredirect(True)
        self.root.geometry(f"{CLIENT_WIDTH}x{CLIENT_HEIGHT}")
        self.root.minsize(240, 110)
        self.root.configure(bg=BACKGROUND)
        self.root.attributes("-topmost", True)

        self.title_bar = tk.Frame(
            root,
            bg="#323232",
            height=TITLE_BAR_HEIGHT,
            takefocus=False,
        )
        self.title_bar.pack_propagate(False)
        self.title_icon_image = Image.open(ICON_PATH).convert("RGBA")
        self.title_icon_image.thumbnail((20, 20), Image.Resampling.LANCZOS)
        self.title_icon_photo = ImageTk.PhotoImage(self.title_icon_image)
        self.title_icon = tk.Label(
            self.title_bar,
            image=self.title_icon_photo,
            bg="#323232",
            padx=8,
        )
        self.title_icon.pack(side="left")
        self.title_label = tk.Label(
            self.title_bar,
            text=f"Flip Clock {APP_VERSION}",
            bg="#323232",
            fg="#f5f5f5",
            font=("Segoe UI", 9),
        )
        self.title_label.pack(side="left")

        self.window_buttons = tk.Frame(self.title_bar, bg="#323232")
        self.window_buttons.pack(side="right", fill="y")
        self.minimize_button = self.create_title_button(
            "—", self.minimize_window, hover="#454545"
        )
        self.maximize_button = self.create_title_button(
            "□", self.toggle_maximize, hover="#454545"
        )
        self.close_button = self.create_title_button(
            "×", self.root.destroy, hover="#c42b1c"
        )

        self.canvas = tk.Canvas(root, bg=BACKGROUND, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.image_item = self.canvas.create_image(0, 0, anchor="nw")
        self.title_visible = False
        self.rounded_corners = None
        self.maximized = False
        self.restore_geometry = None
        self.drag_offset = None
        self.hover_check = None
        self.bind_hover_events()
        self.bind_drag_events((self.title_bar, self.title_icon, self.title_label))
        self.root.bind("<Configure>", self.on_window_configure, add="+")

        self.photo = None
        self.last_digits = None
        self.flips = {}
        self.font_cache = {}
        self.digit_cache = {}
        self.render_size = None
        self.root.after(0, self.ensure_taskbar_icon)
        self.root.after(0, self.update_time)

    def create_title_button(self, text, command, hover):
        button = tk.Label(
            self.window_buttons,
            text=text,
            bg="#323232",
            fg="#f5f5f5",
            font=("Segoe UI", 10),
            width=7,
            cursor="arrow",
        )
        button.pack(side="left", fill="y")
        button.bind("<Button-1>", lambda _event: command())
        button.bind("<Enter>", lambda _event: button.configure(bg=hover))
        button.bind(
            "<Leave>",
            lambda _event: button.configure(bg="#323232"),
        )
        return button

    def bind_hover_events(self):
        widgets = (
            self.root,
            self.title_bar,
            self.title_icon,
            self.title_label,
            self.window_buttons,
            self.minimize_button,
            self.maximize_button,
            self.close_button,
            self.canvas,
        )
        for widget in widgets:
            widget.bind("<Enter>", self.on_pointer_enter, add="+")
            widget.bind("<Leave>", self.on_pointer_leave, add="+")

    def bind_drag_events(self, widgets):
        for widget in widgets:
            widget.bind("<ButtonPress-1>", self.start_window_drag, add="+")
            widget.bind("<B1-Motion>", self.drag_window, add="+")
            widget.bind("<Double-Button-1>", lambda _event: self.toggle_maximize())

    def on_pointer_enter(self, _event=None):
        if self.hover_check is not None:
            self.root.after_cancel(self.hover_check)
            self.hover_check = None
        self.show_title_bar()

    def on_pointer_leave(self, _event=None):
        if self.hover_check is not None:
            self.root.after_cancel(self.hover_check)
        self.hover_check = self.root.after(80, self.update_hover_state)

    def update_hover_state(self):
        self.hover_check = None
        pointer_x, pointer_y = self.root.winfo_pointerxy()
        left = self.root.winfo_rootx()
        top = self.root.winfo_rooty()
        inside = (
            left <= pointer_x < left + self.root.winfo_width()
            and top <= pointer_y < top + self.root.winfo_height()
        )
        if inside:
            self.show_title_bar()
        else:
            self.hide_title_bar()

    def show_title_bar(self):
        if self.title_visible:
            return
        self.title_bar.pack(side="top", fill="x", before=self.canvas)
        self.title_visible = True
        self.root.after_idle(self.set_window_corners, False)
        if not self.maximized:
            self.root.geometry(
                f"{self.root.winfo_width()}x"
                f"{CLIENT_HEIGHT + TITLE_BAR_HEIGHT}"
                f"+{self.root.winfo_x()}+{self.root.winfo_y()}"
            )

    def hide_title_bar(self):
        if not self.title_visible:
            return
        self.title_bar.pack_forget()
        self.title_visible = False
        self.root.after_idle(self.set_window_corners, True)
        if not self.maximized:
            self.root.geometry(
                f"{self.root.winfo_width()}x{CLIENT_HEIGHT}"
                f"+{self.root.winfo_x()}+{self.root.winfo_y()}"
            )

    def on_window_configure(self, _event=None):
        self.root.after_idle(self.set_window_corners, not self.title_visible)

    def ensure_taskbar_icon(self):
        if sys.platform != "win32" or not self.root.winfo_exists():
            return

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        get_ancestor = user32.GetAncestor
        get_ancestor.argtypes = (wintypes.HWND, wintypes.UINT)
        get_ancestor.restype = wintypes.HWND
        hwnd = get_ancestor(self.root.winfo_id(), 2)
        if not hwnd:
            raise ctypes.WinError(ctypes.get_last_error())

        get_window_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        get_window_long.argtypes = (wintypes.HWND, ctypes.c_int)
        get_window_long.restype = ctypes.c_ssize_t
        set_window_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        set_window_long.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t)
        set_window_long.restype = ctypes.c_ssize_t

        extended_style = get_window_long(hwnd, -20)
        taskbar_style = (extended_style | 0x00040000) & ~0x00000080
        if taskbar_style != extended_style:
            ctypes.set_last_error(0)
            previous_style = set_window_long(hwnd, -20, taskbar_style)
            if previous_style == 0 and ctypes.get_last_error():
                raise ctypes.WinError(ctypes.get_last_error())

        set_window_pos = user32.SetWindowPos
        set_window_pos.argtypes = (
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        )
        set_window_pos.restype = wintypes.BOOL
        flags = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020
        if not set_window_pos(hwnd, None, 0, 0, 0, 0, flags):
            raise ctypes.WinError(ctypes.get_last_error())

    def set_window_corners(self, rounded):
        if sys.platform != "win32" or not self.root.winfo_exists():
            return

        if self.maximized:
            rounded = False

        width = self.root.winfo_width()
        height = self.root.winfo_height()
        state = (rounded, width, height)
        if state == self.rounded_corners:
            return

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        get_ancestor = user32.GetAncestor
        get_ancestor.argtypes = (wintypes.HWND, wintypes.UINT)
        get_ancestor.restype = wintypes.HWND
        hwnd = get_ancestor(self.root.winfo_id(), 2)
        if not hwnd:
            raise ctypes.WinError(ctypes.get_last_error())

        user32.SetWindowRgn.argtypes = (
            wintypes.HWND,
            wintypes.HRGN,
            wintypes.BOOL,
        )
        user32.SetWindowRgn.restype = ctypes.c_int

        region = None
        if rounded:
            gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
            gdi32.CreateRoundRectRgn.argtypes = (
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
            )
            gdi32.CreateRoundRectRgn.restype = wintypes.HRGN
            radius = 18
            region = gdi32.CreateRoundRectRgn(
                0, 0, width + 1, height + 1, radius * 2, radius * 2
            )
            if not region:
                raise ctypes.WinError(ctypes.get_last_error())

        if not user32.SetWindowRgn(hwnd, region, True):
            if region:
                ctypes.WinDLL("gdi32").DeleteObject(region)
            raise ctypes.WinError(ctypes.get_last_error())

        self.rounded_corners = state

    def start_window_drag(self, event):
        if not self.maximized:
            self.drag_offset = (
                event.x_root - self.root.winfo_x(),
                event.y_root - self.root.winfo_y(),
            )

    def drag_window(self, event):
        if self.drag_offset is None:
            return
        x = event.x_root - self.drag_offset[0]
        y = event.y_root - self.drag_offset[1]
        self.root.geometry(f"+{x}+{y}")

    def minimize_window(self):
        self.hide_title_bar()
        self.root.overrideredirect(False)
        self.root.iconify()
        self.root.bind("<Map>", self.restore_borderless, add="+")

    def restore_borderless(self, _event=None):
        if self.root.state() == "normal":
            def restore_window_style():
                self.root.overrideredirect(True)
                self.ensure_taskbar_icon()

            self.root.after_idle(restore_window_style)

    def toggle_maximize(self):
        if not self.maximized:
            self.restore_geometry = self.root.geometry()
            self.maximized = True
            if not self.title_visible:
                self.title_bar.pack(side="top", fill="x", before=self.canvas)
                self.title_visible = True
            self.root.geometry(
                f"{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}+0+0"
            )
        else:
            self.maximized = False
            self.root.geometry(self.restore_geometry)
            self.show_title_bar()

    def load_font(self, size, bold=False):
        key = (size, bold)
        if key in self.font_cache:
            return self.font_cache[key]

        font_name = "segoeuib.ttf" if bold else "segoeui.ttf"
        try:
            font = ImageFont.truetype(font_name, size)
        except OSError:
            font = ImageFont.load_default(size=size)
        self.font_cache[key] = font
        return font

    def render_digit(self, digit, width, height, font):
        key = (digit, width, height, font)
        if key in self.digit_cache:
            return self.digit_cache[key]

        image = Image.new("RGB", (width, height), CARD_COLOR)
        draw = ImageDraw.Draw(image)
        bounds = draw.textbbox((0, 0), digit, font=font)
        text_width = bounds[2] - bounds[0]
        text_height = bounds[3] - bounds[1]
        draw.text(
            (
                (width - text_width) / 2 - bounds[0],
                (height - text_height) / 2 - bounds[1],
            ),
            digit,
            fill=TIME_COLOR,
            font=font,
        )
        self.digit_cache[key] = image
        return image

    @staticmethod
    def shade(image, factor):
        return ImageEnhance.Brightness(image).enhance(factor)

    def draw_projected_flap(
        self, frame, image, x, seam_y, width, angle, direction, brightness
    ):
        flap_height = image.height
        if flap_height <= 0 or width <= 0 or math.cos(angle) <= 0.015:
            return

        center_x = x + width / 2
        camera_depth = flap_height * 4
        strip_step = max(1, flap_height // 45)

        def projected_distance(distance):
            depth = distance * math.sin(angle)
            return distance * math.cos(angle) * camera_depth / (camera_depth + depth)

        for source_y in range(0, flap_height, strip_step):
            source_end = min(flap_height, source_y + strip_step)
            middle = (source_y + source_end) / 2
            distance = flap_height - middle if direction == "up" else middle
            perspective = camera_depth / (
                camera_depth + distance * math.sin(angle)
            )
            target_width = max(1, round(width * perspective))

            if direction == "up":
                first_distance = flap_height - source_y
                last_distance = flap_height - source_end
                first_y = seam_y - projected_distance(first_distance)
                last_y = seam_y - projected_distance(last_distance)
            else:
                first_distance = source_y
                last_distance = source_end
                first_y = seam_y + projected_distance(first_distance)
                last_y = seam_y + projected_distance(last_distance)

            target_height = max(1, round(abs(last_y - first_y)))
            strip = image.crop((0, source_y, image.width, source_end))
            strip = strip.resize(
                (target_width, target_height), Image.Resampling.BICUBIC
            )
            if brightness != 1:
                strip = self.shade(strip, brightness)
            frame.paste(
                strip,
                (
                    round(center_x - target_width / 2),
                    round(min(first_y, last_y)),
                ),
            )

        edge_distance = projected_distance(flap_height)
        edge_scale = camera_depth / (
            camera_depth + flap_height * math.sin(angle)
        )
        edge_y = seam_y + edge_distance if direction == "down" else seam_y - edge_distance
        edge_width = max(1, round(width * edge_scale))
        ImageDraw.Draw(frame).line(
            (
                round(center_x - edge_width / 2),
                round(edge_y),
                round(center_x + edge_width / 2),
                round(edge_y),
            ),
            fill="#171517" if brightness < 0.9 else "#454145",
            width=2,
        )

    def draw_card(self, frame, x, y, width, height, digit, font, flip, now):
        half = height // 2
        current = self.render_digit(digit, width, height, font)
        upper = current.crop((0, 0, width, half))
        lower = current.crop((0, half, width, height))

        if flip:
            old_digit, started = flip
            progress = min(1.0, max(0.0, (now - started) / FLIP_DURATION))
            previous = self.render_digit(old_digit, width, height, font)
            old_upper = previous.crop((0, 0, width, half))
            old_lower = previous.crop((0, half, width, height))

            frame.paste(upper, (x, y))
            frame.paste(old_lower, (x, y + half))

            if progress < 0.5:
                angle = progress * math.pi
                self.draw_projected_flap(
                    frame,
                    old_upper,
                    x,
                    y + half,
                    width,
                    angle,
                    "up",
                    1.0 - math.sin(angle) * 0.35,
                )

            if progress >= 0.5:
                angle = (1.0 - progress) * math.pi
                self.draw_projected_flap(
                    frame,
                    lower,
                    x,
                    y + half,
                    width,
                    angle,
                    "down",
                    0.72 + 0.28 * math.cos(angle),
                )
        else:
            frame.paste(upper, (x, y))
            frame.paste(lower, (x, y + half))

        draw = ImageDraw.Draw(frame)
        draw.rectangle((x, y, x + width - 1, y + height - 1), outline="#1b191b")
        draw.rectangle(
            (x, y + half - 1, x + width - 1, y + half + 1),
            fill=SEAM_COLOR,
        )

    def draw(self, now):
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        digits = now.strftime("%H%M%S")

        margin = max(8, round(width * 0.018))
        small_gap = max(3, round(width * 0.008))
        group_gap = max(8, round(width * 0.022))
        gap_width = small_gap * 3 + group_gap * 2
        card_width = max(1, (width - margin * 2 - gap_width) // 6)
        card_height = max(1, min(round(height * 0.78), round(card_width * 0.96)))
        card_width = min(card_width, round(card_height / 0.96))
        total_width = card_width * 6 + gap_width
        x = (width - total_width) // 2
        y = max(4, (height - card_height - 28) // 2)
        font_size = max(8, round(card_height * 0.86))
        font = self.load_font(font_size)
        render_size = (card_width, card_height, font_size)
        if render_size != self.render_size:
            self.digit_cache.clear()
            self.render_size = render_size

        frame = Image.new("RGB", (width, height), BACKGROUND)
        tick = time.monotonic()
        for index, digit in enumerate(digits):
            flip = self.flips.get(index)
            if flip and tick - flip[1] >= FLIP_DURATION:
                del self.flips[index]
                flip = None

            self.draw_card(
                frame, x, y, card_width, card_height, digit, font, flip, tick
            )
            x += card_width
            if index in (0, 1, 2, 3, 4):
                x += group_gap if index in (1, 3) else small_gap

        date_size = max(4, font_size // 3)
        date_font = self.load_font(date_size)
        date_draw = ImageDraw.Draw(frame)
        date_draw.text(
            (width - 16, height - 20),
            now.strftime("%Y-%m-%d"),
            fill=DATE_COLOR,
            font=date_font,
            anchor="rs",
        )

        self.photo = ImageTk.PhotoImage(frame)
        self.canvas.itemconfigure(self.image_item, image=self.photo)

    def update_time(self):
        now = datetime.now()
        digits = now.strftime("%H%M%S")
        tick = time.monotonic()

        if self.last_digits is not None and digits != self.last_digits:
            for index, (old_digit, new_digit) in enumerate(
                zip(self.last_digits, digits)
            ):
                if old_digit != new_digit:
                    self.flips[index] = (old_digit, tick)

        self.last_digits = digits
        self.draw(now)
        self.root.after(FRAME_INTERVAL, self.update_time)


if __name__ == "__main__":
    window = tk.Tk()
    Clock(window)
    window.mainloop()
