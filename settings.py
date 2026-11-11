"""Neto Meter settings dialog. Independent implementation; no DU Meter code used."""
import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".netometer")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

DEFAULTS = {
    "rate_units": "Bits per second (Kbps)",
    "multipliers": "Common (KB, MB, GB)",
    "month_start": 1, "week_start": "Sunday",
    "ip_mode": "No IP filtering",
    "ip_rules": "", "include_private": False,
    "adapters": {}, "wifi_mode": "All networks",
    "suspend_totals": False,
    "window_alpha": 80, "always_on_top": True, "click_through": False,
    "tab_content": "Graphical & numeric", "show_internet_lan_tabs": True,
    "average_seconds": 10, "show_per_app": False, "app_average_seconds": 15,
    "auto_show": False, "show_threshold": 125, "show_seconds": 5,
    "auto_hide": False, "hide_threshold": 125, "hide_seconds": 120,
    "start_windows": False,
    "graph_type": "Line graph (3-second average)",
    "graph_mode": "One graph, overlaid", "grid_lines": "Every 30 seconds",
    "max_label": "Show both line and label", "download_bandwidth": 0,
    "upload_bandwidth": 0, "custom_graph_colors": False,
    "download_color": "#e74c3c", "upload_color": "#a3b400",
    "font_name": "Segoe UI", "font_size": 10,
    "sound_enabled": False, "sound_bytes": 1, "sound_file": "",
    "short_alert_enabled": False, "short_direction": "More than",
    "short_traffic": "Sent & received", "short_amount": 1,
    "short_unit": "GB", "short_period": 1, "short_period_unit": "hours",
    "short_notify": True, "long_alert_enabled": False,
    "long_direction": "Incoming & outgoing", "long_period": "Current month",
    "long_amount": 600, "long_unit": "GB", "long_notify": True,
    "long_cost_enabled": False, "long_cost": 0.0,
    "email_enabled": False, "email_to": "", "email_from": "",
    "email_server": "", "email_port": 587, "email_user": "",
    "email_password": "", "transfer_cost_per_gb": 0.0,
    "currency": "USD"
}

def load_settings():
    data = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            data.update(saved)
    except (OSError, ValueError):
        pass
    return data

def save_settings(data):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, CONFIG_FILE)

class SettingsDialog:
    PAGES = [
        "General", "Data units and time periods", "Filter by IP address",
        "Filter by network adapters", "Reports and totals filter",
        "Traffic monitor window", "Start & stop automatically",
        "Traffic monitor graph", "Colors & sounds", "Link to dumeter.net",
        "Data transfer costs", "Short period alert", "Long period alert",
        "E-mail notifications", "Database management"
    ]
    def __init__(self, parent, adapters=None, on_save=None):
        self.parent, self.adapters, self.on_save = parent, adapters or [], on_save
        self.data = load_settings()
        self.vars = {}
        self.win = tk.Toplevel(parent)
        self.win.title("Neto Meter Options")
        self.win.geometry("850x570")
        self.win.minsize(760, 500)
        self.win.configure(bg="#252525")
        self.win.transient(parent)
        self._style()
        self._build()
        self.show_page("General")

    def _style(self):
        self.style = ttk.Style(self.win)
        try: self.style.theme_use("clam")
        except tk.TclError: pass
        self.style.configure("TFrame", background="#252525")
        self.style.configure("TLabel", background="#252525", foreground="#eeeeee")
        self.style.configure("TLabelframe", background="#252525", foreground="#eeeeee")
        self.style.configure("TLabelframe.Label", background="#252525", foreground="#eeeeee")
        self.style.configure("TCheckbutton", background="#252525", foreground="#eeeeee")
        self.style.configure("TRadiobutton", background="#252525", foreground="#eeeeee")
        self.style.configure("TButton", padding=5)
        self.style.configure("TCombobox", fieldbackground="#333333", background="#333333", foreground="#eeeeee")

    def _build(self):
        base = ttk.Frame(self.win); base.pack(fill="both", expand=True, padx=10, pady=10)
        ttk.Label(base, text="Category").pack(anchor="w")
        body = ttk.Frame(base); body.pack(fill="both", expand=True, pady=5)
        self.nav = tk.Listbox(body, width=27, bg="#202020", fg="#eeeeee",
                              selectbackground="#0878c9", relief="flat",
                              highlightthickness=1, highlightbackground="#555555")
        self.nav.pack(side="left", fill="y")
        for item in self.PAGES: self.nav.insert("end", item)
        self.nav.bind("<<ListboxSelect>>", self._nav)
        self.panel = ttk.Frame(body); self.panel.pack(side="left", fill="both", expand=True, padx=(10,0))
        self.panel.columnconfigure(0, weight=1)
        foot = ttk.Frame(base); foot.pack(fill="x", pady=(8,0))
        ttk.Button(foot, text="OK", command=self.apply_close).pack(side="right", padx=3)
        ttk.Button(foot, text="Apply", command=self.apply).pack(side="right", padx=3)
        ttk.Button(foot, text="Cancel", command=self.win.destroy).pack(side="right", padx=3)
        ttk.Button(foot, text="Help", command=self.help).pack(side="right", padx=3)

    def _nav(self, _event=None):
        sel = self.nav.curselection()
        if sel: self.show_page(self.PAGES[sel[0]])

    def _var(self, key):
        if key not in self.vars:
            value = self.data.get(key, DEFAULTS.get(key, ""))
            if isinstance(value, bool): self.vars[key] = tk.BooleanVar(value=value)
            else: self.vars[key] = tk.StringVar(value=str(value))
        return self.vars[key]

    def _row(self, parent, label, key, choices=None, kind="entry", width=34):
        row = ttk.Frame(parent); row.pack(fill="x", pady=4)
        ttk.Label(row, text=label, width=35).pack(side="left", anchor="w")
        var = self._var(key)
        if kind == "check":
            w = ttk.Checkbutton(row, variable=var); w.pack(side="left", anchor="w")
        elif choices:
            w = ttk.Combobox(row, textvariable=var, values=choices, state="readonly", width=width)
            w.pack(side="left", fill="x", expand=True)
        else:
            w = ttk.Entry(row, textvariable=var, width=width, show="*" if "password" in key else "")
            w.pack(side="left", fill="x", expand=True)
        return w

    def _check(self, parent, label, key):
        ttk.Checkbutton(parent, text=label, variable=self._var(key)).pack(anchor="w", pady=3)

    def _section(self, parent, title):
        box = ttk.LabelFrame(parent, text=title); box.pack(fill="x", pady=6, padx=3)
        return box

    def show_page(self, page):
        for child in self.panel.winfo_children(): child.destroy()
        ttk.Label(self.panel, text=page, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0,8))
        p = self.panel
        if page == "General":
            b = self._section(p, "Totals balloon display")
            self._check(b, "Show totals in tray icon", "tray_totals")
            self._check(b, "Show totals in monitor window", "window_totals")
            self._check(b, "Show totals in taskbar band", "taskbar_totals")
            self._row(b, "Show totals balloon after (milliseconds)", "balloon_ms")
            b = self._section(p, "User interface")
            self._row(b, "Language", "language", ["English"])
        elif page == "Data units and time periods":
            b = self._section(p, "Data units")
            self._row(b, "Data transfer rate units", "rate_units", ["Bytes per second (kB/sec)", "Bits per second (Kbps)", "Bytes per hour", "Bits per hour"])
            self._row(b, "Abbreviation of multipliers", "multipliers", ["Common (KB, MB, GB)", "Binary (KiB, MiB, GiB)", "Long names"])
            b = self._section(p, "Weekly and monthly periods")
            self._row(b, "Each month starts on day", "month_start")
            self._row(b, "Each week starts on", "week_start", ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"])
        elif page == "Filter by IP address":
            b = self._section(p, "Separate traffic based on remote IP address")
            for label, value in [("Separate Internet and LAN; account Internet traffic","Internet only"),("Separate Internet and LAN; account LAN traffic","LAN only"),("Custom IP filtering rules (advanced)","Custom rules"),("Do not filter by IP address","No IP filtering")]:
                ttk.Radiobutton(b, text=label, value=value, variable=self._var("ip_mode")).pack(anchor="w", pady=3)
            b = self._section(p, "Custom IP address filtering rules")
            self._row(b, "Rules (one IP/CIDR per line)", "ip_rules")
            self._check(b, "Also match link-local, broadcast and private IP addresses", "include_private")
        elif page == "Filter by network adapters":
            b = self._section(p, "Network adapters")
            ttk.Label(b, text="Select the adapters whose traffic should be counted:").pack(anchor="w")
            saved = self.data.get("adapters", {})
            for name in self.adapters:
                key = "adapter:" + name
                self.vars[key] = tk.BooleanVar(value=saved.get(name, True))
                ttk.Checkbutton(b, text=name, variable=self.vars[key]).pack(anchor="w")
        elif page == "Reports and totals filter":
            b = self._section(p, "Update reports and totals only on some Wi-Fi networks")
            self._row(b, "Wi-Fi network rule", "wifi_mode", ["All networks","Only selected networks","Except selected networks"])
            self._row(b, "Wi-Fi network names (comma separated)", "wifi_names")
            self._check(p, "Suspend updating reports and totals (traffic is still displayed, not logged)", "suspend_totals")
        elif page == "Traffic monitor window":
            b = self._section(p, "Window properties")
            self._row(b, "Border style", "border_style", ["Minimal (thin border)","Standard","No border"])
            self._row(b, "Window translucency (%)", "window_alpha", ["0","10","20","30","40","50","60","70","80","90","100"])
            self._check(b, "Always on top", "always_on_top")
            self._check(b, "Click through window", "click_through")
            b = self._section(p, "Network traffic tabs")
            self._row(b, "Traffic monitor tab contents", "tab_content", ["Graphical & numeric","Graph only","Numeric only"])
            self._check(b, "Show tabs for Internet and LAN network traffic", "show_internet_lan_tabs")
            self._row(b, "Traffic average of the last (seconds)", "average_seconds")
            b = self._section(p, "Per-application traffic tab")
            self._check(b, "Display per-application network usage", "show_per_app")
            self._row(b, "Display average of the last (seconds)", "app_average_seconds")
        elif page == "Start & stop automatically":
            b = self._section(p, "Auto show/hide thresholds")
            self._check(b, "Auto-show monitor when average rate is above", "auto_show")
            self._row(b, "Show threshold (bytes/sec)", "show_threshold")
            self._row(b, "For (seconds)", "show_seconds")
            self._check(b, "Auto-hide if average rate is below", "auto_hide")
            self._row(b, "Hide threshold (bytes/sec)", "hide_threshold")
            self._row(b, "For (seconds)", "hide_seconds")
            self._check(p, "Start Neto Meter monitor automatically with Windows", "start_windows")
        elif page == "Traffic monitor graph":
            b = self._section(p, "Graph appearance")
            self._row(b, "Graph type", "graph_type", ["Line graph (3-second average)","Area graph","Bar graph"])
            self._row(b, "Graph mode", "graph_mode", ["One graph, overlaid","Separate download and upload graphs"])
            b = self._section(p, "Grid and labels")
            self._row(b, "Vertical grid lines", "grid_lines", ["None","Every 10 seconds","Every 30 seconds","Every 60 seconds"])
            self._row(b, "Maximum graph value", "max_label", ["Show both line and label","Show line only","Show label only"])
            b = self._section(p, "Graph scale")
            self._row(b, "Available download bandwidth (bps)", "download_bandwidth")
            self._row(b, "Available upload bandwidth (bps)", "upload_bandwidth")
        elif page == "Colors & sounds":
            b = self._section(p, "Colors and fonts")
            self._check(b, "Use custom graph colors", "custom_graph_colors")
            self._row(b, "Download color (hex)", "download_color")
            self._row(b, "Upload color (hex)", "upload_color")
            self._row(b, "Font name", "font_name")
            self._row(b, "Font size", "font_size")
            b = self._section(p, "Audible network traffic monitoring")
            self._check(b, "Play a sound each time data is transferred", "sound_enabled")
            self._row(b, "Sound every (bytes)", "sound_bytes")
            self._row(b, "Sound file", "sound_file")
        elif page == "Link to dumeter.net":
            ttk.Label(p, text="Neto Meter is an independent project and does not connect to DU Meter services.").pack(anchor="w", pady=8)
        elif page == "Data transfer costs":
            b = self._section(p, "Transfer cost calculation")
            self._row(b, "Cost per GB", "transfer_cost_per_gb")
            self._row(b, "Currency", "currency", ["USD","EUR","EGP","GBP"])
        elif page == "Short period alert":
            ttk.Label(p, text="Sliding time-window traffic alert").pack(anchor="w")
            b = self._section(p, "Alert rule")
            self._check(b, "Alert me when enabled", "short_alert_enabled")
            self._row(b, "Condition", "short_direction", ["More than","Less than"])
            self._row(b, "Traffic direction", "short_traffic", ["Sent & received","Incoming","Outgoing"])
            self._row(b, "Traffic amount", "short_amount")
            self._row(b, "Amount unit", "short_unit", ["MB","GB","TB"])
            self._row(b, "Time window", "short_period")
            self._row(b, "Time unit", "short_period_unit", ["seconds","minutes","hours","days"])
            self._check(b, "Display a notification message", "short_notify")
        elif page == "Long period alert":
            b = self._section(p, "Long period traffic limit")
            self._check(b, "Enable alert based on traffic volume", "long_alert_enabled")
            self._row(b, "Traffic direction", "long_direction", ["Incoming & outgoing","Incoming only","Outgoing only"])
            self._row(b, "Period", "long_period", ["Current day","Current week","Current month","Current year"])
            self._row(b, "Traffic limit", "long_amount")
            self._row(b, "Unit", "long_unit", ["MB","GB","TB"])
            self._check(b, "Enable alert based on traffic cost", "long_cost_enabled")
            self._row(b, "Cost limit", "long_cost")
            self._check(b, "Display notification message", "long_notify")
        elif page == "E-mail notifications":
            b = self._section(p, "SMTP settings")
            self._check(b, "Enable e-mail notifications", "email_enabled")
            for label,key in [("To address","email_to"),("From address","email_from"),("SMTP server","email_server"),("SMTP port","email_port"),("Username","email_user"),("Password","email_password")]:
                self._row(b,label,key)
            ttk.Label(p, text="Email credentials are stored locally in your user settings file.").pack(anchor="w")
        elif page == "Database management":
            b = self._section(p, "Backup & restore")
            ttk.Button(b, text="Backup data", command=self.backup).pack(side="left", padx=5, pady=8)
            ttk.Button(b, text="Restore data", command=self.restore).pack(side="left", padx=5, pady=8)
            self._check(b, "Clear all data before restoring", "clear_before_restore")
            b = self._section(p, "Delete data")
            ttk.Label(b, text="Delete historic traffic data from the selected date range.").pack(anchor="w")
            self._row(b, "From date (YYYY-MM-DD)", "delete_from")
            self._row(b, "To date (YYYY-MM-DD)", "delete_to")
            ttk.Button(b, text="Delete selected data", command=self.delete_range).pack(anchor="w", pady=5)

    def collect(self):
        data = dict(self.data)
        for key,var in self.vars.items():
            if key.startswith("adapter:"): continue
            value = var.get()
            if key in {"month_start","window_alpha","average_seconds","app_average_seconds","show_threshold","show_seconds","hide_threshold","hide_seconds","download_bandwidth","upload_bandwidth","font_size","sound_bytes","short_amount","short_period","long_amount","email_port"}:
                try: value = int(value)
                except (TypeError,ValueError): value = 0
            if key in {"transfer_cost_per_gb","long_cost"}:
                try: value = float(value)
                except (TypeError,ValueError): value = 0.0
            data[key] = value
        data["adapters"] = {name: bool(self.vars.get("adapter:"+name, tk.BooleanVar(value=True)).get()) for name in self.adapters}
        return data

    def apply(self):
        try:
            self.data = self.collect()
            save_settings(self.data)
            if self.on_save: self.on_save(self.data)
        except Exception as exc:
            messagebox.showerror("Neto Meter", str(exc), parent=self.win)

    def apply_close(self):
        self.apply()
        self.win.destroy()

    def backup(self):
        path = filedialog.asksaveasfilename(parent=self.win, defaultextension=".json", filetypes=[("JSON backup","*.json")])
        if not path: return
        try:
            with open(path,"w",encoding="utf-8") as f: json.dump({"settings":self.collect()},f,indent=2)
            messagebox.showinfo("Backup","Settings backup created.",parent=self.win)
        except Exception as exc: messagebox.showerror("Backup",str(exc),parent=self.win)

    def restore(self):
        path = filedialog.askopenfilename(parent=self.win,filetypes=[("JSON backup","*.json")])
        if not path: return
        try:
            with open(path,"r",encoding="utf-8") as f: raw=json.load(f)
            restored=raw.get("settings",raw)
            if not isinstance(restored,dict): raise ValueError("Invalid backup")
            self.data.update(restored)
            self.vars.clear()
            self.show_page(self.PAGES[self.nav.curselection()[0]] if self.nav.curselection() else "General")
            messagebox.showinfo("Restore","Settings restored in the dialog. Press Apply to save.",parent=self.win)
        except Exception as exc: messagebox.showerror("Restore",str(exc),parent=self.win)

    def delete_range(self):
        messagebox.showinfo("Database management","Date-range deletion will be connected to the traffic history database in the next data-engine update.",parent=self.win)

    def help(self):
        messagebox.showinfo("Neto Meter Options","Settings are saved locally on this PC. Features requiring Windows-level network drivers or native Explorer integration are not represented as completed until implemented and tested.",parent=self.win)
