# 大肥鱼状态中心 · packaged by YunShan You
import json
import os
import re
import socket
import sqlite3
import subprocess
import threading
import time
import tkinter as tk
import webbrowser
try:
    import pystray
    from PIL import Image
except ImportError:
    pystray = None
    Image = None
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import messagebox, ttk

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'runtime/AstrBot-4.29.3/data'
LOG = ROOT / 'runtime/AstrBot-4.29.3/startup.log'
HIDDEN = subprocess.CREATE_NO_WINDOW
RESET_NOTICE = '刚刚主人把我的私聊额度重置啦，我们又可以聊天了！'
STOP_NOTICE = '我要下线啦，明天再来聊天吧'
START_NOTICE = '我上线啦，快来和我聊聊天吧'



def qqmusic_status():
    """Read the local QQ Music backend state.

    Returns:
        A dict with running/logged/uin fields.
    """
    import urllib.request
    songs = 0
    try:
        library = json.loads((ROOT / 'data/music_library' / 'index.json').read_text(encoding='utf-8'))
        songs = len(library.get('songs', []))
    except (OSError, ValueError):
        pass
    try:
        with urllib.request.urlopen('http://127.0.0.1:3311/health', timeout=2) as response:
            data = json.loads(response.read().decode('utf-8'))
        return {'running': True, 'logged': bool(data.get('logged')), 'uin': str(data.get('uin') or ''), 'songs': songs}
    except Exception:
        return {'running': False, 'logged': False, 'uin': '', 'songs': songs}


def inspect_status():
    ports = {}
    for port in (6185, 6199, 6099):
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.5):
                ports[port] = True
        except OSError:
            ports[port] = False
    try:
        network = subprocess.run(['netstat', '-ano', '-p', 'tcp'], capture_output=True, text=True, creationflags=HIDDEN, timeout=6).stdout
        connected = any('ESTABLISHED' in line and '127.0.0.1:6199 ' in line for line in network.splitlines())
    except (OSError, subprocess.TimeoutExpired):
        connected = None
    log = LOG.read_text(encoding='utf-8', errors='replace') if LOG.exists() else ''
    group_count = None
    group_counts = {}
    day_counts = {}
    diary = {}
    state = DATA / 'dafeiyu_diary_state.json'
    if state.exists():
        try:
            diary = json.loads(state.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            pass
    errors = [line for line in log.splitlines() if '[ERROR]' in line or 'readiness failed' in line]
    watchdog = {}
    wd = DATA / 'dafeiyu_watchdog.json'
    if wd.exists():
        try:
            watchdog = json.loads(wd.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            pass
    try:
        autostart = subprocess.run(['schtasks', '/Query', '/TN', '大肥鱼自动启动'], capture_output=True, creationflags=HIDDEN, timeout=8).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        autostart = None
    backup = None
    backups = sorted((ROOT / 'runtime' / 'backups').glob('dafeiyu_*.zip'), key=lambda p: p.stat().st_mtime, reverse=True)
    if backups:
        newest = backups[0]
        backup = (newest.name, datetime.fromtimestamp(newest.stat().st_mtime).strftime('%m-%d %H:%M'), newest.stat().st_size // 1024)
    memories = {}
    for key, name in (('private', 'dafeiyu_memory.md'), ('group', 'dafeiyu_group_memory.md')):
        path = DATA / name
        if path.exists():
            memories[key] = sum(1 for line in path.read_text(encoding='utf-8').splitlines() if line.strip().startswith('- '))
    quiet = None
    quota_usage = []
    try:
        quota = json.loads((DATA / 'dafeiyu_quota.json').read_text(encoding='utf-8'))
        try:
            quota_cfg = json.loads((DATA / 'dafeiyu_quota_config.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            quota_cfg = {}
        quota_limit = int(quota_cfg.get('daily_limit') or 75)
        friends = json.loads((DATA / 'dafeiyu_friends.json').read_text(encoding='utf-8'))
        today = datetime.now().strftime('%Y-%m-%d')
        for qq, entry in quota.items():
            if qq == '1000000001' or entry.get('day') != today:
                continue
            nick = (friends.get(qq) or {}).get('nick') or qq
            quota_usage.append((nick, int(entry.get('count') or 0), quota_limit))
        quota_usage.sort(key=lambda item: item[1], reverse=True)
    except (OSError, ValueError):
        quota_usage = []
    memory_job = {'pending': (DATA / 'dafeiyu_memory.flag').exists(), 'last_run': '', 'private_added': None, 'group_added': None, 'error': ''}
    job_path = DATA / 'dafeiyu_memory_state.json'
    if job_path.exists():
        try:
            job = json.loads(job_path.read_text(encoding='utf-8'))
            memory_job.update(last_run=str(job.get('last_run') or ''), private_added=job.get('private_added'), group_added=job.get('group_added'), error=str(job.get('error') or ''))
        except (OSError, ValueError):
            pass
    selftest = '暂无报告'
    report = ROOT / 'runtime' / '自检报告.txt'
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
    return ports, connected, log, group_count, diary, errors, watchdog, autostart, backup, memories, quiet, memory_job, quota_usage, group_counts, day_counts, selftest, qqmusic_status()


class StatusWindow:
    def __init__(self, start_hidden=True):
        self.root = tk.Tk()
        self.root.title('大肥鱼 · 状态中心')
        icon = Path(__file__).resolve().parent.parent / 'assets' / 'icon.ico'
        if icon.exists():
            try:
                self.root.iconbitmap(str(icon))
            except tk.TclError:
                pass
        self.root.geometry('780x700')
        self.root.minsize(720, 660)
        self.root.configure(bg='#f0f5fb')
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', font=('Microsoft YaHei UI', 10), padding=9)
        top = tk.Frame(self.root, bg='#f0f5fb')
        top.pack(fill='x', padx=26, pady=(22, 12))
        tk.Label(top, text='大肥鱼状态中心', bg='#f0f5fb', fg='#172d49', font=('Microsoft YaHei UI', 22, 'bold')).pack(anchor='w')
        tk.Label(top, text='独立运行 · 每 5 秒刷新 · 不调用付费模型接口', bg='#f0f5fb', fg='#65758a', font=('Microsoft YaHei UI', 10)).pack(anchor='w', pady=5)
        self.banner = tk.Label(self.root, text='正在检查…', bg='#e1ebf8', fg='#254b79', font=('Microsoft YaHei UI', 13, 'bold'), pady=14)
        self.banner.pack(fill='x', padx=26, pady=(0, 12))
        self.values = {}
        for key, title in [('chat','聊天程序'), ('qq','QQ 接入'), ('connection','QQ ↔ 聊天连接'), ('qqmusic','QQ 音乐'), ('group','群聊与独立记忆'), ('diary','每日空间动态'), ('selftest','最近自检')]:
            row = tk.Frame(self.root, bg='white', padx=14, pady=10)
            row.pack(fill='x', padx=26, pady=3)
            tk.Label(row, text=title, width=17, anchor='w', bg='white', fg='#52667e', font=('Microsoft YaHei UI', 10)).pack(side='left')
            label = tk.Label(row, text='检查中', bg='white', fg='#172d49', anchor='w', font=('Microsoft YaHei UI', 10))
            label.pack(side='left', fill='x', expand=True)
            self.values[key] = label
        actions = tk.Frame(self.root, bg='#f0f5fb')
        actions.pack(fill='x', padx=26, pady=(4, 2))
        row1 = tk.Frame(actions, bg='#f0f5fb')
        row1.pack(fill='x')
        for text_, command_, width_ in [
            ('启动上线', self.start, 12),
            ('结束下线（自动备份与记忆提炼）', self.stop, 30),
            ('立即刷新', self.refresh, 12),
        ]:
            ttk.Button(row1, text=text_, command=command_, width=width_).pack(side='left', padx=(0, 8))
        row2 = tk.Frame(actions, bg='#f0f5fb')
        row2.pack(fill='x', pady=(6, 0))
        for text_, command_, width_ in [
            ('取QQ登录二维码', self.show_qr, 18),
            ('QQ音乐登陆', self.qq_login_menu, 16),
            ('重置所有好友私聊额度', self.reset_quota, 22),
        ]:
            ttk.Button(row2, text=text_, command=command_, width=width_).pack(side='left', padx=(0, 8))
        row3 = tk.Frame(actions, bg='#f0f5fb')
        row3.pack(fill='x', pady=(6, 0))
        for text_, command_, width_ in [
            ('插件管理页面', lambda: webbrowser.open('http://127.0.0.1:6185'), 16),
            ('打开日志', self.open_log, 12),
            ('表情包管理', self.manage_stickers, 14),
        ]:
            ttk.Button(row3, text=text_, command=command_, width=width_).pack(side='left', padx=(0, 8))
        self.quota_hint = tk.Label(actions, text='', bg='#f0f5fb', fg='#65758a', font=('Microsoft YaHei UI', 9))
        self.quota_hint.pack(anchor='w', pady=(6, 0))
        self.detail = tk.Text(self.root, height=5, wrap='word', bg='white', fg='#52667e', relief='flat', font=('Microsoft YaHei UI', 10), padx=12, pady=10)
        self.detail.pack(fill='both', expand=True, padx=26)
        self.footer = tk.Label(self.root, text='', bg='#f0f5fb', fg='#65758a', font=('Microsoft YaHei UI', 9))
        self.footer.pack(anchor='w', padx=26, pady=12)
        self.busy = False
        self.last_alert = 0
        self.result = None
        self.closed = False
        self.tray = None
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.setup_tray()
        if start_hidden and self.tray is not None:
            self.root.withdraw()
        self.root.after(100, self.refresh)
        self.root.after(200, self.poll)

    def setup_tray(self):
        """Create the system-tray icon and keep the window available on demand."""
        if pystray is None or Image is None:
            self.footer.config(text='系统托盘组件缺失：请安装 pystray，窗口将直接显示')
            return
        icon_path = Path(__file__).resolve().parent.parent / 'assets' / 'icon.ico'
        if not icon_path.exists():
            self.footer.config(text='找不到托盘图标：assets/icon.ico')
            return
        try:
            image = Image.open(icon_path)
            menu = pystray.Menu(
                pystray.MenuItem('打开状态中心', self.show_window, default=True),
                pystray.MenuItem('启动上线', lambda: self.root.after(0, self.start)),
                pystray.MenuItem('结束下线', lambda: self.root.after(0, self.stop)),
                pystray.MenuItem('退出托盘', self.quit_app),
            )
            self.tray = pystray.Icon('dafeiyu', image, '大肥鱼 · 状态中心', menu)
            self.tray.run_detached()
        except Exception as exc:
            self.tray = None
            self.footer.config(text='托盘启动失败：' + type(exc).__name__)

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

    def quit_app(self):
        """Stop the tray icon and close the status process."""
        self.closed = True
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

    def qq_login_menu(self):
        """Open the QQ Music login actions in a small dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title('QQ音乐登陆')
        dialog.configure(bg='#f0f5fb')
        dialog.transient(self.root)
        dialog.resizable(False, False)
        tk.Label(dialog, text='QQ音乐登陆', bg='#f0f5fb', fg='#172d49',
                 font=('Microsoft YaHei UI', 15, 'bold')).pack(anchor='w', padx=18, pady=(16, 4))
        tk.Label(dialog, text='二维码约 2 分钟有效；用 QQ音乐 App 扫。', bg='#f0f5fb', fg='#65758a',
                 font=('Microsoft YaHei UI', 9)).pack(anchor='w', padx=18, pady=(0, 12))

        def choose(action):
            dialog.destroy()
            action()

        box = tk.Frame(dialog, bg='#f0f5fb')
        box.pack(fill='x', padx=18, pady=(0, 10))
        ttk.Button(box, text='本机显示二维码', command=lambda: choose(self.qq_qr), width=18).pack(side='left', padx=(0, 8))
        ttk.Button(box, text='发到QQ', command=lambda: choose(self.qq_qr_to_qq), width=12).pack(side='left', padx=(0, 8))
        ttk.Button(box, text='刷新登录', command=lambda: choose(self.qq_refresh), width=12).pack(side='left')
        ttk.Button(dialog, text='关闭', command=dialog.destroy, width=10).pack(anchor='e', padx=18, pady=(0, 14))
        dialog.grab_set()

    def manage_stickers(self):
        """Open the sticker folders with basic counts."""
        dialog = tk.Toplevel(self.root)
        dialog.title('表情包管理')
        dialog.configure(bg='#f0f5fb')
        dialog.transient(self.root)
        dialog.resizable(False, False)
        collected = DATA / 'collected_stickers'
        builtin = DATA / 'stickers'
        fish = collected / '大肥鱼表情包'
        fish.mkdir(parents=True, exist_ok=True)
        tk.Label(dialog, text='表情包管理', bg='#f0f5fb', fg='#172d49',
                 font=('Microsoft YaHei UI', 15, 'bold')).pack(anchor='w', padx=18, pady=(16, 4))
        info = tk.Label(dialog, text='', justify='left', bg='#f0f5fb', fg='#52667e',
                        font=('Microsoft YaHei UI', 9))
        info.pack(anchor='w', padx=18, pady=(0, 10))

        def refresh_info():
            count = sum(1 for path in collected.glob('*') if path.is_file()) if collected.is_dir() else 0
            size = sum(path.stat().st_size for path in collected.glob('*') if path.is_file()) / 1024 / 1024 if collected.is_dir() else 0
            static_count = sum(1 for path in builtin.glob('*') if path.is_file()) if builtin.is_dir() else 0
            fish_count = sum(1 for path in fish.glob('*') if path.is_file() and path.suffix.lower() in ('.gif', '.webp', '.png', '.jpg', '.jpeg')) if fish.is_dir() else 0
            info.config(text='收集表情：%d 个 / %.1f MB\n内置表情：%d 个\n大肥鱼表情包：%d 个' % (count, size, static_count, fish_count))

        def open_dir(path):
            if not path.is_dir():
                messagebox.showwarning('表情包管理', '目录不存在：\n' + str(path))
                return
            os.startfile(str(path))

        refresh_info()
        box = tk.Frame(dialog, bg='#f0f5fb')
        box.pack(fill='x', padx=18, pady=(0, 10))
        ttk.Button(box, text='打开收集表情目录', command=lambda: open_dir(collected), width=16).pack(side='left', padx=(0, 8))
        ttk.Button(box, text='打开内置表情目录', command=lambda: open_dir(builtin), width=16).pack(side='left', padx=(0, 8))
        ttk.Button(box, text='打开大肥鱼表情包目录', command=lambda: open_dir(fish), width=20).pack(side='left', padx=(0, 8))
        ttk.Button(dialog, text='刷新统计', command=refresh_info, width=10).pack(anchor='w', padx=18, pady=(0, 6))
        ttk.Button(dialog, text='关闭', command=dialog.destroy, width=10).pack(anchor='e', padx=18, pady=(0, 14))
        dialog.grab_set()

    def qq_qr_to_qq(self):
        """Ask the bot process to push a fresh QR to the owner's QQ."""
        path = ROOT / 'runtime' / 'qqmusic_login.request'
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
            path = ROOT / 'runtime' / 'QQ音乐登录二维码.png'
            path.write_bytes(base64.b64decode(data))
            sig = str(payload.get('qrsig') or '')
            self.root.after(0, lambda: self._show_qq_qr(path, sig))
        except Exception as exc:
            self.root.after(0, lambda: messagebox.showerror('QQ 音乐', '取二维码失败：' + type(exc).__name__))

    def _show_qq_qr(self, path, sig):
        window = tk.Toplevel(self.root)
        window.title('QQ 音乐登录二维码 · 用 QQ音乐App 扫')
        window.configure(bg='white')
        try:
            image = tk.PhotoImage(file=str(path))
            image = image.zoom(4, 4)
        except tk.TclError:
            image = None
        if image is not None:
            label = tk.Label(window, image=image, bg='white')
            label.image = image
            label.pack(padx=20, pady=16)
        tk.Label(window, text='用手机 QQ音乐 App 扫码；二维码约 2 分钟有效', bg='white', fg='#52667e',
                 font=('Microsoft YaHei UI', 10)).pack(pady=(0, 12))
        self.values['qqmusic'].config(text='二维码已弹出 · 等待扫码')
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
                self.root.after(0, lambda: self.values['qqmusic'].config(text='已登录 · uin ' + str(state.get('uin') or '')))
                return
            if code in (800, 801):
                self.root.after(0, lambda: self.values['qqmusic'].config(text='二维码已过期 · 再点一次「QQ音乐二维码」'))
                return

    def close(self):
        if self.tray is not None:
            self.root.withdraw()
            return
        self.closed = True
        self.root.destroy()

    def refresh(self):
        if self.busy:
            return
        self.busy = True
        self.footer.config(text='正在刷新…')
        threading.Thread(target=self.collect, daemon=True).start()

    def collect(self):
        try:
            self.result = (True, inspect_status())
        except Exception as exc:
            self.result = (False, type(exc).__name__)

    def poll(self):
        if self.result is not None:
            ok, result = self.result
            self.result = None
            self.busy = False
            if ok:
                self.render(result)
            else:
                self.banner.config(text='检查暂时失败，请刷新', bg='#fff0d9', fg='#8c5b17')
                self.footer.config(text='检查错误：' + result)
            self.root.after(5000, self.refresh)
        if not self.closed:
            self.root.after(200, self.poll)

    def render(self, result):
        ports, connection, log, count, diary, errors, watchdog, autostart, backup, memories, quiet, memory_job, quota_usage, group_counts, day_counts, selftest, _qqmusic = result
        ready = ports[6185] and ports[6099] and connection
        self.banner.config(text='运行正常 · QQ 连接已建立' if ready else '需要关注 · 部分服务未连接', bg='#dff3e9' if ready else '#fff0d9', fg='#226747' if ready else '#8c5b17')
        self.values['chat'].config(text='运行中' if ports[6185] else '未运行')
        self.values['qq'].config(text='接入服务运行中' if ports[6099] else '未运行')
        self.values['connection'].config(text='已连接' if connection else ('等待连接' if connection is False else '暂时无法确认'))
        qqmusic = result[-1] if isinstance(result[-1], dict) else {}
        if not qqmusic.get('running'):
            self.values['qqmusic'].config(text='后端未启动')
        elif qqmusic.get('logged'):
            self.values['qqmusic'].config(text='已登录 · uin ' + (qqmusic.get('uin') or '未知') + ' · 库 ' + str(qqmusic.get('songs', 0)) + ' 首')
        else:
            self.values['qqmusic'].config(text='后端运行中 · 未登录 · 库 ' + str(qqmusic.get('songs', 0)) + ' 首（点下面「QQ音乐二维码」）')
        joined = ('Whale group 1000000002 membership: True' in log)
        used = 0
        group_db_path = DATA / 'dafeiyu_group_memory.db'
        if group_db_path.exists():
            try:
                with sqlite3.connect(group_db_path, timeout=1) as group_db:
                    used = group_db.execute('SELECT count(*) FROM messages WHERE group_id=?', ('1000000002',)).fetchone()[0]
            except sqlite3.Error:
                used = 0
        self.values['group'].config(text='群聊 · **群 · 今日消息 %d 条 · ' % used + ('本次启动已验证入群' if joined and ready else '当前在线状态待确认'))
        loaded = 'Whale diary next run:' in log
        status = {'published':'发布成功','failed':'发布失败','sending':'发送结果待核对'}.get(diary.get('status'),'尚无发布记录')
        kind = {'library':'图库照','sticker':'表情包'}.get(diary.get('image_kind'),'')
        if diary.get('image') and diary.get('image_error'):
            figure = ' · 配图未附上'
        elif diary.get('image'):
            figure = ' · 已配图' + ('（'+kind+'）' if kind else '')
        else:
            figure = ''
        self.values['diary'].config(text='每天 21:00 · '+('任务已加载' if loaded and ports[6185] else '任务待启动')+' · '+status+figure)
        if '通过' in selftest and datetime.now().strftime('%Y-%m-%d') in selftest:
            selftest_color = '#226747'
        elif '通过' in selftest:
            selftest_color = '#8c5b17'
        else:
            selftest_color = '#b03030'
        self.values['selftest'].config(text=selftest, fg=selftest_color)
        if not ready and time.time() - self.last_alert > 1800:
            self.last_alert = time.time()
            self.root.deiconify()
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.after(3000, lambda: self.root.attributes('-topmost', False))
        lines = ['当前连接状态来自本机端口和实时连接；不代表每次模型调用一定成功。', '群聊入群检查与日记加载情况来自本次启动日志。']
        if memory_job.get('pending'):
            lines.append('记忆提炼：已请求，约 10 秒内开始（结果会自动刷新）')
        elif memory_job.get('error'):
            lines.append('记忆提炼：上次失败（' + memory_job['error'] + '）')
        elif memory_job.get('last_run'):
            lines.append('记忆提炼：手动触发 · 最近 ' + memory_job['last_run'] + '（新增 私聊 ' + str(memory_job.get('private_added')) + ' / 群聊 ' + str(memory_job.get('group_added')) + ' 条）')
        else:
            lines.append('记忆提炼：手动触发（点“提炼记忆”按钮，约 10 秒完成）')
        if quota_usage:
            lines.append('今日好友额度：' + ' · '.join(f'{nick} {used}/{limit}' for nick, used, limit in quota_usage[:4]))
        protect = []
        try:
            lock = json.loads((DATA / 'dafeiyu_lock.json').read_text(encoding='utf-8'))
            hits = sum(int(v.get('count') or 0) for v in lock.values())
            if hits:
                protect.append(f'人设改写拦截 {hits} 次')
        except (OSError, ValueError):
            pass
        try:
            blocked = json.loads((DATA / 'dafeiyu_blocked.json').read_text(encoding='utf-8'))
            if blocked:
                protect.append(f'拉黑 {len(blocked)} 人')
        except (OSError, ValueError):
            pass
        try:
            qr = json.loads((DATA / 'dafeiyu_qzone_reply.json').read_text(encoding='utf-8'))
            if qr.get('count'):
                lines.append('空间评论回复：今天已回 %d 条（同一动态同一人只回一次）' % qr['count'])
        except (OSError, ValueError):
            pass
        if protect:
            lines.append('防护：' + ' · '.join(protect))
        lines.insert(0, '群聊作息：全天在线（无定时静默）')
        if watchdog:
            if watchdog.get('online'):
                lines.insert(0, '看门狗：QQ 在线（最近探测 '+str(watchdog.get('checked_at',''))[-8:]+'）')
            else:
                lines.insert(0, '看门狗：QQ 未连接（自 '+str(watchdog.get('offline_since') or '未知')+'，原因 '+str(watchdog.get('detail') or '未知')+'）')
        if diary.get('text'):
            lines.append('最近一条动态：'+str(diary['text'])[:70])
        if diary.get('image'):
            lines.append('配图：'+('已随动态发出' if not diary.get('image_error') else '未附上，已退回纯文字'))
        if diary.get('image_source'):
            lines.append('配图来源：'+str(diary['image_source'])[:80])
        if backup:
            size_kb = backup[2]
            size_text = '%.1f MB' % (size_kb / 1024) if size_kb >= 1024 else '%d KB' % size_kb
            lines.append('最近备份：' + backup[1] + '（' + size_text + '，保留最近 8 份）')
        last_shutdown = ROOT / 'runtime' / '关机记录.txt'
        if last_shutdown.exists():
            try:
                tail = [ln.strip() for ln in last_shutdown.read_text(encoding='utf-8', errors='replace').splitlines() if ln.strip()]
                if tail:
                    lines.append('上次关机：' + tail[-1][:100])
            except OSError:
                pass
        try:
            online_state = json.loads((DATA / 'dafeiyu_online_state.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            online_state = {}
        outage = online_state.get('last_outage') or {}
        if outage.get('end'):
            when = datetime.fromtimestamp(float(outage['end'])).strftime('%m-%d %H:%M')
            lines.append('上次断线：%s 断了 %s 分钟，补回 %s 位好友（共 %s 条待回）' % (
                when, outage.get('minutes', '?'), outage.get('sent', 0), outage.get('friends', 0)))
        else:
            lines.append('上次断线：暂无记录')
        if online_state.get('outages_today'):
            lines.append('今日断线：%d 次（断满 5 分钟才计数）' % int(online_state['outages_today']))
        if autostart is not None:
            lines.append('自动启动：'+('已启用（登录后自动拉起）' if autostart else '未启用（在状态中心手动上线）'))
        if diary.get('attempted_day'):
            lines.append('最近发布日期：'+str(diary['attempted_day']))
        if errors:
            lines.append('日志中最近的错误：'+errors[-1][:230])
        if not ready:
            if not ports[6099]:
                lines.append('QQ 接入未运行：请先登录 QQ（1000000000），并同意管理员权限——NapCat 需要管理员才能挂载。')
            lines.append('可点击“启动 / 恢复大肥鱼”；若仍未连接，请打开日志检查 QQ 扫码或模型错误。')
        self.detail.config(state='normal')
        self.detail.delete('1.0','end')
        self.detail.insert('1.0','\n'.join(lines))
        self.detail.config(state='disabled')
        self.footer.config(text='最近检查：'+datetime.now().strftime('%H:%M:%S')+'   关闭此窗口不会关闭大肥鱼')

    def stop(self):
        if not messagebox.askyesno('结束下线', '将先自动提炼记忆并备份，然后关闭聊天程序和 QQ（NapCat）。\n\n下次上线需要重新登录 QQ，确定结束吗？'):
            return
        script = Path(__file__).resolve().parent / 'stop.ps1'
        if not script.exists():
            self.footer.config(text='找不到结束脚本：' + str(script))
            return
        queued = self.queue_private_notices(STOP_NOTICE) if self.bot_online() else 0
        if queued:
            self.footer.config(text='已排队通知 %d 位最近聊过的好友，通知发完就下线…' % queued)
            self._wait_outbox_then_stop(script, time.time() + 180)
        else:
            self._launch_stop(script)

    def start(self):
        self.queue_private_notices(START_NOTICE)
        subprocess.Popen(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(Path(__file__).parent/'start.ps1')], creationflags=HIDDEN)
        self.banner.config(text='已发出启动请求，正在等待服务就绪…', bg='#e1ebf8', fg='#254b79')
        self.root.after(3000,self.refresh)

    def extract_memory(self):
        flag = DATA / 'dafeiyu_memory.flag'
        try:
            flag.write_text('manual', encoding='utf-8')
            self.footer.config(text='已请求提炼记忆，约 10 秒后完成；稍等几秒会自动刷新')
        except OSError:
            self.footer.config(text='无法写入提炼请求，请检查文件权限')
        self.root.after(12000, self.refresh)

    def quota_reset_recipients(self):
        """Return friends with a private conversation in the last 12 hours."""
        friends = {}
        try:
            friends = json.loads((DATA / 'dafeiyu_friends.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return []
        cutoff = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=12)).strftime('%Y-%m-%d %H:%M:%S')
        try:
            with sqlite3.connect(DATA / 'data_v4.db') as db:
                rows = db.execute(
                    "SELECT user_id FROM conversations WHERE user_id LIKE 'dafeiyu-qq:FriendMessage:%' AND updated_at >= ? GROUP BY user_id",
                    (cutoff,),
                ).fetchall()
        except sqlite3.Error:
            return []
        result = []
        for (uid,) in rows:
            qq = str(uid).rsplit(':', 1)[-1]
            if qq and qq != '1000000001' and qq in friends and qq not in result:
                result.append(qq)
        return result

    def queue_private_notices(self, text):
        """Queue one exact notice for recent private friends.

        Args:
            text: Notice text to send.

        Returns:
            Number of newly queued recipients.
        """
        recipients = self.quota_reset_recipients()
        if not recipients:
            return 0
        outbox = DATA / 'dafeiyu_private_outbox.json'
        try:
            items = json.loads(outbox.read_text(encoding='utf-8')) if outbox.exists() else []
        except (OSError, ValueError):
            items = []
        if not isinstance(items, list):
            items = []
        queued = {
            (str(item.get('qq')), str(item.get('text')))
            for item in items if isinstance(item, dict)
        }
        added = 0
        for qq in recipients:
            key = (qq, text)
            if key in queued:
                continue
            items.append({'qq': qq, 'text': text})
            queued.add(key)
            added += 1
        if added:
            try:
                outbox.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')
            except OSError as exc:
                self.footer.config(text='通知队列写入失败：' + str(exc))
                return 0
        return added

    def queue_reset_notices(self):
        """Queue the quota-reset notice for recent private friends."""
        return self.queue_private_notices(RESET_NOTICE)

    def bot_online(self):
        """Return whether the AstrBot dashboard port is listening."""
        try:
            with socket.create_connection(('127.0.0.1', 6185), timeout=0.8):
                return True
        except OSError:
            return False

    def _launch_stop(self, script):
        self.footer.config(text='正在提炼记忆并备份，然后下线…（约 60–90 秒）')
        subprocess.Popen(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)], creationflags=HIDDEN)
        self.root.after(100000, self.refresh)

    def _wait_outbox_then_stop(self, script, deadline):
        outbox = DATA / 'dafeiyu_private_outbox.json'
        pending = False
        try:
            if outbox.exists():
                pending = bool(json.loads(outbox.read_text(encoding='utf-8')))
        except (OSError, ValueError):
            pending = outbox.exists()
        if not pending or time.time() >= deadline:
            self._launch_stop(script)
            return
        self.footer.config(text='正在通知最近聊过的好友，通知发完就下线…')
        self.root.after(1000, lambda: self._wait_outbox_then_stop(script, deadline))

    def reset_quota(self):
        state = DATA / 'dafeiyu_quota.json'
        try:
            current = json.loads(state.read_text(encoding='utf-8')) if state.exists() else {}
        except (OSError, ValueError):
            current = {}
        today = datetime.now().strftime('%Y-%m-%d')
        spent = [qq for qq, item in current.items() if isinstance(item, dict) and item.get('day') == today]
        if not messagebox.askyesno('重置私聊额度', '把所有好友今天的私聊条数清零？\n\n现在有 %d 位好友记着今天的用量。\n（主人不受限，群聊不受影响）' % len(spent)):
            return
        try:
            state.write_text('{}', encoding='utf-8')
        except OSError as exc:
            messagebox.showerror('重置失败', str(exc))
            return
        notified = self.queue_reset_notices()
        self.quota_hint.config(text='已重置 %d 位好友的今日额度（%s）；已排队通知 %d 位近12小时聊过的好友' % (
            len(spent), datetime.now().strftime('%H:%M'), notified))
        messagebox.showinfo('已重置', '所有好友的私聊额度已清零，下一条消息开始按 0 计数。\n\n被清掉的有 %d 位好友。\n近12小时聊过的 %d 位好友会收到重置通知。' % (len(spent), notified))
        self.root.after(600, self.refresh)

    def show_qr(self):
        source = (Path(__file__).resolve().parent.parent / 'runtime' / 'napcat-shell' / 'cache' / 'qrcode.png')
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
        subprocess.Popen(['notepad.exe',str(LOG)])


if __name__ == '__main__':
    StatusWindow().root.mainloop()
    def reset_quota(self):
        state = DATA / 'dafeiyu_quota.json'
        try:
            current = json.loads(state.read_text(encoding='utf-8')) if state.exists() else {}
        except (OSError, ValueError):
            current = {}
        today = datetime.now().strftime('%Y-%m-%d')
        spent = [qq for qq, item in current.items() if isinstance(item, dict) and item.get('day') == today]
        if not messagebox.askyesno('重置私聊额度', '把所有好友今天的私聊条数清零？\n\n现在有 %d 位好友记着今天的用量。\n（主人不受限，群聊不受影响）' % len(spent)):
            return
        try:
            state.write_text('{}', encoding='utf-8')
        except OSError as exc:
            messagebox.showerror('重置失败', str(exc))
            return
        notified = self.queue_reset_notices()
        self.quota_hint.config(text='已重置 %d 位好友的今日额度（%s）；已排队通知 %d 位近12小时聊过的好友' % (
            len(spent), datetime.now().strftime('%H:%M'), notified))
        messagebox.showinfo('已重置', '所有好友的私聊额度已清零，下一条消息开始按 0 计数。\n\n被清掉的有 %d 位好友。\n近12小时聊过的 %d 位好友会收到重置通知。' % (len(spent), notified))
        self.root.after(600, self.refresh)

    def show_qr(self):
        source = (Path(__file__).resolve().parent.parent / 'runtime' / 'napcat-shell' / 'cache' / 'qrcode.png')
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
        subprocess.Popen(['notepad.exe',str(LOG)])


if __name__ == '__main__':
    StatusWindow().root.mainloop()
