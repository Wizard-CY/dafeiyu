# 大肥鱼 2.0 控制中心 · 整理：YunShan_You（悠云山）
import ctypes
import json
import math
import os
import queue
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
import webbrowser
import hashlib
import importlib.util
from datetime import datetime
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox, ttk

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk
    PIL_OK = True
except ImportError:
    Image = ImageDraw = ImageFilter = ImageTk = None
    PIL_OK = False

try:
    import pystray
except ImportError:
    pystray = None

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'runtime/AstrBot-4.29.3/data'
sys.path.insert(0, str(DATA.parent))
from data.dafeiyu_state import transaction, enqueue

MIRROR_DATA = DATA / 'mirror_data'
LOG = ROOT / 'runtime/AstrBot-4.29.3/startup.log'
HIDDEN = subprocess.CREATE_NO_WINDOW
RESET_NOTICE = '刚刚主人把我的私聊额度重置啦，我们又可以聊天了！'
STOP_NOTICE = '我要下线啦，明天再来聊天吧'
START_NOTICE = '我上线啦，快来和我聊聊天吧'

# ---------- 视觉系统 ----------
BG = '#070E18'
SIDEBAR = '#060C15'
CARD = '#0F1B2C'
CARD_SOFT = '#0B1728'
BORDER = '#20324B'
BORDER_HI = '#2E4A6B'
TEXT = '#E8F1FB'
MUTED = '#93A9C3'
DIM = '#647C97'
CYAN = '#38BDF8'
TEAL = '#2DD4BF'
BLUE = '#3B82F6'
INDIGO = '#6366F1'
VIOLET = '#A78BFA'
GREEN = '#34D399'
AMBER = '#FBBF24'
ORANGE = '#FB923C'
CORAL = '#FB7185'
RED = '#F87171'
GOLD = '#F5C451'
FONT = 'Microsoft YaHei UI'
ICON_FONT = 'Segoe Fluent Icons'
WEEKDAYS = '一二三四五六日'

I_HOME = '\uE80F'
I_CHAT = '\uE8BD'
I_GROUP = '\uE716'
I_REFRESH = '\uE72C'
I_SEARCH = '\uE721'
I_PLAY = '\uE768'
I_STOP = '\uE71A'
I_LINK = '\uE71B'
I_DOC = '\uE8A5'
I_SETTINGS = '\uE713'
I_CHECK = '\uE73E'
I_WARN = '\uE7BA'
I_INFO = '\uE946'
I_CLOSE = '\uE711'
I_DOWN = '\uE70D'
I_RIGHT = '\uE76C'
I_CLOCK = '\uE823'
I_SAVE = '\uE74E'
I_STAR = '\uE734'
I_ADD = '\uE710'
I_REMOVE = '\uE738'

_PIL_CACHE = {}
_PHOTO_CACHE = {}
_FONT_CACHE = {}


def _hex_rgb(color):
    color = color.lstrip('#')
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def mix(c1, c2, t):
    a, b = _hex_rgb(c1), _hex_rgb(c2)
    return '#%02x%02x%02x' % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def lighten(color, t=0.25):
    return mix(color, '#FFFFFF', t)


def darken(color, t=0.25):
    return mix(color, '#000000', t)


def _parent_bg(widget):
    try:
        value = widget.cget('bg')
        if value:
            return value
    except tk.TclError:
        pass
    return BG


def _font(size, bold=False, icon=False):
    key = (size, bool(bold), bool(icon))
    if key not in _FONT_CACHE:
        family = ICON_FONT if icon else FONT
        _FONT_CACHE[key] = tkfont.Font(family=family, size=size, weight='bold' if bold else 'normal')
    return _FONT_CACHE[key]


def _measure(text, size, bold=False, icon=False):
    return _font(size, bold, icon).measure(text)


def _cache_put(key, value):
    if len(_PIL_CACHE) > 160:
        _PIL_CACHE.clear()
    _PIL_CACHE[key] = value
    return value


def _photo(key, pil_image):
    if key not in _PHOTO_CACHE:
        if len(_PHOTO_CACHE) > 120:
            _PHOTO_CACHE.clear()
        _PHOTO_CACHE[key] = ImageTk.PhotoImage(pil_image)
    return _PHOTO_CACHE[key]


def _round_points(x1, y1, x2, y2, r):
    r = max(1, min(r, (x2 - x1) // 2, (y2 - y1) // 2))
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


def round_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    return canvas.create_polygon(_round_points(x1, y1, x2, y2, r), smooth=True, splinesteps=18, **kwargs)


def _gradient(w, h, stops, angle=0.4):
    key = ('grad', w, h, tuple(stops), angle)
    if key in _PIL_CACHE:
        return _PIL_CACHE[key]
    sw, sh = 80, 80
    img = Image.new('RGB', (sw, sh))
    px = img.load()
    for y in range(sh):
        for x in range(sw):
            t = (x / (sw - 1)) * (1 - angle) + (y / (sh - 1)) * angle
            pos = max(0.0, min(1.0, t)) * (len(stops) - 1)
            i = min(len(stops) - 2, int(pos))
            px[x, y] = tuple(int(stops[i][j] + (stops[i + 1][j] - stops[i][j]) * (pos - i)) for j in range(3))
    return _cache_put(key, img.resize((w, h), Image.LANCZOS))


def _rounded_mask(w, h, r):
    key = ('mask', w, h, r)
    if key in _PIL_CACHE:
        return _PIL_CACHE[key]
    mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=255)
    return _cache_put(key, mask)


def hero_photo(w, h, ready=True):
    key = ('hero', w, h, bool(ready))
    if key in _PIL_CACHE:
        return _PIL_CACHE[key]
    if ready:
        stops = [(9, 36, 66), (8, 83, 108), (28, 54, 128)]
    else:
        stops = [(54, 38, 18), (92, 54, 18), (74, 32, 54)]
    base = _gradient(w, h, stops, 0.46).convert('RGBA')
    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    if ready:
        draw.ellipse((w * 0.60, -h * 0.85, w * 1.06, h * 0.92), fill=(56, 189, 248, 58))
        draw.ellipse((w * 0.76, h * 0.06, w * 1.20, h * 1.25), fill=(139, 92, 246, 62))
        draw.ellipse((-w * 0.18, h * 0.28, w * 0.30, h * 1.30), fill=(45, 212, 191, 24))
    else:
        draw.ellipse((w * 0.62, -h * 0.8, w * 1.05, h * 0.9), fill=(251, 146, 60, 50))
        draw.ellipse((w * 0.78, h * 0.1, w * 1.2, h * 1.2), fill=(244, 63, 94, 45))
    overlay = overlay.filter(ImageFilter.GaussianBlur(max(20, h // 4)))
    base = Image.alpha_composite(base, overlay)
    waves = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    wd = ImageDraw.Draw(waves)
    for k in range(3):
        pts = []
        for x in range(0, w + 10, 8):
            y = h * (0.73 + k * 0.075) + math.sin(x / (95 + k * 32) + k * 1.7) * (8 + k * 4)
            pts.append((x, y))
        wd.line(pts, fill=(130, 225, 255, 24 + k * 9), width=2)
    base = Image.alpha_composite(base, waves)
    try:
        icon = Image.open(Path(__file__).resolve().parent / '大肥鱼.ico').convert('RGBA')
        icon.thumbnail((int(h * 2.45), int(h * 2.45)), Image.LANCZOS)
        alpha = icon.getchannel('A').point(lambda v: int(v * 0.17))
        ink = Image.new('RGBA', icon.size, (255, 255, 255, 0))
        ink.putalpha(alpha)
        base.alpha_composite(ink, (w - icon.width - 16, (h - icon.height) // 2 + 4))
    except (OSError, ValueError):
        pass
    base.putalpha(_rounded_mask(w, h, 20))
    return _cache_put(key, base)


def make_mirror_icon(size=64):
    """Generate a purple tray icon for mirror mode."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 2
    draw.ellipse([margin, margin, size - margin, size - margin], fill='#7B1FA2')
    try:
        from PIL import ImageFont
        font = ImageFont.truetype('arial.ttf', size // 2)
    except (OSError, ImportError):
        try:
            from PIL import ImageFont
            font = ImageFont.load_default()
        except ImportError:
            return img
    letter = 'M'
    bbox = draw.textbbox((0, 0), letter, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2, (size - th) / 2 - bbox[1]), letter, fill='white', font=font)
    return img


def card_photo(w, h, radius=16, fill=CARD, border=BORDER, shadow=8, accent=None):
    key = ('card', w, h, radius, fill, border, shadow, accent)
    if key in _PIL_CACHE:
        return _PIL_CACHE[key]
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    sh = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        (shadow + 1, shadow + 3, w - shadow - 2, h - shadow - 1),
        radius=radius, fill=(0, 0, 0, 115),
    )
    sh = sh.filter(ImageFilter.GaussianBlur(max(3, shadow * 0.85)))
    img = Image.alpha_composite(img, sh)
    body = Image.new('RGBA', (w - 2 * shadow, h - 2 * shadow), fill)
    draw = ImageDraw.Draw(body)
    draw.rounded_rectangle((0, 0, body.width - 1, body.height - 1), radius=radius, outline=border, width=1)
    draw.rounded_rectangle((1, 1, body.width - 2, body.height - 2), radius=radius - 1,
                           outline=(255, 255, 255, 9), width=1)
    if accent:
        draw.rounded_rectangle((1, 10, 4, body.height - 11), radius=2, fill=accent)
    img.alpha_composite(body, (shadow, shadow))
    return _cache_put(key, img)


def button_photo(w, h, variant='ghost', state='normal'):
    key = ('btn', w, h, variant, state)
    if key in _PIL_CACHE:
        return _PIL_CACHE[key]
    radius = min(12, h // 2)
    if variant == 'primary':
        c1, c2 = (10, 105, 132), (37, 99, 235)
        if state == 'hover':
            c1, c2 = (13, 137, 166), (59, 130, 246)
        elif state == 'press':
            c1, c2 = (8, 83, 106), (29, 78, 188)
        outline = (125, 211, 252, 120)
    elif variant == 'danger':
        c1, c2 = (120, 28, 38), (168, 35, 92)
        if state == 'hover':
            c1, c2 = (148, 36, 48), (201, 46, 112)
        elif state == 'press':
            c1, c2 = (100, 23, 32), (145, 29, 78)
        outline = (251, 113, 133, 95)
    elif variant == 'soft':
        c1 = c2 = (25, 42, 64)
        if state == 'hover':
            c1 = c2 = (33, 55, 82)
        elif state == 'press':
            c1 = c2 = (19, 34, 53)
        outline = (59, 88, 122, 190)
    else:
        c1 = c2 = (17, 29, 46)
        if state == 'hover':
            c1 = c2 = (24, 41, 64)
        elif state == 'press':
            c1 = c2 = (12, 22, 37)
        outline = (49, 73, 103, 185)
    img = _gradient(w, h, [c1, c2], 0.92).convert('RGBA')
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, outline=outline, width=1)
    draw.line((radius, 1, w - radius, 1), fill=(255, 255, 255, 42), width=1)
    img.putalpha(_rounded_mask(w, h, radius))
    return _cache_put(key, img)


class Card(tk.Canvas):
    """A soft card with a painted shadow and an embedded content frame."""

    def __init__(self, parent, height=None, pad=16, shadow=8, radius=16, fill=CARD,
                 border=BORDER, accent=None, auto=False, **kwargs):
        super().__init__(parent, bg=_parent_bg(parent), highlightthickness=0, bd=0, width=10,
                         height=(height + 2 * shadow if height else 84), **kwargs)
        self.pad = pad
        self.shadow = shadow
        self.radius = radius
        self.fill = fill
        self.border = border
        self.accent = accent
        self.auto = auto
        self._img = None
        self._bg_item = None
        self.body = tk.Frame(self, bg=fill)
        self._win = self.create_window(shadow + pad, shadow + pad, anchor='nw', window=self.body)
        self.bind('<Configure>', self._resize)
        self.body.bind('<Configure>', self._fit)

    def _resize(self, _event=None):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 30 or h < 30:
            return
        if PIL_OK:
            self._img = _photo(('card', w, h, self.radius, self.fill, self.border,
                                self.shadow, self.accent),
                               card_photo(w, h, self.radius, self.fill, self.border,
                                          self.shadow, self.accent))
            if self._bg_item is None:
                self._bg_item = self.create_image(0, 0, anchor='nw', image=self._img, tags='cardbg')
            else:
                self.itemconfigure(self._bg_item, image=self._img)
            self.tag_lower('cardbg')
        else:
            self.delete('cardbg')
            x1, y1 = self.shadow, self.shadow
            x2, y2 = w - self.shadow - 1, h - self.shadow - 1
            round_rect(self, x1, y1, x2, y2, self.radius, fill=self.fill,
                       outline=self.border, width=1, tags='cardbg')
            if self.accent:
                round_rect(self, x1 + 1, y1 + 10, x1 + 4, y2 - 10, 2,
                           fill=self.accent, outline='', tags='cardbg')
            self.tag_lower('cardbg')
        self.itemconfigure(self._win, width=max(20, w - 2 * (self.shadow + self.pad)))

    def _fit(self, _event=None):
        if not self.auto:
            return
        need = self.body.winfo_reqheight() + 2 * self.pad + 2 * self.shadow
        if abs(need - int(self['height'])) > 1:
            self.configure(height=need)

    def set_height(self, visual_height):
        self.configure(height=visual_height + 2 * self.shadow)


class ActionFlow(tk.Frame):
    """Wrap action buttons to the available content width."""

    def __init__(self, parent, actions):
        super().__init__(parent, bg=CARD, height=36)
        self.buttons = []
        for label, command, variant in actions:
            width = max(104, _measure(label, 9) + 30)
            button = SoftButton(self, label, command, variant, width=width, height=34,
                                font_size=9, bg=CARD)
            self.buttons.append((button, width))
        self.bind('<Configure>', self._reflow)

    def _reflow(self, event=None):
        width = self.winfo_width()
        if width < 40:
            return
        x = y = 0
        for button, requested in self.buttons:
            if x and x + requested > width:
                x = 0
                y += 42
            button.place(x=x, y=y, width=requested, height=34)
            x += requested + 8
        height = y + 34
        if int(self.cget('height')) != height:
            self.configure(height=height)


class Pill(tk.Canvas):
    def __init__(self, parent, text='', color=GREEN, dot=True, height=26, bg=None, **kwargs):
        self.bg = bg or _parent_bg(parent)
        super().__init__(parent, height=height, bg=self.bg, highlightthickness=0, bd=0, **kwargs)
        self.height = height
        self.dot = dot
        self._text = text
        self._color = color
        self.set(text, color)

    def set(self, text, color=None, height=None):
        if color:
            self._color = color
        if height:
            self.height = height
        text = str(text)
        width = _measure(text, 9, True) + 26 + (14 if self.dot else 0)
        self.configure(width=width, height=self.height)
        self.delete('all')
        round_rect(self, 0, 0, width - 1, self.height - 1, self.height // 2,
                   fill=mix(self._color, self.bg, 0.83), outline=mix(self._color, self.bg, 0.55), width=1)
        x = 13
        if self.dot:
            self.create_oval(x - 3, self.height // 2 - 3, x + 3, self.height // 2 + 3,
                             fill=self._color, outline='')
            x += 12
        self.create_text(x, self.height // 2, text=text, anchor='w',
                         fill=lighten(self._color, 0.60), font=(FONT, 9, 'bold'))


class SoftButton(tk.Canvas):
    def __init__(self, parent, text, command=None, variant='ghost', width=None, height=34,
                 icon=None, font_size=9, bg=None, bold=False):
        self.bg = bg or _parent_bg(parent)
        self.variant = variant
        self.state = 'normal'
        self.command = command
        self.enabled = True
        self.icon = icon
        self.text = text
        self.font_size = font_size
        self.bold = bold
        content = _measure(text, font_size, bold) if text else 0
        if icon:
            content += _measure(icon, font_size, icon=True) + (7 if text else 0)
        self.box_w = width or max(54, content + 28)
        self.box_h = height
        super().__init__(parent, width=self.box_w, height=self.box_h, bg=self.bg,
                         highlightthickness=0, bd=0, cursor='hand2', takefocus=1)
        self._images = {}
        if PIL_OK:
            for state in ('normal', 'hover', 'press'):
                self._images[state] = _photo(('btn', self.box_w, self.box_h, variant, state),
                                             button_photo(self.box_w, self.box_h, variant, state))
        self._text_item = None
        self._icon_item = None
        self._draw()
        self.bind('<Enter>', self._enter)
        self.bind('<Leave>', self._leave)
        self.bind('<ButtonPress-1>', self._press)
        self.bind('<ButtonRelease-1>', self._release)
        self.bind('<Return>', lambda _e: self._invoke())
        self.bind('<space>', lambda _e: self._invoke())

    def _draw(self):
        self.delete('all')
        if PIL_OK and self._images:
            self.create_image(0, 0, anchor='nw', image=self._images[self.state])
        else:
            fill = {'primary': '#0E7490', 'danger': '#9F1239', 'soft': '#1E2E44'}.get(self.variant, '#111D2E')
            if self.state == 'hover':
                fill = lighten(fill, 0.10)
            elif self.state == 'press':
                fill = darken(fill, 0.10)
            round_rect(self, 0, 0, self.box_w - 1, self.box_h - 1, min(12, self.box_h // 2),
                       fill=fill, outline=mix(fill, '#FFFFFF', 0.22), width=1)
        fg = '#FFFFFF' if self.variant in ('primary', 'danger') else '#D8E6F6'
        if not self.enabled:
            fg = '#5C728C'
        x = self.box_w // 2
        if self.icon and self.text:
            total = _measure(self.icon, self.font_size, icon=True) + 7 + _measure(self.text, self.font_size, self.bold)
            left = (self.box_w - total) // 2
            self._icon_item = self.create_text(left, self.box_h // 2, text=self.icon, anchor='w',
                                               fill=fg, font=(ICON_FONT, self.font_size))
            self._text_item = self.create_text(left + _measure(self.icon, self.font_size, icon=True) + 7,
                                               self.box_h // 2, text=self.text, anchor='w', fill=fg,
                                               font=(FONT, self.font_size, 'bold' if self.bold else 'normal'))
        elif self.icon:
            self._icon_item = self.create_text(x, self.box_h // 2, text=self.icon,
                                               fill=fg, font=(ICON_FONT, self.font_size))
            self._text_item = None
        else:
            self._text_item = self.create_text(x, self.box_h // 2, text=self.text,
                                               fill=fg, font=(FONT, self.font_size, 'bold' if self.bold else 'normal'))
            self._icon_item = None

    def _set_state(self, state):
        if not self.enabled:
            return
        if state != self.state:
            self.state = state
            self._draw()

    def _enter(self, _event=None):
        self._set_state('hover')

    def _leave(self, _event=None):
        self._set_state('normal')

    def _press(self, _event=None):
        self._set_state('press')

    def _release(self, event=None):
        self._set_state('hover')
        if not self.enabled:
            return
        if event is not None and not (0 <= event.x <= self.box_w and 0 <= event.y <= self.box_h):
            return
        self._invoke()

    def _invoke(self):
        if self.enabled and self.command:
            self.command()

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.configure(cursor='hand2' if enabled else 'arrow')
        self._draw()


class ToggleSwitch(tk.Canvas):
    def __init__(self, parent, variable, command=None, bg=None, width=46, height=24):
        self.bg = bg or _parent_bg(parent)
        super().__init__(parent, width=width, height=height, bg=self.bg,
                         highlightthickness=0, bd=0, cursor='hand2')
        self.var = variable
        self.command = command
        self.w = width
        self.h = height
        self.level = 1.0 if bool(self.var.get()) else 0.0
        self.target = self.level
        self.job = None
        self.bind('<Button-1>', self._click)
        self._draw()

    def _click(self, _event=None):
        self.var.set(not bool(self.var.get()))
        self.target = 1.0 if self.var.get() else 0.0
        self._animate()
        if self.command:
            self.command()

    def set(self, value, animate=False):
        """Set the switch from code without firing the command."""

        value = bool(value)
        self.var.set(value)
        self.target = 1.0 if value else 0.0
        if animate:
            self._animate()
        else:
            self.level = self.target
            self._draw()

    def _animate(self):
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        if self.job:
            try:
                self.after_cancel(self.job)
            except tk.TclError:
                pass
        step = 0.18 if self.target > self.level else -0.18
        self.level = max(0.0, min(1.0, self.level + step))
        self._draw()
        if abs(self.level - self.target) > 0.01:
            self.job = self.after(16, self._animate)
        else:
            self.level = self.target
            self.job = None
            self._draw()

    def _draw(self):
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        self.delete('all')
        track = mix('#1B2C44', TEAL, self.level)
        round_rect(self, 1, 3, self.w - 1, self.h - 3, (self.h - 6) // 2,
                   fill=track, outline=mix(track, '#FFFFFF', 0.10))
        x = 4 + self.level * (self.w - 16)
        self.create_oval(x - 5, self.h // 2 - 9, x + 13, self.h // 2 + 9,
                         fill=mix(track, '#FFFFFF', 0.14), outline='')
        self.create_oval(x, self.h // 2 - 7, x + 14, self.h // 2 + 7,
                         fill='#F8FCFF', outline='')


class GlowSlider(tk.Canvas):
    def __init__(self, parent, variable, command=None, color=CYAN, width=300,
                 to=200, bg=None):
        self.bg = bg or _parent_bg(parent)
        super().__init__(parent, width=width, height=38, bg=self.bg, highlightthickness=0, bd=0)
        self.var = variable
        self.command = command
        self.color = color
        self.maximum = to
        self.w = width
        self.pad = 8
        self.active = False
        self.bind('<Button-1>', self._start)
        self.bind('<B1-Motion>', self._drag)
        self.bind('<ButtonRelease-1>', self._stop)
        self.bind('<Left>', lambda _e: self._nudge(-5))
        self.bind('<Right>', lambda _e: self._nudge(5))
        self.bind('<Configure>', self._resize)
        self._draw()

    def _resize(self, event):
        self.w = max(80, event.width)
        self._draw()

    def _x_for(self, value):
        return self.pad + (self.w - 2 * self.pad) * max(0, min(self.maximum, value)) / self.maximum

    def _value_for(self, x):
        value = (x - self.pad) / max(1, self.w - 2 * self.pad) * self.maximum
        return int(round(value / 5.0) * 5)

    def _set_from_event(self, event):
        value = max(0, min(self.maximum, self._value_for(event.x)))
        self.var.set(value)
        self._draw()
        if self.command:
            self.command(value)

    def _start(self, event):
        self.active = True
        self._set_from_event(event)

    def _drag(self, event):
        if self.active:
            self._set_from_event(event)

    def _stop(self, _event=None):
        self.active = False

    def _nudge(self, delta):
        value = max(0, min(self.maximum, int(self.var.get()) + delta))
        self.var.set(value)
        self._draw()
        if self.command:
            self.command(value)

    def _draw(self):
        self.delete('all')
        try:
            value = int(self.var.get())
        except (tk.TclError, ValueError):
            value = 0
        value = max(0, min(self.maximum, value))
        y = 11
        round_rect(self, self.pad, y, self.w - self.pad, y + 8, 4, fill='#172941', outline='')
        x = self._x_for(value)
        if x > self.pad + 1:
            segments = 8
            for i in range(segments):
                x1 = self.pad + (x - self.pad) * i / segments
                x2 = self.pad + (x - self.pad) * (i + 1) / segments + 1
                col = mix(darken(self.color, 0.28), self.color, (i + 1) / segments)
                self.create_rectangle(x1, y, x2, y + 8, fill=col, outline='')
            self.create_oval(self.pad, y - 0, self.pad + 8, y + 8, fill=darken(self.color, 0.28), outline='')
        self.create_oval(x - 4, y - 3, x + 12, y + 13,
                         fill=mix(self.color, self.bg, 0.62), outline='')
        self.create_oval(x, y + 1, x + 8, y + 9, fill='#F7FCFF', outline='')
        for tick, label in ((0, '0'), (100, '100'), (200, '200')):
            tx = self._x_for(tick)
            self.create_line(tx, y + 14, tx, y + 17, fill='#36506D')
            self.create_text(tx, y + 23, text=label, fill=DIM, font=(FONT, 7))


class GradientBar(tk.Canvas):
    def __init__(self, parent, height=9, bg=None, animate=True):
        self.bg = bg or _parent_bg(parent)
        super().__init__(parent, height=height, bg=self.bg, highlightthickness=0, bd=0)
        self.h = height
        self.animate = animate
        self.value = 0
        self.maximum = 100
        self.c1 = CYAN
        self.c2 = BLUE
        self.ratio = 0.0
        self.job = None
        self.bind('<Configure>', lambda _e: self._draw())

    def set(self, value, maximum=100, c1=CYAN, c2=BLUE, animate=None):
        self.value = max(0, value)
        self.maximum = max(1, maximum)
        self.c1, self.c2 = c1, c2
        target = max(0.0, min(1.0, self.value / self.maximum))
        if animate is None:
            animate = self.animate
        if not animate or not self.winfo_viewable():
            self.ratio = target
            self._draw()
            return
        self._animate_to(target)

    def _animate_to(self, target):
        if self.job:
            try:
                self.after_cancel(self.job)
            except tk.TclError:
                pass
        start = self.ratio

        def step(i=0):
            t = i / 8.0
            eased = 1 - (1 - t) ** 3
            self.ratio = start + (target - start) * eased
            self._draw()
            if i < 8:
                self.job = self.after(18, lambda: step(i + 1))
            else:
                self.ratio = target
                self.job = None

        step()

    def _draw(self):
        self.delete('all')
        w = max(1, self.winfo_width())
        h = max(1, self.winfo_height())
        if w < 8:
            return
        round_rect(self, 0, 1, w - 1, h - 2, (h - 2) // 2, fill='#172941', outline='')
        fw = max(0, min(w, int((w - 1) * self.ratio)))
        if fw <= 2:
            return
        if fw < h:
            self.create_oval(0, 0, fw, h, fill=self.c1, outline='')
        else:
            round_rect(self, 0, 1, fw - 1, h - 2, (h - 2) // 2, fill=self.c1, outline='')
            self.create_oval(fw - h, 0, fw, h, fill=self.c2, outline='')
            self.create_line(h // 2, 2, max(h // 2, fw - h // 2), 2,
                             fill=mix(self.c1, '#FFFFFF', 0.45), width=1)
        gx = max(3, fw - 3)
        self.create_oval(gx - 5, h // 2 - 5, gx + 5, h // 2 + 5,
                         fill=mix(self.c2, '#0B1728', 0.55), outline='')
        self.create_oval(gx - 2, h // 2 - 2, gx + 2, h // 2 + 2,
                         fill=mix(self.c2, '#FFFFFF', 0.55), outline='')


class SlimScrollbar(tk.Canvas):
    def __init__(self, parent, canvas, bg=BG):
        super().__init__(parent, width=9, bg=bg, highlightthickness=0, bd=0)
        self.canvas = canvas
        self.first = 0.0
        self.last = 1.0
        self.drag = None
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.bind('<Configure>', lambda _e: self._draw())
        self.bind('<Button-1>', self._start)
        self.bind('<B1-Motion>', self._drag)
        self.bind('<Enter>', lambda _e: self._draw(hover=True))
        self.bind('<Leave>', lambda _e: self._draw())

    def _on_scroll(self, first, last):
        self.first, self.last = float(first), float(last)
        self._draw()

    def _draw(self, hover=False):
        self.delete('all')
        h = self.winfo_height()
        if h < 10 or self.last - self.first >= 0.999:
            return
        y1 = max(2, int(self.first * h))
        y2 = min(h - 2, int(self.last * h))
        if y2 - y1 < 28:
            y2 = min(h - 2, y1 + 28)
        color = '#3E5B7D' if hover or self.drag else '#2A405C'
        round_rect(self, 3, y1, 7, y2, 2, fill=color, outline='')

    def _start(self, event):
        if self.last - self.first >= 0.999:
            return
        h = self.winfo_height()
        y1 = int(self.first * h)
        y2 = int(self.last * h)
        if y1 <= event.y <= y2:
            self.drag = event.y - y1
        else:
            self.drag = (y2 - y1) // 2
            self._move(event.y)
        self._draw(hover=True)

    def _drag(self, event):
        if self.drag is not None:
            self._move(event.y)

    def _move(self, y):
        h = max(1, self.winfo_height())
        span = max(0.01, self.last - self.first)
        top = (y - (self.drag or 0)) / h
        top = max(0.0, min(1.0 - span, top))
        self.canvas.yview_moveto(top)


class ScrollArea(tk.Frame):
    def __init__(self, parent, bg=BG):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.bar = SlimScrollbar(self, self.canvas, bg)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.bar.pack(side='right', fill='y')
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.win = self.canvas.create_window((0, 0), anchor='nw', window=self.inner)
        self.inner.bind('<Configure>', self._sync)
        self.canvas.bind('<Configure>', self._resize)
        self._job = None
        self._start_y = 0.0
        self._target_y = 0.0
        self._step = 0

    def _sync(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        self.bar._draw()

    def _resize(self, event):
        self.canvas.itemconfigure(self.win, width=event.width)
        self.bar._draw()

    def scroll_pixels(self, dy):
        total = max(1, self.inner.winfo_height())
        view = max(1, self.canvas.winfo_height())
        if total <= view + 1:
            return
        cur = self.canvas.canvasy(0)
        target = max(0, min(total - view, cur + dy))
        if abs(target - cur) < 1:
            return
        if self._job:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            cur = self._current_y(total)
        self._start_y = cur
        self._target_y = target
        self._step = 0

        def tick():
            self._step += 1
            t = min(1.0, self._step / 9.0)
            eased = 1 - (1 - t) ** 3
            y = self._start_y + (self._target_y - self._start_y) * eased
            self.canvas.yview_moveto(max(0.0, min(1.0, y / total)))
            if t < 1:
                self._job = self.after(16, tick)
            else:
                self._job = None

        tick()

    def _current_y(self, total):
        return self.canvas.canvasy(0)

    def scroll_to_top(self):
        self.canvas.yview_moveto(0)


class SearchBox(tk.Canvas):
    def __init__(self, parent, placeholder='搜索昵称 / QQ', command=None, bg=None, width=460, height=40):
        self.bg = bg or _parent_bg(parent)
        super().__init__(parent, width=width, height=height, bg=self.bg,
                         highlightthickness=0, bd=0)
        self.placeholder = placeholder
        self.command = command
        self.var = tk.StringVar()
        self.entry = tk.Entry(self, textvariable=self.var, bg=CARD_SOFT, fg=TEXT,
                              insertbackground=TEXT, relief='flat', bd=0,
                              highlightthickness=0, font=(FONT, 10))
        self._focused = False
        self._win = self.create_window(40, height // 2, anchor='w', window=self.entry,
                                       width=width - 78, height=height - 12)
        self.placeholder_label = tk.Label(self, text=placeholder, bg=CARD_SOFT, fg=DIM,
                                          font=(FONT, 9), anchor='w', cursor='xterm')
        self._ph_win = self.create_window(42, height // 2, anchor='w',
                                          window=self.placeholder_label,
                                          width=width - 90, height=height - 12)
        self.placeholder_label.bind('<Button-1>', lambda _e: self.entry.focus_set())
        self.bind('<Configure>', self._resize)
        self.entry.bind('<FocusIn>', self._focus_in)
        self.entry.bind('<FocusOut>', self._focus_out)
        self.var.trace_add('write', lambda *_args: self._on_change())
        self.bind('<Button-1>', lambda _e: self.entry.focus_set())
        self._draw()
        self._sync_placeholder()

    def _resize(self, event):
        self.itemconfigure(self._win, width=max(40, event.width - 78))
        self.itemconfigure(self._ph_win, width=max(30, event.width - 90))
        self._draw()

    def _focus_in(self, _event=None):
        self._focused = True
        self._sync_placeholder()
        self._draw()

    def _focus_out(self, _event=None):
        self._focused = False
        self._sync_placeholder()
        self._draw()

    def _on_change(self):
        self._sync_placeholder()
        self._draw()
        if self.command:
            self.command()

    def _sync_placeholder(self):
        show = not self.var.get().strip() and not self._focused
        try:
            self.itemconfigure(self._ph_win, state='normal' if show else 'hidden')
            if show:
                self.tag_raise(self._ph_win)
        except tk.TclError:
            pass

    def _draw(self):
        self.delete('tag_bg')
        self.delete('tag_ui')
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20:
            return
        round_rect(self, 1, 1, w - 2, h - 2, 14,
                   fill=CARD_SOFT, outline=(CYAN if self._focused else BORDER), width=1, tags='tag_bg')
        self.tag_lower('tag_bg')
        self.create_text(15, h // 2, text=I_SEARCH, fill=(CYAN if self._focused else DIM),
                         font=(ICON_FONT, 11), tags='tag_ui')
        if self.var.get():
            self.create_text(w - 18, h // 2, text=I_CLOSE, fill=DIM,
                             font=(ICON_FONT, 8), tags=('tag_ui', 'clear'))
            self.tag_bind('clear', '<Button-1>', lambda _e: self.var.set(''))
            self.tag_bind('clear', '<Enter>', lambda _e: self.configure(cursor='hand2'))
            self.tag_bind('clear', '<Leave>', lambda _e: self.configure(cursor=''))


class Stepper(tk.Frame):
    def __init__(self, parent, value=75, minimum=0, maximum=2000, width=92, bg=CARD):
        super().__init__(parent, bg=CARD_SOFT, highlightbackground=BORDER,
                         highlightcolor=BORDER_HI, highlightthickness=1, bd=0)
        self.minimum = minimum
        self.maximum = maximum
        self.var = tk.StringVar(value=str(value))
        self._minus = tk.Canvas(self, width=24, height=28, bg=CARD_SOFT,
                                highlightthickness=0, bd=0, cursor='hand2')
        self._minus.pack(side='left')
        self._minus.create_text(12, 14, text='−', fill=MUTED, font=(FONT, 11, 'bold'))
        self.entry = tk.Entry(self, textvariable=self.var, width=5, justify='center',
                              bg=CARD_SOFT, fg=TEXT, insertbackground=TEXT, relief='flat',
                              bd=0, highlightthickness=0, font=(FONT, 9, 'bold'))
        self.entry.pack(side='left', fill='both', expand=True, pady=2)
        self._plus = tk.Canvas(self, width=24, height=28, bg=CARD_SOFT,
                               highlightthickness=0, bd=0, cursor='hand2')
        self._plus.pack(side='left')
        self._plus.create_text(12, 14, text='+', fill=MUTED, font=(FONT, 11, 'bold'))
        self._minus.bind('<Button-1>', lambda *_: self.step(-1))
        self._plus.bind('<Button-1>', lambda *_: self.step(1))
        self.entry.bind('<FocusOut>', lambda *_: self.clamp())
        self.entry.bind('<Return>', lambda *_: self.clamp())
        self.configure(width=width)

    def step(self, delta):
        try:
            value = int(self.var.get())
        except ValueError:
            value = self.minimum
        self.var.set(str(max(self.minimum, min(self.maximum, value + delta))))

    def clamp(self):
        try:
            value = int(self.var.get())
        except ValueError:
            value = self.minimum
        self.var.set(str(max(self.minimum, min(self.maximum, value))))

    def get(self):
        self.clamp()
        return int(self.var.get())

    def set(self, value):
        self.var.set(str(value))


def _bind_tree(widget, sequence, func):
    widget.bind(sequence, func)
    for child in widget.winfo_children():
        _bind_tree(child, sequence, func)


class NavItem(tk.Frame):
    def __init__(self, parent, icon, text, command):
        super().__init__(parent, bg=SIDEBAR, height=44, cursor='hand2')
        self.pack_propagate(False)
        self.command = command
        self.active = False
        self._bar = tk.Frame(self, bg=SIDEBAR, width=3)
        self._bar.pack(side='left', fill='y')
        self._icon = tk.Label(self, text=icon, bg=SIDEBAR, fg=DIM, font=(ICON_FONT, 12))
        self._icon.pack(side='left', padx=(14, 10))
        self._text = tk.Label(self, text=text, bg=SIDEBAR, fg=MUTED, font=(FONT, 10))
        self._text.pack(side='left')
        _bind_tree(self, '<Button-1>', lambda _e: self.command())
        _bind_tree(self, '<Enter>', self._hover)
        _bind_tree(self, '<Leave>', self._leave)

    def _hover(self, _event=None):
        if not self.active:
            self._paint('#0B1626', MUTED, '#B9CBE0')

    def _leave(self, _event=None):
        if not self.active:
            self._paint(SIDEBAR, DIM, MUTED)

    def _paint(self, bg, icon_fg, text_fg, bar=None):
        self.configure(bg=bg)
        self._bar.configure(bg=bar or bg)
        self._icon.configure(bg=bg, fg=icon_fg)
        self._text.configure(bg=bg, fg=text_fg)

    def set_active(self, active):
        self.active = bool(active)
        if active:
            self._paint('#0D1B2E', CYAN, '#F3F9FF', CYAN)
            self._text.configure(font=(FONT, 10, 'bold'))
        else:
            self._paint(SIDEBAR, DIM, MUTED)
            self._text.configure(font=(FONT, 10))


# ---------- 数据采集 ----------
_AUTOSTART_CACHE = {'at': 0.0, 'value': None}


def _read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def _log_startup_crash(details):
    """Record a fatal startup error when the app is launched with pythonw."""
    try:
        path = ROOT / 'runtime' / 'logs' / 'control_center_error.log'
        if path.exists() and path.stat().st_size > 512 * 1024:
            path.write_text('', encoding='utf-8')
        with path.open('a', encoding='utf-8') as handle:
            handle.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '\n' + details + '\n')
    except OSError:
        pass


def _show_startup_error(message):
    """Show a native Windows dialog even when Tk could not start."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, '大肥鱼 · 启动失败', 0x10)
    except Exception:
        pass


def _read_log(path=None, tail_bytes=640000, head_bytes=192000):
    """Read the head (startup markers) and tail (recent errors) of the log."""
    path = Path(path or LOG)
    try:
        with path.open('rb') as handle:
            handle.seek(0, 2)
            size = handle.tell()
            if size <= tail_bytes + head_bytes:
                handle.seek(0)
                return handle.read().decode('utf-8', 'replace')
            handle.seek(0)
            head = handle.read(head_bytes)
            handle.seek(size - tail_bytes)
            tail = handle.read(tail_bytes)
        return (head + b'\n' + tail).decode('utf-8', 'replace')
    except OSError:
        return ''


def qqmusic_status():
    """Read the local QQ Music backend state.

    Returns:
        A dict with running/logged/uin/songs fields.
    """
    import urllib.request
    songs = 0
    try:
        library = json.loads((ROOT / 'music_library' / 'index.json').read_text(encoding='utf-8'))
        songs = len(library.get('songs', []))
    except (OSError, ValueError):
        pass
    try:
        with urllib.request.urlopen('http://127.0.0.1:3311/health', timeout=1.5) as response:
            data = json.loads(response.read().decode('utf-8'))
        return {'running': True, 'logged': bool(data.get('logged')),
                'uin': str(data.get('uin') or ''), 'songs': songs}
    except Exception:
        return {'running': False, 'logged': False, 'uin': '', 'songs': songs}


def collect_quota_rows():
    """Return today's private quota rows, sorted by usage."""
    today = datetime.now().strftime('%Y-%m-%d')
    state = _read_json(DATA / 'dafeiyu_quota.json', {})
    cfg = _read_json(DATA / 'dafeiyu_quota_config.json', {})
    friends = _read_json(DATA / 'dafeiyu_friends.json', {})
    if not isinstance(state, dict):
        state = {}
    if not isinstance(cfg, dict):
        cfg = {}
    if not isinstance(friends, dict):
        friends = {}
    base_limit = int(cfg.get('daily_limit') or 75)
    per_user = cfg.get('per_user') or {}
    blocked = _read_json(DATA / 'dafeiyu_blocked.json', {})
    if not isinstance(blocked, dict):
        blocked = {}
    rows = {}
    for qq, entry in state.items():
        if not isinstance(entry, dict) or entry.get('day') != today or str(qq) == '1000000001':
            continue
        rows[str(qq)] = {'qq': str(qq), 'count': int(entry.get('count', 0) or 0)}
    for qq, ban in blocked.items():
        # A ban fires before the quota counter runs, and old bans have no
        # today quota row; keep every banned user on the page so the switch
        # stays reachable for a manual unblock.
        if str(qq) == '1000000001' or str(qq) in rows:
            continue
        rows[str(qq)] = {'qq': str(qq), 'count': 0}
    for qq, item in rows.items():
        info = friends.get(qq) if isinstance(friends, dict) else {}
        info = info if isinstance(info, dict) else {}
        ban = blocked.get(qq) if isinstance(blocked.get(qq), dict) else {}
        nick = info.get('remark') or info.get('nick') or ban.get('name')
        item['nick'] = str(nick or 'QQ ' + qq)
        try:
            item['limit'] = max(1, int(per_user.get(qq, base_limit)))
        except (TypeError, ValueError):
            item['limit'] = base_limit
        item['custom'] = qq in per_user
        item['blocked'] = qq in blocked
        item['blocked_at'] = str(ban.get('at') or '')
        item['blocked_reason'] = str(ban.get('reason') or '')
        try:
            item['blocked_ts'] = datetime.strptime(item['blocked_at'],
                                                   '%Y-%m-%d %H:%M:%S').timestamp()
        except (TypeError, ValueError):
            item['blocked_ts'] = 0.0
    def _sort_key(item):
        if item['blocked']:
            return (0, -item['blocked_ts'], item['nick'])
        return (1, -item['count'], item['nick'])
    return sorted(rows.values(), key=_sort_key)


def collect_group_rows(log=''):
    """Return group counts, enabled state and membership state."""
    defaults = {}
    registry = _read_json(DATA / 'dafeiyu_groups.json', {})
    if not isinstance(registry, dict):
        registry = {}
    names = []
    for gid, fallback in defaults.items():
        info = registry.get(gid) if isinstance(registry.get(gid), dict) else {}
        name = str(info.get('name') or fallback[0])
        original = str(info.get('original') or '')
        label = name if not original or original == name else name + '（' + original + '）'
        names.append((label, gid, bool(info.get('auto', fallback[1]))))
    for gid, info in registry.items():
        if str(gid) in defaults or not isinstance(info, dict):
            continue
        name = str(info.get('name') or ('群聊 ' + str(gid)))
        original = str(info.get('original') or '')
        label = name if not original or original == name else name + '（' + original + '）'
        names.append((label, str(gid), bool(info.get('auto', True))))

    today = datetime.now().strftime('%Y-%m-%d')
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    counts = {}
    db_path = DATA / 'dafeiyu_group_memory.db'
    if db_path.exists():
        try:
            with sqlite3.connect(db_path, timeout=1) as db:
                counts = {
                    str(gid): int(total)
                    for gid, total in db.execute(
                        "SELECT group_id, count(*) FROM messages WHERE role='assistant' AND created_at >= ? GROUP BY group_id",
                        (start,),
                    ).fetchall()
                }
        except sqlite3.Error:
            counts = {}
    if not counts:
        raw = _read_json(DATA / 'dafeiyu_group_counts.json', {})
        if str(raw.get('day') or '') == today:
            counts = {str(k): int(v) for k, v in (raw.get('counts') or {}).items()}

    controls = _read_json(DATA / 'dafeiyu_group_controls.json', {})
    limit_cfg = _read_json(DATA / 'dafeiyu_group_limits.json', {})
    settings_cfg = _read_json(DATA / 'dafeiyu_group_settings.json', {})
    if not isinstance(controls, dict):
        controls = {}
    if not isinstance(limit_cfg, dict):
        limit_cfg = {}
    if not isinstance(settings_cfg, dict):
        settings_cfg = {}
    default_limit = int(limit_cfg.get('default_daily') or 120)
    per_group = limit_cfg.get('per_group') or {}
    rate_defaults = settings_cfg.get('defaults') or {}
    rate_per_group = settings_cfg.get('per_group') or {}

    rows = []
    for name, gid, auto in names:
        try:
            limit = max(0, int(per_group.get(gid, default_limit)))
        except (TypeError, ValueError):
            limit = default_limit
        rates = rate_per_group.get(gid) if isinstance(rate_per_group.get(gid), dict) else {}

        def _rate(key, rates=rates):
            try:
                return max(0, min(200, int(rates.get(key, rate_defaults.get(key, 100)))))
            except (TypeError, ValueError):
                return 100

        rows.append({
            'name': name,
            'gid': gid,
            'count': int(counts.get(gid, 0) or 0),
            'enabled': bool(controls.get(gid, not auto)),
            'member': ('Whale group %s membership: True' % gid) in log,
            'limit': limit,
            'custom': gid in per_group,
            'reply_desire': _rate('reply_desire'),
            'sticker_rate': _rate('sticker_rate'),
            'voice_rate': _rate('voice_rate'),
        })
    return rows


def collect_mirror_snapshot():
    """Collect the mirror's shadow-run state, pilot feed and review queues."""
    status = _read_json(MIRROR_DATA / 'cycle_status.json', {})
    if not isinstance(status, dict):
        status = {}
    decisions = _read_json(MIRROR_DATA / 'review_decisions.json', {})
    if not isinstance(decisions, dict):
        decisions = {}
    decided_batches = decisions.get('batches') if isinstance(decisions.get('batches'), dict) else {}
    decided_profiles = decisions.get('profiles') if isinstance(decisions.get('profiles'), dict) else {}

    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    obs_total = obs_today = fb_count = positive = 0
    score_sum = 0.0
    recent = []
    obs_path = MIRROR_DATA / 'observations.jsonl'
    if obs_path.exists():
        try:
            lines = obs_path.read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError:
            lines = []
        for line in lines:
            try:
                rec = json.loads(line)
            except (ValueError, TypeError):
                continue
            if not isinstance(rec, dict):
                continue
            obs_total += 1
            if float(rec.get('observed_at') or 0) >= start:
                obs_today += 1
            fb = rec.get('feedback')
            if isinstance(fb, dict):
                try:
                    score = float(fb.get('quality_score'))
                except (TypeError, ValueError):
                    score = None
                if score is not None:
                    fb_count += 1
                    score_sum += score
                    if score >= 0.6:
                        positive += 1
            recent.append(rec)
        recent = recent[-8:]

    pending = 0
    try:
        pending = sum(1 for line in (MIRROR_DATA / 'pending.jsonl').read_text(
            encoding='utf-8').splitlines() if line.strip())
    except OSError:
        pending = 0

    batches = []
    batches_dir = MIRROR_DATA / 'batches'
    if batches_dir.is_dir():
        for path in sorted(batches_dir.glob('batch_*.json'),
                           key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                report = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if not isinstance(report, dict):
                continue
            bid = str(report.get('batch_id') or path.stem.replace('batch_', ''))
            summary = report.get('summary') if isinstance(report.get('summary'), dict) else {}
            decision = decided_batches.get(bid)
            batches.append({
                'batch_id': bid,
                'created_at': path.stat().st_mtime,
                'total': int(report.get('total_observations') or summary.get('total') or 0),
                'avg_score': float(summary.get('avg_score') or 0),
                'positive_ratio': float(summary.get('positive_ratio') or 0),
                'rules': [str(x) for x in (report.get('suggested_strategies') or []) if str(x).strip()],
                'insights': [str(x) for x in (report.get('insights') or []) if str(x).strip()][:4],
                'api_review': bool(report.get('api_review')),
                'low': len(report.get('low_quality_examples') or []),
                'high': len(report.get('high_quality_examples') or []),
                'decision': decision if isinstance(decision, dict) else None,
            })

    profiles = []
    profiles_dir = DATA / 'profiles'
    published_dir = profiles_dir / 'published'
    if profiles_dir.is_dir():
        for path in sorted(profiles_dir.glob('*.md'),
                           key=lambda p: p.stat().st_mtime, reverse=True):
            name = path.stem
            try:
                content = path.read_text(encoding='utf-8')
            except OSError:
                continue
            title = name
            for line in content.splitlines():
                if line.startswith('#'):
                    title = line.lstrip('#').strip() or name
                    break
            decision = decided_profiles.get(name)
            published = published_dir / (name + '.md')
            stale = bool(published.exists() and path.stat().st_mtime > published.stat().st_mtime)
            action = decision.get('action') if isinstance(decision, dict) else None
            state = 'pending' if stale or action not in ('approve', 'reject') else action
            profiles.append({
                'name': name,
                'title': title,
                'content': content[:1600],
                'updated_at': path.stat().st_mtime,
                'state': state,
                'published': published.exists(),
                'stale': stale,
                'decided_at': str((decision or {}).get('at') or ''),
            })

    insights = []
    insights_path = MIRROR_DATA / 'insights.jsonl'
    if insights_path.exists():
        try:
            lines = insights_path.read_text(encoding='utf-8', errors='replace').splitlines()[-8:]
        except OSError:
            lines = []
        for line in lines:
            try:
                rec = json.loads(line)
            except (ValueError, TypeError):
                continue
            text = str(rec.get('insight') or '').strip()
            if text:
                insights.append({
                    'at': rec.get('insight_at') or 0,
                    'message': str(rec.get('message') or '')[:60],
                    'text': text,
                })

    strategy = _read_json(MIRROR_DATA / 'learned_strategy.json', {})
    rules = []
    strategy_updated = 0
    if isinstance(strategy, dict):
        rules = [str(x) for x in (strategy.get('rules') or []) if str(x).strip()]
        try:
            strategy_updated = float(strategy.get('updated_at') or 0)
        except (TypeError, ValueError):
            strategy_updated = 0
    baseline = _read_json(MIRROR_DATA / 'effect_baseline.json', {})
    if not isinstance(baseline, dict):
        baseline = {}

    phase = str(status.get('phase') or 'accumulating')
    phase_label, phase_step = mirror_phase_info(phase)
    supervisor = _read_json(DATA / 'dafeiyu_supervisor_state.json', {})
    supervisor_config = _read_json(DATA / 'dafeiyu_supervisor.json', {})
    if not isinstance(supervisor, dict):
        supervisor = {}
    if not isinstance(supervisor_config, dict):
        supervisor_config = {}
    return {
        'phase': phase,
        'phase_label': phase_label,
        'phase_step': phase_step,
        'batch_count': int(status.get('batch_count') or 0),
        'sync_count': int(status.get('sync_count') or 0),
        'last_batch_id': str(status.get('last_batch_id') or ''),
        'last_sync_id': str(status.get('last_sync_id') or ''),
        'updated_at': float(status.get('updated_at') or 0),
        'obs_total': obs_total,
        'obs_today': obs_today,
        'fb_count': fb_count,
        'pending': pending,
        'avg_score': (score_sum / fb_count if fb_count else 0.0),
        'positive_ratio': (positive / fb_count if fb_count else 0.0),
        'recent': recent,
        'batches': batches,
        'pending_batches': sum(1 for item in batches if item['decision'] is None),
        'profiles': profiles,
        'pending_profiles': sum(1 for item in profiles if item['state'] == 'pending'),
        'insights': insights,
        'rules': rules,
        'strategy_updated': strategy_updated,
        'baseline': baseline,
        'supervisor': supervisor,
        'supervisor_config': supervisor_config,
    }


def mirror_phase_info(phase):
    """Return the display label and timeline step for one cycle phase."""
    return {
        'accumulating': ('影子观察', 0),
        'observing': ('影子观察', 0),
        'batch_sent': ('批次待批', 1),
        'synced': ('策略已同步', 2),
        'observing_effects': ('效果观察', 3),
    }.get(phase, (phase or '影子观察', 0))


def _mirror_decisions():
    """Load the review decision log, tolerant of a missing or broken file."""
    data = _read_json(MIRROR_DATA / 'review_decisions.json', {})
    if not isinstance(data, dict):
        data = {}
    data.setdefault('batches', {})
    data.setdefault('profiles', {})
    return data


def mirror_approve_batch(batch_id, rules):
    """Approve one batch's selected rules and write a mirror sync signal."""
    rules = [str(rule).strip() for rule in rules if str(rule).strip()]
    if not batch_id or not rules:
        return False, '请至少勾选一条建议'
    now = time.time()
    sync_id = '%d-%s' % (int(now), str(batch_id)[-8:])
    checksum_source = {
        'sync_id': sync_id,
        'batch_id': str(batch_id),
        'applied_changes': [],
        'new_rules': rules,
        'timestamp': now,
    }
    checksum = hashlib.sha256(
        json.dumps(checksum_source, sort_keys=True, ensure_ascii=False).encode('utf-8'),
    ).hexdigest()[:16]
    payload = {
        'sync_id': sync_id,
        'protocol_version': '1.0',
        'batch_id': str(batch_id),
        'applied_changes': [],
        'new_rules': rules,
        'removed_rules': [],
        'production_version': '4.29.3',
        'timestamp': now,
        'checksum': checksum,
    }
    try:
        sync_dir = MIRROR_DATA / 'sync'
        sync_dir.mkdir(parents=True, exist_ok=True)
        (sync_dir / ('sync_' + sync_id + '.json')).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    except OSError as exc:
        return False, '写同步信号失败：%s' % exc

    strategy_path = MIRROR_DATA / 'learned_strategy.json'
    strategy = _read_json(strategy_path, {})
    if not isinstance(strategy, dict):
        strategy = {}
    current = [str(rule) for rule in (strategy.get('rules') or [])]
    for rule in rules:
        if rule not in current:
            current.append(rule)
    strategy['rules'] = current[-15:]
    strategy['updated_at'] = now
    strategy['last_sync_rules'] = rules
    try:
        strategy_path.write_text(json.dumps(strategy, ensure_ascii=False, indent=2), encoding='utf-8')
    except OSError:
        pass

    notes_path = DATA / 'dafeiyu_learned_notes.md'
    try:
        existing = notes_path.read_text(encoding='utf-8')
    except OSError:
        existing = '# 主人批阅过的经验提醒\n'
    stamp = datetime.now().strftime('%m-%d')
    lines = [line for line in existing.splitlines() if line.strip()]
    known = {line.split('] ', 1)[-1] for line in lines if line.startswith('- ')}
    for rule in rules:
        if rule not in known:
            lines.append('- [%s] %s' % (stamp, rule))
    body = [line for line in lines if line.startswith('#') or line.startswith('- ')][-8:]
    if not any(line.startswith('#') for line in body):
        body.insert(0, '# 主人批阅过的经验提醒')
    try:
        notes_path.write_text('\n'.join(body) + '\n', encoding='utf-8')
    except OSError:
        pass

    decisions = _mirror_decisions()
    decisions['batches'][str(batch_id)] = {
        'action': 'approve',
        'at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'note': '',
        'rules': rules,
        'sync_id': sync_id,
    }
    try:
        (MIRROR_DATA / 'review_decisions.json').write_text(
            json.dumps(decisions, ensure_ascii=False, indent=2), encoding='utf-8')
    except OSError as exc:
        return False, '写批阅记录失败：%s' % exc
    return True, '已采纳 %d 条建议，同步信号 %s' % (len(rules), sync_id)


def mirror_reject_batch(batch_id):
    """Reject one batch report."""
    decisions = _mirror_decisions()
    decisions['batches'][str(batch_id)] = {
        'action': 'reject',
        'at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'note': '',
    }
    try:
        (MIRROR_DATA / 'review_decisions.json').write_text(
            json.dumps(decisions, ensure_ascii=False, indent=2), encoding='utf-8')
    except OSError as exc:
        return False, '写批阅记录失败：%s' % exc
    return True, '已驳回批次 %s' % batch_id


def mirror_decide_profile(name, action):
    """Publish or reject one relationship profile."""
    name = str(name or '').strip()
    if not name or '/' in name or '\\' in name or name.startswith('.'):
        return False, '画像名不合法'
    source = DATA / 'profiles' / (name + '.md')
    if not source.is_file():
        return False, '找不到这个画像'
    decisions = _mirror_decisions()
    entry = {'action': action, 'at': datetime.now().strftime('%Y-%m-%d %H:%M'), 'note': ''}
    if action == 'approve':
        target_dir = DATA / 'profiles' / 'published'
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target_dir / (name + '.md'))
        except OSError as exc:
            return False, '发布失败：%s' % exc
        entry['published_at'] = entry['at']
    decisions['profiles'][name] = entry
    try:
        (MIRROR_DATA / 'review_decisions.json').write_text(
            json.dumps(decisions, ensure_ascii=False, indent=2), encoding='utf-8')
    except OSError as exc:
        return False, '写批阅记录失败：%s' % exc
    return True, ('已发布画像 %s' % name) if action == 'approve' else ('已驳回画像 %s' % name)


def collect_friend_clean_rows():
    """Collect friends, activity, whitelist and archive state for cleanup."""
    friends = _read_json(DATA / 'dafeiyu_friends.json', {})
    activity = _read_json(DATA / 'dafeiyu_friend_activity.json', {})
    whitelist = _read_json(DATA / 'dafeiyu_friend_whitelist.json', {})
    state = _read_json(DATA / 'dafeiyu_friend_activity_state.json', {})
    result = _read_json(DATA / 'dafeiyu_friend_clean_result.json', {})
    if not isinstance(friends, dict):
        friends = {}
    if not isinstance(activity, dict):
        activity = {}
    if not isinstance(whitelist, dict):
        whitelist = {}
    if not isinstance(state, dict):
        state = {}
    if not isinstance(result, dict):
        result = {}
    now = time.time()
    rows = []
    for qq, info in friends.items():
        qq = str(qq)
        if qq == '1000000000':
            continue
        info = info if isinstance(info, dict) else {}
        act = activity.get(qq) if isinstance(activity.get(qq), dict) else {}
        try:
            last = float(act.get('last_user_at') or 0)
        except (TypeError, ValueError):
            last = 0.0
        try:
            added = float(info.get('added_at') or 0)
        except (TypeError, ValueError):
            added = 0.0
        reference = last or added
        idle_days = (now - reference) / 86400 if reference else None
        whitelisted = qq in whitelist
        protected = qq == '1000000001'
        rows.append({
            'qq': qq,
            'nick': str(info.get('remark') or info.get('nick') or act.get('name') or 'QQ ' + qq),
            'last_user_at': last,
            'last_text': str(act.get('last_text') or ''),
            'idle_days': idle_days,
            'whitelisted': whitelisted,
            'protected': protected,
            'eligible': bool(reference and not whitelisted and not protected
                             and now - reference >= 5 * 86400),
        })
    rows.sort(key=lambda item: (-(item['idle_days'] if item['idle_days'] is not None else -1),
                                item['nick']))
    archived = 0
    archive_dir = DATA / 'friend_archive'
    if archive_dir.is_dir():
        archived = sum(1 for path in archive_dir.iterdir() if path.is_dir())
    return {
        'rows': rows,
        'friends_total': len(rows),
        'idle_count': sum(1 for item in rows
                          if item['idle_days'] is not None and item['idle_days'] >= 5),
        'eligible_count': sum(1 for item in rows if item['eligible']),
        'whitelist_count': len(whitelist),
        'archived_count': archived,
        'scan_state': state,
        'clean_result': result,
    }


def inspect_status(mirror=False):
    """Collect everything the dashboard shows. Safe to run off the UI thread."""
    ports = {}
    for port in (6185, 6199, 6099):
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.5):
                ports[port] = True
        except OSError:
            ports[port] = False
    try:
        network = subprocess.run(['netstat', '-ano', '-p', 'tcp'], capture_output=True, text=True,
                                 creationflags=HIDDEN, timeout=5).stdout
        connected = any('ESTABLISHED' in line and '127.0.0.1:6199 ' in line for line in network.splitlines())
    except (OSError, subprocess.TimeoutExpired):
        connected = None

    log = _read_log()
    errors = [line for line in log.splitlines() if '[ERROR]' in line or 'readiness failed' in line]
    group_rows = collect_group_rows(log)
    quota_rows = collect_quota_rows()

    diary = _read_json(DATA / 'dafeiyu_diary_state.json', {})
    diary_library = _read_json(DATA / 'diary_library' / 'catalog.json', [])
    watchdog = _read_json(DATA / 'dafeiyu_watchdog.json', {})
    if not isinstance(diary, dict):
        diary = {}
    if not isinstance(diary_library, list):
        diary_library = []
    else:
        library_folder = DATA / 'diary_library' / 'images'
        diary_library = [
            item for item in diary_library
            if isinstance(item, dict)
            and (library_folder / str(item.get('file') or '')).is_file()
        ]
    if not isinstance(watchdog, dict):
        watchdog = {}

    now = time.time()
    if now - _AUTOSTART_CACHE['at'] > 300:
        _AUTOSTART_CACHE['at'] = now
        try:
            _AUTOSTART_CACHE['value'] = subprocess.run(
                ['schtasks', '/Query', '/TN', '大肥鱼自动启动'],
                capture_output=True, creationflags=HIDDEN, timeout=8,
            ).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            _AUTOSTART_CACHE['value'] = None
    autostart = _AUTOSTART_CACHE['value']

    backup = None
    backups = sorted((ROOT / 'runtime' / 'backups').glob('dafeiyu_*.zip'),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    if backups:
        newest = backups[0]
        backup = (newest.name, datetime.fromtimestamp(newest.stat().st_mtime).strftime('%m-%d %H:%M'),
                  newest.stat().st_size // 1024)

    memories = {}
    for key, name in (('private', 'dafeiyu_memory.md'), ('group', 'dafeiyu_group_memory.md')):
        path = DATA / name
        if path.exists():
            try:
                memories[key] = sum(1 for line in path.read_text(encoding='utf-8').splitlines()
                                    if line.strip().startswith('- '))
            except OSError:
                pass

    memory_job = {'pending': (DATA / 'dafeiyu_memory.flag').exists(), 'last_run': '',
                  'private_added': None, 'group_added': None, 'error': ''}
    job = _read_json(DATA / 'dafeiyu_memory_state.json', {})
    if isinstance(job, dict):
        memory_job.update(last_run=str(job.get('last_run') or ''),
                          private_added=job.get('private_added'),
                          group_added=job.get('group_added'),
                          error=str(job.get('error') or ''))

    selftest = '未运行'
    report = ROOT / 'runtime' / 'logs' / '自检报告.txt'
    if report.exists():
        try:
            report_text = report.read_text(encoding='utf-8', errors='replace')
            passed = re.search(r'通过 (\d+)/(\d+)', report_text)
            day = re.search(r'大肥鱼自检 · ([0-9-]+) ([0-9:]+)', report_text)
            if passed:
                selftest = '%s/%s 通过' % (passed.group(1), passed.group(2))
                if day:
                    selftest += ' · ' + day.group(1) + ' ' + day.group(2)[:5]
                if isinstance(backup, tuple) and len(backup) == 3:
                    selftest += ' · 备份 %.0f MB（%s）' % (backup[2] / 1024, backup[1])
            else:
                selftest = '报告格式异常'
        except OSError:
            selftest = '读取失败'

    protect = []
    lock = _read_json(DATA / 'dafeiyu_lock.json', {})
    if isinstance(lock, dict):
        try:
            hits = sum(int(v.get('count') or 0) for v in lock.values() if isinstance(v, dict))
            if hits:
                protect.append('人设改写拦截 %d 次' % hits)
        except (TypeError, ValueError):
            pass
    blocked = _read_json(DATA / 'dafeiyu_blocked.json', {})
    if blocked:
        protect.append('拉黑 %d 人' % len(blocked))

    qzone = _read_json(DATA / 'dafeiyu_qzone_reply.json', {})
    qzone_replies = int(qzone.get('count') or 0) if isinstance(qzone, dict) else 0

    open_group_used = 0

    online_state = _read_json(DATA / 'dafeiyu_online_state.json', {})
    if not isinstance(online_state, dict):
        online_state = {}
    last_shutdown = ''
    shutdown_path = ROOT / 'runtime' / 'logs' / '下线记录.txt'
    if shutdown_path.exists():
        try:
            tail = [ln.strip() for ln in shutdown_path.read_text(encoding='utf-8', errors='replace').splitlines()
                    if ln.strip()]
            if tail:
                last_shutdown = tail[-1][:100]
        except OSError:
            pass

    joined = bool(group_rows) and all(row.get('member') for row in group_rows)
    ready = bool(ports[6185] and ports[6099] and connected)
    today_replies = sum(int(row.get('count') or 0) for row in group_rows)
    private_used = sum(int(row.get('count') or 0) for row in quota_rows)
    limit_total = sum(int(row.get('limit') or 1) for row in quota_rows)
    return {
        'ports': ports,
        'connected': connected,
        'errors': errors,
        'group_rows': group_rows,
        'quota_rows': quota_rows,
        'diary': diary,
        'diary_library': len(diary_library),
        'watchdog': watchdog,
        'autostart': autostart,
        'backup': backup,
        'memories': memories,
        'memory_job': memory_job,
        'selftest': selftest,
        'qqmusic': qqmusic_status(),
        'joined': joined,
        'diary_loaded': 'Whale diary next run:' in log,
        'protect': protect,
        'qzone_replies': qzone_replies,
        'open_group_used': open_group_used,
        'online_state': online_state,
        'last_shutdown': last_shutdown,
        'ready': ready,
        'today_replies': today_replies,
        'private_used': private_used,
        'limit_total': limit_total,
        'group_joined': sum(1 for row in group_rows if row['member']),
        'group_disabled': sum(1 for row in group_rows if not row['enabled']),
        'group_unlimited': sum(1 for row in group_rows if row['limit'] == 0),
        'mirror': collect_mirror_snapshot() if mirror else None,
    }


# ---------- 总览 ----------
class OverviewPage(tk.Frame):
    def __init__(self, app, parent):
        super().__init__(parent, bg=BG)
        self.app = app
        self.data = {}
        self.banner_text = None
        self.banner_kind = 'info'
        self._pulse_phase = 0.0
        self._pulse_ids = None
        self.values = {}

        self.scroll = ScrollArea(self, BG)
        self.scroll.pack(fill='both', expand=True)
        content = self.scroll.inner

        self.hero = tk.Canvas(content, height=128, bg=BG, highlightthickness=0, bd=0)
        self.hero.pack(fill='x', padx=26, pady=(6, 8))
        self.hero.bind('<Configure>', lambda _e: self._draw_hero())

        self.tiles = tk.Frame(content, bg=BG)
        self.tiles.pack(fill='x', padx=26)
        specs = [
            ('chat', '聊天程序', I_CHAT, CYAN, '端口 6185'),
            ('qq', 'QQ 接入', I_GROUP, VIOLET, 'NapCat 6099'),
            ('connection', 'QQ 连接', I_LINK, GREEN, '实时链路'),
        ]
        self.tile_values = {}
        self.tile_subs = {}
        self.tile_dots = {}
        for i, (key, label, icon, color, sub) in enumerate(specs):
            card = Card(self.tiles, height=86, pad=14, accent=color)
            card.pack(side='left', fill='x', expand=True, padx=(0 if i == 0 else 8, 0))
            icon_box = tk.Canvas(card.body, width=36, height=36, bg=CARD, highlightthickness=0)
            icon_box.pack(side='left', padx=(0, 11))
            icon_box.create_oval(0, 0, 36, 36, fill=mix(color, CARD, 0.83), outline=mix(color, CARD, 0.62))
            icon_box.create_text(18, 18, text=icon, fill=color, font=(ICON_FONT, 13))
            box = tk.Frame(card.body, bg=CARD)
            box.pack(side='left', fill='both', expand=True)
            tk.Label(box, text=label, bg=CARD, fg=DIM, font=(FONT, 8)).pack(anchor='w')
            value = tk.Label(box, text='检查中', bg=CARD, fg=TEXT, font=(FONT, 15, 'bold'))
            value.pack(anchor='w')
            sub_label = tk.Label(box, text=sub, bg=CARD, fg=DIM, font=(FONT, 8))
            sub_label.pack(anchor='w')
            self.tile_values[key] = value
            self.tile_subs[key] = sub_label
            self.tile_dots[key] = color

        self.info = Card(content, height=190, pad=16, accent=CYAN)
        self.info.pack(fill='x', padx=26, pady=(8, 0))
        info_head = tk.Frame(self.info.body, bg=CARD)
        info_head.pack(fill='x', pady=(0, 4))
        tk.Label(info_head, text='系统状态', bg=CARD, fg='#DCEBFF',
                 font=(FONT, 10, 'bold')).pack(side='left')
        self.info_pill = Pill(info_head, '自动刷新 · 5s', TEAL, dot=True, bg=CARD)
        self.info_pill.pack(side='right')
        self.info_values = {}
        rows = [
            ('qqmusic', 'QQ 音乐', I_STAR, VIOLET),
            ('group', '群聊与独立记忆', I_GROUP, CYAN),
            ('diary', '每日空间动态', I_CLOCK, AMBER),
            ('selftest', '最近自检（可选）', I_CHECK, GREEN),
        ]
        for index, (key, label, icon, color) in enumerate(rows):
            if index:
                tk.Frame(self.info.body, bg='#172941', height=1).pack(fill='x', pady=2)
            row = tk.Frame(self.info.body, bg=CARD, height=33)
            row.pack(fill='x')
            dot = tk.Canvas(row, width=22, height=22, bg=CARD, highlightthickness=0)
            dot.pack(side='left', padx=(0, 8))
            dot.create_oval(2, 2, 20, 20, fill=mix(color, CARD, 0.84), outline='')
            dot.create_text(11, 11, text=icon, fill=color, font=(ICON_FONT, 8))
            tk.Label(row, text=label, bg=CARD, fg=MUTED, font=(FONT, 9),
                     width=13, anchor='w').pack(side='left')
            value = tk.Label(row, text='—', bg=CARD, fg=TEXT, font=(FONT, 9), anchor='w')
            value.pack(side='left', fill='x', expand=True)
            self.info_values[key] = value
        self.values.update(self.info_values)

        self.actions = Card(content, pad=14, accent=GOLD, auto=True)
        self.actions.pack(fill='x', padx=26, pady=(8, 0))
        tk.Label(self.actions.body, text='运行与管理', bg=CARD, fg=TEXT,
                 font=(FONT, 10, 'bold')).pack(anchor='w')
        self.auto_label = tk.Label(self.actions.body,
                                  text='每 5 秒自动刷新 · 下线时自动提炼记忆并备份',
                                  bg=CARD, fg=DIM, font=(FONT, 8))
        self.auto_label.pack(anchor='w', pady=(3, 10))
        groups = [
            ('常用操作', [('启动上线', app.start, 'primary'),
                         ('结束下线', app.stop, 'danger'),
                         ('立即刷新', lambda: app.refresh(manual=True), 'ghost')]),
            ('账号与内容', [('QQ 登录二维码', app.show_qr, 'ghost'),
                           ('QQ 音乐登录', app.qq_login_menu, 'ghost'),
                           ('表情包管理', app.manage_stickers, 'ghost'),
                           ('动态图库', app.open_diary_library, 'ghost')]),
            ('检查与维护', [('通知待核查', app.review_notices, 'ghost'),
                           ('插件管理', lambda: webbrowser.open('http://127.0.0.1:6185'), 'ghost'),
                           ('打开日志', app.open_log, 'ghost'),
                           ('重置所有好友额度', app.reset_quota, 'ghost')]),
        ]
        for label, actions in groups:
            tk.Label(self.actions.body, text=label, bg=CARD, fg=DIM,
                     font=(FONT, 8)).pack(anchor='w', pady=(5, 5))
            ActionFlow(self.actions.body, actions).pack(fill='x', pady=(0, 5))

        self.detail_card = Card(content, height=136, pad=14, accent=None)
        self.detail_card.pack(fill='x', padx=26, pady=(8, 10))
        detail_head = tk.Frame(self.detail_card.body, bg=CARD)
        detail_head.pack(fill='x')
        tk.Label(detail_head, text='运行详情', bg=CARD, fg='#DCEBFF',
                 font=(FONT, 10, 'bold')).pack(side='left')
        SoftButton(detail_head, '查看全部', self.open_detail_dialog, 'ghost', width=82,
                   height=24, font_size=8, bg=CARD).pack(side='right')
        self.detail = tk.Text(self.detail_card.body, height=4, wrap='word', bg=CARD, fg=MUTED,
                              relief='flat', bd=0, highlightthickness=0, font=(FONT, 8),
                              padx=0, pady=2, spacing1=2, spacing3=2, cursor='arrow')
        self.detail.pack(fill='both', expand=True, pady=(4, 0))
        self.detail.configure(state='disabled')
        self.detail.tag_configure('good', foreground=GREEN)
        self.detail.tag_configure('warn', foreground=AMBER)
        self.detail.tag_configure('bad', foreground=CORAL)
        self.detail.tag_configure('dim', foreground=DIM)
        self.detail.bind('<MouseWheel>', lambda e: (self.scroll.scroll_pixels(-e.delta / 120 * 80), 'break')[1])

    def set_banner(self, text, kind='info'):
        self.banner_text = text
        self.banner_kind = kind
        self._draw_hero()

    def _service_count(self):
        ports = self.data.get('ports') or {}
        return sum(1 for p in (6185, 6099) if ports.get(p)) + (1 if self.data.get('connected') else 0)

    def _draw_hero(self):
        canvas = self.hero
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if w < 120 or h < 80:
            return
        ready = bool(self.data.get('ready'))
        if self.banner_kind == 'warn':
            ready = False
        canvas.delete('all')
        if PIL_OK:
            self._hero_photo = _photo(('hero', w, h, ready), hero_photo(w, h, ready))
            canvas.create_image(0, 0, anchor='nw', image=self._hero_photo)
        else:
            canvas.create_rectangle(0, 0, w, h, fill=('#0B2A4A' if ready else '#4A2A12'),
                                    outline='')
        canvas.create_text(28, 18, text='D A F E I Y U   ·   C O N T R O L   C E N T E R',
                           anchor='nw', fill='#BAE6FD', font=(FONT, 7, 'bold'))
        canvas.create_text(w - 26, 18, text='YunShan_You · 悠云山',
                           anchor='ne', fill='#7FA6C8', font=(FONT, 7))
        status_text = '运行正常' if self.data.get('ready') else '需要关注'
        if not self.data:
            status_text = '正在检查…'
        if self.banner_text:
            status_text = '正在启动…' if self.banner_kind == 'info' else '需要处理'
        status_color = '#FFFFFF' if self.data.get('ready') and not self.banner_text else '#FFE7B0'
        self._pulse_ids = (
            canvas.create_oval(30, 48, 44, 62, fill=mix(status_color, '#0B2A4A', 0.72), outline=''),
            canvas.create_oval(33, 51, 41, 59, fill=status_color, outline=''),
        )
        canvas.create_text(52, 38, text=status_text, anchor='nw', fill=status_color,
                           font=(FONT, 25, 'bold'))
        if self.banner_text:
            sub = self.banner_text
        elif self.data:
            services = self._service_count()
            sub = ('QQ 连接已建立' if self.data.get('connected') else '等待 QQ 连接')
            sub += ' · %d / 3 项服务在线 · 最近刷新 %s' % (services, self.app.last_refresh_text)
        else:
            sub = '正在读取本机服务与群聊状态'
        canvas.create_text(30, 82, text=sub, anchor='nw', fill='#CBE8FF', font=(FONT, 9))

        if self.data:
            stats = [
                ('今日群回复', str(self.data.get('today_replies', 0)), GREEN),
                ('私聊已用', str(self.data.get('private_used', 0)), GOLD),
                ('在线群', '%d/%d' % (self.data.get('group_joined', 0),
                                     len(self.data.get('group_rows') or [])), CYAN),
            ]
            x = w - 352
            for label, value, color in stats:
                canvas.create_text(x, 38, text=value, anchor='nw', fill=color,
                                   font=('Bahnschrift', 20, 'bold'))
                canvas.create_text(x, 70, text=label, anchor='nw', fill='#A0C6E2', font=(FONT, 8))
                x += 118

        pills = [
            ('聊天程序', bool((self.data.get('ports') or {}).get(6185))),
            ('QQ 接入', bool((self.data.get('ports') or {}).get(6099))),
            ('QQ 连接', bool(self.data.get('connected'))),
        ]
        x = 30
        for label, ok in pills:
            color = GREEN if ok else CORAL
            pw = _measure(label, 8) + 30
            round_rect(canvas, x, h - 25, x + pw, h - 8, 8,
                       fill='#0B2740', outline=mix(color, '#0B2740', 0.55))
            canvas.create_oval(x + 10, h - 19, x + 16, h - 13, fill=color, outline='')
            canvas.create_text(x + 21, h - 16, text=label, anchor='w',
                               fill='#D5ECFF', font=(FONT, 8))
            x += pw + 8
        self._pulse_phase = 0.0

    def tick_pulse(self):
        if not self._pulse_ids or not self.hero.winfo_viewable():
            return
        self._pulse_phase += 0.22
        scale = 1 + 0.16 * math.sin(self._pulse_phase)
        color = GREEN if self.data.get('ready') else AMBER
        if not self.data:
            color = CYAN
        self.hero.coords(self._pulse_ids[0], 37 - 8 * scale, 55 - 8 * scale,
                         37 + 8 * scale, 55 + 8 * scale)
        self.hero.coords(self._pulse_ids[1], 37 - 3 * scale, 55 - 3 * scale,
                         37 + 3 * scale, 55 + 3 * scale)
        self.hero.itemconfigure(self._pulse_ids[0], fill=mix(color, '#0B2A4A', 0.70))
        self.hero.itemconfigure(self._pulse_ids[1], fill=color)

    def update_data(self, data):
        self.data = data
        self.banner_text = None
        self._draw_hero()
        ports = data.get('ports') or {}
        connected = data.get('connected')
        chat_ok = bool(ports.get(6185))
        qq_ok = bool(ports.get(6099))
        conn_ok = bool(connected)
        self.tile_values['chat'].configure(text='运行中' if chat_ok else '未运行',
                                           fg=(TEXT if chat_ok else CORAL))
        self.tile_subs['chat'].configure(text='端口 6185 正常' if chat_ok else '端口 6185 未监听',
                                         fg=(DIM if chat_ok else CORAL))
        self.tile_values['qq'].configure(text='接入服务运行中' if qq_ok else '未运行',
                                         fg=(TEXT if qq_ok else CORAL))
        self.tile_subs['qq'].configure(text='NapCat 6099' if qq_ok else 'NapCat 未监听',
                                       fg=(DIM if qq_ok else CORAL))
        conn_text = '已连接' if conn_ok else ('等待连接' if connected is False else '暂时无法确认')
        self.tile_values['connection'].configure(text=conn_text, fg=(TEXT if conn_ok else AMBER))
        self.tile_subs['connection'].configure(text='实时链路稳定' if conn_ok else '检查 127.0.0.1:6199',
                                               fg=(DIM if conn_ok else AMBER))
        self._update_info(data)
        self._update_detail(data)
        self.info_pill.set('自动刷新 · 5s', TEAL)

    def _update_info(self, data):
        qqmusic = data.get('qqmusic') or {}
        if not qqmusic.get('running'):
            text, color = '后端未启动', CORAL
        elif qqmusic.get('logged'):
            text = '已登录 · uin %s · 库 %s 首' % (qqmusic.get('uin') or '未知', qqmusic.get('songs', 0))
            color = '#BAE6FD'
        else:
            text = '后端运行中 · 未登录 · 库 %s 首' % qqmusic.get('songs', 0)
            color = AMBER
        self.info_values['qqmusic'].configure(text=text, fg=color)

        rows = data.get('group_rows') or []
        counts = {row['gid']: row['count'] for row in rows}
        if rows:
            labels = [(row['gid'], str(row['name']).split('（')[0][:6]) for row in rows[:5]]
            group_text = '今日回 ' + ' · '.join('%s %d' % (name, counts.get(gid, 0)) for gid, name in labels)
            five_total = sum(counts.get(gid, 0) for gid, _name in labels)
            other_total = max(0, int(data.get('today_replies', 0)) - five_total)
            if other_total:
                group_text += ' · 其他 %d' % other_total
            group_text += ' · 本次启动已验证入群' if data.get('joined') and data.get('ready') else ' · 在线状态待确认'
        else:
            group_text = '还没有发现群 · 拉进群后到「群聊状态」放权'
        self.info_values['group'].configure(text=group_text, fg='#DCEBFF')

        diary = data.get('diary') or {}
        status = {'published': '发布成功', 'failed': '发布失败',
                  'sending': '发送结果待核对'}.get(diary.get('status'), '尚无发布记录')
        kind = {'library': '图库照', 'sticker': '表情包'}.get(diary.get('image_kind'), '')
        if diary.get('image') and diary.get('image_error'):
            figure = ' · 配图未附上'
        elif diary.get('image'):
            figure = ' · 已配图' + ('（' + kind + '）' if kind else '')
        else:
            figure = ''
        diary_color = '#DCEBFF'
        if diary.get('status') == 'failed':
            diary_color = CORAL
        elif diary.get('status') == 'sending' or not diary.get('status'):
            diary_color = AMBER
        text = '每天 21:00 · ' + ('任务已加载' if data.get('diary_loaded') and (data.get('ports') or {}).get(6185)
                                 else '任务待启动') + ' · ' + status + figure
        library_count = int(data.get('diary_library') or 0)
        text += (' · 图库 %d 张' % library_count) if library_count else ' · 图库未建'
        self.info_values['diary'].configure(text=text, fg=diary_color)

        selftest = str(data.get('selftest') or '未运行')
        today = datetime.now().strftime('%Y-%m-%d')
        if '通过' in selftest and today in selftest:
            color = GREEN
        elif '通过' in selftest:
            color = AMBER
        else:
            color = CORAL
        self.info_values['selftest'].configure(text=selftest, fg=color)

    def detail_lines(self, data=None):
        data = data or self.data
        lines = []
        watchdog = data.get('watchdog') or {}
        if watchdog:
            if watchdog.get('online'):
                lines.append(('看门狗：QQ 在线（最近探测 ' + str(watchdog.get('checked_at', ''))[-8:] + '）', 'good'))
            else:
                lines.append(('看门狗：QQ 未连接（自 ' + str(watchdog.get('offline_since') or '未知') +
                              '，原因 ' + str(watchdog.get('detail') or '未知') + '）', 'bad'))
        lines.append(('群聊作息：全天在线（无定时静默）', 'dim'))
        job = data.get('memory_job') or {}
        if job.get('pending'):
            lines.append(('记忆提炼：已请求，约 10 秒内开始（结果会自动刷新）', 'warn'))
        elif job.get('error'):
            lines.append(('记忆提炼：上次失败（' + str(job.get('error')) + '）', 'bad'))
        elif job.get('last_run'):
            lines.append(('记忆提炼：最近 ' + str(job.get('last_run')) + '（新增 私聊 ' +
                          str(job.get('private_added')) + ' / 群聊 ' + str(job.get('group_added')) + ' 条）', 'normal'))
        quota = data.get('quota_rows') or []
        if quota:
            top = quota[:4]
            lines.append(('今日好友额度：' + ' · '.join('%s %d/%d' % (r['nick'], r['count'], r['limit'])
                                                       for r in top), 'normal'))
        if data.get('qzone_replies'):
            lines.append(('空间评论回复：今天已回 %d 条（同一动态同一人只回一次）' % data['qzone_replies'], 'normal'))
        if data.get('protect'):
            lines.append(('防护：' + ' · '.join(data['protect']), 'good'))
        backup = data.get('backup')
        if backup:
            size_kb = backup[2]
            size_text = '%.1f MB' % (size_kb / 1024) if size_kb >= 1024 else '%d KB' % size_kb
            lines.append(('最近备份：' + backup[1] + '（' + size_text + '，保留最近 8 份）', 'normal'))
        if data.get('last_shutdown'):
            lines.append(('上次关机：' + data['last_shutdown'], 'dim'))
        online_state = data.get('online_state') or {}
        outage = online_state.get('last_outage') or {}
        if outage.get('end'):
            when = datetime.fromtimestamp(float(outage['end'])).strftime('%m-%d %H:%M')
            if str(outage.get('mode') or '') == 'startup':
                lines.append(('上次启动：%s 离线 %s 分钟' % (
                    when, outage.get('minutes', '?')), 'normal'))
            else:
                lines.append(('上次断线：%s 断了 %s 分钟，补回 %s 位好友（共 %s 条待回）' % (
                    when, outage.get('minutes', '?'), outage.get('sent', 0), outage.get('friends', 0)), 'normal'))
        else:
            lines.append(('上次断线：暂无记录', 'dim'))
        if online_state.get('outages_today'):
            lines.append(('今日断线：%d 次（断满 5 分钟才计数）' % int(online_state['outages_today']), 'normal'))
        if data.get('autostart') is not None:
            lines.append(('自动启动：' + ('已启用（登录后自动在托盘启动）' if data['autostart']
                                          else '未启用（在控制中心手动上线）'), 'dim'))
        diary = data.get('diary') or {}
        if diary.get('attempted_day'):
            lines.append(('最近发布日期：' + str(diary['attempted_day']), 'normal'))
        if data.get('errors'):
            lines.append(('日志中最近的错误：' + data['errors'][-1][:230], 'bad'))
        if data and not data.get('ready'):
            if not (data.get('ports') or {}).get(6099):
                lines.append(('QQ 接入未运行：请先登录 QQ（1000000000），并同意管理员权限。', 'warn'))
            lines.append(('可点「启动上线」；若仍未连接，请打开日志检查 QQ 扫码或模型错误。', 'warn'))
        return lines

    def _update_detail(self, data):
        lines = self.detail_lines(data)
        self.detail.configure(state='normal')
        self.detail.delete('1.0', 'end')
        for text_, tag in lines[:4]:
            self.detail.insert('end', text_ + '\n', tag)
        self.detail.configure(state='disabled')

    def open_detail_dialog(self):
        dialog = tk.Toplevel(self.app.root)
        dialog.title('运行详情')
        dialog.configure(bg=BG)
        dialog.geometry('760x560')
        dialog.transient(self.app.root)
        card = Card(dialog, pad=20, shadow=10, auto=True)
        card.pack(fill='both', expand=True, padx=18, pady=18)
        tk.Label(card.body, text='运行详情', bg=CARD, fg=TEXT,
                 font=(FONT, 15, 'bold')).pack(anchor='w')
        tk.Label(card.body, text='本机服务、记忆、备份与断线记录', bg=CARD, fg=DIM,
                 font=(FONT, 8)).pack(anchor='w', pady=(2, 10))
        text = tk.Text(card.body, wrap='word', bg=CARD_SOFT, fg=MUTED, relief='flat', bd=0,
                       highlightthickness=1, highlightbackground=BORDER, font=(FONT, 9),
                       padx=12, pady=10, spacing1=3, spacing3=3)
        text.pack(fill='both', expand=True)
        for tag, color in (('good', GREEN), ('warn', AMBER), ('bad', CORAL), ('dim', DIM), ('normal', TEXT)):
            text.tag_configure(tag, foreground=color)
        for text_, tag in self.detail_lines():
            text.insert('end', text_ + '\n', tag)
        text.configure(state='disabled')
        SoftButton(card.body, '关闭', dialog.destroy, 'ghost', width=92, height=30,
                   bg=CARD).pack(anchor='e', pady=(10, 0))
        dialog.grab_set()


# ---------- 私聊额度 ----------
def quota_colors(ratio):
    if ratio >= 0.99:
        return CORAL, RED
    if ratio >= 0.9:
        return ORANGE, CORAL
    if ratio >= 0.7:
        return AMBER, ORANGE
    return CYAN, BLUE


def avatar_color(qq):
    palette = [CYAN, VIOLET, TEAL, AMBER, CORAL, BLUE, INDIGO, GREEN]
    return palette[sum(ord(c) for c in str(qq)) % len(palette)]


class QuotaRow:
    ROW_HEIGHT = 110
    CARD_HEIGHT = 102

    def __init__(self, parent, app):
        self.app = app
        self.row = {'qq': '', 'nick': '—', 'count': 0, 'limit': 75, 'custom': False}
        self.frame = tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1,
                              height=self.CARD_HEIGHT)
        self.frame.pack_propagate(False)
        top = tk.Frame(self.frame, bg=CARD)
        top.pack(fill='x', padx=12, pady=(8, 2))
        self.avatar = tk.Canvas(top, width=38, height=38, bg=CARD, highlightthickness=0)
        self.avatar.pack(side='left', padx=(0, 10))
        self._avatar_ring = self.avatar.create_oval(1, 1, 37, 37, fill=CARD, outline=BORDER)
        self._avatar_text = self.avatar.create_text(19, 19, text='Q', fill=TEXT, font=(FONT, 12, 'bold'))
        who = tk.Frame(top, bg=CARD)
        who.pack(side='left', fill='x', expand=True)
        name_line = tk.Frame(who, bg=CARD)
        name_line.pack(anchor='w')
        self.name_label = tk.Label(name_line, text='—', bg=CARD, fg='#EAF3FF',
                                   font=(FONT, 10, 'bold'))
        self.name_label.pack(side='left')
        self.qq_label = tk.Label(name_line, text='', bg=CARD, fg=DIM, font=(FONT, 8))
        self.qq_label.pack(side='left', padx=(8, 0))
        self.custom = tk.Label(name_line, text=' 自定义 ', bg=mix(VIOLET, CARD, 0.82),
                               fg=lighten(VIOLET, 0.40), font=(FONT, 7), padx=4, pady=1)
        self.custom.pack_forget()
        self.count_label = tk.Label(top, text='', bg=CARD, fg=TEXT, font=(FONT, 10, 'bold'))
        self.count_label.pack(side='right', padx=(10, 0))

        self.bar = GradientBar(self.frame, height=9, bg=CARD)
        self.bar.pack(fill='x', padx=12, pady=(2, 4))

        controls = tk.Frame(self.frame, bg=CARD)
        controls.pack(fill='x', padx=12, pady=(0, 9))
        tk.Label(controls, text='每日上限', bg=CARD, fg=DIM, font=(FONT, 8)).pack(side='left')
        self.stepper = Stepper(controls, 75, minimum=1, maximum=2000, width=88, bg=CARD)
        self.stepper.pack(side='left', padx=(6, 8))
        SoftButton(controls, '保存上限', self._save, 'soft', width=82, height=28,
                   font_size=8, bg=CARD).pack(side='left', padx=(0, 6))
        SoftButton(controls, '重置本用户额度', self._reset, 'ghost', width=108, height=28,
                   font_size=8, bg=CARD).pack(side='left')
        tk.Label(controls, text='封禁', bg=CARD, fg=DIM, font=(FONT, 8)).pack(side='left', padx=(10, 5))
        self.block_var = tk.BooleanVar(value=False)
        self.block_switch = ToggleSwitch(controls, self.block_var, command=self._toggle_block,
                                         bg=CARD, width=40, height=22)
        self.block_switch.pack(side='left')
        self.block_state = tk.Label(controls, text='正常', bg=CARD, fg=GREEN, font=(FONT, 8))
        self.block_state.pack(side='left', padx=(6, 0))
        self.remain = tk.Label(controls, text='', bg=CARD, fg=MUTED, font=(FONT, 8))
        self.remain.pack(side='right')

    def _save(self):
        if self.row.get('qq'):
            self.app.save_user_limit(self.row['qq'], self.stepper.var)

    def _reset(self):
        if self.row.get('qq'):
            self.app.reset_user_quota(self.row['qq'], self.row['nick'])

    def _toggle_block(self):
        if self.row.get('qq'):
            self.app.set_user_blocked(self.row['qq'], self.block_var, self.row.get('nick', ''))

    def set_row(self, row, animate=False):
        changed = (self.row.get('qq') != row['qq'] or self.row.get('nick') != row['nick']
                   or bool(self.row.get('custom')) != bool(row.get('custom')))
        if changed:
            self.row = row
            color = avatar_color(row['qq'])
            initial = 'Q'
            if row['nick'].startswith('QQ'):
                initial = 'Q'
            else:
                for ch in row['nick'].strip():
                    if ch.isalnum() or '\u4e00' <= ch <= '\u9fff':
                        initial = ch
                        break
            self.avatar.itemconfigure(self._avatar_ring, fill=mix(color, CARD, 0.78),
                                      outline=mix(color, CARD, 0.55))
            self.avatar.itemconfigure(self._avatar_text, text=initial.upper(),
                                      fill=lighten(color, 0.45))
            self.name_label.configure(text=row['nick'][:24])
            self.qq_label.configure(text=row['qq'])
            if row['custom']:
                self.custom.pack(side='left', padx=(6, 0))
            else:
                self.custom.pack_forget()
            self.stepper.set(row['limit'])
            self.update(row, animate=False)
        else:
            self.row = row
            self.update(row, animate=animate)

    def update(self, row, animate=True):
        self.row = row
        ratio = row['count'] / max(1, row['limit'])
        c1, c2 = quota_colors(ratio)
        self.count_label.configure(text='%d / %d' % (row['count'], row['limit']),
                                   fg=(CORAL if ratio >= 1 else (ORANGE if ratio >= 0.9 else TEXT)))
        self.bar.set(min(row['count'], row['limit']), max(1, row['limit']), c1, c2, animate=animate)
        remaining = max(0, row['limit'] - row['count'])
        self.remain.configure(text='今日剩余 %d 条' % remaining,
                              fg=(CORAL if remaining == 0 else (AMBER if ratio >= 0.8 else MUTED)))
        try:
            focused = self.frame.focus_get() is self.stepper.entry
        except (tk.TclError, KeyError):
            focused = False
        if not focused and str(self.stepper.var.get()) != str(row['limit']):
            self.stepper.set(row['limit'])
        blocked = bool(row.get('blocked'))
        if bool(self.block_var.get()) != blocked:
            self.block_switch.set(blocked)
        self.block_state.configure(text='已封禁' if blocked else '正常',
                                   fg=(CORAL if blocked else GREEN))
        self.frame.configure(highlightbackground=(CORAL if blocked else BORDER))


class QuotaPage(tk.Frame):
    def __init__(self, app, parent):
        super().__init__(parent, bg=BG)
        self.app = app
        self.all_rows = []
        self.rows = []
        self._signature = None
        self._filter_job = None
        self._viewport_job = None
        self._pool = []
        self._mounted = {}
        self._loaded = False

        bar_box = tk.Frame(self, bg=BG)
        bar_box.pack(fill='x', padx=26, pady=(4, 8))
        self.search = SearchBox(bar_box, command=self.schedule_filter, bg=BG, width=680, height=40)
        self.search.pack(side='left', fill='x', expand=True)
        SoftButton(bar_box, '刷新', lambda: app.refresh(manual=True), 'ghost', width=92,
                   height=38, icon=I_REFRESH, bg=BG).pack(side='left', padx=(10, 0))
        self.search_hint = tk.Label(bar_box, text='按昵称或 QQ 过滤', bg=BG, fg=DIM,
                                    font=(FONT, 8))
        self.search_hint.pack(side='right', padx=(12, 0))

        summary = Card(self, height=110, pad=14, accent=GOLD)
        summary.pack(fill='x', padx=26)
        left = tk.Frame(summary.body, bg=CARD)
        left.pack(side='left', fill='y')
        tk.Label(left, text='今日私聊已用', bg=CARD, fg=DIM, font=(FONT, 8)).pack(anchor='w')
        line = tk.Frame(left, bg=CARD)
        line.pack(anchor='w')
        self.used_value = tk.Label(line, text='0', bg=CARD, fg=GOLD, font=('Bahnschrift', 20, 'bold'))
        self.used_value.pack(side='left')
        self.used_unit = tk.Label(line, text=' 条', bg=CARD, fg=MUTED, font=(FONT, 8))
        self.used_unit.pack(side='left', pady=(5, 0))
        self.people_value = tk.Label(left, text='覆盖 0 位好友', bg=CARD, fg=DIM, font=(FONT, 8))
        self.people_value.pack(anchor='w', pady=(1, 0))
        right = tk.Frame(summary.body, bg=CARD)
        right.pack(side='right', fill='both', expand=True, padx=(24, 0))
        top_line = tk.Frame(right, bg=CARD)
        top_line.pack(fill='x', pady=(4, 0))
        self.limit_value = tk.Label(top_line, text='0 / 0 条', bg=CARD, fg='#DCEBFF',
                                    font=(FONT, 9, 'bold'))
        self.limit_value.pack(side='right')
        tk.Label(top_line, text='全部好友总额度', bg=CARD, fg=DIM, font=(FONT, 8)).pack(side='left')
        style = ttk.Style()
        style.configure('QuotaSummary.Horizontal.TProgressbar', troughcolor='#22344F',
                        background=CYAN, bordercolor='#22344F', lightcolor=CYAN,
                        darkcolor=CYAN, thickness=9)
        self.total_bar = ttk.Progressbar(right, style='QuotaSummary.Horizontal.TProgressbar',
                                         maximum=100, value=0)
        self.total_bar.pack(fill='x', pady=(8, 0))
        self.summary_note = tk.Label(right, text='', bg=CARD, fg=DIM, font=(FONT, 8))
        self.summary_note.pack(anchor='w', pady=(4, 0))

        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill='both', expand=True, padx=20, pady=(10, 8))
        self.scroll = ScrollArea(self.body, BG)
        self.scroll.pack(fill='both', expand=True)
        self.list_inner = self.scroll.inner
        self.spacer = tk.Frame(self.list_inner, bg=BG, height=0)
        self.spacer.pack(fill='x')
        self.empty = tk.Label(self.list_inner, text='没有匹配的私聊用户', bg=BG, fg=DIM,
                              font=(FONT, 11), pady=40)
        self.scroll.canvas.configure(yscrollcommand=self._on_yscroll)
        self.scroll.canvas.bind('<Configure>', lambda _e: self._schedule_viewport(), add='+')

    def _on_yscroll(self, first, last):
        self.scroll.bar._on_scroll(first, last)
        self._schedule_viewport()

    def schedule_filter(self):
        if self._filter_job:
            try:
                self.after_cancel(self._filter_job)
            except tk.TclError:
                pass
        self._filter_job = self.after(180, self.apply_filter)

    def visible_rows(self):
        query = self.search.var.get().strip().lower()
        if not query:
            return list(self.all_rows)
        return [row for row in self.all_rows if query in row['nick'].lower() or query in row['qq']]

    def update_data(self, data, force=False):
        rows = data.get('quota_rows')
        if rows is not None:
            self.all_rows = list(rows)
        self._update_stats()
        self.apply_filter(force=force)

    def _update_stats(self):
        active = [row for row in self.all_rows if not row.get('blocked')]
        used = sum(row['count'] for row in self.all_rows)
        limit = sum(max(1, row['limit']) for row in active)
        custom = sum(1 for row in active if row['custom'])
        hot = sum(1 for row in active if row['count'] >= row['limit'])
        blocked = len(self.all_rows) - len(active)
        self.used_value.configure(text=str(used))
        self.people_value.configure(text='覆盖 %d 位好友 · 自定义上限 %d 位' % (len(active), custom))
        self.limit_value.configure(text='%d / %d 条' % (used, limit))
        self.total_bar.configure(value=(min(100, used / limit * 100) if limit else 0))
        note = '今日整体用量 %.0f%%' % (used / limit * 100 if limit else 0)
        if hot:
            note += ' · %d 位已用完' % hot
        if blocked:
            note += ' · 封禁 %d 人' % blocked
        self.summary_note.configure(text=note, fg=(CORAL if (hot or blocked) else DIM))

    def apply_filter(self, force=False):
        self._filter_job = None
        rows = self.visible_rows()
        signature = tuple((row['qq'], row['limit'], row['custom'], row['nick'],
                           bool(row.get('blocked'))) for row in rows)
        if force or not self._loaded or signature != self._signature:
            self._set_rows(rows)
            self._signature = signature
        else:
            self.rows = rows
            for pos, card in self._mounted.items():
                if pos < len(rows):
                    card.update(rows[pos])
        self._loaded = True

    def _set_rows(self, rows):
        self.rows = rows
        total = max(0, len(rows) * QuotaRow.ROW_HEIGHT + 8)
        self.spacer.configure(height=total)
        if rows:
            self.empty.pack_forget()
        else:
            self.empty.pack(fill='x')
        self.scroll.canvas.yview_moveto(0)
        self._schedule_viewport(force=True)

    def _ensure_pool(self, count):
        while len(self._pool) < count:
            self._pool.append(QuotaRow(self.list_inner, self.app))

    def _schedule_viewport(self, force=False):
        if force and self._viewport_job:
            try:
                self.after_cancel(self._viewport_job)
            except tk.TclError:
                pass
            self._viewport_job = None
        if self._viewport_job:
            return
        self._viewport_job = self.after(12, self._render_viewport)

    def _render_viewport(self):
        self._viewport_job = None
        if not self.rows:
            for card in self._pool:
                card.frame.place_forget()
            self._mounted = {}
            return
        top = self.scroll.canvas.canvasy(0)
        view_h = max(80, self.scroll.canvas.winfo_height())
        start = max(0, int(top // QuotaRow.ROW_HEIGHT) - 2)
        end = min(len(self.rows), int((top + view_h) // QuotaRow.ROW_HEIGHT) + 3)
        need = max(1, end - start)
        self._ensure_pool(need)
        for slot in range(need):
            pos = start + slot
            if pos >= len(self.rows):
                break
            card = self._pool[slot]
            card.set_row(self.rows[pos], animate=False)
            card.frame.place(x=0, y=pos * QuotaRow.ROW_HEIGHT + 4, relwidth=1.0)
            self._mounted[pos] = card
        for slot in range(need, len(self._pool)):
            self._pool[slot].frame.place_forget()
        for pos in list(self._mounted):
            if pos < start or pos >= end:
                self._mounted.pop(pos, None)

    def reload(self):
        position = self.scroll.canvas.yview()[0]
        self.update_data({'quota_rows': self.app.quota_snapshot()}, force=True)
        self.after(30, lambda: self.scroll.canvas.yview_moveto(position))


# ---------- 群聊状态 ----------
GROUP_COLORS = {}
GROUP_PALETTE = [CYAN, VIOLET, TEAL, AMBER, CORAL, BLUE, INDIGO, GREEN]


class GroupCard:
    def __init__(self, parent, app, row, expanded, color):
        self.app = app
        self.row = row
        self.color = color
        self.card = Card(parent, pad=16, shadow=8, accent=color, auto=True)
        self.card.pack(fill='x', padx=4, pady=2)
        body = self.card.body

        head = tk.Frame(body, bg=CARD)
        head.pack(fill='x')
        icon_box = tk.Canvas(head, width=38, height=38, bg=CARD, highlightthickness=0)
        icon_box.pack(side='left', padx=(0, 11))
        icon_box.create_oval(1, 1, 37, 37, fill=mix(color, CARD, 0.80),
                             outline=mix(color, CARD, 0.55), width=1)
        icon_box.create_text(19, 19, text=I_GROUP, fill=lighten(color, 0.38), font=(ICON_FONT, 11))
        title_box = tk.Frame(head, bg=CARD)
        title_box.pack(side='left', fill='x', expand=True)
        title = tk.Frame(title_box, bg=CARD)
        title.pack(anchor='w')
        tk.Label(title, text=row['name'][:34], bg=CARD, fg='#ECF5FF',
                 font=(FONT, 11, 'bold')).pack(side='left')
        tk.Label(title, text='  ' + row['gid'], bg=CARD, fg=DIM,
                 font=(FONT, 8)).pack(side='left')
        self.state_pill = Pill(head, '', GREEN, dot=True, height=24, bg=CARD)
        self.state_pill.pack(side='right', padx=(8, 0))
        self.count_label = tk.Label(head, text='', bg=CARD, fg='#DCEBFF', font=(FONT, 9))
        self.count_label.pack(side='right')

        self.bar = GradientBar(body, height=9, bg=CARD)
        self.bar.pack(fill='x', pady=(5, 4))
        self.no_limit = tk.Label(body, text='本群不设每日上限', bg=CARD, fg=DIM, font=(FONT, 8))

        meta = tk.Frame(body, bg=CARD)
        meta.pack(fill='x', pady=(2, 0))
        self.meta = meta
        self.member_label = tk.Label(meta, text='', bg=CARD, fg=MUTED, font=(FONT, 8))
        self.member_label.pack(side='left')
        self.toggle_var = tk.BooleanVar(value=bool(row['enabled']))
        switch_box = tk.Frame(meta, bg=CARD)
        switch_box.pack(side='right')
        tk.Label(switch_box, text='允许大肥鱼在这个群回复', bg=CARD, fg=MUTED,
                 font=(FONT, 8)).pack(side='left', padx=(0, 7))
        ToggleSwitch(switch_box, self.toggle_var,
                     command=lambda: self.app.set_group_enabled(self.row['gid'], self.toggle_var),
                     bg=CARD).pack(side='left')

        controls = tk.Frame(body, bg=CARD)
        controls.pack(fill='x', pady=(7, 0))
        tk.Label(controls, text='每日上限', bg=CARD, fg=DIM, font=(FONT, 8)).pack(side='left')
        self.stepper = Stepper(controls, row['limit'], minimum=0, maximum=2000, width=88, bg=CARD)
        self.stepper.pack(side='left', padx=(6, 8))
        SoftButton(controls, '保存上限',
                   lambda: self.app.save_group_limit(self.row['gid'], self.stepper.var),
                   'soft', width=82, height=28, font_size=8, bg=CARD).pack(side='left', padx=(0, 6))
        tk.Label(controls, text='0 = 无限', bg=CARD, fg=DIM, font=(FONT, 7)).pack(side='left')
        SoftButton(controls, '收起 ▾' if expanded else '调节 ▸',
                   lambda: self.app.toggle_group_settings(self.row['gid']),
                   'ghost', width=86, height=28, font_size=8, bg=CARD).pack(side='right')

        if expanded:
            panel = tk.Frame(body, bg=CARD_SOFT, highlightbackground='#1C3350',
                             highlightthickness=1)
            panel.pack(fill='x', pady=(9, 0))
            tk.Label(panel, text='本群互动强度（100 = 默认，200 = 双倍，0 = 关闭）',
                     bg=CARD_SOFT, fg='#B8CDE6', font=(FONT, 9, 'bold')).pack(anchor='w', padx=12, pady=(8, 5))
            self.settings_vars = {}
            for key, label, color, value in (
                    ('reply_desire', '回复欲望', CYAN, row['reply_desire']),
                    ('sticker_rate', '表情包发送频率', VIOLET, row['sticker_rate']),
                    ('voice_rate', '语音发送频率', CORAL, row['voice_rate'])):
                line = tk.Frame(panel, bg=CARD_SOFT)
                line.pack(fill='x', padx=12, pady=1)
                tk.Label(line, text=label, width=13, anchor='w', bg=CARD_SOFT, fg=MUTED,
                         font=(FONT, 8)).pack(side='left')
                var = tk.IntVar(value=int(value))
                self.settings_vars[key] = var
                value_label = tk.StringVar(value=str(value) + '%')
                GlowSlider(line, var, color=color, width=300, to=200,
                           command=lambda v, lab=value_label: lab.set(str(int(float(v))) + '%'),
                           bg=CARD_SOFT).pack(side='left', padx=(2, 8))
                tk.Label(line, textvariable=value_label, width=5, anchor='e', bg=CARD_SOFT,
                         fg=lighten(color, 0.35), font=(FONT, 8, 'bold')).pack(side='left')
            SoftButton(panel, '保存本群互动设置',
                       lambda: self.app.save_group_settings(self.row['gid'], self.settings_vars),
                       'soft', width=152, height=30, font_size=8,
                       bg=CARD_SOFT).pack(anchor='w', padx=12, pady=(6, 9))
        else:
            self.settings_vars = {}

        self.update_row(row, animate=False)

    def update_row(self, row, animate=True):
        self.row = row
        self.count_label.configure(text='今日回复 %d / %s' % (
            row['count'], '无限' if row['limit'] == 0 else row['limit']))
        if row['limit'] > 0:
            self.no_limit.pack_forget()
            if self.bar.winfo_manager() == '':
                self.bar.pack(fill='x', pady=(5, 4), before=self.meta)
            ratio = row['count'] / max(1, row['limit'])
            c1, c2 = quota_colors(ratio)
            self.bar.set(min(row['count'], row['limit']), max(1, row['limit']), c1, c2, animate=animate)
        else:
            self.bar.pack_forget()
            if self.no_limit.winfo_manager() == '':
                self.no_limit.pack(anchor='w', pady=(3, 4), before=self.meta)
        self.state_pill.set('已启用' if row['enabled'] else '已关闭',
                            GREEN if row['enabled'] else CORAL)
        self.member_label.configure(text='● 已入群' if row['member'] else '○ 入群状态待确认',
                                    fg=(GREEN if row['member'] else AMBER))
        if bool(self.toggle_var.get()) != bool(row['enabled']):
            self.toggle_var.set(bool(row['enabled']))
        try:
            focused = self.card.focus_get() is self.stepper.entry
        except (tk.TclError, KeyError):
            focused = False
        if not focused and str(self.stepper.var.get()) != str(row['limit']):
            self.stepper.set(row['limit'])


class GroupPage(tk.Frame):
    def __init__(self, app, parent):
        super().__init__(parent, bg=BG)
        self.app = app
        self.rows = []
        self.cards = {}
        self._signature = None
        self._loaded = False

        toolbar = tk.Frame(self, bg=BG)
        toolbar.pack(fill='x', padx=26, pady=(4, 8))
        SoftButton(toolbar, '刷新', lambda: app.refresh(manual=True), 'ghost', width=84,
                   height=36, icon=I_REFRESH, bg=BG).pack(side='left', padx=(0, 8))
        SoftButton(toolbar, '全部启用', lambda: app.set_all_groups(True), 'ghost', width=100,
                   height=36, bg=BG).pack(side='left', padx=(0, 6))
        SoftButton(toolbar, '全部关闭', lambda: app.set_all_groups(False), 'ghost', width=100,
                   height=36, bg=BG).pack(side='left', padx=(0, 6))
        SoftButton(toolbar, '全部无限', lambda: app.set_all_group_limits(0), 'ghost', width=100,
                   height=36, bg=BG).pack(side='left', padx=(0, 6))
        SoftButton(toolbar, '全部120', lambda: app.set_all_group_limits(120), 'ghost', width=92,
                   height=36, bg=BG).pack(side='left')
        tk.Label(toolbar, text='修改后实时生效 · 点「调节」展开互动强度', bg=BG, fg=DIM, font=(FONT, 8)).pack(side='right')

        stats = tk.Frame(self, bg=BG)
        stats.pack(fill='x', padx=26, pady=(0, 8))
        self.stat_pills = {}
        for key, label, color in (
                ('groups', '个群', CYAN), ('replies', '今日回复', GREEN),
                ('joined', '已入群', TEAL), ('off', '已关闭', CORAL),
                ('unlimited', '无限', AMBER)):
            pill = Pill(stats, '0 ' + label, color, dot=False, height=24, bg=BG)
            pill.pack(side='left', padx=(0, 7))
            self.stat_pills[key] = (pill, label)

        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill='both', expand=True, padx=20, pady=(0, 8))
        self.scroll = ScrollArea(self.body, BG)
        self.scroll.pack(fill='both', expand=True)
        self.list_inner = self.scroll.inner

    def update_data(self, data, force=False):
        rows = data.get('group_rows')
        if rows is not None:
            self.rows = list(rows)
        self._update_stats()
        signature = tuple((row['gid'], bool(row['enabled']), row['limit'], row['member'],
                           row['reply_desire'], row['sticker_rate'], row['voice_rate'],
                           row['gid'] in self.app.group_expanded) for row in self.rows)
        if force or not self._loaded or signature != self._signature:
            self._rebuild()
        else:
            for row in self.rows:
                card = self.cards.get(row['gid'])
                if card:
                    card.update_row(row)
        self._signature = signature
        self._loaded = True

    def _update_stats(self):
        total = len(self.rows)
        replies = sum(row['count'] for row in self.rows)
        joined = sum(1 for row in self.rows if row['member'])
        off = sum(1 for row in self.rows if not row['enabled'])
        unlimited = sum(1 for row in self.rows if row['limit'] == 0)
        values = {'groups': total, 'replies': replies, 'joined': joined,
                  'off': off, 'unlimited': unlimited}
        for key, (pill, label) in self.stat_pills.items():
            pill.set('%d %s' % (values.get(key, 0), label))

    def _rebuild(self):
        position = self.scroll.canvas.yview()[0]
        for child in self.list_inner.winfo_children():
            child.destroy()
        self.cards = {}
        for index, row in enumerate(self.rows):
            color = GROUP_COLORS.get(row['gid'], GROUP_PALETTE[index % len(GROUP_PALETTE)])
            card = GroupCard(self.list_inner, self.app, row,
                             row['gid'] in self.app.group_expanded, color)
            self.cards[row['gid']] = card
        self.list_inner.update_idletasks()
        self.scroll.canvas.yview_moveto(position)

    def reload(self):
        self.update_data({'group_rows': self.app.group_snapshot()}, force=True)


class BroadcastPage(tk.Frame):
    """Pick friends/groups and send one message straight from the control center."""

    def __init__(self, app, parent):
        super().__init__(parent, bg=BG)
        self.app = app
        self.targets = []
        self.vars = {}
        self.blocks = []
        self.request_id = None
        self._poll_job = None
        self._filter_job = None

        bar = tk.Frame(self, bg=BG)
        bar.pack(fill='x', padx=26, pady=(2, 8))
        self.search = SearchBox(bar, placeholder='搜索昵称 / QQ / 群名',
                                command=self.schedule_filter, bg=BG, width=340, height=38)
        self.search.pack(side='left', fill='x', expand=True)
        for text, command, width in (
                ('全选', lambda: self.bulk(True), 62),
                ('清空', lambda: self.bulk(False), 62),
                ('仅好友', lambda: self.bulk('friend'), 74),
                ('仅群聊', lambda: self.bulk('group'), 74),
                ('刷新', self.reload_targets, 68)):
            SoftButton(bar, text, command, 'ghost', width=width, height=36,
                       bg=BG).pack(side='left', padx=(6, 0))

        # The composer must claim its space before the scrolling list, otherwise
        # pack() gives the whole page to the list and the composer is clipped.
        compose = tk.Frame(self, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        compose.pack(side='bottom', fill='x', padx=26, pady=(10, 8))
        top = tk.Frame(compose, bg=CARD)
        top.pack(fill='x', padx=14, pady=(10, 0))
        tk.Label(top, text='消息内容', bg=CARD, fg='#DCEBFF',
                 font=(FONT, 10, 'bold')).pack(side='left')
        tk.Label(top, text='纯文本 · 原文发送', bg=CARD, fg=DIM,
                 font=(FONT, 8)).pack(side='right')
        self.message = tk.Text(compose, height=4, bg='#0B1524', fg=TEXT, insertbackground=TEXT,
                               relief='flat', font=(FONT, 10), wrap='word', padx=10, pady=8,
                               highlightthickness=0, bd=0)
        self.message.pack(fill='x', padx=14, pady=(6, 8))
        row = tk.Frame(compose, bg=CARD)
        row.pack(fill='x', padx=14, pady=(0, 12))
        self.send_btn = SoftButton(row, '发送广播', self.send, 'primary', width=120,
                                   height=34, bg=CARD)
        self.send_btn.pack(side='left')
        self.status = tk.Label(row, text='', bg=CARD, fg=DIM, font=(FONT, 9), anchor='w')
        self.status.pack(side='left', padx=(12, 0), fill='x', expand=True)

        list_box = tk.Frame(self, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        list_box.pack(fill='both', expand=True, padx=26)
        head = tk.Frame(list_box, bg=CARD)
        head.pack(fill='x', padx=14, pady=(10, 2))
        tk.Label(head, text='接收对象', bg=CARD, fg='#DCEBFF',
                 font=(FONT, 10, 'bold')).pack(side='left')
        self.count_label = tk.Label(head, text='已选 0 个', bg=CARD, fg=DIM, font=(FONT, 8))
        self.count_label.pack(side='right')
        self.scroll = ScrollArea(list_box, CARD)
        self.scroll.pack(fill='both', expand=True, padx=8, pady=(4, 10))
        self.list_inner = self.scroll.inner
        self.list_inner.columnconfigure(0, weight=1)

        self.reload_targets()

    # ---------- data ----------
    def collect_targets(self):
        """Read friends, groups and their enabled state from the data folder."""
        targets = []
        try:
            groups = json.loads((DATA / 'dafeiyu_groups.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            groups = {}
        try:
            controls = json.loads((DATA / 'dafeiyu_group_controls.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            controls = {}
        if isinstance(groups, dict):
            for gid, info in groups.items():
                name = ''
                if isinstance(info, dict):
                    name = str(info.get('name') or info.get('original') or '')
                label = '%s  (群 %s)' % (name or '未命名群', gid)
                if isinstance(controls, dict) and str(gid) in controls and not controls[str(gid)]:
                    label += ' · 已关闭'
                targets.append({'key': 'group:' + str(gid), 'id': str(gid),
                                'type': 'group', 'label': label})
        try:
            friends = json.loads((DATA / 'dafeiyu_friends.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            friends = {}
        if isinstance(friends, dict):
            for qq, info in friends.items():
                name = ''
                if isinstance(info, dict):
                    name = str(info.get('remark') or info.get('nick') or '')
                label = '%s  (%s)' % (name, qq) if name else str(qq)
                targets.append({'key': 'friend:' + str(qq), 'id': str(qq),
                                'type': 'friend', 'label': label})
        return targets

    def reload_targets(self):
        """Rebuild the checkbox list from the current friend/group snapshots."""
        for child in list(self.list_inner.winfo_children()):
            child.destroy()
        self.vars = {}
        self.blocks = []
        self.targets = self.collect_targets()
        if not self.targets:
            tk.Label(self.list_inner, text='没有读到好友或群，先确认 AstrBot 已上线',
                     bg=CARD, fg=DIM, font=(FONT, 10), pady=30).pack(fill='x')
            self._refresh_count()
            return
        groups = [t for t in self.targets if t['type'] == 'group']
        friends = [t for t in self.targets if t['type'] == 'friend']
        index = 0
        for title, items in (('群聊', groups), ('好友', friends)):
            if not items:
                continue
            header = tk.Label(self.list_inner, text='%s · %d' % (title, len(items)),
                              bg=CARD, fg=DIM, font=(FONT, 8), anchor='w')
            header.grid(row=index, column=0, sticky='ew', padx=8, pady=(8, 2))
            index += 1
            block = []
            for item in items:
                var = tk.BooleanVar(value=False)
                self.vars[item['key']] = var
                check = tk.Checkbutton(
                    self.list_inner, text=item['label'], variable=var, anchor='w',
                    bg=CARD, fg=TEXT, activebackground=CARD, activeforeground=TEXT,
                    selectcolor='#1B3352', font=(FONT, 9), bd=0, highlightthickness=0,
                    padx=8, pady=1, cursor='hand2', command=self._refresh_count)
                check.grid(row=index, column=0, sticky='ew')
                index += 1
                block.append((item, check))
            self.blocks.append((header, block))
        self._refresh_count()
        self.apply_filter()

    # ---------- selection ----------
    def bulk(self, mode):
        """Select everything, nothing, only friends or only groups."""
        for item in self.targets:
            var = self.vars.get(item['key'])
            if var is None:
                continue
            if mode is True:
                var.set(True)
            elif mode is False:
                var.set(False)
            else:
                var.set(item['type'] == mode)
        self._refresh_count()

    def selected_targets(self):
        return [t for t in self.targets if self.vars.get(t['key']) and self.vars[t['key']].get()]

    def _refresh_count(self):
        count = len(self.selected_targets())
        self.count_label.configure(text='已选 %d 个' % count)

    def schedule_filter(self):
        if self._filter_job:
            try:
                self.after_cancel(self._filter_job)
            except tk.TclError:
                pass
        self._filter_job = self.after(160, self.apply_filter)

    def apply_filter(self):
        query = self.search.var.get().strip().lower()
        for header, block in self.blocks:
            visible = 0
            for item, check in block:
                match = (not query) or query in item['label'].lower() or query in item['id']
                if match:
                    check.grid()
                    visible += 1
                else:
                    check.grid_remove()
            if visible:
                header.grid()
            else:
                header.grid_remove()

    # ---------- sending ----------
    def send(self):
        targets = self.selected_targets()
        text = self.message.get('1.0', 'end').strip()
        if not targets:
            self._set_status('先选至少一个接收对象', RED)
            return
        if not text:
            self._set_status('消息不能为空', RED)
            return
        request_id = str(int(time.time() * 1000))
        payload = {
            'request_id': request_id,
            'created_at': time.time(),
            'message': text,
            'targets': [{'id': t['id'], 'type': t['type']} for t in targets],
        }
        try:
            (DATA / 'dafeiyu_broadcast_request.json').write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as exc:
            self._set_status('写入失败：%s' % exc, RED)
            return
        self.request_id = request_id
        self.send_btn.set_enabled(False)
        self._set_status('已提交，正在发送给 %d 个对象…' % len(targets), AMBER)
        self._poll_result(time.time() + 180)

    def _poll_result(self, deadline):
        if self.request_id is None:
            return
        try:
            report = json.loads((DATA / 'dafeiyu_broadcast_result.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            report = None
        if isinstance(report, dict) and str(report.get('request_id')) == self.request_id:
            sent = int(report.get('sent') or 0)
            total = int(report.get('total') or 0)
            errors = [item for item in (report.get('results') or []) if not item.get('success')]
            note = '已发送 %d / %d' % (sent, total)
            if errors:
                detail = '、'.join(str(item.get('error') or '失败') for item in errors[:2])
                note += ' · 失败 %d（%s）' % (len(errors), detail)
            self._set_status(note, GREEN if sent == total else (AMBER if sent else RED))
            self.send_btn.set_enabled(True)
            self.request_id = None
            return
        if time.time() > deadline:
            self._set_status('没等到回执，确认 AstrBot 是否在线', RED)
            self.send_btn.set_enabled(True)
            self.request_id = None
            return
        self._poll_job = self.after(1200, lambda: self._poll_result(deadline))

    def _set_status(self, text, color=DIM):
        self.status.configure(text=text, fg=color)

    def update_data(self, data):
        """Kept for the page contract; the target list is loaded on build."""
        return


def mirror_hero_photo(w, h):
    """Painted violet hero background for the mirror dashboard."""
    key = ('mirror-hero', w, h)
    if key in _PIL_CACHE:
        return _PIL_CACHE[key]
    base = _gradient(w, h, [(26, 16, 52), (44, 26, 86), (9, 24, 46)], 0.55).convert('RGBA')
    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.ellipse((w * 0.50, -h * 0.90, w * 1.05, h * 0.95), fill=(139, 92, 246, 74))
    draw.ellipse((w * 0.74, h * 0.04, w * 1.22, h * 1.30), fill=(99, 102, 241, 52))
    draw.ellipse((-w * 0.16, h * 0.30, w * 0.30, h * 1.35), fill=(45, 212, 191, 20))
    overlay = overlay.filter(ImageFilter.GaussianBlur(max(18, h // 4)))
    base = Image.alpha_composite(base, overlay)
    grid = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    for x in range(0, w, 46):
        gd.line((x, 0, x, h), fill=(167, 139, 250, 9), width=1)
    for y in range(0, h, 28):
        gd.line((0, y, w, y), fill=(167, 139, 250, 6), width=1)
    base = Image.alpha_composite(base, grid)
    try:
        icon = make_mirror_icon(64)
        icon = icon.resize((int(h * 1.55), int(h * 1.55)), Image.LANCZOS)
        alpha = icon.getchannel('A').point(lambda v: int(v * 0.15))
        ink = Image.new('RGBA', icon.size, (255, 255, 255, 0))
        ink.putalpha(alpha)
        base.alpha_composite(ink, (w - icon.width - 26, (h - icon.height) // 2))
    except (OSError, ValueError):
        pass
    base.putalpha(_rounded_mask(w, h, 20))
    return _cache_put(key, base)


_THINK_CACHE = {'fn': None, 'error': ''}


def load_think():
    """Import the mirror think-chain library from the AstrBot plugin tree."""
    if _THINK_CACHE['fn'] is not None:
        return _THINK_CACHE['fn']
    path = DATA / 'plugins' / 'dafeiyu_think' / 'chain.py'
    spec = importlib.util.spec_from_file_location('dafeiyu_pilot_chain', path)
    if spec is None or spec.loader is None:
        raise RuntimeError('找不到思维链模块')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _THINK_CACHE['fn'] = module.think
    return module.think


def _fmt_ts(value):
    """Format a unix timestamp as MM-DD HH:MM, or a dash."""
    try:
        return datetime.fromtimestamp(float(value)).strftime('%m-%d %H:%M')
    except (TypeError, ValueError, OSError):
        return '--'


class MirrorPage(tk.Frame):
    """Mirror-only dashboard: shadow state, pilot sandbox and review queues."""

    def __init__(self, app, parent):
        super().__init__(parent, bg=BG)
        self.app = app
        self.data = {}
        self._pulse_phase = 0.0
        self._dot_id = None
        self._dot_xy = (0, 0)
        self.scroll = ScrollArea(self, BG)
        self.scroll.pack(fill='both', expand=True)
        content = self.scroll.inner

        self.hero = tk.Canvas(content, height=150, bg=BG, highlightthickness=0, bd=0)
        self.hero.pack(fill='x', padx=26, pady=(6, 10))
        self.hero.bind('<Configure>', lambda _e: self._draw_hero())

        self.actions = Card(content, pad=14, accent=VIOLET, auto=True)
        self.actions.pack(fill='x', padx=26, pady=(0, 8))
        tk.Label(self.actions.body, text='镜像操作', bg=CARD, fg=TEXT,
                 font=(FONT, 10, 'bold')).pack(anchor='w', pady=(0, 8))
        ActionFlow(self.actions.body, [
            ('进入批阅', lambda: app.show_page('review'), 'primary'),
            ('独立批阅状态', app.reviewer_status, 'ghost'),
            ('立即刷新', lambda: app.refresh(manual=True), 'ghost'),
            ('打开日志', app.open_log, 'ghost'),
        ]).pack(fill='x')

        self.tiles = tk.Frame(content, bg=BG)
        self.tiles.pack(fill='x', padx=26)
        self.tile_values = {}
        self.tile_subs = {}
        self.tile_bars = {}
        specs = [
            ('obs', '影子观察', I_SEARCH, VIOLET, '累计进入镜像'),
            ('today', '今日观察', I_CLOCK, CYAN, '按北京时间'),
            ('quality', '平均质量', I_STAR, GOLD, '有反馈的观察'),
            ('review', '待批内容', I_CHECK, CORAL, '批次 + 画像'),
        ]
        for index, (key, label, icon, color, sub) in enumerate(specs):
            card = Card(self.tiles, height=126, pad=13, accent=color)
            card.pack(side='left', fill='x', expand=True, padx=(0 if index == 0 else 8, 0))
            head = tk.Frame(card.body, bg=CARD)
            head.pack(fill='x')
            icon_box = tk.Canvas(head, width=30, height=30, bg=CARD, highlightthickness=0)
            icon_box.pack(side='left')
            icon_box.create_oval(0, 0, 30, 30, fill=mix(color, CARD, 0.82),
                                 outline=mix(color, CARD, 0.58))
            icon_box.create_text(15, 15, text=icon, fill=color, font=(ICON_FONT, 9))
            tk.Label(head, text=label, bg=CARD, fg=DIM, font=(FONT, 8)).pack(side='left', padx=(7, 0))
            value = tk.Label(card.body, text='—', bg=CARD, fg=TEXT, font=(FONT, 15, 'bold'))
            value.pack(anchor='w', pady=(2, 0))
            sub_label = tk.Label(card.body, text=sub, bg=CARD, fg=DIM, font=(FONT, 7))
            sub_label.pack(anchor='w')
            bar = GradientBar(card.body, height=5, bg=CARD)
            bar.pack(fill='x', pady=(4, 0))
            self.tile_values[key] = value
            self.tile_subs[key] = sub_label
            self.tile_bars[key] = bar

        self.pilot = Card(content, pad=16, accent=INDIGO, auto=True)
        self.pilot.pack(fill='x', padx=26, pady=(10, 0))
        pilot_head = tk.Frame(self.pilot.body, bg=CARD)
        pilot_head.pack(fill='x')
        tk.Label(pilot_head, text='先行测试 · 思维链试跑', bg=CARD, fg='#EAF0FF',
                 font=(FONT, 11, 'bold')).pack(side='left')
        Pill(pilot_head, '不发送 · 不影响线上', VIOLET, dot=True, height=24, bg=CARD).pack(side='right')
        tk.Label(self.pilot.body, text='输入一句话，按镜像的感知 → 关联 → 策略 → 审查链试跑，看它会怎么理解。',
                 bg=CARD, fg=DIM, font=(FONT, 8)).pack(anchor='w', pady=(3, 8))
        pilot_row = tk.Frame(self.pilot.body, bg=CARD)
        pilot_row.pack(fill='x')
        self.pilot_var = tk.StringVar()
        self.pilot_entry = tk.Entry(pilot_row, textvariable=self.pilot_var, bg='#0B1728',
                                    fg=TEXT, insertbackground=VIOLET, relief='flat', bd=0,
                                    highlightthickness=1, highlightbackground=BORDER,
                                    highlightcolor=VIOLET, font=(FONT, 10))
        self.pilot_entry.pack(side='left', fill='x', expand=True, ipady=7)
        self.pilot_entry.bind('<Return>', lambda _e: self.run_pilot())
        owner_box = tk.Frame(pilot_row, bg=CARD)
        owner_box.pack(side='left', padx=(10, 8))
        self.owner_var = tk.BooleanVar(value=False)
        tk.Label(owner_box, text='按主人试跑', bg=CARD, fg=MUTED, font=(FONT, 8)).pack(side='left', padx=(0, 6))
        ToggleSwitch(owner_box, self.owner_var, bg=CARD, width=40, height=22).pack(side='left')
        SoftButton(pilot_row, '试跑', self.run_pilot, 'primary', width=82, height=34,
                   icon=I_PLAY, bg=CARD, bold=True).pack(side='left')
        self.pilot_text = tk.Text(self.pilot.body, height=5, width=60, wrap='word', bg='#0B1728',
                                  fg=MUTED, relief='flat', bd=0, highlightthickness=0,
                                  font=(FONT, 9), padx=10, pady=8, spacing1=2, spacing3=2,
                                  cursor='arrow')
        self.pilot_text.pack(fill='x', pady=(9, 0))
        self.pilot_text.tag_configure('head', foreground=lighten(VIOLET, 0.35),
                                      font=(FONT, 9, 'bold'))
        self.pilot_text.tag_configure('body', foreground=MUTED, font=(FONT, 9))
        self.pilot_text.tag_configure('ok', foreground=GREEN, font=(FONT, 9))
        self.pilot_text.tag_configure('warn', foreground=AMBER, font=(FONT, 9))
        self.pilot_text.insert('end', '输入一句话，点「试跑」看镜像会怎么理解。\n', 'body')
        self.pilot_text.configure(state='disabled')

        self.shadow = Card(content, pad=16, accent=VIOLET, auto=True)
        self.shadow.pack(fill='x', padx=26, pady=(10, 0))
        shadow_head = tk.Frame(self.shadow.body, bg=CARD)
        shadow_head.pack(fill='x')
        tk.Label(shadow_head, text='影子状态', bg=CARD, fg='#EAF0FF',
                 font=(FONT, 11, 'bold')).pack(side='left')
        self.phase_pill = Pill(shadow_head, '影子观察', VIOLET, dot=True, height=24, bg=CARD)
        self.phase_pill.pack(side='right')
        self.steps = tk.Frame(self.shadow.body, bg=CARD)
        self.steps.pack(fill='x', pady=(10, 6))
        self.shadow_stats = tk.Label(self.shadow.body, text='', bg=CARD, fg=MUTED, font=(FONT, 8))
        self.shadow_stats.pack(anchor='w')
        tk.Frame(self.shadow.body, bg='#1B2B44', height=1).pack(fill='x', pady=(8, 6))
        tk.Label(self.shadow.body, text='已批阅的经验规则', bg=CARD, fg=DIM,
                 font=(FONT, 8)).pack(anchor='w')
        self.rules_frame = tk.Frame(self.shadow.body, bg=CARD)
        self.rules_frame.pack(fill='x', pady=(4, 0))

        self.guard = Card(content, pad=16, accent=AMBER, auto=True)
        self.guard.pack(fill='x', padx=26, pady=(10, 0))
        guard_head = tk.Frame(self.guard.body, bg=CARD)
        guard_head.pack(fill='x')
        tk.Label(guard_head, text='上线守候 · 主程序监听', bg=CARD, fg='#EAF0FF',
                 font=(FONT, 11, 'bold')).pack(side='left')
        self.guard_pill = Pill(guard_head, '等待', AMBER, dot=True, height=24, bg=CARD)
        self.guard_pill.pack(side='right')
        self.guard_text = tk.Label(self.guard.body, text='正在读取守候状态…', bg=CARD, fg=MUTED,
                                   font=(FONT, 8), justify='left', anchor='w')
        self.guard_text.pack(fill='x', pady=(8, 0))

        self.insights_card = Card(content, pad=16, accent=TEAL, auto=True)
        self.insights_card.pack(fill='x', padx=26, pady=(10, 10))
        insight_head = tk.Frame(self.insights_card.body, bg=CARD)
        insight_head.pack(fill='x')
        tk.Label(insight_head, text='最近自省', bg=CARD, fg='#EAF0FF',
                 font=(FONT, 11, 'bold')).pack(side='left')
        Pill(insight_head, '自动生成 · 只读', TEAL, dot=True, height=24, bg=CARD).pack(side='right')
        self.insights_frame = tk.Frame(self.insights_card.body, bg=CARD)
        self.insights_frame.pack(fill='x', pady=(6, 0))

    def update_data(self, data):
        self.data = data if isinstance(data, dict) else {}
        self._draw_hero()
        self._render_metrics()
        self._render_phase()
        self._render_rules()
        self._render_guard()
        self._render_insights()

    def tick_pulse(self):
        self._pulse_phase = (self._pulse_phase + 0.10) % 1.0
        if self._dot_id is None:
            return
        try:
            radius = 3.5 + 2.5 * abs(math.sin(self._pulse_phase * math.pi))
            x, y = self._dot_xy
            self.hero.coords(self._dot_id, x - radius, y - radius, x + radius, y + radius)
        except tk.TclError:
            self._dot_id = None

    def _draw_hero(self):
        canvas = self.hero
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if w < 160 or h < 100:
            return
        canvas.delete('all')
        if PIL_OK:
            self._hero_photo = _photo(('mirror-hero', w, h), mirror_hero_photo(w, h))
            canvas.create_image(0, 0, anchor='nw', image=self._hero_photo)
        else:
            canvas.create_rectangle(0, 0, w, h, fill='#241A45', outline='')
        canvas.create_text(28, 16, anchor='nw', text='M I R R O R   ·   S H A D O W   R U N',
                           fill='#C4B5FD', font=(FONT, 7, 'bold'))
        canvas.create_text(28, 36, anchor='nw', text='影子运行中', fill='#F7F5FF',
                           font=(FONT, 21, 'bold'))
        self._dot_xy = (28 + _measure('影子运行中', 21, True) + 14, 50)
        self._dot_id = canvas.create_oval(0, 0, 0, 0, fill=VIOLET, outline='')
        self.tick_pulse()
        data = self.data
        phase = str(data.get('phase_label') or '影子观察')
        canvas.create_text(28, 92, anchor='nw',
                           text='观察 %d 条 · 今日 %d 条 · 有反馈 %d 条 · 平均质量 %.2f' % (
                               int(data.get('obs_total') or 0), int(data.get('obs_today') or 0),
                               int(data.get('fb_count') or 0), float(data.get('avg_score') or 0)),
                           fill='#C7C9E8', font=(FONT, 9))
        canvas.create_text(28, 118, anchor='nw',
                           text='阶段：%s · 批次 %d · 同步 %d · 最近同步 %s' % (
                               phase, int(data.get('batch_count') or 0),
                               int(data.get('sync_count') or 0),
                               _fmt_ts(data.get('updated_at'))),
                           fill='#9C9FC7', font=(FONT, 8))
        right = w - 150
        canvas.create_text(right, 44, anchor='nw', text='%d' % int(data.get('pending_batches') or 0),
                           fill='#F5D0FE', font=('Bahnschrift', 24, 'bold'))
        canvas.create_text(right, 82, anchor='nw', text='待批批次', fill='#B7A8D9', font=(FONT, 8))
        canvas.create_text(right + 70, 46, anchor='nw', text='%d' % int(data.get('pending_profiles') or 0),
                           fill='#DDD6FE', font=('Bahnschrift', 20, 'bold'))
        canvas.create_text(right + 70, 82, anchor='nw', text='待批画像', fill='#B7A8D9', font=(FONT, 8))

    def _render_metrics(self):
        data = self.data
        values = {
            'obs': '%d' % int(data.get('obs_total') or 0),
            'today': '%d' % int(data.get('obs_today') or 0),
            'quality': '%.2f' % float(data.get('avg_score') or 0),
            'review': '%d' % (int(data.get('pending_batches') or 0) + int(data.get('pending_profiles') or 0)),
        }
        for key, text in values.items():
            self.tile_values[key].configure(text=text)
        self.tile_subs['obs'].configure(text='有反馈 %d 条' % int(data.get('fb_count') or 0))
        self.tile_subs['today'].configure(text='待配对 %d 条' % int(data.get('pending') or 0))
        self.tile_subs['quality'].configure(text='正反馈 %.0f%%' % (float(data.get('positive_ratio') or 0) * 100))
        self.tile_subs['review'].configure(
            text='批次 %d · 画像 %d' % (int(data.get('pending_batches') or 0),
                                    int(data.get('pending_profiles') or 0)))
        self.tile_bars['obs'].set(int(data.get('fb_count') or 0),
                                  max(1, int(data.get('obs_total') or 0)), VIOLET, INDIGO,
                                  animate=False)
        self.tile_bars['today'].set(int(data.get('obs_today') or 0),
                                    max(1, int(data.get('obs_total') or 0)), CYAN, BLUE, animate=False)
        self.tile_bars['quality'].set(int(float(data.get('avg_score') or 0) * 100), 100, GOLD, ORANGE,
                                      animate=False)
        total_pending = int(data.get('pending_batches') or 0) + int(data.get('pending_profiles') or 0)
        self.tile_bars['review'].set(min(total_pending, 10), 10, CORAL, ORANGE, animate=False)

    def _render_guard(self):
        state = self.data.get('supervisor')
        config = self.data.get('supervisor_config')
        state = state if isinstance(state, dict) else {}
        config = config if isinstance(config, dict) else {}
        if config.get('enable') is False:
            self.guard_pill.set('已关闭', AMBER)
            self.guard_text.configure(text='上线守候已关闭；主程序上下线不会自动发通知。')
            return
        if not state:
            self.guard_pill.set('等待镜像', AMBER)
            self.guard_text.configure(text='镜像守候尚未写入状态；请确认镜像控制中心正在运行。')
            return
        try:
            beat = float(state.get('heartbeat') or 0)
        except (TypeError, ValueError):
            beat = 0
        age = time.time() - beat if beat else 1e9
        if age > 60:
            self.guard_pill.set('守候未运行', AMBER)
            self.guard_text.configure(text='上次心跳 %s，已超过 60 秒未更新。' % _fmt_ts(beat))
            return
        online = bool(state.get('main_online'))
        self.guard_pill.set('主程序在线' if online else '主程序离线', GREEN if online else AMBER)
        lines = []
        if online:
            lines.append('主程序在线；镜像每 %d 秒监听一次。' % int(state.get('poll_seconds') or 5))
        else:
            lines.append('主程序离线 %.0f 分钟（从上次正常在线起算）。' % (
                float(state.get('downtime_seconds') or 0) / 60))
        try:
            downtime = float(state.get('downtime_seconds') or 0)
        except (TypeError, ValueError):
            downtime = 0.0
        downtime_text = ('%d 分钟' % int(downtime // 60)) if downtime >= 60 else ('%d 秒' % int(downtime))
        mode = str(state.get('mode') or '')
        if mode == 'reconnect':
            lines.append('上次恢复：断线重连（%s），走补回复。' % downtime_text)
        elif mode == 'startup':
            lines.append('上次恢复：离线 %s，按「我上线啦」处理。' % downtime_text)
        notice = state.get('notice')
        if isinstance(notice, dict) and notice.get('at'):
            lines.append('上线通知：%s 选中 %d 位，入队 %d 条%s。' % (
                _fmt_ts(notice.get('at')), int(notice.get('recipients') or 0),
                int(notice.get('queued') or 0), '（演练）' if notice.get('dry_run') else ''))
        if state.get('last_error'):
            lines.append('最近错误：' + str(state['last_error'])[:60])
        self.guard_text.configure(text='\n'.join(lines[:3]))

    def _render_phase(self):
        for child in self.steps.winfo_children():
            child.destroy()
        step = int(self.data.get('phase_step') or 0)
        labels = ('影子观察', '批次待批', '策略同步', '效果观察')
        for index, label in enumerate(labels):
            if index < step:
                color, mark = TEAL, '✓'
            elif index == step:
                color, mark = VIOLET, str(index + 1)
            else:
                color, mark = BORDER, str(index + 1)
            block = tk.Frame(self.steps, bg=CARD)
            block.pack(side='left')
            dot = tk.Canvas(block, width=24, height=24, bg=CARD, highlightthickness=0)
            dot.pack()
            dot.create_oval(2, 2, 22, 22, fill=mix(color, CARD, 0.80),
                            outline=mix(color, CARD, 0.45))
            dot.create_text(12, 12, text=mark, fill=lighten(color, 0.45), font=(FONT, 8, 'bold'))
            tk.Label(block, text=label, bg=CARD, fg=(TEXT if index <= step else DIM),
                     font=(FONT, 8, 'bold' if index == step else 'normal')).pack(pady=(2, 0))
            if index < len(labels) - 1:
                line = tk.Frame(self.steps, bg=(mix(TEAL, CARD, 0.55) if index < step else '#1B2B44'),
                                height=2, width=54)
                line.pack(side='left', padx=(6, 6), pady=(0, 16))
                line.pack_propagate(False)
        self.phase_pill.set(str(self.data.get('phase_label') or '影子观察'), VIOLET)
        baseline = self.data.get('baseline') if isinstance(self.data.get('baseline'), dict) else {}
        base_metrics = baseline.get('metrics') if isinstance(baseline.get('metrics'), dict) else {}
        self.shadow_stats.configure(
            text='批次 %d · 同步 %d · 最近批次 %s · 基线质量 %.2f / 正反馈 %.0f%%' % (
                int(self.data.get('batch_count') or 0), int(self.data.get('sync_count') or 0),
                (str(self.data.get('last_batch_id') or '--')[:8]),
                float(base_metrics.get('avg_score') or 0),
                float(base_metrics.get('positive_ratio') or 0) * 100))

    def _render_rules(self):
        for child in self.rules_frame.winfo_children():
            child.destroy()
        rules = self.data.get('rules') or []
        if not rules:
            tk.Label(self.rules_frame, text='还没有批阅通过的经验规则。', bg=CARD, fg=DIM,
                     font=(FONT, 8)).pack(anchor='w')
            return
        for rule in rules[:5]:
            line = tk.Frame(self.rules_frame, bg=CARD)
            line.pack(fill='x', pady=1)
            dot = tk.Canvas(line, width=14, height=16, bg=CARD, highlightthickness=0)
            dot.pack(side='left')
            dot.create_oval(5, 6, 9, 10, fill=VIOLET, outline='')
            tk.Label(line, text=str(rule)[:120], bg=CARD, fg=MUTED, font=(FONT, 8),
                     anchor='w', justify='left', wraplength=700).pack(side='left', fill='x', expand=True)

    def _render_insights(self):
        for child in self.insights_frame.winfo_children():
            child.destroy()
        insights = self.data.get('insights') or []
        if not insights:
            tk.Label(self.insights_frame, text='还没有自省记录，等镜像积累几条带反馈的观察。',
                     bg=CARD, fg=DIM, font=(FONT, 8)).pack(anchor='w')
            return
        for index, item in enumerate(reversed(insights[-4:])):
            if index:
                tk.Frame(self.insights_frame, bg='#172941', height=1).pack(fill='x', pady=4)
            head = tk.Frame(self.insights_frame, bg=CARD)
            head.pack(fill='x')
            tk.Label(head, text=_fmt_ts(item.get('at')), bg=CARD, fg=DIM, font=(FONT, 7)).pack(side='left')
            tk.Label(head, text=' · 对方：' + str(item.get('message') or '')[:40], bg=CARD,
                     fg=MUTED, font=(FONT, 8)).pack(side='left')
            tk.Label(self.insights_frame, text=str(item.get('text') or '')[:200], bg=CARD,
                     fg='#C9D6E8', font=(FONT, 9), anchor='w', justify='left',
                     wraplength=820).pack(anchor='w', pady=(1, 0))

    def run_pilot(self):
        text = self.pilot_var.get().strip()
        if not text:
            self.app.set_hint('先在输入框写一句话，再点试跑', 4000)
            return
        try:
            think = load_think()
            result = think('pilot-%d' % time.time_ns(), text, is_owner=bool(self.owner_var.get()))
        except Exception as exc:
            self._show_pilot([('试跑失败', str(exc), 'warn')])
            return
        lines = [('感知', result.perception.to_prompt(), 'body'),
                 ('关联', result.association.to_prompt(), 'body'),
                 ('策略', result.strategy.to_prompt(), 'body')]
        if result.review is not None:
            lines.append(('审查', result.review.to_prompt(), 'body'))
        else:
            lines.append(('审查', '这次跳过审查', 'warn'))
        if result.learned_strategy:
            lines.append(('经验策略', '；'.join(result.learned_strategy), 'ok'))
        self._show_pilot(lines)

    def _show_pilot(self, lines):
        widget = self.pilot_text
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        for head, body, tag in lines:
            widget.insert('end', '【%s】' % head, 'head')
            widget.insert('end', ' ' + str(body) + '\n', tag)
        widget.configure(state='disabled')


class ReviewPage(tk.Frame):
    """Mirror review queues: batch suggestions and relationship profiles."""

    def __init__(self, app, parent):
        super().__init__(parent, bg=BG)
        self.app = app
        self.data = {}
        self._signature = None
        self._loading = False
        self._reload_job = None
        self.scroll = ScrollArea(self, BG)
        self.scroll.pack(fill='both', expand=True)
        content = self.scroll.inner

        self.summary = Card(content, height=118, pad=14, accent=VIOLET)
        self.summary.pack(fill='x', padx=26, pady=(6, 14))
        head = tk.Frame(self.summary.body, bg=CARD)
        head.pack(fill='x')
        tk.Label(head, text='镜像批阅', bg=CARD, fg='#EAF0FF',
                 font=(FONT, 11, 'bold')).pack(side='left')
        SoftButton(head, '刷新', lambda: self.reload(reset_scroll=True), 'ghost', width=76, height=28, font_size=8,
                   icon=I_REFRESH, bg=CARD).pack(side='right')
        tk.Label(head, text='只有你点采纳，才会作用到大肥鱼本人', bg=CARD, fg=DIM,
                 font=(FONT, 8)).pack(side='left', padx=(10, 0))
        stats = tk.Frame(self.summary.body, bg=CARD)
        stats.pack(fill='x', pady=(6, 0))
        self.stat_labels = {}
        for key, label, color in (('batches', '待批批次', VIOLET), ('profiles', '待批画像', CYAN),
                                  ('obs', '影子观察', GOLD), ('score', '平均质量', GREEN)):
            block = tk.Frame(stats, bg=CARD)
            block.pack(side='left', padx=(0, 26))
            value = tk.Label(block, text='—', bg=CARD, fg=color, font=(FONT, 15, 'bold'))
            value.pack(anchor='w')
            tk.Label(block, text=label, bg=CARD, fg=DIM, font=(FONT, 7)).pack(anchor='w')
            self.stat_labels[key] = value

        self.list_host = tk.Frame(content, bg=BG)
        self.list_host.pack(fill='x', padx=20, pady=(0, 12))
        self._loading = False

    def update_data(self, data):
        self.data = data if isinstance(data, dict) else {}
        self._render_summary()
        signature = self._make_signature()
        if signature != self._signature:
            self._signature = signature
            self.reload()

    def _render_summary(self):
        self.stat_labels['batches'].configure(text=str(int(self.data.get('pending_batches') or 0)))
        self.stat_labels['profiles'].configure(text=str(int(self.data.get('pending_profiles') or 0)))
        self.stat_labels['obs'].configure(text=str(int(self.data.get('obs_total') or 0)))
        self.stat_labels['score'].configure(text='%.2f' % float(self.data.get('avg_score') or 0))

    def _make_signature(self):
        batches = tuple((item.get('batch_id'), (item.get('decision') or {}).get('action'))
                        for item in (self.data.get('batches') or []))
        profiles = tuple((item.get('name'), item.get('state'))
                         for item in (self.data.get('profiles') or []))
        return (batches, profiles)

    def reload(self, reset_scroll=False):
        if self._loading:
            return
        self._loading = True
        try:
            self.data = collect_mirror_snapshot()
            self._signature = self._make_signature()
            self._render_summary()
            try:
                self._rebuild()
            except Exception as exc:
                self._log_ui_error(traceback.format_exc())
                for child in self.list_host.winfo_children():
                    child.destroy()
                tk.Label(self.list_host, text='批阅页刷新失败：%s（已记录到 runtime/logs/control_center_error.log）'
                         % type(exc).__name__, bg=BG, fg=CORAL, font=(FONT, 9),
                         anchor='w', justify='left', wraplength=820).pack(fill='x', padx=10, pady=10)
            try:
                self.scroll.inner.update_idletasks()
                self.scroll._sync()
            except tk.TclError:
                pass
            if reset_scroll:
                try:
                    self.scroll.canvas.yview_moveto(0)
                except tk.TclError:
                    pass
        finally:
            self._loading = False

    def _reload_soon(self):
        """Rebuild after the current button event finishes, at the page top."""
        if self._reload_job:
            try:
                self.after_cancel(self._reload_job)
            except tk.TclError:
                pass
        self._reload_job = self.after(60, self._finish_reload)

    def _finish_reload(self):
        self._reload_job = None
        self.reload(reset_scroll=True)

    def _rebuild(self):
        for child in self.list_host.winfo_children():
            child.destroy()
        batches = [item for item in (self.data.get('batches') or [])]
        profiles = [item for item in (self.data.get('profiles') or [])]
        pending_batches = [item for item in batches if item.get('decision') is None]
        pending_profiles = [item for item in profiles if item.get('state') == 'pending']
        self._section('批次待批', '%d 份等待你批阅' % len(pending_batches), VIOLET)
        if not pending_batches:
            self._empty('没有待批批次。镜像每 10 分钟跑一轮，攒够观察会生成新批次。')
        for item in pending_batches[:8]:
            self._batch_card(item)
        self._section('关系画像待批', '%d 份等待发布' % len(pending_profiles), CYAN)
        if not pending_profiles:
            self._empty('没有待批画像。镜像会自动从私聊里整理关系画像。')
        for item in pending_profiles[:10]:
            self._profile_card(item)
        decided = [item for item in batches if item.get('decision') is not None][:5]
        if decided:
            self._section('最近批阅', '已经处理过的批次', TEAL)
            for item in decided:
                self._decided_row(item)

    def _section(self, title, subtitle, color):
        head = tk.Frame(self.list_host, bg=BG)
        head.pack(fill='x', padx=6, pady=(16, 2))
        bar = tk.Frame(head, bg=color, width=3, height=16)
        bar.pack(side='left', padx=(0, 8))
        bar.pack_propagate(False)
        tk.Label(head, text=title, bg=BG, fg='#EAF0FF', font=(FONT, 11, 'bold')).pack(side='left')
        tk.Label(head, text=subtitle, bg=BG, fg=DIM, font=(FONT, 8)).pack(side='left', padx=(10, 0))

    def _empty(self, text):
        tk.Label(self.list_host, text=text, bg=BG, fg=DIM, font=(FONT, 9),
                 anchor='w', justify='left', wraplength=820).pack(fill='x', padx=10, pady=(2, 6))

    def _batch_card(self, item):
        card = Card(self.list_host, pad=14, accent=VIOLET, auto=True)
        card.pack(fill='x', padx=6, pady=4)
        body = card.body
        head = tk.Frame(body, bg=CARD)
        head.pack(fill='x')
        tk.Label(head, text='批次 %s' % str(item.get('batch_id') or '')[:10], bg=CARD,
                 fg='#EAF0FF', font=(FONT, 10, 'bold')).pack(side='left')
        tk.Label(head, text=_fmt_ts(item.get('created_at')), bg=CARD, fg=DIM,
                 font=(FONT, 8)).pack(side='left', padx=(10, 0))
        Pill(head, '待批', AMBER, dot=True, height=22, bg=CARD).pack(side='right')
        stats = '观察 %d · 均分 %.2f · 正反馈 %.0f%% · 低质 %d / 高质 %d' % (
            int(item.get('total') or 0), float(item.get('avg_score') or 0),
            float(item.get('positive_ratio') or 0) * 100,
            int(item.get('low') or 0), int(item.get('high') or 0))
        if item.get('api_review'):
            stats = '独立 API 批阅 · 待你确认 · 未应用（未提供可信效果评分）'
        tk.Label(body, text=stats, bg=CARD, fg=MUTED, font=(FONT, 8)).pack(anchor='w', pady=(2, 0))
        for text_ in (item.get('insights') or [])[:4]:
            tk.Label(body, text='·' + str(text_)[:6000], bg=CARD, fg='#B9C7DA', font=(FONT, 8),
                     anchor='w', justify='left', wraplength=790).pack(anchor='w', pady=(2, 0))
        tk.Label(body, text='勾选要采纳的建议：', bg=CARD, fg=DIM,
                 font=(FONT, 8)).pack(anchor='w', pady=(8, 2))
        pairs = []
        for rule in item.get('rules') or []:
            var = tk.BooleanVar(value=True)
            check = tk.Checkbutton(body, text=str(rule), variable=var, bg=CARD, fg='#DCE8F7',
                                   activebackground=CARD, activeforeground=TEXT,
                                   selectcolor='#24324A', highlightthickness=0, bd=0,
                                   font=(FONT, 9), anchor='w', justify='left', wraplength=760,
                                   padx=2)
            check.pack(fill='x', anchor='w', pady=1)
            pairs.append((str(rule), var))
        footer = tk.Frame(body, bg=CARD)
        footer.pack(fill='x', pady=(8, 0))
        SoftButton(footer, '采纳勾选规则', lambda b=item, p=pairs: self._approve_batch(b, p),
                   'primary', width=122, height=30, font_size=8, icon=I_CHECK,
                   bg=CARD).pack(side='left', padx=(0, 8))
        SoftButton(footer, '驳回', lambda b=item: self._reject_batch(b), 'danger', width=76,
                   height=30, font_size=8, bg=CARD).pack(side='left')

    def _approve_batch(self, item, pairs):
        rules = [rule for rule, var in pairs if var.get()]
        if not rules:
            messagebox.showwarning('镜像批阅', '请至少勾选一条建议')
            return
        if not messagebox.askyesno('采纳规则', '采纳这 %d 条建议，并同步给镜像？\n\n%s'
                                   % (len(rules), '\n'.join('· ' + rule for rule in rules))):
            return
        ok, message = mirror_approve_batch(item.get('batch_id'), rules)
        self.app.set_hint(message, 8000)
        if not ok:
            messagebox.showerror('镜像批阅', message)
        self._reload_soon()

    def _reject_batch(self, item):
        if not messagebox.askyesno('驳回批次', '驳回批次 %s？\n（不会写入同步信号）'
                                   % str(item.get('batch_id') or '')[:10]):
            return
        ok, message = mirror_reject_batch(item.get('batch_id'))
        self.app.set_hint(message, 6000)
        if not ok:
            messagebox.showerror('镜像批阅', message)
        self._reload_soon()

    def _profile_card(self, item):
        card = Card(self.list_host, pad=14, accent=CYAN, auto=True)
        card.pack(fill='x', padx=6, pady=4)
        body = card.body
        head = tk.Frame(body, bg=CARD)
        head.pack(fill='x')
        tk.Label(head, text=str(item.get('title') or item.get('name') or ''), bg=CARD,
                 fg='#EAF0FF', font=(FONT, 10, 'bold')).pack(side='left')
        tk.Label(head, text=' · ' + str(item.get('name') or ''), bg=CARD, fg=DIM,
                 font=(FONT, 8)).pack(side='left')
        Pill(head, '待批', AMBER, dot=True, height=22, bg=CARD).pack(side='right')
        preview = '\n'.join(line for line in str(item.get('content') or '').splitlines()
                            if line.strip() and not line.startswith('_'))[:600]
        tk.Label(body, text=preview, bg=CARD, fg='#C4D2E4', font=(FONT, 9), anchor='w',
                 justify='left', wraplength=800).pack(anchor='w', pady=(4, 0))
        footer = tk.Frame(body, bg=CARD)
        footer.pack(fill='x', pady=(8, 0))
        SoftButton(footer, '发布画像', lambda i=item: self._decide_profile(i, 'approve'),
                   'primary', width=100, height=30, font_size=8, icon=I_CHECK,
                   bg=CARD).pack(side='left', padx=(0, 8))
        SoftButton(footer, '驳回', lambda i=item: self._decide_profile(i, 'reject'), 'ghost',
                   width=76, height=30, font_size=8, bg=CARD).pack(side='left')

    def _decide_profile(self, item, action):
        name = str(item.get('name') or '')
        if action == 'approve':
            if not messagebox.askyesno('发布画像', '发布「%s」？\n发布后私聊 prompt 会优先使用这份画像。'
                                       % item.get('title')):
                return
        else:
            if not messagebox.askyesno('驳回画像', '驳回「%s」？' % item.get('title')):
                return
        ok, message = mirror_decide_profile(name, action)
        self.app.set_hint(message, 8000)
        if not ok:
            messagebox.showerror('镜像批阅', message)
        self._reload_soon()

    def _decided_row(self, item):
        decision = item.get('decision') or {}
        row = tk.Frame(self.list_host, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        row.pack(fill='x', padx=6, pady=3)
        action = decision.get('action')
        color = GREEN if action == 'approve' else CORAL
        tk.Label(row, text='批次 %s' % str(item.get('batch_id') or '')[:10], bg=CARD, fg=TEXT,
                 font=(FONT, 9)).pack(side='left', padx=(10, 8), pady=6)
        tk.Label(row, text='已采纳' if action == 'approve' else '已驳回', bg=CARD, fg=color,
                 font=(FONT, 8, 'bold')).pack(side='left')
        tk.Label(row, text=str(decision.get('at') or ''), bg=CARD, fg=DIM,
                 font=(FONT, 8)).pack(side='right', padx=(0, 10))
        rules = decision.get('rules') or []
        if rules:
            tk.Label(row, text='· %d 条规则' % len(rules), bg=CARD, fg=MUTED,
                     font=(FONT, 8)).pack(side='right', padx=(0, 12))



class FriendCleanPage(tk.Frame):
    """List idle friends, manage the whitelist and request deletions."""

    def __init__(self, app, parent):
        super().__init__(parent, bg=BG)
        self.app = app
        self.data = {}
        self._filter_job = None
        self._poll_job = None
        self._request_id = None
        self._deadline = 0.0

        self.summary = Card(self, height=118, pad=14, accent=CORAL)
        self.summary.pack(fill='x', padx=26, pady=(6, 10))
        head = tk.Frame(self.summary.body, bg=CARD)
        head.pack(fill='x')
        tk.Label(head, text='好友清理', bg=CARD, fg='#EAF0FF',
                 font=(FONT, 11, 'bold')).pack(side='left')
        tk.Label(head, text='只删除 5 天没发过消息、且不在白名单的好友；聊天记录会封存',
                 bg=CARD, fg=DIM, font=(FONT, 8)).pack(side='left', padx=(10, 0))
        self.scan_note = tk.Label(head, text='', bg=CARD, fg=DIM, font=(FONT, 8))
        self.scan_note.pack(side='right')
        stats = tk.Frame(self.summary.body, bg=CARD)
        stats.pack(fill='x', pady=(8, 0))
        self.stat_labels = {}
        for key, label, color in (
                ('friends', '好友总数', CYAN), ('idle', '5 天未联系', AMBER),
                ('eligible', '可清理', CORAL), ('white', '白名单', GREEN),
                ('archive', '已封存', VIOLET)):
            block = tk.Frame(stats, bg=CARD)
            block.pack(side='left', padx=(0, 30))
            value = tk.Label(block, text='—', bg=CARD, fg=color, font=(FONT, 16, 'bold'))
            value.pack(anchor='w')
            tk.Label(block, text=label, bg=CARD, fg=DIM, font=(FONT, 7)).pack(anchor='w')
            self.stat_labels[key] = value

        bar = tk.Frame(self, bg=BG)
        bar.pack(fill='x', padx=26, pady=(0, 8))
        self.search = SearchBox(bar, command=self.schedule_filter, bg=BG, width=380, height=38)
        self.search.pack(side='left', fill='x', expand=True)
        self.only_idle = tk.BooleanVar(value=True)
        tk.Checkbutton(bar, text='只看 5 天未联系', variable=self.only_idle,
                       command=self.apply_filter, bg=BG, fg=MUTED, selectcolor='#1E2E44',
                       activebackground=BG, activeforeground=TEXT, font=(FONT, 9),
                       highlightthickness=0, bd=0).pack(side='left', padx=(10, 8))
        SoftButton(bar, '扫描活跃', self.scan, 'ghost', width=92, height=34,
                   icon=I_REFRESH, bg=BG).pack(side='left', padx=(0, 6))
        SoftButton(bar, '刷新', self.reload, 'ghost', width=68, height=34,
                   icon=I_REFRESH, bg=BG).pack(side='left', padx=(0, 6))
        SoftButton(bar, '清理好友', self.clean, 'danger', width=104, height=34,
                   icon=I_REMOVE, bg=BG, bold=True).pack(side='left')

        tree_box = tk.Frame(self, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        tree_box.pack(fill='both', expand=True, padx=26)
        style = ttk.Style()
        style.configure('Friends.Treeview', background=CARD, fieldbackground=CARD,
                        foreground=TEXT, rowheight=31, borderwidth=0, font=(FONT, 9))
        style.configure('Friends.Treeview.Heading', background=CARD_SOFT, foreground=MUTED,
                        font=(FONT, 8, 'bold'), relief='flat', padding=(6, 5))
        style.map('Friends.Treeview', background=[('selected', '#1D3557')],
                  foreground=[('selected', '#FFFFFF')])
        self.tree = ttk.Treeview(tree_box, columns=('nick', 'qq', 'last', 'idle', 'white'),
                                 show='headings', style='Friends.Treeview',
                                 selectmode='extended')
        for column, title, width, anchor in (
                ('nick', '昵称', 320, 'w'), ('qq', 'QQ', 150, 'w'),
                ('last', '最后一条消息', 180, 'w'), ('idle', '未联系', 100, 'center'),
                ('white', '白名单', 80, 'center')):
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, anchor=anchor, stretch=(column == 'nick'))
        self.tree.tag_configure('idle', foreground=CORAL)
        self.tree.tag_configure('white', foreground=GREEN)
        self.tree.tag_configure('protected', foreground=AMBER)
        self.tree.bind('<Double-1>', self._on_double)
        scroll = ttk.Scrollbar(tree_box, orient='vertical', command=self.tree.yview,
                               style='Vertical.TScrollbar')
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        foot = tk.Frame(self, bg=BG)
        foot.pack(fill='x', padx=26, pady=(8, 10))
        self.status = tk.Label(foot, text='', bg=BG, fg=MUTED, font=(FONT, 8),
                               anchor='w', justify='left', wraplength=620)
        self.status.pack(side='left', fill='x', expand=True)
        SoftButton(foot, '移出白名单', lambda: self.set_whitelist(False), 'ghost', width=108,
                   height=32, font_size=8, bg=BG).pack(side='right', padx=(8, 0))
        SoftButton(foot, '加入白名单', lambda: self.set_whitelist(True), 'soft', width=108,
                   height=32, font_size=8, bg=BG).pack(side='right')

    def reload(self):
        self.data = collect_friend_clean_rows()
        state = self.data.get('scan_state') or {}
        self.stat_labels['friends'].configure(text=str(self.data.get('friends_total', 0)))
        self.stat_labels['idle'].configure(text=str(self.data.get('idle_count', 0)))
        self.stat_labels['eligible'].configure(text=str(self.data.get('eligible_count', 0)))
        self.stat_labels['white'].configure(text=str(self.data.get('whitelist_count', 0)))
        self.stat_labels['archive'].configure(text=str(self.data.get('archived_count', 0)))
        if state.get('running'):
            self.scan_note.configure(text='正在扫描活跃…')
        elif state.get('last_scan_at'):
            self.scan_note.configure(text='上次扫描 %s · %s/%s' % (
                _fmt_ts(state.get('last_scan_at')), state.get('scanned', 0), state.get('total', 0)))
        else:
            self.scan_note.configure(text='还没扫描过，点「扫描活跃」')
        result = self.data.get('clean_result') or {}
        if result.get('finished_at'):
            deleted = len(result.get('deleted') or [])
            skipped = len(result.get('skipped') or [])
            failed = len(result.get('failed') or [])
            self.status.configure(
                text='上次清理 %s：删除 %d · 跳过 %d · 失败 %d' % (
                    _fmt_ts(result.get('finished_at')), deleted, skipped, failed))
        else:
            self.status.configure(text='双击一行可切换白名单；勾选「只看 5 天未联系」只看候选。')
        self.apply_filter()

    def schedule_filter(self):
        if self._filter_job:
            try:
                self.after_cancel(self._filter_job)
            except tk.TclError:
                pass
        self._filter_job = self.after(160, self.apply_filter)

    def apply_filter(self):
        self._filter_job = None
        if not hasattr(self, 'tree'):
            return
        query = self.search.var.get().strip().lower()
        only_idle = bool(self.only_idle.get())
        selected = set(self.tree.selection())
        for item in self.tree.get_children():
            self.tree.delete(item)
        parents = {}
        for row in self.data.get('rows') or []:
            days = row.get('idle_days')
            if only_idle and (days is None or days < 5):
                continue
            if query and query not in row['nick'].lower() and query not in row['qq']:
                continue
            tags = []
            if days is not None and days >= 5:
                tags.append('idle')
            if row.get('whitelisted'):
                tags.append('white')
            if row.get('protected'):
                tags.append('protected')
            values = (row['nick'][:28], row['qq'],
                      _fmt_ts(row.get('last_user_at')) if row.get('last_user_at') else '—',
                      ('%.1f 天' % days) if days is not None else '—',
                      '是' if row.get('whitelisted') else '否')
            self.tree.insert('', 'end', iid=row['qq'], values=values, tags=tuple(tags))
            parents[row['qq']] = row
        self._rows_by_qq = parents
        keep = [qq for qq in selected if qq in parents]
        if keep:
            self.tree.selection_set(keep)

    def _selected_rows(self):
        rows = []
        for qq in self.tree.selection():
            row = (getattr(self, '_rows_by_qq', {}) or {}).get(qq)
            if row is not None:
                rows.append(row)
        return rows

    def _on_double(self, _event=None):
        rows = self._selected_rows()
        if len(rows) != 1:
            return
        row = rows[0]
        if row.get('protected'):
            self._set_status('主人始终在白名单，不能移出')
            return
        self.set_whitelist(not row.get('whitelisted'))

    def set_whitelist(self, add):
        rows = self._selected_rows()
        if not rows:
            self._set_status('先在列表里选一位好友')
            return
        path = DATA / 'dafeiyu_friend_whitelist.json'
        whitelist = _read_json(path, {})
        if not isinstance(whitelist, dict):
            whitelist = {}
        changed = []
        for row in rows:
            qq = row['qq']
            if add:
                whitelist[qq] = {'name': row['nick'], 'at': datetime.now().strftime('%Y-%m-%d %H:%M')}
                changed.append(row['nick'])
            elif row.get('protected'):
                continue
            else:
                whitelist.pop(qq, None)
                changed.append(row['nick'])
        try:
            path.write_text(json.dumps(whitelist, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as exc:
            messagebox.showerror('保存失败', str(exc))
            return
        self.reload()
        self._set_status(('已加入白名单：' if add else '已移出白名单：') + '、'.join(changed[:6]))

    def _set_status(self, text, color=MUTED):
        self.status.configure(text=text, fg=color)

    def scan(self):
        path = DATA / 'dafeiyu_friend_scan_request.json'
        state = _read_json(DATA / 'dafeiyu_friend_activity_state.json', {})
        self._scan_before = float((state or {}).get('last_scan_at') or 0)
        try:
            temp = path.with_suffix('.json.tmp')
            temp.write_text(json.dumps({
                'request_id': str(int(time.time())), 'reason': 'manual',
                'at': time.time(),
            }, ensure_ascii=False), encoding='utf-8')
            os.replace(temp, path)
        except OSError as exc:
            messagebox.showerror('扫描失败', str(exc))
            return
        self._set_status('已请求扫描活跃，等待插件返回…', AMBER)
        self._deadline = time.time() + 600
        self._poll_scan()

    def _poll_scan(self):
        if time.time() > self._deadline:
            self._set_status('扫描超时，确认 AstrBot 在线后重试', CORAL)
            return
        state = _read_json(DATA / 'dafeiyu_friend_activity_state.json', {})
        if isinstance(state, dict) and not state.get('running'):
            if float(state.get('last_scan_at') or 0) > getattr(self, '_scan_before', 0) + 1:
                self.reload()
                self._set_status('扫描完成：%s/%s 位好友' % (
                    state.get('scanned', 0), state.get('total', 0)), GREEN)
                return
        self._poll_job = self.after(2000, self._poll_scan)

    def clean(self):
        candidates = [row for row in (self.data.get('rows') or []) if row.get('eligible')]
        if not candidates:
            messagebox.showinfo('好友清理', '没有可清理的好友：5 天内都发过消息，或都在白名单里。')
            return
        preview = '\n'.join('· %s（%s）%s' % (
            row['nick'][:18], row['qq'],
            (' · %.0f 天未联系' % row['idle_days']) if row.get('idle_days') is not None else '')
            for row in candidates[:12])
        more = '' if len(candidates) <= 12 else '\n… 另外 %d 位' % (len(candidates) - 12)
        if not messagebox.askyesno(
                '清理好友',
                '将删除以下 %d 位好友（白名单已排除）：\n\n%s%s\n\n'
                '删除后聊天记录会封存到本机，重新加好友会继续收录。\n确定继续？'
                % (len(candidates), preview, more)):
            return
        request_id = str(int(time.time()))
        path = DATA / 'dafeiyu_friend_clean_request.json'
        try:
            # The plugin polls this file; write atomically so it never reads a
            # half-written request and silently cleans nothing.
            temp = path.with_suffix('.json.tmp')
            temp.write_text(json.dumps({
                'request_id': request_id,
                'qqs': [row['qq'] for row in candidates],
                'at': time.time(),
            }, ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(temp, path)
        except OSError as exc:
            messagebox.showerror('清理失败', str(exc))
            return
        self._request_id = request_id
        self._deadline = time.time() + 600
        self._set_status('正在清理 %d 位好友…' % len(candidates), AMBER)
        self._poll_clean()

    def _poll_clean(self):
        result = _read_json(DATA / 'dafeiyu_friend_clean_result.json', {})
        if isinstance(result, dict) and str(result.get('request_id')) == str(self._request_id):
            deleted = len(result.get('deleted') or [])
            skipped = len(result.get('skipped') or [])
            failed_items = result.get('failed') or []
            failed = len(failed_items)
            reason = ''
            if failed_items and isinstance(failed_items[0], dict):
                reason = str(failed_items[0].get('error') or '')
            self._request_id = None
            self.reload()
            text = '清理完成：删除 %d · 跳过 %d · 失败 %d' % (deleted, skipped, failed)
            if reason:
                text += '（%s）' % reason[:40]
            self._set_status(text, GREEN if not failed else AMBER)
            self.app.set_hint('好友清理：删除 %d，跳过 %d，失败 %d' % (deleted, skipped, failed))
            return
        if time.time() > self._deadline:
            self._set_status('清理超时，确认 AstrBot 在线后重试', CORAL)
            return
        self._poll_job = self.after(1200, self._poll_clean)


# ---------- 单实例唤醒通道 ----------
# 第二个实例（桌面图标、启动脚本）不再静默退出：通过本机回环端口请求已有实例把窗口打开。
# 走 TCP 而不是窗口消息，是因为控制中心常以管理员身份运行，普通权限进程没法给它发消息。
CONTROL_PORTS = {'main': 6211, 'mirror': 6212}


def _activation_port(mode):
    return CONTROL_PORTS.get(mode, CONTROL_PORTS['main'])


def _start_activation_server(port, on_show):
    """在 127.0.0.1:port 上等唤醒请求，返回监听 socket；端口被占用时返回 None。

    协议：客户端发 ping/show，服务端回 pong/ok。ping 只用来判断实例是否还活着，
    show 会在界面线程里把窗口显示出来。
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server.bind(('127.0.0.1', port))
        server.listen(4)
    except OSError:
        try:
            server.close()
        except OSError:
            pass
        return None

    def serve():
        while True:
            try:
                conn, _ = server.accept()
            except OSError:
                return
            try:
                conn.settimeout(2.0)
                request = conn.recv(64).decode('utf-8', 'ignore').strip().lower()
                if request == 'ping':
                    conn.sendall(b'pong')
                elif request == 'show':
                    on_show()
                    conn.sendall(b'ok')
                else:
                    conn.sendall(b'no')
            except (OSError, RuntimeError, tk.TclError):
                pass
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    threading.Thread(target=serve, name='dafeiyu-activate', daemon=True).start()
    return server


def _send_activation(port, command, timeout=1.5):
    """向已在运行的控制中心发一条命令，返回它的回复；连不上返回空串。"""
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=timeout) as conn:
            conn.settimeout(timeout)
            conn.sendall(command.encode('ascii'))
            return conn.recv(16).decode('ascii', 'ignore')
    except OSError:
        return ''


def _report_unresponsive(mode):
    """已有实例但唤醒失败时给用户一个明确的恢复入口。"""
    title = '大肥鱼·镜像 · 控制中心' if mode == 'mirror' else '大肥鱼 · 控制中心'
    try:
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes('-topmost', True)
        except tk.TclError:
            pass
        answer = messagebox.askyesno(
            title,
            '控制中心已经在后台运行，但这次没有响应（多半是托盘图标丢失或界面卡住）。\n\n'
            '要现在重启控制中心吗？重启需要管理员权限，会弹一次确认。')
        root.destroy()
    except Exception:
        return
    if not answer:
        return
    script = ROOT / 'scripts' / 'restart-ui.ps1'
    if not script.exists():
        return
    try:
        subprocess.Popen(
            ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
             '-File', str(script), '-Mode', mode],
            creationflags=HIDDEN)
    except OSError:
        pass


class StatusWindow:
    def __init__(self, start_hidden=True, mode='main', autostart=False):
        self.mode = mode
        self.is_mirror = (mode == 'mirror')
        # --autostart is kept for the scheduled task; the mirror supervisor now
        # owns the online notice, so the main control center never queues it.
        self.root = tk.Tk()
        self.root.report_callback_exception = self._report_callback_exception
        title = '大肥鱼·镜像 · 控制中心' if self.is_mirror else '大肥鱼 · 控制中心'
        self.root.title(title)
        icon = Path(__file__).resolve().parent / '大肥鱼.ico'
        if self.is_mirror and PIL_OK and ImageTk is not None:
            try:
                self._window_icon = ImageTk.PhotoImage(make_mirror_icon(64))
                self.root.iconphoto(True, self._window_icon)
            except (tk.TclError, OSError, ValueError):
                pass
        elif icon.exists():
            try:
                self.root.iconbitmap(str(icon))
            except tk.TclError:
                pass
        self.root.geometry('1200x860')
        self.root.minsize(1060, 720)
        self.root.configure(bg=BG)
        self._setup_style()

        self.closed = False
        self.busy = False
        self.result = None
        self.tray = None
        self._tray_error = ''
        self._tray_icon_id = ''
        self._tray_image = None
        self._tray_title = ''
        self._display_signature = None
        self._activation_server = None
        self._activation_queue = queue.Queue()
        self.data = {}
        self.current_page = None
        self.group_expanded = set()
        self.last_alert = 0
        self.last_refresh_text = '--:--:--'
        self._refresh_job = None
        self._poll_job = None
        self._hint_job = None
        self._clock_job = None
        self._pulse_job = None
        self._quota_dirty = True
        self._group_dirty = True
        self.quota_page = None
        self.group_page = None
        self.broadcast_page = None
        self.mirror_page = None
        self.review_page = None
        self.overview_page = None
        self.friend_clean_page = None
        self.supervisor = None

        self._build_shell()
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.setup_tray()
        self._start_activation()
        self._center()
        if start_hidden and self.tray is not None:
            self.root.withdraw()
        elif start_hidden and self._tray_error:
            self.root.after(250, self._show_tray_error)
        self.show_page('mirror' if self.is_mirror else 'overview')
        self.root.after(100, self.refresh)
        self.root.after(140, self.poll)
        self.root.after(300, self._tick_clock)
        self.root.after(400, self._pulse)
        if self.is_mirror:
            self._start_supervisor()
        self.root.after(300, self._poll_activation)
        self.root.after(3000, self._watch_tray)
        self.root.bind_all('<MouseWheel>', self._on_wheel, add='+')

    def _start_supervisor(self):
        """Start the mirror-side online supervisor in this process."""
        try:
            from dafeiyu_supervisor import OnlineSupervisor
            self.supervisor = OnlineSupervisor(notice_text=START_NOTICE)
            if not self.supervisor.start():
                self._log_ui_error('上线守候未启动：dafeiyu_supervisor.json 的 enable=false')
        except Exception as exc:
            self.supervisor = None
            self._log_ui_error('上线守候启动失败：%s: %s\n%s' % (
                type(exc).__name__, exc, traceback.format_exc()))

    def _log_ui_error(self, text):
        """Append one UI failure to a bounded log file."""
        try:
            path = ROOT / 'runtime' / 'logs' / 'control_center_error.log'
            if path.exists() and path.stat().st_size > 512 * 1024:
                path.write_text('', encoding='utf-8')
            with path.open('a', encoding='utf-8') as handle:
                handle.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '\n' + text + '\n')
        except OSError:
            pass

    def _report_callback_exception(self, exc, value, tb):
        """Record Tk callback failures instead of losing them in pythonw."""
        self._log_ui_error(''.join(traceback.format_exception(exc, value, tb)))
        try:
            self.footer.configure(text='界面异常：%s（已记录到 runtime/logs/control_center_error.log）'
                                  % type(value).__name__)
        except (tk.TclError, AttributeError):
            pass

    def _setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('QuotaSummary.Horizontal.TProgressbar', troughcolor='#172941',
                        background=CYAN, bordercolor='#172941', lightcolor=CYAN,
                        darkcolor=CYAN, thickness=9)
        style.configure('Vertical.TScrollbar', background='#22344F', troughcolor=BG,
                        bordercolor=BG, arrowcolor=MUTED, lightcolor='#22344F',
                        darkcolor='#22344F')

    def _center(self):
        self.root.update_idletasks()
        width, height = 1200, 860
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.root.geometry('%dx%d+%d+%d' % (width, height, x, y))

    def _build_shell(self):
        shell = tk.Frame(self.root, bg=BG)
        shell.pack(fill='both', expand=True)

        side = tk.Frame(shell, bg=SIDEBAR, width=(228 if self.is_mirror else 212))
        side.pack(side='left', fill='y')
        side.pack_propagate(False)
        self.sidebar = side

        brand = tk.Frame(side, bg=SIDEBAR)
        brand.pack(fill='x', padx=18, pady=(26, 28))
        avatar = tk.Canvas(brand, width=48, height=48, bg=SIDEBAR, highlightthickness=0)
        avatar.pack(side='left')
        self._draw_avatar(avatar)
        box = tk.Frame(brand, bg=SIDEBAR)
        box.pack(side='left', padx=(11, 0))
        brand_name = '大肥鱼·镜像' if self.is_mirror else '大肥鱼'
        brand_size = 13 if self.is_mirror else 15
        tk.Label(box, text=brand_name, bg=SIDEBAR, fg='#F7FBFF', anchor='w',
                 font=(FONT, brand_size, 'bold')).pack(anchor='w')
        tk.Label(box, text='控制中心', bg=SIDEBAR, fg=DIM,
                 font=(FONT, 9)).pack(anchor='w', pady=(1, 0))

        nav = tk.Frame(side, bg=SIDEBAR)
        nav.pack(fill='x', padx=12)
        self.nav = {}
        nav_specs = (
            ('mirror', I_STAR, '镜像总览'),
            ('review', I_CHECK, '镜像批阅'),
            ('quota', I_CHAT, '私聊额度'),
            ('group', I_GROUP, '群聊状态'),
            ('friendclean', I_REMOVE, '好友清理'),
        ) if self.is_mirror else (
            ('overview', I_HOME, '总览'),
            ('quota', I_CHAT, '私聊额度'),
            ('group', I_GROUP, '群聊状态'),
            ('friendclean', I_REMOVE, '好友清理'),
            ('broadcast', I_LINK, '广播'),
        )
        for key, icon, label in nav_specs:
            item = NavItem(nav, icon, label, lambda k=key: self.show_page(k))
            item.pack(fill='x', pady=3)
            self.nav[key] = item

        bottom = tk.Frame(side, bg=SIDEBAR)
        bottom.pack(side='bottom', fill='x', padx=18, pady=20)
        self.clock = tk.Label(bottom, text='--:--:--', bg=SIDEBAR, fg='#E7F2FF',
                              font=('Bahnschrift', 21, 'bold'))
        self.clock.pack(anchor='w')
        self.date_label = tk.Label(bottom, text='', bg=SIDEBAR, fg=DIM, font=(FONT, 8))
        self.date_label.pack(anchor='w', pady=(1, 12))
        tk.Frame(bottom, bg='#172941', height=1).pack(fill='x', pady=(0, 12))
        status_line = tk.Frame(bottom, bg=SIDEBAR)
        status_line.pack(fill='x')
        self.side_dot = tk.Canvas(status_line, width=14, height=14, bg=SIDEBAR, highlightthickness=0)
        self.side_dot.pack(side='left')
        self.side_dot.create_oval(2, 2, 12, 12, fill=DIM, outline='')
        self.side_status = tk.Label(status_line, text='正在检查', bg=SIDEBAR, fg=MUTED,
                                    font=(FONT, 8))
        self.side_status.pack(side='left', padx=(4, 0))
        tk.Label(bottom, text='每 5 秒自动刷新 · 常驻托盘', bg=SIDEBAR, fg=DIM,
                 font=(FONT, 7)).pack(anchor='w', pady=(8, 0))
        tk.Label(bottom, text='YunShan_You · 悠云山', bg=SIDEBAR, fg='#5F7690',
                 font=(FONT, 7)).pack(anchor='w', pady=(2, 0))

        main = tk.Frame(shell, bg=BG)
        main.pack(side='left', fill='both', expand=True)
        header = tk.Frame(main, bg=BG, height=58)
        header.pack(fill='x', padx=26, pady=(14, 4))
        header.pack_propagate(False)
        titles = tk.Frame(header, bg=BG)
        titles.pack(side='left', fill='y')
        self.page_title = tk.Label(titles, text='总览', bg=BG, fg='#F4F9FF',
                                   font=(FONT, 22, 'bold'))
        self.page_title.pack(anchor='w')
        self.page_sub = tk.Label(titles, text='', bg=BG, fg=DIM, font=(FONT, 8))
        self.page_sub.pack(anchor='w', pady=(2, 0))

        right = tk.Frame(header, bg=BG)
        right.pack(side='right', fill='y')
        self.busy_pill = Pill(right, '刷新中', AMBER, dot=True, height=26, bg=BG)
        self.status_pill = Pill(right, '正在检查', AMBER, dot=True, height=28, bg=BG)
        self.status_pill.pack(side='right', padx=(8, 0), pady=8)
        self.refresh_btn = SoftButton(right, '刷新', lambda: self.refresh(manual=True), 'ghost',
                                      width=88, height=34, icon=I_REFRESH, bg=BG)
        self.refresh_btn.pack(side='right', pady=5)
        self.last_label = tk.Label(right, text='最近刷新 --:--:--', bg=BG, fg=DIM,
                                   font=(FONT, 8))
        self.last_label.pack(side='right', padx=(0, 12), pady=8)

        self.page_host = tk.Frame(main, bg=BG)
        self.page_host.pack(fill='both', expand=True)

        footer = tk.Frame(main, bg=BG, height=28)
        footer.pack(fill='x', padx=26)
        footer.pack_propagate(False)
        self.footer = tk.Label(footer, text='正在启动控制中心…', bg=BG, fg=DIM,
                               font=(FONT, 8), anchor='w')
        self.footer.pack(side='left', fill='x', expand=True)
        tk.Label(footer, text='关闭窗口不会关闭大肥鱼 · 设置会自动保存', bg=BG, fg=DIM,
                 font=(FONT, 8)).pack(side='right')
        tk.Label(footer, text='YunShan_You · 悠云山', bg=BG, fg='#5F7690',
                 font=(FONT, 7)).pack(side='right', padx=(0, 14))

        if self.is_mirror:
            self.mirror_page = MirrorPage(self, self.page_host)
            self.pages = {'mirror': self.mirror_page}
        else:
            self.overview_page = OverviewPage(self, self.page_host)
            self.pages = {'overview': self.overview_page}
        self.page_titles = {
            'mirror': ('镜像总览', '影子运行 · 先行测试 · 自省与批阅一眼看清'),
            'review': ('镜像批阅', '批次建议与关系画像 · 只有你采纳才会生效'),
            'overview': ('总览', '运行状态、连接与今日互动一眼看清'),
            'quota': ('私聊额度', '按昵称或 QQ 搜索 · 单独改上限 · 单独重置 · 封禁开关'),
            'group': ('群聊状态', '分条展示今日回复 · 关闭只停聊天，点歌继续可用'),
            'friendclean': ('好友清理', '5 天未联系好友 · 白名单 · 聊天记录封存'),
            'broadcast': ('广播', '选好友或群，写一句话，原文群发'),
        }

    def _draw_avatar(self, canvas):
        try:
            if PIL_OK:
                if self.is_mirror:
                    icon = make_mirror_icon(40)
                    ring = Image.new('RGBA', (48, 48), (0, 0, 0, 0))
                    draw = ImageDraw.Draw(ring)
                    draw.ellipse((1, 1, 47, 47), fill=(24, 16, 48, 255),
                                 outline=(167, 139, 250, 120), width=1)
                    ring.alpha_composite(icon, (4, 4))
                    canvas._photo = _photo(('avatar-mirror', 48), ring)
                    canvas.create_image(0, 0, anchor='nw', image=canvas._photo)
                    return
                icon = Image.open(Path(__file__).resolve().parent / '大肥鱼.ico').convert('RGBA')
                icon = icon.resize((40, 40), Image.LANCZOS)
                ring = Image.new('RGBA', (48, 48), (0, 0, 0, 0))
                draw = ImageDraw.Draw(ring)
                draw.ellipse((1, 1, 47, 47), fill=(13, 30, 50, 255), outline=(56, 189, 248, 110), width=1)
                ring.alpha_composite(icon, (4, 4))
                canvas._photo = _photo(('avatar', 48), ring)
                canvas.create_image(0, 0, anchor='nw', image=canvas._photo)
                return
        except (OSError, ValueError):
            pass
        if self.is_mirror:
            canvas.create_oval(1, 1, 47, 47, fill='#181030', outline=VIOLET)
            canvas.create_text(24, 24, text='M', fill=VIOLET, font=(FONT, 15, 'bold'))
            return
        canvas.create_oval(1, 1, 47, 47, fill='#0D1E32', outline=CYAN)
        canvas.create_text(24, 24, text='鲸', fill=CYAN, font=(FONT, 13, 'bold'))

    def show_page(self, key):
        if key not in ('overview', 'mirror', 'review', 'quota', 'group', 'friendclean', 'broadcast'):
            return
        if key == 'review' and self.review_page is None:
            self.build_review_page()
        if key == 'friendclean' and self.friend_clean_page is None:
            self.build_friend_clean_page()
        if key == 'quota' and self.quota_page is None:
            self.build_quota_page()
        if key == 'group' and self.group_page is None:
            self.build_group_page()
        if key == 'broadcast' and self.broadcast_page is None:
            self.build_broadcast_page()
        page = self.pages.get(key)
        if page is None:
            return
        if self.current_page is not None:
            self.pages[self.current_page].pack_forget()
        page.pack(fill='both', expand=True)
        self.current_page = key
        for name, item in self.nav.items():
            item.set_active(name == key)
        title, subtitle = self.page_titles[key]
        self.page_title.configure(text=title)
        self.page_sub.configure(text=subtitle)
        if key == 'friendclean' and self.friend_clean_page is not None:
            self.friend_clean_page.reload()
        if self.data:
            if key in ('mirror', 'review') and self.data.get('mirror'):
                if key == 'mirror' and self.mirror_page is not None:
                    self.mirror_page.update_data(self.data['mirror'])
                elif key == 'review' and self.review_page is not None:
                    self.review_page.update_data(self.data['mirror'])
            elif key == 'quota' and (self._quota_dirty or self.quota_page):
                self.quota_page.update_data(self.data)
                self._quota_dirty = False
            elif key == 'group':
                self.group_page.update_data(self.data)
                self._group_dirty = False

    def build_review_page(self):
        """Build the mirror review queues page."""
        self.review_page = ReviewPage(self, self.page_host)
        self.pages['review'] = self.review_page
        if self.data and self.data.get('mirror'):
            self.review_page.update_data(self.data['mirror'])

    def build_friend_clean_page(self):
        """Build the idle-friend cleanup page."""
        self.friend_clean_page = FriendCleanPage(self, self.page_host)
        self.pages['friendclean'] = self.friend_clean_page
        self.friend_clean_page.reload()

    def build_quota_page(self):
        """Build the searchable per-friend quota page."""
        self.quota_page = QuotaPage(self, self.page_host)
        self.quota_search_var = self.quota_page.search.var
        self.pages['quota'] = self.quota_page
        if self.data:
            self.quota_page.update_data(self.data)
        self._quota_dirty = False

    def build_group_page(self):
        """Build the live group status and enable/disable page."""
        self.group_page = GroupPage(self, self.page_host)
        self.pages['group'] = self.group_page
        if self.data:
            self.group_page.update_data(self.data)
        self._group_dirty = False

    def build_broadcast_page(self):
        """Build the broadcast composer page."""
        self.broadcast_page = BroadcastPage(self, self.page_host)
        self.pages['broadcast'] = self.broadcast_page

    def quota_snapshot(self):
        """Return current-day private quota rows with limits and nicknames."""
        return collect_quota_rows()

    def group_snapshot(self):
        """Return group counts, enabled state and membership state."""
        return collect_group_rows(_read_log())

    def set_hint(self, text, timeout=8000):
        self.footer.configure(text=text)
        if self._hint_job:
            try:
                self.root.after_cancel(self._hint_job)
            except tk.TclError:
                pass
        self._hint_job = self.root.after(timeout, self._default_hint)

    def _default_hint(self):
        self._hint_job = None
        self.footer.configure(text='最近检查：%s · 关闭此窗口不会关闭大肥鱼' % self.last_refresh_text)

    def _tick_clock(self):
        now = datetime.now()
        try:
            self.clock.configure(text=now.strftime('%H:%M:%S'))
            self.date_label.configure(text=now.strftime('%m月%d日') + ' 周' + WEEKDAYS[now.weekday()])
        except tk.TclError:
            return
        self._clock_job = self.root.after(1000, self._tick_clock)

    def _pulse(self):
        try:
            if self.root.winfo_viewable():
                if self.current_page == 'overview' and self.overview_page is not None:
                    self.overview_page.tick_pulse()
                elif self.current_page == 'mirror' and self.mirror_page is not None:
                    self.mirror_page.tick_pulse()
        except tk.TclError:
            return
        self._pulse_job = self.root.after(120, self._pulse)

    def _on_wheel(self, event):
        if self.current_page == 'quota' and self.quota_page is not None:
            area = self.quota_page.scroll
        elif self.current_page == 'group' and self.group_page is not None:
            area = self.group_page.scroll
        elif self.current_page == 'mirror' and self.mirror_page is not None:
            area = self.mirror_page.scroll
        elif self.current_page == 'review' and self.review_page is not None:
            area = self.review_page.scroll
        elif self.current_page == 'overview' and self.overview_page is not None:
            area = self.overview_page.scroll
        else:
            return
        widget = self.root.winfo_containing(self.root.winfo_pointerx(), self.root.winfo_pointery())
        if widget is None:
            return
        target = widget
        inside = False
        while target is not None:
            if target is self.page_host or target is area:
                inside = True
                break
            target = target.master
        if not inside:
            return
        area.scroll_pixels(-event.delta / 120 * 80)
        return 'break'

    def refresh(self, manual=False):
        if self.closed:
            return
        if self.busy:
            if manual:
                self.set_hint('正在刷新，请稍等…', 3000)
            return
        if self._refresh_job:
            try:
                self.root.after_cancel(self._refresh_job)
            except tk.TclError:
                pass
            self._refresh_job = None
        self.busy = True
        self.result = None
        self.busy_pill.pack(side='right', padx=(8, 0), pady=8, before=self.status_pill)
        self.refresh_btn.set_enabled(False)
        self.footer.configure(text='正在刷新…')
        threading.Thread(target=self.collect, daemon=True).start()

    def collect(self):
        try:
            self.result = (True, inspect_status(mirror=self.is_mirror))
        except Exception as exc:
            self.result = (False, type(exc).__name__)

    def poll(self):
        if self.result is not None:
            ok, payload = self.result
            self.result = None
            self.busy = False
            try:
                self.busy_pill.pack_forget()
                self.refresh_btn.set_enabled(True)
            except tk.TclError:
                pass
            if ok:
                self.data = payload
                self.last_refresh_text = datetime.now().strftime('%H:%M:%S')
                self.last_label.configure(text='最近刷新 ' + self.last_refresh_text)
                self.render(payload)
            else:
                self.overview_page.set_banner('检查暂时失败，请点刷新', 'warn')
                self.set_hint('检查错误：' + str(payload))
            self._schedule_refresh()
        if not self.closed:
            self._poll_job = self.root.after(120, self.poll)

    def _schedule_refresh(self):
        if self.closed:
            return
        visible = False
        try:
            visible = bool(self.root.winfo_viewable()) and self.root.state() == 'normal'
        except tk.TclError:
            visible = False
        delay = 5000 if visible else 30000
        self._refresh_job = self.root.after(delay, self.refresh)

    def render(self, data):
        ready = bool(data.get('ready'))
        if self.is_mirror:
            self.status_pill.set('影子运行' if ready else '主程序离线', VIOLET if ready else AMBER)
            self.side_status.configure(text='镜像在线' if ready else '主程序未连接',
                                       fg=(VIOLET if ready else AMBER))
        else:
            self.status_pill.set('运行正常' if ready else '需要关注', GREEN if ready else AMBER)
            self.side_status.configure(text='系统在线' if ready else '部分服务离线',
                                       fg=(GREEN if ready else AMBER))
        self.side_dot.delete('all')
        self.side_dot.create_oval(2, 2, 12, 12, fill=(GREEN if ready else AMBER), outline='')
        if self.overview_page is not None:
            self.overview_page.update_data(data)
        if self.mirror_page is not None:
            self.mirror_page.update_data(data.get('mirror') or {})
        if self.review_page is not None and self.current_page == 'review':
            self.review_page.update_data(data.get('mirror') or {})
        if self.quota_page is not None and self.current_page == 'quota':
            self.quota_page.update_data(data)
            self._quota_dirty = False
        else:
            self._quota_dirty = True
        if self.group_page is not None and self.current_page == 'group':
            self.group_page.update_data(data)
            self._group_dirty = False
        else:
            self._group_dirty = True
        self._default_hint()
        if not ready and not self.is_mirror and time.time() - self.last_alert > 1800:
            self.last_alert = time.time()
            try:
                self.root.deiconify()
                self.root.lift()
                self.root.attributes('-topmost', True)
                self.root.after(3000, lambda: self.root.attributes('-topmost', False))
            except tk.TclError:
                pass

    # ---------- 托盘 ----------
    def _tray_menu(self):
        return pystray.Menu(
            pystray.MenuItem('打开控制中心', self.show_window, default=True),
            pystray.MenuItem('启动上线', lambda: self.root.after(0, self.start)),
            pystray.MenuItem('结束下线', lambda: self.root.after(0, self.stop)),
            pystray.MenuItem('退出托盘', self.quit_app),
        )

    def setup_tray(self):
        """Create the system-tray icon and keep the window available on demand."""
        if pystray is None or Image is None:
            self._tray_error = '系统托盘组件缺失（pystray/Pillow 未安装），无法在后台驻留托盘。'
            self.footer.configure(text='系统托盘组件缺失：请安装 pystray')
            return
        try:
            if self.is_mirror:
                image = make_mirror_icon(64)
                tray_name = '大肥鱼·镜像 · 控制中心 · YunShan_You'
                icon_id = 'dafeiyu_mirror'
            else:
                icon_path = Path(__file__).resolve().parent / '大肥鱼.ico'
                if not icon_path.exists():
                    raise FileNotFoundError('找不到托盘图标：大肥鱼.ico')
                image = Image.open(icon_path)
                tray_name = '大肥鱼 · 控制中心 · YunShan_You'
                icon_id = 'dafeiyu'
            self._tray_image = image
            self._tray_title = tray_name
            self._tray_icon_id = icon_id
            self._display_signature = self._current_display_signature()
            self.tray = pystray.Icon(icon_id, image, tray_name, self._tray_menu())
            self.tray.run_detached()
        except Exception as exc:
            self.tray = None
            self._tray_error = '托盘图标启动失败：%s: %s' % (type(exc).__name__, exc)
            self.footer.configure(text='托盘启动失败：' + type(exc).__name__)
            self._log_ui_error(self._tray_error + '\n' + traceback.format_exc())

    # ---------- 唤醒通道 ----------
    def _start_activation(self):
        """开一个本机唤醒通道，让桌面图标和启动脚本能把窗口叫出来。"""
        port = _activation_port(self.mode)
        self._activation_server = _start_activation_server(port, self._on_activation_show)
        if self._activation_server is None:
            self._log_ui_error('唤醒通道端口 %d 被占用，桌面图标可能唤不醒这个窗口。' % port)

    def _stop_activation(self):
        server = self._activation_server
        self._activation_server = None
        if server is not None:
            try:
                server.close()
            except OSError:
                pass

    def _on_activation_show(self):
        """唤醒通道线程的回调：只入队，界面线程自己去取，避免跨线程碰 Tk。"""
        try:
            self._activation_queue.put_nowait('show')
        except Exception:
            pass

    def _poll_activation(self):
        """界面线程定时处理唤醒请求；窗口启动过程中收到的请求也不会丢。"""
        try:
            while True:
                command = self._activation_queue.get_nowait()
                if command == 'show':
                    self._show_window()
        except queue.Empty:
            pass
        except Exception:
            self._log_ui_error('处理唤醒请求失败：\n' + traceback.format_exc())
        finally:
            if not self.closed:
                self.root.after(300, self._poll_activation)

    # ---------- 托盘自愈 ----------
    @staticmethod
    def _current_display_signature():
        """显示器数量 + 主屏分辨率；变了说明 shell 可能把托盘图标丢了。"""
        try:
            user32 = ctypes.windll.user32
            return (user32.GetSystemMetrics(80), user32.GetSystemMetrics(0),
                    user32.GetSystemMetrics(1))
        except (AttributeError, OSError):
            return None

    def _tray_window(self):
        """托盘图标线程的消息窗口；线程没了，这个窗口也会消失。"""
        if self.tray is None:
            return 0
        try:
            class_name = '%s%dSystemTrayIcon' % (self._tray_icon_id, id(self.tray))
            return ctypes.windll.user32.FindWindowW(class_name, None)
        except (AttributeError, OSError):
            return 0

    def _rebuild_tray(self):
        """丢掉旧图标重开一个，shell 弄丢图标后还能自己回来。"""
        old = self.tray
        self.tray = None
        if old is not None:
            try:
                old.stop()
            except Exception:
                pass
        if pystray is None or Image is None or not self._tray_icon_id:
            return
        try:
            icon = pystray.Icon(self._tray_icon_id, self._tray_image,
                                self._tray_title, self._tray_menu())
            icon.run_detached()
            self.tray = icon
            self._tray_error = ''
            self._log_ui_error('托盘图标已重建（%s）。' % self._tray_title)
        except Exception as exc:
            self.tray = None
            self._tray_error = '托盘图标重建失败：%s: %s' % (type(exc).__name__, exc)
            self._log_ui_error(self._tray_error + '\n' + traceback.format_exc())

    def _watch_tray(self):
        """每 30 秒巡检：图标线程死了或显示器换过就重建；实在没有托盘就把窗口露出来。"""
        if self.closed:
            return
        try:
            if self.tray is not None:
                if not self._tray_window():
                    self._log_ui_error('托盘图标线程已退出，正在重建。')
                    self._rebuild_tray()
                else:
                    signature = self._current_display_signature()
                    if signature != self._display_signature:
                        previous = self._display_signature
                        self._display_signature = signature
                        self._log_ui_error('显示器布局变化（%s -> %s），重建托盘图标。'
                                           % (previous, signature))
                        self._rebuild_tray()
            if self.tray is None and self.root.state() == 'withdrawn':
                # 托盘不可用时不能再把窗口藏起来，否则用户完全没有入口。
                self.root.deiconify()
                self._log_ui_error(self._tray_error or '托盘不可用，已把窗口显示出来。')
        except Exception:
            self._log_ui_error('托盘巡检失败：\n' + traceback.format_exc())
        finally:
            if not self.closed:
                self.root.after(30000, self._watch_tray)

    def _show_tray_error(self):
        """Explain why the window could not start hidden in the tray."""
        try:
            messagebox.showwarning(
                '大肥鱼 · 托盘启动失败',
                self._tray_error + '\n\n主界面会保持打开；修好托盘组件后重启控制中心即可。'
            )
        except tk.TclError:
            pass

    def show_window(self):
        """Bring the status window back from the tray."""
        try:
            self.root.after(0, self._show_window)
        except tk.TclError:
            pass

    def _show_window(self):
        self.root.deiconify()
        self.root.state('normal')
        self.root.lift()
        self.root.focus_force()
        if time.time() - self.last_alert > 4:
            self.refresh()
        self.last_alert = 0

    def quit_app(self):
        """Stop the tray icon and close the status process."""
        self.closed = True
        self._stop_activation()
        if self.supervisor is not None:
            self.supervisor.stop()
            self.supervisor = None
        for job in (self._refresh_job, self._poll_job, self._hint_job, self._clock_job, self._pulse_job):
            if job:
                try:
                    self.root.after_cancel(job)
                except tk.TclError:
                    pass
        if self.tray is not None:
            try:
                self.tray.stop()
            except Exception:
                pass
            self.tray = None
        try:
            self.root.after(0, self.root.destroy)
        except tk.TclError:
            pass

    def close(self):
        if self.tray is not None:
            self.root.withdraw()
            return
        self.closed = True
        self._stop_activation()
        if self.supervisor is not None:
            self.supervisor.stop()
            self.supervisor = None
        if self._poll_job:
            try:
                self.root.after_cancel(self._poll_job)
            except tk.TclError:
                pass
        self.root.destroy()

    # ---------- 额度 ----------
    def _effective_quota_limit(self, qq):
        cfg = _read_json(DATA / 'dafeiyu_quota_config.json', {})
        base = int(cfg.get('daily_limit') or 75) if isinstance(cfg, dict) else 75
        try:
            return max(1, int((cfg.get('per_user') or {}).get(str(qq), base)))
        except (TypeError, ValueError):
            return base

    def queue_user_notice(self, qq, text):
        """Queue one exact private notice for a user."""
        try:
            return enqueue(DATA / 'dafeiyu_private_outbox.json', [qq], text)
        except (OSError, ValueError) as exc:
            messagebox.showwarning('通知未排队', str(exc))
            return 0

    def save_user_limit(self, qq, var):
        """Persist a per-user daily limit from the quota page."""
        try:
            limit = int(str(var.get()).strip())
        except (ValueError, tk.TclError):
            messagebox.showwarning('额度上限', '请输入 1 到 2000 的整数')
            return
        if not 1 <= limit <= 2000:
            messagebox.showwarning('额度上限', '请输入 1 到 2000 的整数')
            return
        path = DATA / 'dafeiyu_quota_config.json'
        try:
            cfg = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            cfg = {}
        if not isinstance(cfg, dict):
            cfg = {}
        base = int(cfg.get('daily_limit') or 75)
        old_limit = self._effective_quota_limit(qq)
        per_user = cfg.setdefault('per_user', {})
        if limit == base:
            per_user.pop(str(qq), None)
        else:
            per_user[str(qq)] = limit
        try:
            path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as exc:
            messagebox.showerror('保存失败', str(exc))
            return
        if old_limit != limit:
            self.queue_user_notice(qq, '您的聊天上限已被调整至%d条每天。' % limit)
        if self.quota_page is not None:
            self.quota_page.reload()
        self.set_hint('已保存 %s 的每日上限：%d 条' % (qq, limit))

    def reset_user_quota(self, qq, nick):
        """Reset one friend's current-day quota count."""
        if not messagebox.askyesno('重置额度', '重置 %s（%s）今天的私聊额度？' % (nick, qq)):
            return
        today = datetime.now().strftime('%Y-%m-%d')
        path = DATA / 'dafeiyu_quota.json'
        try:
            with transaction(path) as state:
                entry = state.setdefault(str(qq), {})
                entry.update(day=today, count=0, notified=True, exhausted=False)
        except (OSError, ValueError) as exc:
            messagebox.showerror('重置失败', str(exc))
            return
        remaining = self._effective_quota_limit(qq)
        self.queue_user_notice(qq, '您当天的聊天额度已被重置，今日聊天额度剩余%d条。' % remaining)
        if self.quota_page is not None:
            self.quota_page.reload()
        self.set_hint('已重置 %s 的今日额度，剩余 %d 条' % (nick, remaining))

    def set_user_blocked(self, qq, var, nick=''):
        """Persist one user's block switch; the guard reads the file per message."""
        qq = str(qq)
        path = DATA / 'dafeiyu_blocked.json'
        try:
            blocked = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            blocked = {}
        if not isinstance(blocked, dict):
            blocked = {}
        enable = bool(var.get())
        if enable:
            info = blocked.get(qq) if isinstance(blocked.get(qq), dict) else {}
            blocked[qq] = {
                'at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'reason': str(info.get('reason') or '手动封禁'),
                'name': str(info.get('name') or nick or ''),
            }
        else:
            blocked.pop(qq, None)
        try:
            temp = path.with_suffix('.json.tmp')
            temp.write_text(json.dumps(blocked, ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(temp, path)
        except OSError as exc:
            messagebox.showerror('保存失败', str(exc))
            if self.quota_page is not None:
                self.quota_page.reload()
            return
        if not enable:
            # Keep the card visible after unblocking: today's counter starts at 0.
            today = datetime.now().strftime('%Y-%m-%d')
            qpath = DATA / 'dafeiyu_quota.json'
            try:
                with transaction(qpath) as state:
                    entry = state.get(qq) or {}
                    if entry.get('day') != today:
                        state[qq] = {'day': today, 'count': 0, 'notified': True, 'exhausted': False}
            except (OSError, ValueError) as exc:
                self.set_hint('已解封，但额度状态更新失败：' + str(exc))
        if self.quota_page is not None:
            self.quota_page.reload()
        if enable:
            self.set_hint('已封禁 %s（%s），大肥鱼不再回复' % (nick or qq, qq))
        else:
            self.set_hint('已解除 %s（%s）的封禁，可以正常聊天' % (nick or qq, qq))

    # ---------- 群聊 ----------
    def set_group_enabled(self, gid, var):
        """Persist one group's enabled switch."""
        path = DATA / 'dafeiyu_group_controls.json'
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data[str(gid)] = bool(var.get())
        try:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as exc:
            messagebox.showerror('保存失败', str(exc))
            return
        self._reload_groups()

    def save_group_limit(self, gid, var):
        """Persist one group's daily chat limit (0 means unlimited)."""
        try:
            limit = int(str(var.get()).strip())
        except (ValueError, tk.TclError):
            messagebox.showwarning('群聊上限', '请输入 0 到 2000 的整数，0 表示无限')
            return
        if not 0 <= limit <= 2000:
            messagebox.showwarning('群聊上限', '请输入 0 到 2000 的整数，0 表示无限')
            return
        path = DATA / 'dafeiyu_group_limits.json'
        try:
            cfg = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            cfg = {}
        if not isinstance(cfg, dict):
            cfg = {}
        base = int(cfg.get('default_daily') or 120)
        per = cfg.setdefault('per_group', {})
        if limit == base:
            per.pop(str(gid), None)
        else:
            per[str(gid)] = limit
        cfg['default_daily'] = base
        try:
            path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as exc:
            messagebox.showerror('保存失败', str(exc))
            return
        self._reload_groups()
        self.set_hint('已保存群 %s 的每日上限：%s' % (gid, '无限' if limit == 0 else limit))

    def set_all_group_limits(self, limit):
        """Set every group to unlimited (0) or back to the 120 default."""
        path = DATA / 'dafeiyu_group_limits.json'
        try:
            cfg = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            cfg = {}
        if not isinstance(cfg, dict):
            cfg = {}
        cfg['default_daily'] = 120
        if int(limit) == 120:
            cfg['per_group'] = {}
        else:
            cfg['per_group'] = {row['gid']: int(limit) for row in self.group_snapshot()}
        try:
            path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as exc:
            messagebox.showerror('保存失败', str(exc))
            return
        self._reload_groups()
        self.set_hint('已把全部群的每日上限设为 %s' % ('无限' if int(limit) == 0 else limit))

    def toggle_group_settings(self, gid):
        """Open or close one group's behavior sliders."""
        gid = str(gid)
        if gid in self.group_expanded:
            self.group_expanded.discard(gid)
        else:
            self.group_expanded.add(gid)
        self._reload_groups()

    def save_group_settings(self, gid, values):
        """Persist reply, sticker and voice percentages for one group."""
        path = DATA / 'dafeiyu_group_settings.json'
        try:
            cfg = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            cfg = {}
        if not isinstance(cfg, dict):
            cfg = {}
        defaults = cfg.setdefault('defaults', {'reply_desire': 100, 'sticker_rate': 100, 'voice_rate': 100})
        per = cfg.setdefault('per_group', {})
        entry = {key: int(var.get()) for key, var in values.items()}
        if all(int(entry.get(key, 100)) == int(defaults.get(key, 100))
               for key in ('reply_desire', 'sticker_rate', 'voice_rate')):
            per.pop(str(gid), None)
        else:
            per[str(gid)] = entry
        try:
            path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as exc:
            messagebox.showerror('保存失败', str(exc))
            return
        self._reload_groups()
        self.set_hint('已保存群 %s 的互动强度' % gid)

    def set_all_groups(self, enabled):
        """Enable or disable every group at once."""
        path = DATA / 'dafeiyu_group_controls.json'
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        for row in self.group_snapshot():
            data[row['gid']] = bool(enabled)
        try:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as exc:
            messagebox.showerror('保存失败', str(exc))
            return
        self._reload_groups()
        self.set_hint('已%s全部群聊回复' % ('启用' if enabled else '关闭'))

    def _reload_groups(self):
        rows = self.group_snapshot()
        self.data['group_rows'] = rows
        if self.group_page is not None:
            self.group_page.update_data({'group_rows': rows}, force=True)
        self._group_dirty = True

    # ---------- 上下线 ----------
    def stop(self):
        if time.monotonic() < getattr(self, '_stop_pending_until', 0):
            self.set_hint('下线正在处理中，请勿重复操作。')
            return
        if not messagebox.askyesno('结束下线', '将先自动提炼记忆并备份，然后关闭聊天程序和 QQ（NapCat）。\n\n下次上线需要重新登录 QQ，确定结束吗？'):
            return
        script = Path(__file__).resolve().parent / 'stop.ps1'
        if not script.exists():
            self.footer.configure(text='找不到结束脚本：' + str(script))
            return
        self._stop_pending_until = time.monotonic() + 300
        queued = self.queue_private_notices(STOP_NOTICE, hours=6) if self.bot_online() else 0
        if queued:
            self.footer.configure(text='已排队通知 %d 位近6小时聊过的好友，通知发完就下线…' % queued)
            self._wait_outbox_then_stop(script, time.time() + 180)
        else:
            self._launch_stop(script)

    def start(self):
        if self.bot_online():
            self.set_hint('聊天服务已经运行，无需重复启动；修改插件后请下线再上线。')
            return
        if time.monotonic() < getattr(self, '_start_pending_until', 0):
            self.set_hint('启动请求正在处理中，请稍候…')
            return
        self._start_pending_until = time.monotonic() + 120
        subprocess.Popen(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                          '-File', str(Path(__file__).parent / 'start.ps1')],
                         creationflags=HIDDEN)
        self.overview_page.set_banner('已发出启动请求，正在等待服务就绪…', 'info')
        self.set_hint('已发出启动请求，正在等待服务就绪…')
        self.root.after(3000, self.refresh)

    def recent_private_friends(self, hours=6, before=None):
        """Return friends with a private conversation in the window before N hours.

        Args:
            hours: Window length in hours.
            before: Optional epoch end of the window; defaults to now.

        Returns:
            A list of QQ strings.
        """
        try:
            from dafeiyu_supervisor import select_recent_friends
            return select_recent_friends(DATA, hours=hours, before=before)
        except (ImportError, OSError, ValueError):
            return []

    def queue_private_notices(self, text, hours=6):
        """Queue one exact notice for friends active in the last N hours."""
        recipients = self.recent_private_friends(hours)
        if not recipients:
            return 0
        try:
            return enqueue(DATA / 'dafeiyu_private_outbox.json', recipients, text)
        except (OSError, ValueError) as exc:
            self.set_hint('通知队列写入失败：' + str(exc))
            return 0

    def reviewer_status(self):
        status = _read_json(MIRROR_DATA / 'reviewer_status.json', {})
        age = time.time() - float(status.get('heartbeat') or 0)
        lines = ['运行状态：' + ('运行中' if age < 180 else '未运行或处理超时'),
                 '模型：' + str(status.get('model') or '尚未启动'),
                 '应用方式：你确认后应用，不自动采纳']
        usage = _read_json(MIRROR_DATA / 'reviewer_usage.json', {})
        lines.append('调用记录：%s / %s 次' % (usage.get('day', '暂无'), usage.get('calls', 0)))
        dbpath = MIRROR_DATA / 'reviewer.sqlite'
        if dbpath.exists():
            try:
                db = sqlite3.connect(dbpath.as_uri() + '?mode=ro', uri=True, timeout=1)
                try:
                    labels = {'pending': '排队', 'processing': '自言或批阅中', 'reviewed': '待归档', 'done': '已完成', 'needs_review': '异常待检查'}
                    for state, count in db.execute('SELECT state,COUNT(*) FROM jobs GROUP BY state'):
                        lines.append('%s：%d' % (labels.get(state, state), count))
                    for job, error in db.execute("SELECT id,error FROM jobs WHERE state='needs_review' ORDER BY created DESC LIMIT 5"):
                        lines.append('异常 %s：%s' % (job[:8], error))
                finally:
                    db.close()
            except sqlite3.Error:
                lines.append('任务队列暂时无法读取')
        messagebox.showinfo('独立批阅状态', '\n'.join(lines))

    def review_notices(self):
        items = _read_json(DATA / 'dafeiyu_private_outbox.json', [])
        pending = [x for x in items if x.get('status') in ('needs_review', 'sending')]
        if not pending:
            messagebox.showinfo('通知待核查', '没有待核查的通知。')
            return
        lines = ['以下通知可能已送达，不会自动重发。请核对聊天记录。', '']
        lines.extend('%s：%s [%s]' % (x.get('qq'), str(x.get('text', ''))[:100], x.get('reason', x.get('status'))) for x in pending[-30:])
        messagebox.showinfo('通知待核查（%d 条）' % len(pending), '\n'.join(lines))

    def queue_reset_notices(self):
        """Queue the quota-reset notice for friends active in the last 6 hours."""
        return self.queue_private_notices(RESET_NOTICE, hours=6)

    def bot_online(self):
        """Return whether the dashboard port is listening."""
        try:
            with socket.create_connection(('127.0.0.1', 6185), timeout=0.8):
                return True
        except OSError:
            return False

    def _launch_stop(self, script):
        self.footer.configure(text='正在提炼记忆并备份，然后下线…（约 60–90 秒）')
        subprocess.Popen(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                          '-File', str(script)], creationflags=HIDDEN)
        self.root.after(100000, self.refresh)

    def _wait_outbox_then_stop(self, script, deadline):
        outbox = DATA / 'dafeiyu_private_outbox.json'
        pending = False
        try:
            if outbox.exists():
                pending = any(item.get('status', 'pending') in ('pending', 'sending')
                              for item in json.loads(outbox.read_text(encoding='utf-8')))
        except (OSError, ValueError):
            pending = outbox.exists()
        if not pending or time.time() >= deadline:
            self._launch_stop(script)
            return
        self.footer.configure(text='正在通知近6小时聊过的好友，通知发完就下线…')
        self.root.after(1000, lambda: self._wait_outbox_then_stop(script, deadline))

    def reset_quota(self):
        state = DATA / 'dafeiyu_quota.json'
        try:
            current = json.loads(state.read_text(encoding='utf-8')) if state.exists() else {}
        except (OSError, ValueError):
            current = {}
        today = datetime.now().strftime('%Y-%m-%d')
        spent = [qq for qq, item in current.items() if isinstance(item, dict) and item.get('day') == today]
        if not messagebox.askyesno('重置私聊额度', '把所有好友今天的私聊条数清零？\n\n现在有 %d 位好友记着今天的用量。\n（主人不受限）' % len(spent)):
            return
        try:
            with transaction(state) as current:
                current.clear()
        except OSError as exc:
            messagebox.showerror('重置失败', str(exc))
            return
        notified = self.queue_reset_notices()
        self.set_hint('已重置 %d 位好友的今日额度（%s）；已排队通知 %d 位近6小时聊过的好友' % (
            len(spent), datetime.now().strftime('%H:%M'), notified), 12000)
        if self.quota_page is not None:
            self.quota_page.reload()
        messagebox.showinfo('已重置', '所有好友的私聊额度已清零，下一条消息开始按 0 计数。\n\n被清掉的有 %d 位好友。\n近6小时聊过的 %d 位好友会收到重置通知。' % (len(spent), notified))
        self.root.after(600, self.refresh)

    # ---------- 其他入口 ----------
    def qq_login_menu(self):
        """Open the QQ Music login actions in a small dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title('QQ音乐登陆')
        dialog.configure(bg=BG)
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.geometry('620x320+%d+%d' % (self.root.winfo_rootx() + 240, self.root.winfo_rooty() + 220))
        card = Card(dialog, height=270, pad=20, shadow=10, accent=VIOLET)
        card.pack(fill='both', expand=True, padx=18, pady=16)
        tk.Label(card.body, text='QQ音乐登陆', bg=CARD, fg=TEXT,
                 font=(FONT, 16, 'bold')).pack(anchor='w')
        tk.Label(card.body, text='二维码约 2 分钟有效；用 QQ音乐 App 扫。', bg=CARD, fg=MUTED,
                 font=(FONT, 9)).pack(anchor='w', pady=(4, 16))

        def choose(action):
            dialog.destroy()
            action()

        box = tk.Frame(card.body, bg=CARD)
        box.pack(fill='x')
        SoftButton(box, '本机显示二维码', lambda: choose(self.qq_qr), 'primary', width=152,
                   height=36, icon=I_STAR, bg=CARD).pack(side='left', padx=(0, 8))
        SoftButton(box, '发到QQ', lambda: choose(self.qq_qr_to_qq), 'ghost', width=104,
                   height=36, bg=CARD).pack(side='left', padx=(0, 8))
        SoftButton(box, '刷新登录', lambda: choose(self.qq_refresh), 'ghost', width=104,
                   height=36, icon=I_REFRESH, bg=CARD).pack(side='left')
        SoftButton(card.body, '关闭', dialog.destroy, 'ghost', width=92, height=32,
                   bg=CARD).pack(anchor='e', pady=(18, 0))
        dialog.grab_set()

    def manage_stickers(self):
        """Open the sticker folders with basic counts."""
        dialog = tk.Toplevel(self.root)
        dialog.title('表情包管理')
        dialog.configure(bg=BG)
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.geometry('760x430+%d+%d' % (self.root.winfo_rootx() + 180, self.root.winfo_rooty() + 160))
        collected = DATA / 'collected_stickers'
        builtin = DATA / 'stickers'
        daily = collected / 'daily'
        daily.mkdir(parents=True, exist_ok=True)
        fish = collected / '大肥鱼表情包'
        fish.mkdir(parents=True, exist_ok=True)
        card = Card(dialog, height=380, pad=20, shadow=10, accent=AMBER)
        card.pack(fill='both', expand=True, padx=18, pady=16)
        tk.Label(card.body, text='表情包管理', bg=CARD, fg=TEXT,
                 font=(FONT, 16, 'bold')).pack(anchor='w')
        info = tk.Label(card.body, text='统计中…', justify='left', bg=CARD, fg=MUTED,
                        font=(FONT, 9))
        info.pack(anchor='w', pady=(6, 14))

        def refresh_info():
            images = [path for path in collected.rglob('*')
                      if path.is_file() and path.suffix.lower() in ('.gif', '.webp', '.png', '.jpg', '.jpeg')] if collected.is_dir() else []
            count = len(images)
            size = sum(path.stat().st_size for path in images) / 1024 / 1024
            day_count = sum(1 for path in daily.iterdir() if path.is_dir()) if daily.is_dir() else 0
            static_count = sum(1 for path in builtin.glob('*') if path.is_file()) if builtin.is_dir() else 0
            fish_count = sum(1 for path in fish.glob('*')
                             if path.is_file() and path.suffix.lower() in ('.gif', '.webp', '.png', '.jpg', '.jpeg')) if fish.is_dir() else 0
            try:
                info.configure(text='收集表情：%d 个 / %.1f MB    ·    每日表情库：%d 天\n内置表情：%d 个    ·    大肥鱼表情包：%d 个' % (
                    count, size, day_count, static_count, fish_count))
            except tk.TclError:
                pass

        def open_dir(path):
            if not path.is_dir():
                messagebox.showwarning('表情包管理', '目录不存在：\n' + str(path))
                return
            os.startfile(str(path))

        refresh_info()
        row1 = tk.Frame(card.body, bg=CARD)
        row1.pack(fill='x')
        SoftButton(row1, '打开收集表情目录', lambda: open_dir(collected), 'ghost', width=152,
                   height=34, bg=CARD).pack(side='left', padx=(0, 8))
        SoftButton(row1, '打开每日表情库', lambda: open_dir(daily), 'ghost', width=152,
                   height=34, bg=CARD).pack(side='left', padx=(0, 8))
        row2 = tk.Frame(card.body, bg=CARD)
        row2.pack(fill='x', pady=(8, 0))
        SoftButton(row2, '打开内置表情目录', lambda: open_dir(builtin), 'ghost', width=152,
                   height=34, bg=CARD).pack(side='left', padx=(0, 8))
        SoftButton(row2, '打开大肥鱼表情包目录', lambda: open_dir(fish), 'ghost', width=182,
                   height=34, bg=CARD).pack(side='left')
        bottom = tk.Frame(card.body, bg=CARD)
        bottom.pack(fill='x', pady=(16, 0))
        SoftButton(bottom, '刷新统计', refresh_info, 'soft', width=104, height=32,
                   bg=CARD).pack(side='left')
        SoftButton(bottom, '关闭', dialog.destroy, 'ghost', width=92, height=32,
                   bg=CARD).pack(side='right')
        dialog.grab_set()

    def qq_qr_to_qq(self):
        """Ask the bot process to push a fresh QR to the owner's QQ."""
        path = ROOT / 'data' / 'qqmusic_login.request'
        path.write_text('1', encoding='utf-8')
        messagebox.showinfo('QQ 音乐', '已发给主人的 QQ，去手机上看二维码，2 分钟内扫')

    def qq_refresh(self):
        """Ask the backend to refresh the saved QQ Music cookie."""
        import urllib.request
        try:
            with urllib.request.urlopen('http://127.0.0.1:3311/login/refresh', timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))
        except Exception:
            messagebox.showerror('QQ 音乐', '后端没连上，稍后再试')
            return
        if data.get('ok'):
            messagebox.showinfo('QQ 音乐', '登录已刷新')
        else:
            messagebox.showwarning('QQ 音乐', '刷新失败，可能需要重新扫码')
        self.refresh()

    def qq_qr(self):
        """Fetch a fresh QQ Music login QR in the background."""
        threading.Thread(target=self._qq_qr_worker, daemon=True).start()

    def _qq_qr_worker(self):
        import base64
        import urllib.request
        try:
            with urllib.request.urlopen('http://127.0.0.1:3311/login/qr?type=mobile', timeout=10) as response:
                payload = json.loads(response.read().decode('utf-8'))
            raw = str(payload.get('qrcode') or payload.get('qrimg') or '')
            data = raw.split(',', 1)[-1]
            path = ROOT / 'scripts' / 'QQ音乐登录二维码.png'
            path.write_bytes(base64.b64decode(data))
            sig = str(payload.get('qrsig') or '')
            self.root.after(0, lambda: self._show_qq_qr(path, sig))
        except Exception as exc:
            self.root.after(0, lambda error=exc: messagebox.showerror(
                'QQ 音乐', '取二维码失败：' + type(error).__name__))

    def _show_qq_qr(self, path, sig):
        window = tk.Toplevel(self.root)
        window.title('QQ 音乐登录二维码 · 用 QQ音乐App 扫')
        window.configure(bg=BG)
        window.transient(self.root)
        try:
            image = tk.PhotoImage(file=str(path))
            image = image.zoom(4, 4)
        except tk.TclError:
            image = None
        card = Card(window, pad=18, shadow=10, auto=True)
        card.pack(fill='both', expand=True, padx=18, pady=16)
        tk.Label(card.body, text='QQ音乐扫码登录', bg=CARD, fg=TEXT,
                 font=(FONT, 15, 'bold')).pack(anchor='w')
        if image is not None:
            holder = tk.Frame(card.body, bg='#FFFFFF', highlightbackground=BORDER, highlightthickness=1)
            holder.pack(pady=14)
            label = tk.Label(holder, image=image, bg='#FFFFFF')
            label.image = image
            label.pack(padx=12, pady=12)
        tk.Label(card.body, text='用手机 QQ音乐 App 扫码；二维码约 2 分钟有效', bg=CARD, fg=MUTED,
                 font=(FONT, 9)).pack(anchor='w')
        SoftButton(card.body, '关闭', window.destroy, 'ghost', width=92, height=30,
                   bg=CARD).pack(anchor='e', pady=(10, 0))
        self.set_hint('二维码已弹出 · 等待扫码')
        threading.Thread(target=self._qq_wait_login, args=(sig,), daemon=True).start()

    def _qq_wait_login(self, sig):
        import urllib.request
        for _ in range(45):
            time.sleep(3)
            try:
                with urllib.request.urlopen('http://127.0.0.1:3311/login/check?qrsig=' + sig, timeout=8) as response:
                    state = json.loads(response.read().decode('utf-8'))
            except Exception:
                continue
            code = state.get('code')
            if code == 200:
                self.root.after(0, lambda: self.set_hint('QQ 音乐已登录 · uin ' + str(state.get('uin') or '')))
                self.root.after(1500, self.refresh)
                return
            if code in (800, 801):
                self.root.after(0, lambda: self.set_hint('二维码已过期 · 请再点一次「QQ音乐登陆」'))
                return

    def show_qr(self):
        source = ROOT / 'runtime' / 'napcat-shell' / 'cache' / 'qrcode.png'
        target = Path(__file__).resolve().parent / '登录二维码.png'
        if not source.exists():
            messagebox.showwarning('没有二维码', 'NapCat 还没有生成二维码。请先点「启动上线」，等 QQ 登录窗口出现。')
            return
        try:
            data = source.read_bytes()
            target.write_bytes(data)
        except OSError as exc:
            messagebox.showerror('复制失败', str(exc))
            return
        stamp = datetime.fromtimestamp(source.stat().st_mtime).strftime('%H:%M:%S')
        messagebox.showinfo('最新二维码', '已更新：' + str(target) + '\n生成时间：' + stamp + '\n\n二维码约 2 分钟有效，过期就再点一次。')
        try:
            os.startfile(str(target))
        except OSError:
            pass

    def open_log(self):
        subprocess.Popen(['notepad.exe', str(LOG)])

    def open_diary_library(self):
        """Open the illustration library folder and create its inbox."""
        folder = DATA / 'diary_library'
        try:
            (folder / 'inbox').mkdir(parents=True, exist_ok=True)
            os.startfile(folder)
        except OSError as exc:
            messagebox.showerror('打开图库失败', str(exc))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='大肥鱼控制中心')
    parser.add_argument('--mode', choices=['main', 'mirror'], default='main',
                        help='运行模式：main=主程序, mirror=镜像版本')
    parser.add_argument('--autostart', action='store_true',
                        help='开机自启模式（兼容旧任务参数；上线通知现由镜像守候负责）')
    parser.add_argument('--show', action='store_true',
                        help='启动后直接打开窗口；已有实例时请它打开窗口（桌面图标用）')
    parser.add_argument('--probe', action='store_true',
                        help='只探测：0=实例正常响应，1=实例在但没响应，2=没有实例')
    args = parser.parse_args()
    if args.mode == 'mirror':
        # 2.0 发行包不包含镜像版，避免误开一个没有数据的窗口。
        print('2.0 发行包不含镜像版，请使用主控制中心。')
        sys.exit(0)
    _port = _activation_port(args.mode)
    _instance_mutex = None
    if sys.platform == 'win32':
        _mutex_name = ('Local\\DafeiyuMirrorControlCenter' if args.mode == 'mirror'
                       else 'Local\\DafeiyuControlCenter')
        _instance_mutex = ctypes.windll.kernel32.CreateMutexW(None, False, _mutex_name)
        if ctypes.windll.kernel32.GetLastError() == 183:
            # 已有实例。以前这里直接退出，托盘图标一丢桌面图标就完全打不开；
            # 现在把请求交给正在运行的实例，让它把窗口显示出来。
            if args.probe:
                sys.exit(0 if _send_activation(_port, 'ping') == 'pong' else 1)
            if args.show:
                if _send_activation(_port, 'show') == 'ok':
                    sys.exit(0)
                _report_unresponsive(args.mode)
                sys.exit(0)
            sys.exit(0)
    if args.probe:
        sys.exit(2)
    try:
        StatusWindow(start_hidden=not args.show, mode=args.mode,
                     autostart=args.autostart).root.mainloop()
    except Exception:
        details = traceback.format_exc()
        _log_startup_crash(details)
        last_line = details.strip().splitlines()[-1] if details.strip() else '未知错误'
        _show_startup_error(
            '大肥鱼控制中心启动失败：' + last_line
            + '\n\n详细信息已写入 runtime\\logs\\control_center_error.log。'
        )
        sys.exit(1)
