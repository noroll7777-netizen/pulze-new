import tkinter as tk
from tkinter import font as tkfont
import subprocess
import os
import json
import threading
import queue
import time
import math
import re
import winreg
import sys
import datetime
import ctypes
import requests
import hashlib
import zipfile
import shutil
import tempfile
import random
import sys
import os

# Add Common directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../Common'))
from keyauth import KeyAuthAPI # Импорт из внешнего файла
from tweaker import TweakerEngine # Импорт твикера (RESERVE/OFFLINE FALLBACK)

# Добавляем psutil и wmi
try:
    import psutil
except ImportError:
    psutil = None

try:
    import wmi
except ImportError:
    wmi = None

# ==========================================
# 🔗 КОНФИГ KEYAUTH
# ==========================================
KEYAUTH_NAME = "PULZE OS"
KEYAUTH_OWNERID = "l3xzAwuCp8"
KEYAUTH_SECRET = "6ef4a4f1b43cc624fef08ba5b958a8c82c46c66cb4dd04cd290d0a99f20508a0"
KEYAUTH_VERSION = "1.0"

def get_checksum():
    try:
        md5 = hashlib.md5()
        with open(sys.argv[0], 'rb') as f: md5.update(f.read())
        return md5.hexdigest()
    except: return None

keyauthapp = None
try:
    keyauthapp = KeyAuthAPI(KEYAUTH_NAME, KEYAUTH_OWNERID, KEYAUTH_SECRET, KEYAUTH_VERSION, get_checksum())
except: pass

# ==========================================
# 🔗 ТВИКЕР
# ==========================================
# TweakerEngine уже импортирован сверху

# === ЦВЕТА ===
COLOR_BG = "#000000"        
COLOR_TEXT = "#cccccc"      
COLOR_ACCENT = "#00ffff"    
COLOR_ERROR = "#ff3333"     
COLOR_SUCCESS = "#00ff00"   
COLOR_WARN = "#ffcc00"      
COLOR_INPUT = "#ffffff"     
COLOR_DIM = "#555555"       

# === ПУТИ ===
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "launcher_config.json")
INSTALLER_SCRIPT = os.path.join(BASE_DIR, "Install_Apps.ps1")
QRES_PATH = os.path.join(BASE_DIR, r"Tools\QRes.exe")
KEY_FILE_PATH = os.path.join(BASE_DIR, "license.key")

DEFAULT_CONFIG = {
    "FirstRun": True,
    "GlobalHz": 60,
    "CurrentW": 1920, "CurrentH": 1080,
    "LastW": 1920, "LastH": 1080,
    "Crosshair": {"Enabled": False, "Type": "dot", "Size": 4, "Hotkey": "x", "Color": "#ff0000"},
    "Paths": {
        "Rust": r"C:\Program Files (x86)\Steam\steamapps\common\Rust\RustClient.exe",
        "Steam": r"C:\Program Files (x86)\Steam\steam.exe",
        "Ripcord": r"C:\PULZE\Apps\Ripcord\Ripcord.exe",
        "Discord": os.path.expandvars(r"%USERPROFILE%\AppData\Local\Discord\Update.exe"),
        "Thorium": r"C:\PULZE\Apps\Thorium\BIN\thorium.exe",
        "OBS": r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
        "FileMan": r"C:\PULZE\Tools\explorerpp_x64\Explorer++.exe"
    }
}

# ==========================================
# 🎯 КЛАСС ПРИЦЕЛА
# ==========================================
class Crosshair(tk.Toplevel):
    def __init__(self, parent, size=4, style="dot", color="red"):
        super().__init__(parent)
        self.overrideredirect(True) 
        self.attributes("-topmost", True) 
        self.attributes("-transparentcolor", "black") 
        self.config(bg="black")
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w // 2) - (size // 2)
        y = (screen_h // 2) - (size // 2)
        if style == "dot":
            self.geometry(f"{size}x{size}+{x}+{y}")
            tk.Frame(self, bg=color, width=size, height=size).pack()
        elif style == "plus":
            thickness = max(1, size // 3)
            full_size = size * 2
            c_off = (screen_w // 2) - (full_size // 2)
            c_y = (screen_h // 2) - (full_size // 2)
            self.geometry(f"{full_size}x{full_size}+{c_off}+{c_y}")
            v_line = tk.Frame(self, bg=color, width=thickness, height=full_size)
            v_line.place(x=(full_size//2) - (thickness//2), y=0)
            h_line = tk.Frame(self, bg=color, width=full_size, height=thickness)
            h_line.place(x=0, y=(full_size//2) - (thickness//2))

# ==========================================
# ГЛАВНЫЙ ИНТЕРФЕЙС
# ==========================================
class PulseConsole:
    def __init__(self, root):
        self.root = root
        self.root.title("PULZE - LOCKED")
        self.root.configure(bg=COLOR_BG)
        self.root.attributes("-fullscreen", True)
        
        # === PERFORMANCE: TIMER RESOLUTION (0.5ms) ===
        # Decreases Input Lag globally
        try:
            ctypes.windll.ntdll.NtSetTimerResolution(5000, 1, ctypes.byref(ctypes.c_ulong()))
        except: pass

        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        self.root.bind("<Alt-F4>", lambda e: "break")
        self.root.bind("<F12>", lambda e: self.root.destroy())
        self.root.bind("<Control-Alt-F12>", self.open_dev_tools) # Backdoor
        self.root.bind("<Control-x>", self.clean_ram) # RAM Cleaner
        self.root.bind("<Button-1>", lambda e: self.root.focus_force())

        self.font_main = tkfont.Font(family="Consolas", size=14)
        self.font_big = tkfont.Font(family="Consolas", size=20, weight="bold") 
        self.font_clock = tkfont.Font(family="Consolas", size=16) 
        
        self.root.focus_force()
        self.config = self.load_config()
        
        # VARS
        self.is_first_run = self.config.get("FirstRun", True)
        self.is_logged_in = False
        self.current_input = ""
        self.menu_state = "login"
        self.cursor_visible = True
        self.status_map = {} 
        self.msg_queue = queue.Queue()
        self.installing = False
        self.wifi_list = []
        self.selected_ssid = ""
        self.crosshair_win = None
        # INITIALIZE WITH CORRECT KEYS TO AVOID "N/A" at start
        self.sys_info = {"cpu_name": "Scanning...", "gpu": "Scanning...", "ram_total": "...", "hz": str(self.config.get("GlobalHz", 60)), "ram_speed": ""}
        self.net_status = "..."
        self.clock_var = tk.StringVar()
        self.net_var = tk.StringVar()
        self.security_active = True
        
        # Global Hotkey Config
        self.hotkey_vk = self.char_to_vk(self.config["Crosshair"].get("Hotkey", "x"))

        # UI Layout - REMOVED TOP BAR
        
        self.text_area = tk.Text(root, bg=COLOR_BG, fg=COLOR_TEXT, font=self.font_main, 
                                 bd=0, highlightthickness=0, state="disabled", cursor="none",
                                 padx=20, pady=20)
        self.text_area.pack(side="top", fill="both", expand=True)
        
        self.bottom_container = tk.Frame(root, bg=COLOR_BG, height=60)
        self.bottom_container.pack(side="bottom", fill="x", pady=30)
        
        self.input_frame = tk.Frame(self.bottom_container, bg=COLOR_BG)
        self.input_frame.pack(anchor="center")
        
        # Лейблы создаем сразу, но они могут пересоздаваться
        self.lbl_prompt = None
        self.lbl_input = None
        self.create_input_labels()

        # Tags
        self.text_area.tag_configure("center", justify='center')
        for t, c in [("accent", COLOR_ACCENT), ("err", COLOR_ERROR), ("ok", COLOR_SUCCESS), ("warn", COLOR_WARN), ("input", COLOR_INPUT), ("dim", COLOR_DIM), ("dash_lbl", COLOR_DIM), ("dash_val", COLOR_INPUT)]:
            self.text_area.tag_configure(t, foreground=c)
        self.text_area.tag_configure("big", font=self.font_big)
        self.text_area.tag_configure("clock", font=self.font_clock, foreground=COLOR_ACCENT)

        self.root.bind("<Key>", self.on_key_press)
        
        self.check_auto_login()
        self.blink_cursor()

    def create_input_labels(self):
        # Очищаем фрейм
        for widget in self.input_frame.winfo_children(): widget.destroy()
        
        self.lbl_prompt = tk.Label(self.input_frame, text="   Select Option: ", font=self.font_main, bg=COLOR_BG, fg=COLOR_ACCENT)
        self.lbl_prompt.pack(side="left")
        
        self.lbl_input = tk.Label(self.input_frame, text="_", font=self.font_main, bg=COLOR_BG, fg=COLOR_INPUT)
        self.lbl_input.pack(side="left")

    # === CONFIG ===
    def load_config(self):
        if not os.path.exists(r"C:\PULZE"):
            try: os.makedirs(r"C:\PULZE")
            except: pass
        if not os.path.exists(CONFIG_FILE):
            self.save_config_direct(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                for k, v in DEFAULT_CONFIG.items():
                    if k not in data: data[k] = v
                    elif isinstance(v, dict):
                         for sub_k, sub_v in v.items():
                             if sub_k not in data[k]: data[k][sub_k] = sub_v
                return data
        except: return DEFAULT_CONFIG.copy()

    def save_config_direct(self, data):
        try:
            with open(CONFIG_FILE, "w") as f: json.dump(data, f, indent=4)
        except: pass

    def save_config(self):
        self.save_config_direct(self.config)

    # === LOGIN SYSTEM ===
    def check_auto_login(self):
        if os.path.exists(KEY_FILE_PATH):
            try:
                with open(KEY_FILE_PATH, "r") as f: key = f.read().strip()
                if self.perform_auth(key):
                    self.init_main_system(); return
            except: pass
        self.render_login_screen()

    def perform_auth(self, key):
        # DEV BYPASS (For Testing)
        if key.lower() in ["admin", "dev", "test"]:
            with open(KEY_FILE_PATH, "w") as f: f.write(key)
            return True
            
        if keyauthapp and keyauthapp.license(key):
            with open(KEY_FILE_PATH, "w") as f: f.write(key)
            return True
        return False

    def render_login_screen(self, msg=""):
        self.menu_state = "login"
        self.clear()
        self.text_area.configure(pady=80)
        
        art = r"""
      ____  _   _ _     _______ ______ 
     |  _ \| | | | |   |___  /|  ____|
     | |_) | | | | |      / / | |__   
     |  __/| | | | |     / /  |  __|  
     | |   | |_| | |____/ /__ | |____ 
     |_|    \___/|______|_____|______|
                                      
        [ SYSTEM ACCESS TERMINAL ]
        """ + "\n"
        self.print_t(art, ("center", "accent"))
        
        self.print_t("="*50 + "\n\n", ("center", "dim"))

        if msg: self.print_t(f"[!] {msg}\n\n", ("center", "err"))
        else:
             if os.path.exists(KEY_FILE_PATH):
                 self.print_t("[+] LICENSE KEY DETECTED\n", ("center", "ok"))
                 self.print_t("    Press [ENTER] to confirm login.\n\n", ("center", "dim"))
             else:
                 self.print_t("[!] LICENSE KEY NOT FOUND\n", ("center", "warn"))
                 self.print_t("    Please enter your activation key below.\n\n", ("center", "dim"))

        self.print_t("-" * 50 + "\n", ("center", "dim"))
        self.print_t(">> PURCHASE KEY: t.me/pulzeOPT <<\n", ("center", "input"))
        self.print_t("-" * 50 + "\n\n", ("center", "dim"))
        
        self.update_input_line_text_login()

    def update_input_line_text_login(self):
        # Уничтожаем старые лейблы
        for widget in self.input_frame.winfo_children(): widget.destroy()
        
        prompt = tk.Label(self.input_frame, text="ACCESS KEY > ", font=self.font_main, bg=COLOR_BG, fg=COLOR_ACCENT)
        prompt.pack(side="left")
        
        self.entry_key = tk.Entry(self.input_frame, font=self.font_main, bg=COLOR_BG, fg=COLOR_INPUT, insertbackground=COLOR_ACCENT, width=35, bd=0)
        self.entry_key.pack(side="left")
        self.entry_key.focus_force()
        
        # Auto-fill if key exists
        if os.path.exists(KEY_FILE_PATH):
             try: 
                 with open(KEY_FILE_PATH) as f: self.entry_key.insert(0, f.read().strip())
             except: pass

        self.entry_key.bind("<Return>", self.on_login_enter)
        # Ctrl+V support
        self.entry_key.bind("<Control-v>", lambda e: self.entry_key.event_generate("<<Paste>>"))
        
        # Context Menu
        self.context_menu = tk.Menu(self.root, tearoff=0, bg="#222", fg="white")
        self.context_menu.add_command(label="Paste Key", command=lambda: self.entry_key.event_generate("<<Paste>>"))
        self.entry_key.bind("<Button-3>", lambda e: self.context_menu.tk_popup(e.x_root, e.y_root))

    def on_login_enter(self, event=None):
        key = self.entry_key.get().strip()
        if self.perform_auth(key):
            # УСПЕХ: ВОССТАНАВЛИВАЕМ ОБЫЧНЫЙ UI
            # Сначала удаляем Entry
            self.entry_key.destroy()
            # Создаем стандартные лейблы ЗАНОВО (чтобы не было ошибки bad window path)
            self.create_input_labels() 
            
            self.print_t("\n[SUCCESS] ACCESS GRANTED.\n", ("center", "ok"))
            self.root.after(1000, self.init_main_system)
        else:
            self.render_login_screen("INVALID KEY")

    def init_main_system(self):
        self.is_logged_in = True
        self.root.title("PULZE")
        self.apply_security_locks() # LOCKDOWN
        self.check_queue()
        threading.Thread(target=self.fetch_system_info, daemon=True).start()
        threading.Thread(target=self.kill_autorun, daemon=True).start()
        threading.Thread(target=self.net_check_loop, daemon=True).start()
        threading.Thread(target=self.global_hotkey_loop, daemon=True).start() # Global Hotkeys
        self.update_clock_loop()

        if self.config.get("FirstRun", True):
            try:
                subprocess.run('bcdedit /set {bootmgr} displaybootmenu yes', shell=True, stdout=subprocess.DEVNULL)
                subprocess.run('bcdedit /set {bootmgr} timeout 30', shell=True, stdout=subprocess.DEVNULL)
            except: pass

        if self.config["Crosshair"]["Enabled"]: self.toggle_crosshair(force_state=True)
        
        if self.config.get("FirstRun", True): self.render_first_run()
        else: self.render_main_menu()

    # === MAIN MENU ===
    def render_main_menu(self):
        self.menu_state = "main"
        self.clear(); self.text_area.configure(pady=40)
        art = r"""
        $$$$$$$\  $$\   $$\ $$\        $$$$$$$$\ $$$$$$$$\ 
        $$  __$$\ $$ |  $$ |$$ |       \____$$  |$$  _____|
        $$ |  $$ |$$ |  $$ |$$ |           $$  / $$ |      
        $$$$$$$  |$$ |  $$ |$$ |          $$  /  $$$$$\    
        $$  ____/ $$ |  $$ |$$ |         $$  /   $$  __|   
        $$ |      $$ |  $$ |$$ |        $$  /    $$ |      
        $$ |      \$$$$$$  |$$$$$$$$\ $$$$$$$$\ $$$$$$$$\  
        \__|       \______/ \________|\________|\________| 
        """ + "\n"
        self.print_t(art, ("center", "accent"))

        # --- CLOCK AND NETWORK CENTERED ---
        t = datetime.datetime.now().strftime("%H:%M")
        
        # Net Logic for display
        net_name = "Ethernet"
        is_online = self.net_status == "ONLINE"
        try:
            if is_online:
                wifi_out = subprocess.check_output("netsh wlan show interfaces", shell=True).decode('cp866', errors='ignore')
                ssid_match = re.search(r"SSID\s+:\s+(.*)", wifi_out)
                if ssid_match: net_name = ssid_match.group(1).strip()
            else: net_name = "No Connection"
        except: pass

        self.print_t(f"{t} | ", ("center", "dim"))
        if is_online: self.print_t("[+]", ("center", "ok"))
        else: self.print_t("[x]", ("center", "err"))
        self.print_t(f" {net_name}\n", ("center", "dim"))
        # ----------------------------------

        # COLUMNS HEADER
        self.print_t("\n", ("center"))
        self.print_t(f"{':: APPLICATIONS ::':<35}", ("center", "accent"))
        self.print_t("    ", ("center"))
        self.print_t(f"{':: UTILITIES ::':<35}", ("center", "accent"))
        self.print_t("\n", ("center"))
        self.print_t(f"{'='*18:<35}", ("center", "dim"))
        self.print_t("    ", ("center"))
        self.print_t(f"{'='*18:<35}", ("center", "dim"))
        self.print_t("\n\n", ("center"))

        def draw_row(t1, k1, t2, k2):
            icon1, tag1 = self.get_status_icon(k1); icon2, tag2 = self.get_status_icon(k2)
            self.print_t(f"{t1:<30}", ("center", "input")); self.print_t(f"{icon1:<5}", ("center", tag1))
            self.print_t("        ", ("center", "dim")) 
            self.print_t(f"{t2:<30}", ("center", "input")); self.print_t(f"{icon2:<5}", ("center", tag2))
            self.print_t("\n", ("center"))

        draw_row("1. Start RUST", '1', "R. Resolution & GPU", 'r')
        draw_row("2. Steam Client", '2', "T. Optimization Menu", 't')
        draw_row("3. Ripcord (Lite)", '3', "F. File Manager", 'f')
        draw_row("4. Discord", '4', "W. Wi-Fi Manager", 'w')
        draw_row("5. Thorium Browser", '5', "M. Mouse Settings", 'm')
        draw_row("6. OBS Studio", '6', "C. Crosshair Menu", 'c') 
        
        self.print_t("\n" + "="*60 + "\n", ("center", "dim"))
        
        # SPECS BLOCK
        c_cpu = self.sys_info.get('cpu_name', 'N/A')
        c_gpu = self.sys_info.get('gpu', 'N/A')
        c_ram = f"{self.sys_info.get('ram_total', 'N/A')} {self.sys_info.get('ram_speed', '')}"
        c_res = f"{self.config.get('CurrentW')}x{self.config.get('CurrentH')} @ {self.sys_info['hz']}Hz"

        # Calculate dynamic padding to center-align nicely
        # We want two columns that look balanced
        
        self.print_t("\n[ SYSTEM STATUS ]\n", ("center", "dim"))
        
        # Row 1: CPU | GPU
        # Use f-string alignment with fixed width, but ensure content fits
        row1 = f"CPU: {c_cpu[:25]:<25}   GPU: {c_gpu[:25]}"
        self.print_t(f"{row1}\n", ("center", "dim"))
        
        # Row 2: RAM | RES
        row2 = f"RAM: {c_ram[:25]:<25}   RES: {c_res}"
        self.print_t(f"{row2}\n", ("center", "dim"))
        
        self.print_t("-" * 30 + "\n", ("center", "dim"))

        # POWER BLOCK
        self.print_t("0. SHUTDOWN      9. REBOOT PC\n", ("center", "err"))
        
        self.update_input_line_text()

    # === INPUT HANDLER ===
    def on_key_press(self, event):
        key = event.keysym.lower()
        if self.menu_state == "login": return # В логине работает Entry
        if self.installing: return 
        if self.is_first_run:
            if key == "return": self.start_embedded_install(); return
            if key == "s": self.skip_first_run(); return
            
        char = ""
        if len(event.char) == 1 and event.char.isprintable():
            char = event.char.lower()
            ru_map = {'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p', 'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k', 'д': 'l', 'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm'}
            if char in ru_map: char = ru_map[char]
        
        if self.menu_state == "binding":
            if char: 
                self.config["Crosshair"]["Hotkey"] = char
                self.hotkey_vk = self.char_to_vk(char) # Update VK
                self.save_config(); self.change_state("crosshair"); return
            return
        # if char == self.config["Crosshair"]["Hotkey"]: self.toggle_crosshair(); return # Handled by global loop now

        if self.menu_state == "main":
            if key == "0": os.system("shutdown /s /t 0"); return
            if key == "9": os.system("shutdown /r /t 0"); return
            if char: self.current_input = char; self.update_input_line_text(); self.root.after(50, lambda: self.route_command(char))
        else:
            if key == "b": self.change_state("main"); return
            if self.menu_state == "wifi_pass":
                 if key == "return": self.connect_wifi(self.selected_ssid, self.current_input); self.current_input = ""; return
                 if key == "backspace": self.current_input = self.current_input[:-1]; self.update_input_line_text(); return
                 if char: self.current_input += event.char; self.update_input_line_text()
                 return
            if char: self.current_input = char; self.update_input_line_text(); self.root.after(50, lambda: self.route_command(char))

    # === CORE UTILS ===
    def update_input_line_text(self):
        if self.is_first_run and not self.is_logged_in: return
        self.root.focus_force(); self.bottom_container.pack(side="bottom", fill="x", pady=30)
        
        # FIX: Если лейблов нет (мы их убили в логине), создаем заново
        if not getattr(self, 'lbl_prompt', None) or not self.lbl_prompt.winfo_exists():
             self.create_input_labels()

        prompt = "   Select Option: "
        if self.menu_state == "wifi_pass": prompt = "   Enter Password: "
        elif self.menu_state == "audio": prompt = "   [+]Up [-]Down [M]ute [D]evice: "
        elif self.menu_state == "binding": prompt = "   Press Key... "
        self.lbl_prompt.config(text=prompt)
        cursor = "_" if self.cursor_visible else " "
        txt = self.current_input
        if self.menu_state == "wifi_pass": txt = "*" * len(txt)
        self.lbl_input.config(text=txt + cursor)

    def net_check_loop(self):
        while True:
            try:
                subprocess.check_output("ping 8.8.8.8 -n 1 -w 1000", shell=True)
                self.net_status = "ONLINE"
            except: self.net_status = "OFFLINE"
            time.sleep(5)

    def update_clock_loop(self):
        if not self.installing:
            t = datetime.datetime.now().strftime("%H:%M")
            # self.lbl_clock.config(text=f" {t} ", font=("Consolas", 14))
            
            net_name = "Ethernet"
            # Простой детект имени сети (можно улучшить через netsh)
            try:
                if self.net_status == "ONLINE":
                    # Пытаемся получить имя SSID если это Wi-Fi
                    wifi_out = subprocess.check_output("netsh wlan show interfaces", shell=True).decode('cp866', errors='ignore')
                    ssid_match = re.search(r"SSID\s+:\s+(.*)", wifi_out)
                    if ssid_match: net_name = ssid_match.group(1).strip()
                else:
                    net_name = "No Connection"
            except: pass

            status_sym = "[+]" if self.net_status == "ONLINE" else "[x]"
            # color = COLOR_SUCCESS if self.net_status == "ONLINE" else COLOR_ERROR
            
            # self.lbl_net.config(text=f"{status_sym} {net_name}", font=("Consolas", 12), fg=color)
            self.net_var.set(f"{status_sym} {net_name}")
            
            if self.menu_state == "main":
                 # Если мы в главном меню, перерисовываем только верхнюю часть? 
                 # Нет, перерисовывать все будет мерцать. 
                 # Мы просто будем обновлять при следующем render_main_menu или пользователь нажмет кнопку.
                 # Но часы должны идти. 
                 # Сделаем костыль: если пользователь ничего не делает 1 минуту, можно обновить.
                 # Но лучше просто забить, в консольных UI часы обычно статичны до действия.
                 pass

        self.root.after(5000, self.update_clock_loop) # Реже обновляем сеть

    def blink_cursor(self):
        if not self.installing and self.menu_state != "login":
            self.cursor_visible = not self.cursor_visible
            self.update_input_line_text()
        self.root.after(500, self.blink_cursor)

    def open_gpu(self):
        cmds = [r'explorer.exe shell:AppsFolder\NVIDIACorp.NVIDIAControlPanel_56jybvy8sckqj!Nvidiacorp.NvidiaControlPanel', 'control.exe /name Microsoft.NVIDIAControlPanel', r'"C:\Program Files\NVIDIA Corporation\Control Panel Client\nvcplui.exe"', 'RadeonSoftware.exe', r"C:\Windows\System32\nvcplui.exe"]
        for c in cmds:
            if os.path.exists(c) or "explorer" in c or "control" in c:
                try: subprocess.Popen(c, shell=True); return
                except: continue
        subprocess.Popen("control.exe", shell=True)

    def run_app(self, k, steam_id=None, args=None):
        path = self.config["Paths"].get(k, "")
        if steam_id: subprocess.Popen(f"start steam://rungameid/{steam_id}", shell=True); return
        if os.path.exists(path):
            cmd = [path]
            if args: cmd.extend(args)
            if k == "Rust": cmd.extend(["-window-mode", "exclusive", "-screen-fullscreen", "1"])
            subprocess.Popen(cmd, cwd=os.path.dirname(path))
        else: self.status_map[k] = "err"

    def change_state(self, new_state):
        self.menu_state = new_state; self.current_input = ""
        if new_state == "main": self.render_main_menu()
        elif new_state == "resolution": self.render_res_menu()
        elif new_state == "tools": self.render_tools_menu() # NEW
        elif new_state == "wifi": self.scan_wifi()
        elif new_state == "audio": self.render_audio_menu()
        elif new_state == "crosshair": self.render_crosshair_menu()
    def render_audio_menu(self):
        self.clear(); self.text_area.configure(pady=80)
        self.print_t("  // AUDIO CONTROL CENTER //  \n\n", ("center", "accent"))
        self.print_t("="*50 + "\n\n", ("center", "dim"))

        # Get Volume using PowerShell (Visual Bar)
        vol = 50
        try:
            cmd = "powershell -command \"(Get-CimInstance -ClassName Win32_OperatingSystem).CSName\"" # Placeholder check
            # Actually getting volume without deps is hard. 
            # We will just show control instructions.
        except: pass
        
        self.print_t("   [ + ]  INCREASE VOLUME\n", ("center", "input"))
        self.print_t("   [ - ]  DECREASE VOLUME\n", ("center", "input"))
        self.print_t("   [ M ]  MUTE / UNMUTE\n\n", ("center", "input"))
        
        self.print_t("-" * 20 + "  SETTINGS  " + "-" * 20 + "\n\n", ("center", "dim"))
        
        self.print_t("   [ D ]  OPEN SOUND SETTINGS (Device Selection)\n", ("center", "warn"))
        
        self.print_t("\n" + "=" * 50 + "\n\n", ("center", "dim"))
        self.print_t("[ B ] << RETURN TO MAIN MENU", ("center", "dim"))
        self.update_input_line_text()

    def execute_audio(self, char):
        if char == 'b': self.change_state("main"); return
        if char == 'd': self.run_cmd("control mmsys.cpl sounds"); return # Sound Settings
        # Volume Control via nircmd logic or pure VBS/SendKeys
        if char in ['+', '-', 'm']:
            vk = 0
            if char == '+': vk = 0xAF # VK_VOLUME_UP
            if char == '-': vk = 0xAE # VK_VOLUME_DOWN
            if char == 'm': vk = 0xAD # VK_VOLUME_MUTE
            try: ctypes.windll.user32.keybd_event(vk, 0, 0, 0); ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
            except: pass
            return # Stay in menu

    def execute_audio(self, char):
        if char == 'b': self.change_state("main"); return
        if char == 'd': self.run_cmd("control mmsys.cpl sounds"); return # Sound Settings
        # Volume Control via nircmd logic or pure VBS/SendKeys
        if char in ['+', '-', 'm']:
            vk = 0
            if char == '+': vk = 0xAF # VK_VOLUME_UP
            if char == '-': vk = 0xAE # VK_VOLUME_DOWN
            if char == 'm': vk = 0xAD # VK_VOLUME_MUTE
            try: ctypes.windll.user32.keybd_event(vk, 0, 0, 0); ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
            except: pass
            # Render visual bar update? No, native overlay handles it usually.
            return # Stay in menu

    def execute_crosshair(self, char):
        if char == 'b': self.change_state("main"); return
        if char == 't': self.toggle_crosshair(); return
        if char == '1': self.change_crosshair_style(); return
        if char == '2': pass # Handled by +/- below
        if char == '3': self.start_binding(); return
        if char == '+': self.change_crosshair_size(1); return
        if char == '-': self.change_crosshair_size(-1); return
        # No update_input needed as actions call render

    def route_command(self, char):
        if self.menu_state == "main": self.execute_main(char)
        elif self.menu_state == "resolution": self.execute_res(char)
        elif self.menu_state == "tweaks": self.execute_tweaks(char)
        elif self.menu_state == "wifi": self.execute_wifi(char)
        elif self.menu_state == "audio": self.execute_audio(char) # ADDED
        elif self.menu_state == "crosshair": self.execute_crosshair(char)

    def execute_main(self, char):
        if char == 'r': self.change_state("resolution"); return
        if char == 't': self.change_state("tweaks"); return # Change to submenu
        if char == 'w': self.change_state("wifi"); return 
        if char == 'a': self.change_state("audio"); return
        if char == 'c': self.change_state("crosshair"); return
        if char == 'x': self.toggle_crosshair(); return
        cmd_map = {
            '1': ("RUST", lambda: self.run_app("Rust", steam_id="252490"), '1'),
            '2': ("STEAM", lambda: self.run_app("Steam"), '2'),
            '3': ("RIPCORD", lambda: self.run_app("Ripcord"), '3'),
            '4': ("DISCORD", lambda: self.run_app("Discord", args=["--processStart", "Discord.exe"]), '4'),
            '5': ("THORIUM", lambda: self.run_app("Thorium"), '5'),
            '6': ("OBS", lambda: self.run_app("OBS"), '6'),
            'i': ("INSTALLER", lambda: self.start_embedded_install(), 'i'),
            'f': ("FILES", lambda: self.run_app("FileMan"), 'f'),
            'm': ("MOUSE", lambda: self.run_cmd("control main.cpl"), 'm'),
            'g': ("GPU", lambda: self.open_gpu(), 'g'),
        }
        if char in cmd_map:
            msg, action, key_id = cmd_map[char]
            if key_id in ['1','2','3','4','5','6','i','f']: self.status_map[key_id] = "loading"; self.render_main_menu(); self.root.update(); self.root.after(50, lambda: self.run_wrapper(action, key_id))
            else: action(); self.current_input = ""; self.update_input_line_text()
        else: self.current_input = ""; self.update_input_line_text()
    def render_tools_menu(self):
        # DEPRECATED, SPLIT INTO TWEAKS and RES
        pass

    def execute_tools(self, char):
        pass

    def change_state(self, new_state):
        self.menu_state = new_state; self.current_input = ""
        if new_state == "main": self.render_main_menu()
        elif new_state == "resolution": self.render_res_menu()
        elif new_state == "tweaks": self.render_tweaks_menu() # NEW
        elif new_state == "wifi": self.scan_wifi()
        elif new_state == "audio": self.render_audio_menu()
        elif new_state == "crosshair": self.render_crosshair_menu()

    def scan_wifi(self):
        self.clear(); self.text_area.configure(pady=80)
        self.print_t("SCANNING NETWORKS...\n", ("center", "warn"))
        self.root.update()
        try:
            out = subprocess.check_output("netsh wlan show networks mode=bssid", shell=True).decode('cp866', errors='ignore')
            ssids = re.findall(r"SSID \d+ : (.*)", out)
            self.wifi_list = [s.strip() for s in ssids if s.strip()][:9]
        except: self.wifi_list = []
        
        self.clear()
        self.print_t("WI-FI MANAGER\n\n", ("center", "accent"))
        if not self.wifi_list: self.print_t("No networks found.\n", ("center", "err"))
        else:
            for i, ssid in enumerate(self.wifi_list):
                self.print_t(f"{i+1}. {ssid}\n", ("center", "input"))
        self.print_t("\nB. Back\n", ("center", "dim"))
        self.update_input_line_text()

    def connect_wifi(self, ssid, password):
        self.print_t(f"\nConnecting to {ssid}...\n", ("center", "warn"))
        self.root.update()
        profile = f"""
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{ssid}</name>
    <SSIDConfig>
        <SSID><name>{ssid}</name></SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>auto</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>WPA2PSK</authentication>
                <encryption>AES</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
            <sharedKey>
                <keyType>passPhrase</keyType>
                <protected>false</protected>
                <keyMaterial>{password}</keyMaterial>
            </sharedKey>
        </security>
    </MSM>
</WLANProfile>"""
        try:
            with open("wifi_prof.xml", "w") as f: f.write(profile)
            subprocess.run(f'netsh wlan add profile filename="wifi_prof.xml"', shell=True)
            subprocess.run(f'netsh wlan connect name="{ssid}"', shell=True)
            os.remove("wifi_prof.xml")
            self.print_t("Request Sent.\n", ("center", "ok"))
        except Exception as e: self.print_t(f"Error: {e}\n", ("center", "err"))
        self.root.after(2000, lambda: self.change_state("main"))

    def install_gpu_driver(self):
        if self.installing: return
        self.installing = True
        self.print_t("\n[CLOUD] INITIALIZING GPU DRIVER SETUP...\n", ("center", "warn"))
        threading.Thread(target=self._gpu_driver_worker, daemon=True).start()

    def _gpu_driver_worker(self):
        if not self.keyauthapp:
             self.msg_queue.put(("ERR", "Auth Error: KeyAuth not initialized."))
             return

        self.msg_queue.put(("LOG", "Fetching Driver Link..."))
        # KeyAuth Variable "assets.rar" holds the direct link to EXE
        driver_url = self.keyauthapp.var("assets.rar")
        
        if not driver_url or "http" not in driver_url:
             self.msg_queue.put(("ERR", "Driver Link not found in Cloud."))
             return

        try:
            self.msg_queue.put(("LOG", "Downloading NVIDIA Driver (High Speed)..."))
            
            temp_dir = tempfile.mkdtemp()
            driver_path = os.path.join(temp_dir, "gpu_driver.exe")
            
            r = requests.get(driver_url, stream=True, verify=False)
            total_size = int(r.headers.get('content-length', 0))
            block_size = 1024*1024 # 1MB
            downloaded = 0
            
            with open(driver_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        # Optional: Progress update to log (can spam)
            
            self.msg_queue.put(("LOG", "Download Complete. Starting Installer..."))
            self.msg_queue.put(("LOG", "Please wait. Screen may flicker."))
            
            # Run Silent Install: /s /n (Standard NVIDIA flags) or just /s
            # Blocking call
            subprocess.run([driver_path, "-s", "-n"], cwd=temp_dir, check=False)
            
            self.msg_queue.put(("LOG", "Installation Finished."))
            self.msg_queue.put(("DONE_TWEAK", "")) # Reuse existing done signal
            
        except Exception as e:
            self.msg_queue.put(("ERR", f"Driver Error: {e}"))
        finally:
            try: shutil.rmtree(temp_dir, ignore_errors=True)
            except: pass

    def render_tweaks_menu(self):
        self.clear(); self.text_area.configure(pady=80)
        self.print_t("  // SYSTEM OPTIMIZATION MODULE //  \n\n", ("center", "accent"))
        self.print_t("="*50 + "\n\n", ("center", "dim"))
        
        self.print_t("   [ 1 ] >> EXECUTE SYSTEM TWEAKS (Cloud)\n", ("center", "input"))
        self.print_t("            (Registry, Services, Latency, Network)\n\n", ("center", "dim"))
        
        self.print_t("   [ 2 ] >> INSTALL GPU DRIVER (NVIDIA)\n", ("center", "input"))
        self.print_t("            (Downloads & Installs Latest Driver)\n\n", ("center", "dim"))
        
        self.print_t("-" * 50 + "\n\n", ("center", "dim"))
        self.print_t("[ B ] << RETURN TO MAIN MENU", ("center", "dim"))
        self.update_input_line_text()

    def execute_tweaks(self, char):
        if char == 'b': self.change_state("main"); return
        if char == '1': self.start_internal_tweaks(); return
        if char == '2': self.install_gpu_driver(); return

    def execute_res(self, char):
        if char == 'b': self.change_state("main"); return
        if char == 'g': self.open_gpu(); return
        cmd_map = {'1': lambda: self.set_res(1920, 1080), '2': lambda: self.set_res(1440, 1080), '3': lambda: self.set_res(1280, 960), 'q': lambda: self.swap_res()}
        if char in cmd_map: cmd_map[char](); self.current_input = ""; self.render_res_menu()
        else: self.current_input = ""; self.update_input_line_text()
    def render_res_menu(self):
        self.clear(); self.text_area.configure(pady=60)
        self.print_t("  // DISPLAY & GRAPHICS CONFIG //  \n\n", ("center", "accent"))
        self.print_t("="*50 + "\n\n", ("center", "dim"))

        self.print_t("   [ 1 ]  1920 x 1080  ::  Native 16:9\n", ("center", "input"))
        self.print_t("   [ 2 ]  1440 x 1080  ::  Stretched 4:3\n", ("center", "input"))
        self.print_t("   [ 3 ]  1280 x 960   ::  Competitive\n\n", ("center", "input"))
        
        self.print_t("-" * 20 + "  EXTRAS  " + "-" * 20 + "\n\n", ("center", "dim"))
        
        self.print_t("   [ G ]  OPEN NVIDIA CONTROL PANEL\n", ("center", "warn"))
        self.print_t("   [ Q ]  SWAP PREVIOUS RESOLUTION\n", ("center", "input"))
        
        self.print_t("\n" + "=" * 50 + "\n\n", ("center", "dim"))
        self.print_t("[ B ] << RETURN TO MAIN MENU", ("center", "dim"))
        self.update_input_line_text()

    def execute_wifi(self, char):
        if char == 'b': self.change_state("main"); return
        if char.isdigit() and int(char) > 0 and int(char) <= len(self.wifi_list):
            self.selected_ssid = self.wifi_list[int(char)-1]; self.menu_state = "wifi_pass"; self.current_input = ""; self.update_input_line_text()
        else: self.current_input = ""; self.update_input_line_text()
    def run_wrapper(self, action, key_id):
        try: 
            action()
            self.status_map[key_id] = "ok"
        except: 
            self.status_map[key_id] = "err"
        
        # DO NOT RENDER OR FORCE FOCUS HERE
        # Just clear status later silently
        # self.render_main_menu(); 
        
        self.current_input = ""
        self.root.after(3000, lambda: self.clear_status(key_id))

    def clear_status(self, key_id):
        if key_id in self.status_map: del self.status_map[key_id]; 
        # Only re-render if window is actually focused to avoid stealing focus back
        if self.root.focus_displayof(): 
             if self.menu_state == "main": self.render_main_menu()
    def set_res(self, w, h):
        if not os.path.exists(QRES_PATH): return
        self.config["LastW"] = self.config.get("CurrentW", 1920); self.config["LastH"] = self.config.get("CurrentH", 1080); self.config["CurrentW"] = w; self.config["CurrentH"] = h; self.save_config()
        hz = self.sys_info['hz']; subprocess.run([QRES_PATH, f"/x:{w}", f"/y:{h}", f"/r:{hz}"], shell=True)
    def swap_res(self):
        last_w = self.config.get("LastW"); last_h = self.config.get("LastH")
        if last_w and last_h: self.set_res(last_w, last_h)
    def run_cmd(self, c):
        try: subprocess.Popen(c, shell=True)
        except: pass
    def run_script(self, s, ps=False):
        if not os.path.exists(s): return
        if ps: subprocess.Popen(["start", "powershell", "-ExecutionPolicy", "Bypass", "-File", s], shell=True)
        else: subprocess.Popen(["start", s], shell=True)
    def check_queue(self):
        while not self.msg_queue.empty():
            t, c = self.msg_queue.get()
            if t == "LOG":
                col = "dim"
                if any(x in c.lower() for x in ["download", "install", "start"]): col = "warn"
                if any(x in c.lower() for x in ["success", "ok", "complete"]): col = "ok"
                self.print_t(f"{c}\n", ("center", col))
                
            elif t == "DONE": 
                # INSTALL COMPLETE -> START TWEAKS AUTOMATICALLY
                self.print_t("\n[INSTALL COMPLETE] STARTING POST-INSTALL OPTIMIZATION...\n", ("center", "ok"))
                self.root.after(2000, self.start_internal_tweaks)
                
            elif t == "DONE_TWEAK": 
                # TWEAKS COMPLETE -> REBOOT
                self.installing = False; 
                self.is_first_run = False; 
                self.config["FirstRun"] = False; 
                self.save_config()
                
                self.print_t("\n[SUCCESS] SYSTEM READY. REBOOTING IN 5 SECONDS...\n", ("center", "ok"))
                self.root.update()
                time.sleep(5)
                os.system("shutdown /r /t 0")
                
            elif t == "ERR": 
                self.print_t(f"\n[ERROR] {c}\n", ("center", "err")); self.installing = False
        self.root.after(100, self.check_queue)

    def fetch_system_info(self):
        # STATIC INFO (Run once)
        
        # 0. DETECT HZ (REFRESH RATE)
        try:
            hz_cmd = subprocess.check_output("wmic path Win32_VideoController get CurrentRefreshRate", shell=True).decode(errors='ignore')
            lines = [l.strip() for l in hz_cmd.split('\n') if l.strip() and l.strip().isdigit()]
            if lines: self.sys_info["hz"] = lines[0]
        except: pass

        # 1. Try WMI Module
        success_wmi = False
        try:
            if wmi:
                c = wmi.WMI()
                # GPU
                for gpu in c.Win32_VideoController():
                    name = gpu.Name
                    if "parsec" in name.lower() or "virtual" in name.lower() or "microsoft" in name.lower() or "sudomaker" in name.lower(): continue
                    name = name.replace("NVIDIA GeForce ", "").replace("AMD Radeon ", "")
                    self.sys_info["gpu"] = name
                    if "rtx" in name.lower() or "gtx" in name.lower() or "rx" in name.lower(): break
                # CPU
                for cpu in c.Win32_Processor():
                    name = cpu.Name
                    name = name.replace("Intel(R) Core(TM) ", "").replace("AMD Ryzen ", "Ryzen ")
                    name = re.sub(r"\s+@.*", "", name)
                    self.sys_info["cpu_name"] = name.strip()
                    break
                # RAM (Total & Speed)
                total_cap = 0
                max_speed = 0
                for mem in c.Win32_PhysicalMemory():
                    if mem.Capacity: total_cap += int(mem.Capacity)
                    if mem.Speed:
                        s = int(mem.Speed)
                        if s > max_speed: max_speed = s
                
                if total_cap > 0: self.sys_info["ram_total"] = f"{math.ceil(total_cap / (1024**3))}GB"
                if max_speed > 0: self.sys_info["ram_speed"] = f"{max_speed}MHz"
                
                success_wmi = True
        except: pass

        # 2. Fallback to WMIC (if WMI failed or missing)
        if not success_wmi or self.sys_info.get("cpu_name") == "Scanning...":
            try:
                # CPU
                cpu_out = subprocess.check_output("wmic cpu get name", shell=True, timeout=2).decode(errors='ignore')
                lines = [line.strip() for line in cpu_out.split('\n') if line.strip()]
                if len(lines) > 1:
                    name = lines[1]
                    name = name.replace("Intel(R) Core(TM) ", "").replace("AMD Ryzen ", "Ryzen ")
                    name = re.sub(r"\s+@.*", "", name)
                    self.sys_info["cpu_name"] = name.strip()
                
                # GPU
                gpu_out = subprocess.check_output("wmic path win32_videocontroller get name", shell=True, timeout=2).decode(errors='ignore')
                lines = [line.strip() for line in gpu_out.split('\n') if line.strip()]
                for l in lines[1:]:
                    if "parsec" in l.lower() or "virtual" in l.lower() or "microsoft" in l.lower() or "sudomaker" in l.lower(): continue
                    name = l
                    name = name.replace("NVIDIA GeForce ", "").replace("AMD Radeon ", "")
                    self.sys_info["gpu"] = name
                    if "rtx" in name.lower() or "gtx" in name.lower() or "rx" in name.lower(): break
                
                # RAM (Total & Speed) via WMIC
                ram_cap_out = subprocess.check_output("wmic memorychip get capacity", shell=True, timeout=2).decode(errors='ignore')
                total_bytes = sum([int(x) for x in ram_cap_out.split() if x.isdigit()])
                if total_bytes > 0: self.sys_info["ram_total"] = f"{math.ceil(total_bytes / (1024**3))}GB"
                
                ram_spd_out = subprocess.check_output("wmic memorychip get speed", shell=True, timeout=2).decode(errors='ignore')
                speeds = [int(x) for x in ram_spd_out.split() if x.isdigit()]
                if speeds: self.sys_info["ram_speed"] = f"{max(speeds)}MHz"
                
            except: pass

        # 3. Fallback to POWERSHELL (Strongest Fallback)
        # Checks if any info is still missing/default
        missing_cpu = self.sys_info.get("cpu_name", "Scanning...") in ["Scanning...", "Error", "Unknown"]
        missing_gpu = self.sys_info.get("gpu", "Scanning...") in ["Scanning...", "Error", "Unknown"]
        missing_ram = self.sys_info.get("ram_total", "...") in ["...", "N/A"]
        
        if missing_cpu or missing_gpu or missing_ram:
            try:
                if missing_cpu:
                    ps_cmd = "Get-CimInstance -ClassName Win32_Processor | Select-Object -ExpandProperty Name"
                    p = subprocess.check_output(["powershell", "-Command", ps_cmd], shell=True, timeout=3).decode(errors='ignore').strip()
                    if p:
                        name = p.replace("Intel(R) Core(TM) ", "").replace("AMD Ryzen ", "Ryzen ")
                        name = re.sub(r"\s+@.*", "", name)
                        self.sys_info["cpu_name"] = name.strip()
                
                if missing_gpu:
                    ps_cmd_gpu = "Get-CimInstance -ClassName Win32_VideoController | Select-Object -ExpandProperty Name"
                    p_gpu = subprocess.check_output(["powershell", "-Command", ps_cmd_gpu], shell=True, timeout=3).decode(errors='ignore').strip()
                    if p_gpu:
                        for line in p_gpu.split('\n'):
                            line = line.strip()
                            if not line: continue
                            if "parsec" in line.lower() or "virtual" in line.lower() or "microsoft" in line.lower() or "sudomaker" in line.lower(): continue
                            name = line.replace("NVIDIA GeForce ", "").replace("AMD Radeon ", "")
                            self.sys_info["gpu"] = name
                            if "rtx" in name.lower() or "gtx" in name.lower() or "rx" in name.lower(): break
                
                if missing_ram:
                    # RAM Total
                    ps_ram = "Get-CimInstance -ClassName Win32_PhysicalMemory | Measure-Object -Property Capacity -Sum | Select-Object -ExpandProperty Sum"
                    p_ram = subprocess.check_output(["powershell", "-Command", ps_ram], shell=True, timeout=3).decode(errors='ignore').strip()
                    if p_ram and p_ram.isdigit():
                        self.sys_info["ram_total"] = f"{math.ceil(int(p_ram) / (1024**3))}GB"
                    
                    # RAM Speed
                    ps_speed = "Get-CimInstance -ClassName Win32_PhysicalMemory | Select-Object -ExpandProperty Speed"
                    p_spd = subprocess.check_output(["powershell", "-Command", ps_speed], shell=True, timeout=3).decode(errors='ignore').strip()
                    if p_spd:
                        speeds = [int(x) for x in p_spd.split() if x.isdigit()]
                        if speeds: self.sys_info["ram_speed"] = f"{max(speeds)}MHz"

            except: pass

        # FORCE UPDATE UI AFTER FETCH
        if self.menu_state == "main":
            try: self.root.after(0, self.render_main_menu)
            except: pass

        while True:
            time.sleep(10)

    def start_embedded_install(self):
        if self.installing: return
        self.installing = True; self.bottom_container.pack_forget(); self.clear(); self.text_area.configure(pady=150)
        self.print_t("PULZE INSTALLATION MANAGER\n\n", ("center", "big", "accent")); self.print_t("-" * 40 + "\n\n", ("center", "dim"))
        threading.Thread(target=self._install_worker, daemon=True).start()
    
    def start_internal_tweaks(self):
        if self.installing: return
        self.installing = True
        self.print_t("\n[CLOUD] INITIALIZING SECURE CONNECTION...\n", ("center", "warn"))
        threading.Thread(target=self._cloud_tweak_worker, daemon=True).start()

    def _cloud_tweak_worker(self):
        # 1. Get Link from KeyAuth
        if not self.keyauthapp:
             self.msg_queue.put(("ERR", "Auth Error: KeyAuth not initialized."))
             return

        self.msg_queue.put(("LOG", "Authenticating session..."))
        # Check if session is valid (simple check)
        # Assuming user logged in. 
        
        # 2. Fetch Variable
        # User must create variable "TWEAK_ARCHIVE" in KeyAuth panel
        # containing the direct link to ZIP
        tweak_url = self.keyauthapp.var("TWEAK_ARCHIVE")
        
        if not tweak_url or "http" not in tweak_url:
             self.msg_queue.put(("LOG", "[WARN] Cloud Link not found. Using offline backup..."))
             # Fallback to local engine
             try:
                 engine = TweakerEngine(self.msg_queue)
                 engine.run_all_tweaks()
             except Exception as e: self.msg_queue.put(("ERR", str(e)))
             return

        # 3. Download & Run
        try:
            self.msg_queue.put(("LOG", "Downloading Secure Package..."))
            
            # Create Secure Temp Dir
            temp_dir = tempfile.mkdtemp()
            zip_path = os.path.join(temp_dir, "payload.zip")
            
            # Download
            r = requests.get(tweak_url, stream=True, verify=False) # verify=False to avoid SSL errors on some custom hosts
            if r.status_code != 200:
                raise Exception(f"Download failed: {r.status_code}")
                
            with open(zip_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self.msg_queue.put(("LOG", "Verifying Integrity..."))
            # Extract
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Find Entry Point (main.bat or script.py)
            # Priority: tweaks.py -> tweak.bat -> main.bat
            target_script = None
            if os.path.exists(os.path.join(temp_dir, "tweaks.py")): target_script = os.path.join(temp_dir, "tweaks.py")
            elif os.path.exists(os.path.join(temp_dir, "tweak.bat")): target_script = os.path.join(temp_dir, "tweak.bat")
            elif os.path.exists(os.path.join(temp_dir, "main.bat")): target_script = os.path.join(temp_dir, "main.bat")
            elif os.path.exists(os.path.join(temp_dir, "run.py")): target_script = os.path.join(temp_dir, "run.py")
            
            if target_script:
                self.msg_queue.put(("LOG", "Executing Cloud Logic..."))
                if target_script.endswith(".py"):
                    # Run Python script using current interpreter
                    subprocess.run([sys.executable, target_script], cwd=temp_dir, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    # Run BAT hidden
                    subprocess.run([target_script], cwd=temp_dir, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                
                self.msg_queue.put(("DONE_TWEAK", ""))
            else:
                self.msg_queue.put(("ERR", "No executable found in package."))

        except Exception as e:
            self.msg_queue.put(("ERR", f"Cloud Error: {e}"))
        finally:
            # 4. SECURE WIPE
            self.msg_queue.put(("LOG", "Cleaning traces..."))
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                try:
                    # Overwrite files before delete
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            p = os.path.join(root, file)
                            try:
                                with open(p, "ba+") as f:
                                    length = f.tell()
                                    f.write(os.urandom(length))
                            except: pass
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except: pass

    def _tweak_worker(self):
        # OLD LOCAL WORKER - DEPRECATED BUT KEPT AS BACKUP
        try:
            engine = TweakerEngine(self.msg_queue)
            engine.run_all_tweaks()
        except Exception as e:
            self.msg_queue.put(("ERR", str(e)))

    def _install_worker(self):
        if not os.path.exists(INSTALLER_SCRIPT): self.msg_queue.put(("ERR", "Script missing")); return
        try:
            p = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", INSTALLER_SCRIPT], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW, text=True)
            for l in p.stdout:
                if l.strip(): self.msg_queue.put(("LOG", l.strip()))
            p.wait(); self.msg_queue.put(("DONE", ""))
        except Exception as e: self.msg_queue.put(("ERR", str(e)))
    def skip_first_run(self): self.is_first_run = False; self.config["FirstRun"] = False; self.save_config(); self.change_state("main")
    def render_first_run(self):
        self.menu_state = "first_run"; self.clear(); self.text_area.configure(pady=200); self.bottom_container.pack_forget()
        self.print_t("WELCOME TO PULZE OS\n\n", ("center", "big", "accent")); self.print_t("INITIAL SETUP REQUIRED\n\n", ("center", "warn")); self.print_t("PRESS [ENTER] TO START INSTALLATION", ("center", "input"))
    def toggle_crosshair(self, force_state=None):
        current_state = bool(self.crosshair_win)
        target_state = not current_state if force_state is None else force_state
        if target_state:
            if self.crosshair_win: self.crosshair_win.destroy()
            c_conf = self.config["Crosshair"]
            self.crosshair_win = Crosshair(self.root, size=c_conf["Size"], style=c_conf["Type"], color=c_conf["Color"])
            self.config["Crosshair"]["Enabled"] = True
        else:
            if self.crosshair_win: self.crosshair_win.destroy(); self.crosshair_win = None
            self.config["Crosshair"]["Enabled"] = False
        self.save_config(); self.root.focus_force()
        if self.menu_state == "main": self.render_main_menu()
        if self.menu_state == "crosshair": self.render_crosshair_menu()
    def render_crosshair_menu(self):
        self.clear(); self.text_area.configure(pady=80); c_conf = self.config["Crosshair"]
        self.print_t("  // CROSSHAIR OVERLAY CONFIG //  \n\n", ("center", "accent"))
        self.print_t("="*50 + "\n\n", ("center", "dim"))
        
        style_str = "DOT" if c_conf["Type"] == "dot" else "PLUS (+)"
        self.print_t(f"   [ 1 ]  STYLE  ::  {style_str}\n", ("center", "input"))
        self.print_t(f"   [ 2 ]  SIZE   ::  {c_conf['Size']} px  (Use +/-)\n", ("center", "input"))
        
        hotkey_str = c_conf["Hotkey"].upper()
        self.print_t(f"   [ 3 ]  BIND   ::  [{hotkey_str}] (Press H to set)\n\n", ("center", "input"))
        
        status = "ACTIVE" if c_conf["Enabled"] else "DISABLED"; color = "ok" if c_conf["Enabled"] else "err"
        self.print_t(f"   STATUS: [{status}]\n", ("center", color))
        
        self.print_t("\n" + "-" * 50 + "\n\n", ("center", "dim"))
        self.print_t("   [ T ]  TOGGLE OVERLAY ON/OFF\n", ("center", "warn"))
        self.print_t("   [ B ]  << RETURN TO MAIN MENU", ("center", "dim"))
        self.update_input_line_text()
    def change_crosshair_style(self):
        curr = self.config["Crosshair"]["Type"]
        self.config["Crosshair"]["Type"] = "plus" if curr == "dot" else "dot"
        self.save_config(); 
        if self.config["Crosshair"]["Enabled"]: self.toggle_crosshair(True)
        self.render_crosshair_menu()
    def change_crosshair_size(self, delta):
        new_size = self.config["Crosshair"]["Size"] + delta
        if new_size < 2: new_size = 2
        if new_size > 50: new_size = 50
        self.config["Crosshair"]["Size"] = new_size; self.save_config()
        if self.config["Crosshair"]["Enabled"]: self.toggle_crosshair(True)
        self.render_crosshair_menu()
    def start_binding(self):
        self.menu_state = "binding"; self.clear(); self.text_area.configure(pady=150); self.print_t("PRESS ANY KEY TO BIND...\n", ("center", "warn")); self.update_input_line_text()
    def print_t(self, text, tags=None):
        self.text_area.configure(state="normal")
        if isinstance(tags, str): tags = (tags,)
        self.text_area.insert("end", text, tags)
        self.text_area.configure(state="disabled")
    def clear(self):
        self.text_area.configure(state="normal")
        self.text_area.delete("1.0", "end")
        self.text_area.configure(state="disabled")
    def get_status_icon(self, key):
        state = self.status_map.get(key, None)
        if state == "loading": return "[●]", "warn"
        if state == "ok": return "[+]", "ok"
        if state == "err": return "[x]", "err"
        return "   ", "dim"
    def kill_autorun(self):
        keys = [(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"), (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"), (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run")]
        whitelist = ["Audio", "Realtek", "NVIDIA", "AMD", "Radeon", "PULZE"] 
        for root, path in keys:
            try:
                with winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS) as key:
                    info = winreg.QueryInfoKey(key)
                    for i in range(info[1]):
                        try:
                            name, _, _ = winreg.EnumValue(key, 0)
                            keep = False
                            for w in whitelist:
                                if w.lower() in name.lower(): keep = True
                            if not keep: winreg.DeleteValue(key, name)
                        except: pass
            except: pass

    # === SECURITY & TOOLS ===
    def apply_security_locks(self):
        # Disable TaskMgr, Regedit, CMD
        try:
            # System Policies
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Policies\System"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, "DisableTaskMgr", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "DisableRegistryTools", 0, winreg.REG_DWORD, 1)
            
            # Explorer Policies (CMD/Run)
            key_path_expl = r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path_expl) as key:
                 winreg.SetValueEx(key, "NoRun", 0, winreg.REG_DWORD, 1)

            # Disable CMD directly
            key_path_sys = r"Software\Policies\Microsoft\Windows\System"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path_sys) as key:
                winreg.SetValueEx(key, "DisableCMD", 0, winreg.REG_DWORD, 2) # 2 = allow batch only, 1 = disable script processing too
        except: pass
    
    def unlock_security(self):
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Policies\System"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.DeleteValue(key, "DisableTaskMgr")
                winreg.DeleteValue(key, "DisableRegistryTools")
            
            key_path_expl = r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path_expl, 0, winreg.KEY_WRITE) as key:
                winreg.DeleteValue(key, "NoRun")
                
            key_path_sys = r"Software\Policies\Microsoft\Windows\System"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path_sys, 0, winreg.KEY_WRITE) as key:
                winreg.DeleteValue(key, "DisableCMD")
        except: pass

    def open_dev_tools(self, event=None):
        # Backdoor Menu
        self.unlock_security()
        self.print_t("\n[!] DEV MODE ACTIVATED: SECURITY UNLOCKED\n", ("center", "err"))
        self.print_t("    TaskMgr, CMD, Regedit restored.\n", ("center", "warn"))
        # Open basic tools
        subprocess.Popen("taskmgr.exe")
    
    def clean_ram(self, event=None):
        # Pure ctypes implementation to reduce working set
        try:
            psapi = ctypes.windll.psapi
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetCurrentProcess()
            psapi.EmptyWorkingSet(handle)
            
            # Force Garbage Collection
            import gc
            gc.collect()
            
            self.print_t("\n[RAM CLEANER] Memory Released.\n", ("center", "ok"))
        except: pass

    def global_hotkey_loop(self):
        # Simple polling for global hotkey without 'keyboard' lib
        # Using GetAsyncKeyState
        while True:
            if self.config["Crosshair"]["Enabled"]:
                vk = self.hotkey_vk
                if vk and (ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000):
                     # Debounce
                     self.root.after(0, self.toggle_crosshair)
                     time.sleep(0.3) 
            time.sleep(0.05)

    def char_to_vk(self, char):
        # Helper to convert config char to VK Code
        # This is minimal; full mapping is huge.
        if not char: return 0
        char = char.upper()
        # 0-9, A-Z match ASCII for VK
        if len(char) == 1:
            o = ord(char)
            if (o >= 48 and o <= 57) or (o >= 65 and o <= 90): return o
        # Function keys F1-F12
        if char.startswith('F'):
             try: return 0x70 + int(char[1:]) - 1
             except: pass
        return 0 # Fail safe

if __name__ == "__main__":
    root = tk.Tk()
    app = PulseConsole(root)
    root.mainloop()