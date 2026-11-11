#!/usr/bin/env python3
"""
Neto Meter - a DU Meter style network traffic monitor.

Features
  * Live download / upload speed
  * Real-time graph (last 60 seconds)
  * Usage totals: Session / Today / This month / All time (saved between runs)
  * Daily history window
  * Choose a network adapter (or all of them)
  * Bytes/s or Bits/s units
  * Always-on-top option and a small floating "mini" mode

Requirements:  Python 3.8+  and  psutil   (pip install psutil)
Run:           python netometer.py
Console mode:  python netometer.py --console
"""

import datetime as dt
import json
import math
import os
import sys
import time
from collections import deque

import psutil

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    tk = None
    ttk = None

APP_NAME = "Neto Meter"
DATA_DIR = os.path.join(os.path.expanduser("~"), ".netometer")
DATA_FILE = os.path.join(DATA_DIR, "usage.json")
HISTORY_SECONDS = 60
INTERVAL_MS = 1000
SAVE_EVERY = 10
ALL_ADAPTERS = "All adapters"
BG = "#0f1419"
PANEL = "#171d26"
FG = "#e6edf3"
MUTED = "#8b97a5"
DOWN = "#2ecc71"
UP = "#ff9f43"
GRID = "#263040"


def fmt_bytes(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} TB"


def fmt_speed(bytes_per_sec, bits=False):
    if bits:
        v = bytes_per_sec * 8.0
        for unit in ("bps", "Kbps", "Mbps"):
            if v < 1000:
                return f"{v:.0f} {unit}" if unit == "bps" else f"{v:.1f} {unit}"
            v /= 1000
        return f"{v:.2f} Gbps"
    v = float(bytes_per_sec)
    for unit in ("B/s", "KB/s"):
        if v < 1024:
            return f"{v:.0f} {unit}" if unit == "B/s" else f"{v:.1f} {unit}"
        v /= 1024
    if v < 1024:
        return f"{v:.2f} MB/s"
    return f"{v / 1024:.2f} GB/s"


def nice_ceiling(v):
    if v <= 0:
        return 1
    mag = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 5, 10):
        if v <= m * mag:
            return m * mag
    return 10 * mag


class UsageStore:
    def __init__(self, path=DATA_FILE):
        self.path = path
        self.days = {}
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.days = {k: [int(v[0]), int(v[1])] for k, v in raw.items()}
        except (OSError, ValueError, TypeError, IndexError):
            self.days = {}

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.days, f)
            os.replace(tmp, self.path)
        except OSError:
            pass

    @staticmethod
    def today_key():
        return dt.date.today().isoformat()

    def add(self, down, up):
        d = self.days.setdefault(self.today_key(), [0, 0])
        d[0] += int(down)
        d[1] += int(up)

    def today(self):
        return tuple(self.days.get(self.today_key(), [0, 0]))

    def month(self):
        prefix = self.today_key()[:7]
        d = u = 0
        for k, v in self.days.items():
            if k.startswith(prefix):
                d += v[0]
                u += v[1]
        return d, u

    def total(self):
        return sum(v[0] for v in self.days.values()), sum(v[1] for v in self.days.values())

    def recent_days(self, n=60):
        keys = sorted(self.days.keys(), reverse=True)[:n]
        return [(k, self.days[k][0], self.days[k][1]) for k in keys]


def _is_loopback(name):
    low = name.lower()
    return low == "lo" or low.startswith("lo0") or "loopback" in low


class NetSampler:
    def __init__(self):
        self.iface = None
        self.last = self._read()
        self.last_t = time.time()

    @staticmethod
    def _read():
        out = {}
        try:
            for name, c in psutil.net_io_counters(pernic=True).items():
                if not _is_loopback(name):
                    out[name] = (c.bytes_recv, c.bytes_sent)
        except Exception:
            pass
        return out

    def interfaces(self):
        return sorted(self._read().keys())

    def sample(self):
        now = time.time()
        cur = self._read()
        elapsed = max(now - self.last_t, 0.001)
        d_down = d_up = 0
        for name, (rx, tx) in cur.items():
            if self.iface and name != self.iface:
                continue
            if name not in self.last:
                continue
            prx, ptx = self.last[name]
            d_down += rx - prx if rx >= prx else rx
            d_up += tx - ptx if tx >= ptx else tx
        self.last = cur
        self.last_t = now
        return d_down / elapsed, d_up / elapsed, d_down, d_up


class NetoMeterApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.configure(bg=BG)
        self.root.geometry("620x560")
        self.root.minsize(520, 480)
        self.store = UsageStore()
        self.sampler = NetSampler()
        self.down_hist = deque([0.0] * HISTORY_SECONDS, maxlen=HISTORY_SECONDS)
        self.up_hist = deque([0.0] * HISTORY_SECONDS, maxlen=HISTORY_SECONDS)
        self.session_down = self.session_up = 0
        self.peak_down = self.peak_up = 0.0
        self.ticks = 0
        self.mini_mode = False
        self.normal_geometry = None
        self._drag = (0, 0)
        self.units_var = tk.StringVar(value="Bytes/s")
        self.iface_var = tk.StringVar(value=ALL_ADAPTERS)
        self.top_var = tk.BooleanVar(value=False)
        self._style()
        self._build_main()
        self._build_mini()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.after(INTERVAL_MS, self.tick)

    def _style(self):
        s = ttk.Style(self.root)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure("TCombobox", fieldbackground=PANEL, background=PANEL, foreground=FG,
                    arrowcolor=FG, bordercolor=GRID)
        s.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", FG)])
        s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG,
                    rowheight=24, borderwidth=0)
        s.configure("Treeview.Heading", background=GRID, foreground=FG, relief="flat")
        s.map("Treeview", background=[("selected", "#2a3a52")])
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)

    def _button(self, parent, text, cmd):
        return tk.Button(parent, text=text, command=cmd, bg=GRID, fg=FG,
                         activebackground="#33425a", activeforeground=FG,
                         relief="flat", padx=12, pady=4, bd=0, cursor="hand2")

    def _build_main(self):
        self.main = tk.Frame(self.root, bg=BG)
        self.main.pack(fill="both", expand=True, padx=14, pady=12)
        head = tk.Frame(self.main, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text="NETO METER", bg=BG, fg=FG,
                 font=("Segoe UI", 16, "bold")).pack(side="left")
        btns = tk.Frame(head, bg=BG)
        btns.pack(side="right")
        self._button(btns, "Mini", self.enter_mini).pack(side="left", padx=3)
        self._button(btns, "History", self.show_history).pack(side="left", padx=3)
        self._button(btns, "Reset session", self.reset_session).pack(side="left", padx=3)
        row = tk.Frame(self.main, bg=BG)
        row.pack(fill="x", pady=(12, 8))
        self.down_lbl, self.down_peak = self._speed_panel(row, "DOWNLOAD", DOWN, "left")
        self.up_lbl, self.up_peak = self._speed_panel(row, "UPLOAD", UP, "right")
        self.canvas = tk.Canvas(self.main, bg=PANEL, highlightthickness=0, height=190)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.draw_graph())
        table = tk.Frame(self.main, bg=PANEL)
        table.pack(fill="x", pady=(8, 0))
        for c, h in enumerate(("", "Download", "Upload", "Total")):
            tk.Label(table, text=h, bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold"),
                     anchor="e" if c else "w", width=14 if c else 12).grid(
                         row=0, column=c, padx=6, pady=(6, 2), sticky="ew")
        self.stat_labels = {}
        for r, name in enumerate(("Session", "Today", "This month", "All time"), start=1):
            tk.Label(table, text=name, bg=PANEL, fg=FG, anchor="w",
                     font=("Segoe UI", 10)).grid(row=r, column=0, padx=6, pady=2, sticky="w")
            labels = []
            for c, color in enumerate((DOWN, UP, FG), start=1):
                lb = tk.Label(table, text="0 B", bg=PANEL, fg=color, anchor="e",
                              font=("Consolas", 10))
                lb.grid(row=r, column=c, padx=6, pady=2, sticky="e")
                labels.append(lb)
            self.stat_labels[name] = labels
        for c in range(4):
            table.grid_columnconfigure(c, weight=1)
        tk.Frame(table, bg=PANEL, height=4).grid(row=5, column=0)
        opts = tk.Frame(self.main, bg=BG)
        opts.pack(fill="x", pady=(10, 0))
        tk.Label(opts, text="Adapter", bg=BG, fg=MUTED).pack(side="left")
        self.iface_box = ttk.Combobox(opts, textvariable=self.iface_var, state="readonly",
                                      width=22, values=[ALL_ADAPTERS] + self.sampler.interfaces())
        self.iface_box.pack(side="left", padx=(6, 14))
        self.iface_box.bind("<<ComboboxSelected>>", self.on_iface)
        self.iface_box.bind("<Button-1>", self.refresh_ifaces)
        tk.Label(opts, text="Units", bg=BG, fg=MUTED).pack(side="left")
        units = ttk.Combobox(opts, textvariable=self.units_var, state="readonly",
                             width=8, values=["Bytes/s", "Bits/s"])
        units.pack(side="left", padx=(6, 14))
        units.bind("<<ComboboxSelected>>", lambda e: self.refresh_view())
        tk.Checkbutton(opts, text="Always on top", variable=self.top_var, command=self.on_top,
                       bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG,
                       activeforeground=FG, highlightthickness=0).pack(side="left")

    def _speed_panel(self, parent, title, color, side):
        f = tk.Frame(parent, bg=PANEL)
        f.pack(side=side, fill="x", expand=True, padx=(0, 6) if side == "left" else (6, 0))
        tk.Label(f, text=title, bg=PANEL, fg=color,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        big = tk.Label(f, text="0 B/s", bg=PANEL, fg=FG, font=("Segoe UI", 22, "bold"))
        big.pack(anchor="w", padx=12)
        peak = tk.Label(f, text="Peak: 0 B/s", bg=PANEL, fg=MUTED, font=("Segoe UI", 9))
        peak.pack(anchor="w", padx=12, pady=(0, 8))
        return big, peak

    def _build_mini(self):
        self.mini = tk.Frame(self.root, bg=PANEL)
        self.mini_lbl = tk.Label(self.mini, text="", bg=PANEL, fg=FG,
                                 font=("Consolas", 11, "bold"), padx=10, pady=6)
        self.mini_lbl.pack()
        for w in (self.mini, self.mini_lbl):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)
            w.bind("<Double-Button-1>", lambda e: self.exit_mini())

    def _drag_start(self, e):
        self._drag = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())

    def _drag_move(self, e):
        self.root.geometry(f"+{e.x_root - self._drag[0]}+{e.y_root - self._drag[1]}")

    def enter_mini(self):
        self.normal_geometry = self.root.geometry()
        self.mini_mode = True
        self.root.withdraw()
        self.main.pack_forget()
        self.mini.pack(fill="both", expand=True)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.86)
        self.refresh_view()
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"+{sw - self.root.winfo_reqwidth() - 8}+{sh - self.root.winfo_reqheight() - 64}")
        self.root.deiconify()

    def exit_mini(self):
        self.mini_mode = False
        self.root.withdraw()
        self.mini.pack_forget()
        self.root.overrideredirect(False)
        self.root.attributes("-alpha", 1.0)
        self.main.pack(fill="both", expand=True, padx=14, pady=12)
        self.root.attributes("-topmost", self.top_var.get())
        if self.normal_geometry:
            self.root.geometry(self.normal_geometry)
        self.root.deiconify()

    @property
    def bits(self):
        return self.units_var.get() == "Bits/s"

    def on_top(self):
        self.root.attributes("-topmost", self.top_var.get())

    def refresh_ifaces(self, _event=None):
        self.iface_box["values"] = [ALL_ADAPTERS] + self.sampler.interfaces()

    def on_iface(self, _event=None):
        name = self.iface_var.get()
        self.sampler.iface = None if name == ALL_ADAPTERS else name
        self.reset_session()

    def reset_session(self):
        self.session_down = self.session_up = 0
        self.peak_down = self.peak_up = 0.0
        self.refresh_view()

    def show_history(self):
        win = tk.Toplevel(self.root)
        win.title(f"{APP_NAME} - History")
        win.configure(bg=BG)
        win.geometry("460x420")
        cols = ("date", "down", "up", "total")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c, t, w in (("date", "Date", 110), ("down", "Download", 110),
                        ("up", "Upload", 110), ("total", "Total", 110)):
            tree.heading(c, text=t)
            tree.column(c, width=w, anchor="e" if c != "date" else "w")
        for day, d, u in self.store.recent_days(60):
            tree.insert("", "end", values=(day, fmt_bytes(d), fmt_bytes(u), fmt_bytes(d + u)))
        tree.pack(fill="both", expand=True, padx=10, pady=10)

    def quit(self):
        self.store.save()
        self.root.destroy()

    def tick(self):
        down, up, d_down, d_up = self.sampler.sample()
        self.session_down += d_down
        self.session_up += d_up
        self.store.add(d_down, d_up)
        self.peak_down = max(self.peak_down, down)
        self.peak_up = max(self.peak_up, up)
        self.down_hist.append(down)
        self.up_hist.append(up)
        self.ticks += 1
        if self.ticks % SAVE_EVERY == 0:
            self.store.save()
        self.refresh_view()
        self.root.after(INTERVAL_MS, self.tick)

    def refresh_view(self):
        down = self.down_hist[-1]
        up = self.up_hist[-1]
        if self.mini_mode:
            self.mini_lbl.config(text=f"↓ {fmt_speed(down, self.bits)}   ↑ {fmt_speed(up, self.bits)}")
            return
        self.down_lbl.config(text=fmt_speed(down, self.bits))
        self.up_lbl.config(text=fmt_speed(up, self.bits))
        self.down_peak.config(text=f"Peak: {fmt_speed(self.peak_down, self.bits)}")
        self.up_peak.config(text=f"Peak: {fmt_speed(self.peak_up, self.bits)}")
        rows = {
            "Session": (self.session_down, self.session_up),
            "Today": self.store.today(),
            "This month": self.store.month(),
            "All time": self.store.total(),
        }
        for name, (d, u) in rows.items():
            a, b, c = self.stat_labels[name]
            a.config(text=fmt_bytes(d))
            b.config(text=fmt_bytes(u))
            c.config(text=fmt_bytes(d + u))
        self.draw_graph()

    def draw_graph(self):
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 120 or h < 80:
            return
        pl, pr, pt, pb = 78, 12, 12, 22
        gw, gh = w - pl - pr, h - pt - pb
        peak = max(max(self.down_hist), max(self.up_hist), 10 * 1024)
        top = nice_ceiling(peak)
        for i in range(5):
            y = pt + gh * i / 4
            c.create_line(pl, y, w - pr, y, fill=GRID)
            c.create_text(pl - 8, y, text=fmt_speed(top * (1 - i / 4), self.bits),
                          anchor="e", fill=MUTED, font=("Segoe UI", 8))
        c.create_text(pl, h - 8, text=f"{HISTORY_SECONDS}s ago", anchor="w",
                      fill=MUTED, font=("Segoe UI", 8))
        c.create_text(w - pr, h - 8, text="now", anchor="e", fill=MUTED, font=("Segoe UI", 8))
        def points(hist):
            pts = []
            for i, v in enumerate(hist):
                x = pl + gw * i / (HISTORY_SECONDS - 1)
                y = pt + gh * (1 - min(v, top) / top)
                pts += [x, y]
            return pts
        c.create_line(*points(self.up_hist), fill=UP, width=2, smooth=True)
        c.create_line(*points(self.down_hist), fill=DOWN, width=2, smooth=True)

    def run(self):
        self.root.mainloop()


def run_console():
    sampler = NetSampler()
    store = UsageStore()
    print(f"{APP_NAME} - console mode (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(1)
            down, up, dd, du = sampler.sample()
            store.add(dd, du)
            td, tu = store.today()
            print(f"\rDown {fmt_speed(down):>12}  Up {fmt_speed(up):>12}  "
                  f"Today: {fmt_bytes(td)} / {fmt_bytes(tu)}   ", end="", flush=True)
    except KeyboardInterrupt:
        store.save()
        print("\nSaved.")


def main():
    if "--console" in sys.argv or tk is None:
        run_console()
        return
    NetoMeterApp().run()


if __name__ == "__main__":
    main()
