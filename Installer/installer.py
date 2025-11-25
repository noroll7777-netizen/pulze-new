import customtkinter as ctk
import tkinter as tk 
import sys
import ctypes
import os
import subprocess
import threading
import wmi
import requests
import shutil
import psutil
import time
import urllib3
import hashlib
import webbrowser
import traceback
import json
import platform
import re

# Отключаем SSL предупреждения
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# KeyAuth теперь лежит рядом (скопирован перед сборкой), поэтому sys.path.append не нужен
import sys
import os

# Add Common directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../Common'))
from auth_client import KeyAuthAPI
from boot_manager import install_bootloader

# ==============================================================================
# 🔐 ВСТРОЕННЫЙ КЛАСС KEYAUTH (ЧТОБЫ НЕ БЫЛО ОШИБОК С ФАЙЛАМИ)
# ==============================================================================
# KeyAuthAPI теперь импортируется из ../keyauth.py

# --- КОНФИГУРАЦИЯ ---
KEYAUTH_NAME = "PULZE OS"
KEYAUTH_OWNERID = "l3xzAwuCp8"
KEYAUTH_SECRET = "6ef4a4f1b43cc624fef08ba5b958a8c82c46c66cb4dd04cd290d0a99f20508a0"
KEYAUTH_VERSION = "1.0"

# Fallback ссылка (если сервер не выдаст переменную)
# Зашифрованные данные для безопасности
FALLBACK_KEY = 'cUJvanEzNWM=' # Base64 encoded ID
FALLBACK_DOMAIN = 'aHR0cHM6Ly9waXhlbGRyYWluLmNvbS9hcGkvZmlsZS8=' # Base64 encoded URL
TG_LINK = "https://t.me/pulzeOPT"

WIM_NAME = "install.wim" 
INSTALL_SIZE_GB = 30 
MIN_FREE_SPACE_GB = 35 

# --- ЦВЕТА ---
COLOR_BG = "#0f0f11"        
COLOR_PANEL = "#151719"     
COLOR_BORDER = "#2a2f31"    
COLOR_ACCENT = "#7cc8c6"    
COLOR_TEXT = "#c6dada"      
COLOR_BTN = "#1d1f21"       
COLOR_BTN_HOVER = "#232628" 
COLOR_GREEN = "#00ff9d"     
COLOR_RED = "#ff4444"       
COLOR_LOG_BG = "#0c0d0e"    
COLOR_MAIN_BG = "#151719"
COLOR_SEPARATOR = "#2a2f31"

# --- ФУНКЦИИ ---
def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

def get_checksum():
    try:
        md5 = hashlib.md5()
        with open(sys.argv[0], 'rb') as f:
            md5.update(f.read())
        return md5.hexdigest()
    except: return None

# Инициализация защиты (ВСТРОЕННЫЙ КЛАСС)
keyauthapp = None
try:
    keyauthapp = KeyAuthAPI(
        name = KEYAUTH_NAME,
        ownerid = KEYAUTH_OWNERID,
        secret = KEYAUTH_SECRET,
        version = KEYAUTH_VERSION,
        hash_to_check = get_checksum()
    )
except: pass

# Анимация
def hex_to_rgb(hex_col):
    hex_col = hex_col.lstrip('#')
    return tuple(int(hex_col[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    return '#%02x%02x%02x' % rgb

def generate_gradient(color1, color2, steps):
    c1 = hex_to_rgb(color1)
    c2 = hex_to_rgb(color2)
    gradient = []
    for i in range(steps):
        r = int(c1[0] + (c2[0] - c1[0]) * i / steps)
        g = int(c1[1] + (c2[1] - c1[1]) * i / steps)
        b = int(c1[2] + (c2[2] - c1[2]) * i / steps)
        gradient.append(rgb_to_hex((r, g, b)))
    return gradient

# Цвета для анимации перелива
COLOR_NEON_GREEN = "#0fffc1"  # Яркий неоново-зеленый
COLOR_BLUE = "#0066cc"      # Синий (не слишком темный)

# Создаем плавный градиент между цветами для эффекта похожего на CSS background-position
# Создаем большой градиент для плавного перехода
SMOOTH_WAVE = generate_gradient(COLOR_NEON_GREEN, COLOR_BLUE, 50) + generate_gradient(COLOR_BLUE, COLOR_NEON_GREEN, 50)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class PulzeInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PULZE INSTALLER")
        self.geometry("850x600")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG)
        
        # Центрируем окно на экране
        self.center_window()
        
        self.base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
        # Ищем WIM файл во всех возможных местах
        self.wim_path = self.find_wim_file()
        
        # Создаем путь для копирования ключа
        self.resources_src = os.path.dirname(self.base_path)
        
        self.wave_index = 0
        self.is_logged_in = False
        self.cloud_url = None

        # СТРОИМ ТОЛЬКО ЛОГИН ПРИ ЗАПУСКЕ
        self.build_login_ui()
        self.animate_header()
        

    def find_wim_file(self):
        """Ищет WIM файл во всех возможных местах"""
        # Собираем все возможные пути TEMP
        temp_paths = []
        
        # 1. Windows Temp (ПРИОРИТЕТ 1)
        windows_temp_variants = [
            r'C:\Windows\Temp',
            r'C:\WINDOWS\Temp',
            r'C:\Windows\TEMP',
            r'C:\windows\temp',
            os.path.join('C:\\', 'Windows', 'Temp'),
            os.path.join('C:\\', 'WINDOWS', 'Temp')
        ]
        temp_paths.extend(windows_temp_variants)
        
        # 2. Пользовательские Temp (ПРИОРИТЕТ 2)
        # Текущий пользователь
        user_temp = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'Temp')
        temp_paths.append(user_temp)
        
        # 3. Системные переменные TEMP/TMP (ПРИОРИТЕТ 3)
        if os.environ.get('TEMP'):
            temp_paths.append(os.environ.get('TEMP'))
        if os.environ.get('TMP'):
            temp_paths.append(os.environ.get('TMP'))
            
        # 4. Все пользовательские профили (ПРИОРИТЕТ 4)
        try:
            users_dir = os.path.join('C:\\', 'Users')
            if os.path.exists(users_dir):
                for user_folder in os.listdir(users_dir):
                    user_temp_path = os.path.join(users_dir, user_folder, 'AppData', 'Local', 'Temp')
                    if os.path.exists(user_temp_path):
                        temp_paths.append(user_temp_path)
        except Exception as e:
            print(f"Error scanning user profiles: {e}")
            
        # 5. Другие места (ПРИОРИТЕТ 5)
        other_paths = [
            # Рядом с Installer.exe
            self.base_path,
            # В корне диска C
            'C:\\',
            # В текущей директории
            os.getcwd()
        ]
        temp_paths.extend(other_paths)
        
        # Удаляем дубликаты и нормализуем пути
        unique_temp_paths = []
        for path in temp_paths:
            if path:
                try:
                    normalized = os.path.normpath(path)
                    if normalized not in unique_temp_paths and os.path.exists(normalized):
                        unique_temp_paths.append(normalized)
                except:
                    pass
        
        # Теперь ищем файл install.wim в каждой из этих директорий
        possible_wim_paths = []
        for temp_dir in unique_temp_paths:
            wim_path = os.path.join(temp_dir, WIM_NAME)
            possible_wim_paths.append(wim_path)
            # Также проверяем альтернативное имя
            alt_wim_path = os.path.join(temp_dir, 'install.wim')
            if alt_wim_path != wim_path:  # Избегаем дубликатов
                possible_wim_paths.append(alt_wim_path)
        
        print(f"[SEARCH] Searching for WIM in {len(unique_temp_paths)} temp directories ({len(possible_wim_paths)} total paths)...")
        
        # Проверяем каждый путь
        for i, path in enumerate(possible_wim_paths):
            if os.path.exists(path):
                try:
                    size = os.path.getsize(path)
                    size_gb = size / (1024**3)
                    
                    print(f"[FOUND] [{i+1}] Found valid WIM file")
                    print(f"    Size: {size_gb:.2f} GB")
                    
                    # Файл должен быть больше 3 ГБ (минимум для валидного WIM)
                    if size > 3 * (1024**3):
                        print(f"[OK] Valid WIM file found and ready to use")
                        return path
                    else:
                        # Маленький файл - возможно, это битый файл от неудачного скачивания
                        print(f"[WARN] File too small (expected > 3.0 GB), skipping...")
                        # Удаляем маленький/битый файл, чтобы не мешал при следующей попытке
                        try:
                            os.remove(path)
                            print(f"[DELETE] Removed small/corrupted file: {path}")
                        except Exception as e:
                            print(f"[WARN] Could not remove file {path}: {e}")
                except Exception as e:
                    print(f"[ERROR] Error checking file {path}: {e}")
                    continue
        
        # Если не нашли - возвращаем путь по умолчанию (приоритет C:\Windows\Temp)
        default_path = r'C:\Windows\Temp\install.wim'
        print(f"[WARN] WIM not found in any location!")
        print(f"[INFO] Will use default path for download: {default_path}")
        return default_path

    # ====================================================
    # 🔒 СЦЕНА 1: АВТОРИЗАЦИЯ
    # ====================================================
    def build_login_ui(self):
        # Контейнер
        self.login_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.login_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        # Заголовок
        self.header = ctk.CTkLabel(self.login_frame, text="PULZE INSTALLER", font=("Segoe UI", 34, "bold"), text_color=COLOR_ACCENT)
        self.header.pack(pady=(0, 5))

        ctk.CTkLabel(self.login_frame, text="ENTER LICENSE KEY TO CONTINUE", font=("Arial", 11), text_color="#666").pack(pady=(0, 30))

        # Поле ввода
        self.key_entry = ctk.CTkEntry(self.login_frame, placeholder_text="XXXXXX-XXXXXX-XXXXXX-XXXXXX", width=380, height=50, 
                                      font=("Consolas", 15), fg_color="#111", border_color=COLOR_BORDER, text_color=COLOR_ACCENT, justify="center")
        self.key_entry.pack(pady=10)
        
        # --- FIX: РУЧНЫЕ БИНДЫ ДЛЯ ВСТАВКИ ---
        self.key_entry.bind("<Control-v>", self.paste_key)
        self.key_entry.bind("<Button-3>", self.show_context_menu) # ПКМ

        # Меню ПКМ
        self.context_menu = tk.Menu(self, tearoff=0, bg="#2b2b2b", fg="white")
        self.context_menu.add_command(label="Paste", command=lambda: self.paste_key(None))
        self.context_menu.add_command(label="Clear", command=lambda: self.key_entry.delete(0, "end"))

        # Кнопка
        self.login_btn = ctk.CTkButton(self.login_frame, text="ACTIVATE", command=self.do_login, 
                                       width=180, height=45, font=("Arial", 14, "bold"), 
                                       fg_color=COLOR_BTN, hover_color=COLOR_BTN_HOVER, border_width=1, border_color=COLOR_BORDER)
        self.login_btn.pack(pady=15)

        # Статус
        self.status_lbl = ctk.CTkLabel(self.login_frame, text="", font=("Arial", 12))
        self.status_lbl.pack()

        # Футер
        footer_frame = ctk.CTkFrame(self.login_frame, fg_color="transparent")
        footer_frame.pack(pady=(40, 0))
        
        tg_lbl = ctk.CTkLabel(footer_frame, text="Get Key: t.me/pulzeOPT", font=("Consolas", 12, "underline"), text_color=COLOR_ACCENT, cursor="hand2")
        tg_lbl.pack()
        tg_lbl.bind("<Button-1>", lambda e: webbrowser.open(TG_LINK))
        
        ctk.CTkLabel(footer_frame, text="v1.0 | Protected by KeyAuth", font=("Arial", 10), text_color="#333").pack(pady=(5,0))
        
        self.license_path = os.path.join(self.base_path, "license.key")
        
        if os.path.exists(self.license_path):
            try:
                with open(self.license_path, "r") as f:
                    self.key_entry.insert(0, f.read().strip())
            except: pass

    # --- ФУНКЦИИ ВСТАВКИ ---
    def paste_key(self, event=None):
        try:
            text = self.clipboard_get()
            self.key_entry.insert("insert", text)
        except: pass
        return "break" 

    def show_context_menu(self, event):
        try: self.context_menu.tk_popup(event.x_root, event.y_root)
        finally: self.context_menu.grab_release()

    def do_login(self):
        if keyauthapp is None:
            self.status_lbl.configure(text="SECURITY LIBRARY ERROR", text_color=COLOR_RED)
            return

        key = self.key_entry.get().strip()
        if len(key) < 5: return
        
        self.status_lbl.configure(text="CONNECTING...", text_color="#FFA500")
        self.update()
        
        # KEYAUTH CHECK
        if keyauthapp.license(key):
            self.status_lbl.configure(text="FETCHING DATA...", text_color="#FFA500")
            self.update()
            
            # Получаем ссылку с сервера (теперь используем переменную install.wim)
            server_url = keyauthapp.var("install.wim")
            if server_url:
                self.cloud_url = server_url
                self.status_lbl.configure(text="SERVER DATA RECEIVED", text_color=COLOR_GREEN)
            else:
                # Используем зашифрованные данные для безопасности
                import base64
                fallback_id = base64.b64decode(FALLBACK_KEY).decode('utf-8')
                fallback_domain = base64.b64decode(FALLBACK_DOMAIN).decode('utf-8')
                self.cloud_url = f"{fallback_domain}{fallback_id}"
                self.status_lbl.configure(text="USING FALLBACK URL", text_color="#FFA500")
            
            self.update()
            self.after(800, lambda: self.status_lbl.configure(text="ACCESS GRANTED", text_color=COLOR_GREEN))
            self.after(1600, self.build_main_interface)
            
            try:
                with open(self.license_path, "w") as f: f.write(key)
            except Exception as e: 
                print(f"Error saving license: {e}")
                
            self.is_logged_in = True
        else:
            self.status_lbl.configure(text="INVALID KEY", text_color=COLOR_RED)

    def build_main_interface(self):
        self.login_frame.destroy()
        self.title("PULZE OPT INSTALLER")
        
        # Центрируем окно на экране
        self.center_window()
        
        # ИНИЦИАЛИЗАЦИЯ ПЕРЕМЕННЫХ ДЛЯ ОСНОВНОГО ОКНА
        self.available_drives = self.get_available_drives()
        self.selected_drive = None
        self.is_running = False 
        self.cancel_requested = False
        self.is_logged_in = True
        
        # ГЛАВНЫЙ UI
        self.container = ctk.CTkFrame(self, fg_color=COLOR_PANEL, border_color=COLOR_BORDER, border_width=2, corner_radius=16)
        self.container.pack(fill="both", expand=True, padx=30, pady=30)
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(1, weight=1) 

        self.header_main = ctk.CTkLabel(self.container, text="PULZE OPT INSTALLER", font=("Segoe UI", 32, "bold"), text_color=COLOR_ACCENT)
        self.header_main.grid(row=0, column=0, pady=(25, 20))

        # LOGS
        self.logs_frame = ctk.CTkFrame(self.container, fg_color="#111111", border_color=COLOR_BORDER, border_width=2, corner_radius=10)
        self.logs_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.logs_frame.grid_columnconfigure(0, weight=1)
        self.logs_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self.logs_frame, text="SYSTEM LOGS", font=("Arial", 12, "bold"), text_color="#555555").grid(row=0, column=0, pady=5)
        self.log_box = ctk.CTkTextbox(self.logs_frame, font=("Consolas", 11), fg_color=COLOR_LOG_BG, text_color=COLOR_TEXT, border_spacing=10)
        self.log_box.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        
        # Прогресс-бар с закругленными краями
        self.progress_frame = ctk.CTkFrame(self.logs_frame, fg_color="transparent", height=20)
        self.progress_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        self.progress_frame.grid_columnconfigure(0, weight=1)
        
        self.progress = ctk.CTkProgressBar(self.progress_frame, height=8, width=0, 
                                         progress_color=COLOR_ACCENT, fg_color="#222",
                                         corner_radius=4)
        self.progress.grid(row=0, column=0, sticky="ew", pady=(0, 0))
        self.progress.set(0)
        
        # Добавляем метку ETA
        self.eta_label = ctk.CTkLabel(self.progress_frame, text="ETA: --:--", font=("Arial", 10), text_color="#555555")
        self.eta_label.grid(row=1, column=0, sticky="e", padx=5, pady=(2, 0))

        # BOTTOM PANEL
        self.bottom_panel = ctk.CTkFrame(self.container, fg_color="transparent")
        self.bottom_panel.grid(row=2, column=0, padx=20, pady=(0, 25), sticky="ew")
        self.bottom_panel.grid_columnconfigure(0, weight=1)
        self.bottom_panel.grid_columnconfigure(1, weight=0)

        is_ready = bool(self.available_drives)
        btn_state = "normal" if is_ready else "disabled"
        
        self.btn_install = ctk.CTkButton(self.bottom_panel, text="УСТАНОВИТЬ", command=self.toggle_install_process, height=60, font=("Arial", 20, "bold"), fg_color=COLOR_BTN, hover_color=COLOR_BTN_HOVER, border_color=COLOR_BORDER, border_width=2, corner_radius=10, text_color="#e0f4f4", state=btn_state)
        self.btn_install.grid(row=0, column=0, sticky="ew", padx=(0, 20))

        self.disk_wrapper = ctk.CTkFrame(self.bottom_panel, fg_color="transparent", width=220)
        self.disk_wrapper.grid(row=0, column=1, sticky="e")
        
        self.disk_btn = ctk.CTkButton(self.disk_wrapper, text="Выберите диск", command=self.toggle_disk_menu, height=60, width=220, font=("Arial", 14, "bold"), fg_color=COLOR_BTN, hover_color=COLOR_BTN_HOVER, border_color=COLOR_BORDER, border_width=2, corner_radius=10, text_color="#a7bcbc")
        self.disk_btn.pack()

        if not self.available_drives:
            self.btn_install.configure(state="disabled")
            self.disk_btn.configure(text="НЕТ ДИСКОВ", text_color=COLOR_RED)

        # Меню дисков (Скрыто)
        self.disk_menu = ctk.CTkScrollableFrame(self, fg_color=COLOR_MAIN_BG, border_color=COLOR_BORDER, border_width=2, corner_radius=10, height=200, scrollbar_button_color=COLOR_BORDER, scrollbar_button_hover_color=COLOR_ACCENT)

        # Init Logs
        self.log("System Initialized.")
        self.log("✅ Access Granted.", COLOR_GREEN)
        if os.path.exists(self.wim_path) and os.path.getsize(self.wim_path) > 3 * (1024**3):
            self.log(f"[OK] Локальный WIM файл найден", COLOR_GREEN)
        else:
            self.log(f"[INFO] Режим автоматической загрузки", "#FFA500")

    def animate_header(self):
        try:
            # Инициализируем позицию в градиенте для эффекта background-position
            if not hasattr(self, 'gradient_position'):
                self.gradient_position = 0
            
            # Получаем текущий цвет из градиента в зависимости от позиции
            # Это имитирует эффект background-position из CSS
            color_index = self.gradient_position % len(SMOOTH_WAVE)
            current_color = SMOOTH_WAVE[color_index]
            
            # Обновляем цвет заголовков
            for header_widget in ['header', 'header_main']:
                if hasattr(self, header_widget) and getattr(self, header_widget).winfo_exists():
                    header = getattr(self, header_widget)
                    header.configure(text_color=current_color)
            
            # Медленно перемещаемся по градиенту для плавного перелива
            # Используем медленное изменение позиции для плавности
            self.gradient_position += 1
            
            # Плавная анимация - 100 мс между кадрами для медленного перелива
            # В CSS-примере анимация длится 10 секунд, поэтому делаем медленно
            self.after(100, self.animate_header)
        except Exception as e:
            print(f"Animation error: {e}")
            self.after(100, self.animate_header)

    def log(self, message, color=None):
        if not hasattr(self, 'log_box'): return
        if color is None: color = COLOR_TEXT
        tag_name = f"color_{color.replace('#', '')}"
        self.log_box.tag_config(tag_name, foreground=color)
        self.log_box.insert("end", f"> {message}\n", tag_name)
        self.log_box.see("end")

    def toggle_disk_menu(self):
        if self.disk_menu.winfo_ismapped(): self.disk_menu.place_forget()
        else:
            self.build_disk_menu()
            btn_x = self.disk_btn.winfo_rootx() - self.winfo_rootx()
            btn_y = self.disk_btn.winfo_rooty() - self.winfo_rooty()
            self.disk_menu.configure(width=220)
            self.disk_menu.place(x=btn_x, y=btn_y - 5, anchor="sw")
            self.disk_menu.lift()

    def build_disk_menu(self):
        for widget in self.disk_menu.winfo_children(): widget.destroy()
        ctk.CTkLabel(self.disk_menu, text=f"выберите диск (>{MIN_FREE_SPACE_GB}гб)", font=("Arial", 10), text_color="#555").pack(pady=(2, 2))
        for disk in self.available_drives:
            letter, free = disk['letter'], disk['free_gb']
            color = COLOR_TEXT if disk['is_valid'] else "#555"
            line_col = COLOR_GREEN if disk['is_valid'] else COLOR_RED
            state = "normal" if disk['is_valid'] else "disabled"
            row = ctk.CTkFrame(self.disk_menu, fg_color=line_col, height=32, corner_radius=0, border_width=0)
            row.pack(fill="x", padx=0, pady=0)
            btn = ctk.CTkButton(row, text=f"  Disk ({letter}): {free} GB free", command=lambda l=letter: self.select_disk(l), fg_color=COLOR_MAIN_BG, hover_color=COLOR_BTN_HOVER, text_color=color, anchor="w", height=32, state=state, font=("Arial", 13), corner_radius=0, border_width=0)
            btn.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=0)
            ctk.CTkFrame(self.disk_menu, height=1, fg_color=COLOR_SEPARATOR).pack(fill="x")

    def select_disk(self, letter):
        self.selected_drive = letter
        self.disk_btn.configure(text=f"Disk ({letter}): Выбран", text_color=COLOR_ACCENT, border_color=COLOR_ACCENT)
        self.disk_menu.place_forget()
        self.log(f"Target Selected: Disk {letter}", COLOR_GREEN)
        self.btn_install.configure(state="normal", border_color=COLOR_ACCENT)

    def get_available_drives(self):
        drives_list = []
        try:
            for p in psutil.disk_partitions():
                if 'cdrom' in p.opts or p.fstype == '': continue
                try:
                    free_gb = int(psutil.disk_usage(p.mountpoint).free / (1024**3))
                    drives_list.append({'letter': p.device[0], 'free_gb': free_gb, 'is_valid': free_gb >= MIN_FREE_SPACE_GB})
                except: pass
        except: pass
        drives_list.sort(key=lambda x: x['free_gb'], reverse=True)
        return drives_list

    def toggle_install_process(self):
        btn_text = self.btn_install.cget("text")
        if btn_text == "ПЕРЕЗАГРУЗИТЬ": self.reboot_pc()
        elif self.is_running:
            self.cancel_requested = True
            self.log("[WARN] Запрос на отмену...", COLOR_RED)
            self.btn_install.configure(text="ОТМЕНА...", fg_color=COLOR_RED)
        elif btn_text in ("УСТАНОВИТЬ", "СБРОС / ОШИБКА"):
            self.cancel_requested = False
            # Кнопка ОТМЕНА теперь активна во время установки
            self.btn_install.configure(state="normal", text="ОТМЕНА", fg_color=COLOR_RED, hover_color="#880000", text_color="white")
            self.disk_btn.configure(state="disabled")
            self.start_thread()

    def start_thread(self):
        if not self.selected_drive:
            self.log("[ERROR] ОШИБКА: Сначала выберите диск!", COLOR_RED)
            return
        self.is_running = True
        self.progress.set(0)
        threading.Thread(target=self.main_logic).start()

    def main_logic(self):
        # Устанавливаем флаг запущенной установки
        self.installation_running = True
        
        # Сохраняем состояние установки
        if ENHANCEMENTS_AVAILABLE and hasattr(self, 'enhancements'):
            self.enhancements.save_installation_state("start", 0, drive=self.selected_drive)
            
        drive = self.selected_drive
        # Сохраняем информацию о текущем этапе для отката
        self.current_stage = "init"
        self.target_drive_letter = None
        
        # Проверяем отмену перед началом
        if self.cancel_requested: 
            self.cleanup_and_reset("ОТМЕНЕНО")
            return
            
        # 1. DOWNLOAD / CHECK LOCAL
        self.current_stage = "check_wim"
        
        # Сохраняем состояние установки
        if ENHANCEMENTS_AVAILABLE and hasattr(self, 'enhancements'):
            self.enhancements.save_installation_state("check_wim", 5, drive=self.selected_drive)
            
        self.log(f"[SEARCH] Проверка наличия WIM файла", "#555")
        wim_exists = os.path.exists(self.wim_path)
        
        # Если файл не найден - ищем во всех местах
        if not wim_exists:
            self.log(f"[WARN] WIM not found at default path, searching...", "#FFA500")
            found_path = self.find_wim_file()
            if found_path and os.path.exists(found_path):
                wim_size_check = os.path.getsize(found_path)
                if wim_size_check > 3 * (1024**3):
                    self.wim_path = found_path
                    wim_exists = True
                    self.log(f"[OK] Найден валидный WIM файл ({wim_size_check / (1024**3):.2f} GB)", COLOR_GREEN)
        
        if wim_exists:
            try:
                wim_size = os.path.getsize(self.wim_path)
                wim_size_gb = wim_size / (1024**3)
                self.log(f"[INFO] Локальный WIM файл найден: {wim_size_gb:.2f} GB", "#FFA500")
                
                # Проверяем валидность локального файла (не только размер!)
                if wim_size > 3 * (1024**3):  # Минимум 3 ГБ
                    # Проверяем валидность через DISM
                    try:
                        check_cmd = f'dism /Get-WimInfo /WimFile:"{self.wim_path}"'
                        p = subprocess.Popen(check_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        out, err = p.communicate(timeout=30)
                        if p.returncode == 0:
                            self.log(f"[OK] Локальный образ валиден, используем его.", COLOR_GREEN)
                        else:
                            self.log(f"[WARN] Не удалось проверить индекс образа, скачиваем заново...", COLOR_RED)
                            wim_exists = False  # Принудительно скачиваем
                    except Exception as e:
                        self.log(f"[WARN] Не удалось проверить локальный файл: {e}, скачиваем...", COLOR_RED)
                        wim_exists = False
                else:
                    self.log(f"[WARN] Файл слишком мал ({wim_size_gb:.2f} GB), скачиваем...", COLOR_RED)
                    wim_exists = False
            except Exception as e:
                self.log(f"[ERROR] Ошибка при проверке файла: {e}", COLOR_RED)
                wim_exists = False
        else:
            self.log(f"[INFO] Локальный файл не найден", "#FFA500")
        
        if not wim_exists:
            # Проверяем, авторизован ли пользователь через KeyAuth
            if not self.is_logged_in or keyauthapp is None:
                self.log(f"[ERROR] ОШИБКА: Требуется авторизация для скачивания образа", COLOR_RED)
                self.cleanup_and_reset("ОШИБКА АВТОРИЗАЦИИ"); return
            
            self.log(f"[DOWNLOAD] ЗАГРУЗКА ОБРАЗА (Cloud)...", "#FFA500")
            
            # Получаем ссылку с KeyAuth сервера
            wim_url = keyauthapp.var("install.wim")
            if not wim_url:
                self.log(f"[WARN] Не удалось получить ссылку с сервера, используем запасную", "#FFA500")
                # Используем зашифрованные данные для безопасности
                import base64
                fallback_id = base64.b64decode(FALLBACK_KEY).decode('utf-8')
                fallback_domain = base64.b64decode(FALLBACK_DOMAIN).decode('utf-8')
                wim_url = getattr(self, 'cloud_url', None) or f"{fallback_domain}{fallback_id}"
            else:
                self.log(f"[OK] Получена ссылка с сервера KeyAuth", COLOR_GREEN)
            
            # Используем правильный путь для скачивания (C:\Windows\Temp)
            download_path = os.path.join('C:', 'Windows', 'Temp', WIM_NAME)
            
            # Проверяем доступность директории и создаем её при необходимости
            try:
                os.makedirs(os.path.dirname(download_path), exist_ok=True)
                self.log(f"[INFO] Директория для скачивания: {os.path.dirname(download_path)}", "#555")
            except Exception as e:
                self.log(f"[ERROR] Не удалось создать директорию: {e}", COLOR_RED)
                # Пробуем использовать пользовательский TEMP
                download_path = os.path.join(os.environ.get('TEMP', ''), WIM_NAME)
                try:
                    os.makedirs(os.path.dirname(download_path), exist_ok=True)
                    self.log(f"[INFO] Используем альтернативную директорию: {os.path.dirname(download_path)}", "#FFA500")
                except Exception as e2:
                    self.log(f"[ERROR] Не удалось создать директорию: {e2}", COLOR_RED)
                    self.cleanup_and_reset("ОШИБКА ДОСТУПА"); return
            
            self.log(f"[DOWNLOAD] Скачивание WIM файла...", "#FFA500")
            self.log(f"[INFO] Подготовка к сохранению...", "#555")
            
            if not self.download_file_direct(wim_url, download_path):
                self.cleanup_and_reset("ОШИБКА СЕТИ"); return
            
            # Проверяем размер скачанного файла
            try:
                size = os.path.getsize(download_path)
                size_gb = size / (1024**3)
                self.log(f"[INFO] Размер скачанного файла: {size_gb:.2f} GB", "#555")
                
                if size < 3 * (1024**3):
                    self.log(f"[ERROR] Скачанный файл слишком маленький: {size_gb:.2f} GB (ожидалось > 3.0 GB)", COLOR_RED)
                    try:
                        os.remove(download_path)
                        self.log(f"[DELETE] Удален поврежденный файл", "#555")
                    except: pass
                    self.cleanup_and_reset("ОШИБКА СКАЧИВАНИЯ"); return
            except Exception as e:
                self.log(f"[ERROR] Ошибка проверки размера файла: {e}", COLOR_RED)
            
            # Обновляем путь к WIM файлу
            self.wim_path = download_path
            self.log(f"[OK] WIM файл успешно скачан", COLOR_GREEN)
        
        if self.cancel_requested: self.cleanup_and_reset("ОТМЕНЕНО"); return

        # 2. DISKPART
        self.current_stage = "diskpart"
        
        # Сохраняем состояние установки
        if ENHANCEMENTS_AVAILABLE and hasattr(self, 'enhancements'):
            self.enhancements.save_installation_state("diskpart", 20, drive=self.selected_drive)
            
        # Сбрасываем прогресс-бар и метку ETA
        self.progress.set(0)
        self.eta_label.configure(text="Подготовка диска...")
        self.log("[DISK] РАЗБИВКА ДИСКА...", "#FFA500")
        target_drive = self.run_diskpart_script(drive)
        if not target_drive: 
            self.log("[ERROR] Ошибка Diskpart.", COLOR_RED)
            self.cleanup_and_reset()
            return
            
        # Сохраняем информацию о целевом диске для отката
        self.target_drive_letter = target_drive
            
        self.log(f"[OK] Раздел создан: {target_drive}", COLOR_GREEN)
        
        # Проверяем доступность диска
        try:
            # Проверяем, что диск существует
            if not os.path.exists(target_drive):
                self.log(f"[ERROR] Диск {target_drive} не существует после создания!", COLOR_RED)
                self.cleanup_and_reset("ОШИБКА ДОСТУПА")
                return
                
            # Проверяем доступ на запись
            test_file = os.path.join(target_drive, "test_access.tmp")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            self.log(f"[OK] Диск {target_drive} доступен для записи", COLOR_GREEN)
        except Exception as e:
            self.log(f"[ERROR] Проблема с доступом к диску {target_drive}: {e}", COLOR_RED)
            self.cleanup_and_reset("ОШИБКА ДОСТУПА")
            return

        if self.cancel_requested: self.cleanup_and_reset("ОТМЕНЕНО"); return

        # 3. DISM
        self.current_stage = "dism"
        
        # Сохраняем состояние установки
        if ENHANCEMENTS_AVAILABLE and hasattr(self, 'enhancements'):
            self.enhancements.save_installation_state("apply_image", 40, drive=target_drive)
            
        # Сбрасываем прогресс-бар и метку ETA
        self.progress.set(0)
        self.eta_label.configure(text="Подготовка к установке...")
        self.log("[INSTALL] УСТАНОВКА WINDOWS...", "#FFA500")
        result = self.apply_image(target_drive)
        if result == "cancel":
            self.log("[INFO] Отмена установки пользователем", "#FFA500")
            self.cleanup_and_reset("ОТМЕНЕНО")
            return
        elif not result:
            self.log("[ERROR] Ошибка DISM.", COLOR_RED)
            self.cleanup_and_reset()
            return

        if self.cancel_requested: self.cleanup_and_reset("ОТМЕНЕНО"); return
        
        # Проверяем доступность диска после установки образа
        self.log(f"[CHECK] Проверка доступа к диску {target_drive} после установки...", "#555")
        try:
            # Проверяем, что диск существует
            if not os.path.exists(target_drive):
                self.log(f"[ERROR] Диск {target_drive} не существует после установки образа!", COLOR_RED)
                self.cleanup_and_reset("ОШИБКА ДОСТУПА")
                return
                
            # Проверяем доступ на запись
            test_file = os.path.join(target_drive, "test_access_after_wim.tmp")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            self.log(f"[OK] Диск {target_drive} доступен для записи после установки", COLOR_GREEN)
        except Exception as e:
            self.log(f"[ERROR] Проблема с доступом к диску {target_drive} после установки: {e}", COLOR_RED)
            self.cleanup_and_reset("ОШИБКА ДОСТУПА")
            return

        # 4. COPY & BOOT
        self.current_stage = "copy"
        
        # Сохраняем состояние установки
        if ENHANCEMENTS_AVAILABLE and hasattr(self, 'enhancements'):
            self.enhancements.save_installation_state("copy_files", 70, drive=target_drive)
            
        # Сбрасываем прогресс-бар и метку ETA
        self.progress.set(0)
        self.eta_label.configure(text="Подготовка к копированию...")
        self.log("[COPY] КОПИРОВАНИЕ ФАЙЛОВ...", "#FFA500")
        
        # Проверяем существование целевого диска перед копированием
        if not os.path.exists(target_drive):
            self.log(f"[ERROR] Целевой диск {target_drive} не существует!", COLOR_RED)
            return
            
        # Копируем файлы PULZE
        if self.copy_puls_files(target_drive):
            self.log("[OK] Файлы PULZE успешно скопированы", COLOR_GREEN)
        else:
            self.log("[ERROR] Ошибка при копировании файлов PULZE", COLOR_RED)
        
        # Копируем лицензионный ключ
        try: 
            # Проверяем существование исходного файла
            if not os.path.exists(self.license_path):
                self.log(f"[WARN] Файл лицензии не найден: {self.license_path}", COLOR_RED)
                # Создаем пустой файл вместо возврата
                with open(self.license_path, "w") as f:
                    f.write("")
                self.log(f"[INFO] Создан пустой файл лицензии", "#FFA500")
                
            # Проверяем существование папки PULZE на целевом диске
            pulze_dir = os.path.join(target_drive, "PULZE")
            if not os.path.exists(pulze_dir):
                self.log(f"[INFO] Создаем папку {pulze_dir}", "#555")
                os.makedirs(pulze_dir, exist_ok=True)
                
            # Копируем лицензию
            license_dest = os.path.join(pulze_dir, "license.key")
            shutil.copy(self.license_path, license_dest)
            
            # Проверяем, что файл успешно скопирован
            if os.path.exists(license_dest):
                # Проверяем размер файла
                src_size = os.path.getsize(self.license_path)
                dst_size = os.path.getsize(license_dest)
                if dst_size == src_size:
                    self.log(f"[OK] Лицензия успешно сохранена в {license_dest} ({dst_size} байт)", COLOR_GREEN)
                else:
                    self.log(f"[WARN] Размеры файлов лицензий не совпадают: {src_size} -> {dst_size}", "#FFA500")
            else:
                self.log(f"[ERROR] Файл лицензии не был создан: {license_dest}", COLOR_RED)
                # Пробуем создать файл вручную
                try:
                    with open(license_dest, "w") as f:
                        with open(self.license_path, "r") as src_f:
                            f.write(src_f.read())
                    self.log(f"[OK] Лицензия создана вручную", COLOR_GREEN)
                except Exception as e2:
                    self.log(f"[ERROR] Не удалось создать файл лицензии вручную: {e2}", COLOR_RED)
        except Exception as e: 
            self.log(f"[ERROR] Не удалось сохранить лицензию: {e}", COLOR_RED)

        # Финальный этап - настройка загрузчика
        self.current_stage = "bootloader"
        
        # Сохраняем состояние установки
        if ENHANCEMENTS_AVAILABLE and hasattr(self, 'enhancements'):
            self.enhancements.save_installation_state("setup_boot", 90, drive=target_drive)
            
        if self.cancel_requested: self.cleanup_and_reset("ОТМЕНЕНО"); return
        
        if self.setup_boot_safe(target_drive):
            self.current_stage = "complete"
            self.log("[SUCCESS] УСПЕХ! ПЕРЕЗАГРУЗИТЕСЬ.", COLOR_GREEN)
            self.btn_install.configure(state="normal", text="ПЕРЕЗАГРУЗИТЬ", fg_color=COLOR_GREEN, text_color="black", command=self.reboot_pc)
            
            # Устанавливаем флаг завершения установки
            self.installation_running = False
            self.installation_completed = True
            
            # Показываем руководство после установки
            if ENHANCEMENTS_AVAILABLE and hasattr(self, 'enhancements'):
                self.enhancements._show_post_install_guide()
        else: 
            self.log("[ERROR] Ошибка BCDBOOT.", COLOR_RED)
            self.cleanup_and_reset()

    def cleanup_and_reset(self, reason="СБОЙ"):
        """Clean up and reset the installation process"""
        self.is_running = False
        
        # Сбрасываем флаг запущенной установки
        self.installation_running = False
        
        self.log(f"[STOP] {reason}", COLOR_RED)
        
        # Если отмена пользователем, пытаемся откатить изменения
        if reason == "ОТМЕНЕНО":
            self.log(f"[ROLLBACK] Попытка отката изменений на этапе: {getattr(self, 'current_stage', 'неизвестно')}", "#FFA500")
            
            # Получаем целевой диск
            target_drive = getattr(self, 'target_drive_letter', None)
            if not target_drive and hasattr(self, 'selected_drive'):
                # Пытаемся определить целевой диск
                target_drive = "Z:"
            
            # Проверяем создание раздела Z:
            try:
                if target_drive and os.path.exists(target_drive):
                    # Пытаемся удалить раздел через diskpart
                    drive_letter = target_drive.strip(':\\/')
                    self.log(f"[ROLLBACK] Удаление раздела {drive_letter}:", "#FFA500")
                    
                    # Сначала пытаемся отмонтировать раздел
                    try:
                        os.system(f'mountvol {target_drive} /D')
                        self.log(f"[ROLLBACK] Раздел {drive_letter}: отмонтирован", "#FFA500")
                    except:
                        pass
                    
                    # Проверяем службу виртуальных дисков перед запуском diskpart
                    try:
                        self.log("[ROLLBACK] Проверка службы виртуальных дисков...", "#FFA500")
                        p_check = subprocess.run('sc query vds', shell=True, capture_output=True, timeout=10)
                        output = self.safe_decode(p_check.stdout)
                        
                        if "RUNNING" not in output:
                            self.log("[ROLLBACK] Запуск службы Virtual Disk...", "#FFA500")
                            subprocess.run('sc start vds', shell=True, capture_output=True, timeout=20)
                            time.sleep(2)  # Даем время на запуск
                    except Exception as e:
                        self.log(f"[ROLLBACK] Ошибка при проверке службы VDS: {e}", "#FFA500")
                    
                    # Затем удаляем раздел через diskpart
                    rollback_script = f"select volume {drive_letter}\ndelete volume\nexit"
                    with open("rollback.txt", "w") as f:
                        f.write(rollback_script)
                    
                    # Запускаем diskpart для отката
                    try:
                        # Добавляем задержку перед запуском diskpart
                        time.sleep(1)
                        
                        self.log("[ROLLBACK] Запуск diskpart для удаления раздела...", "#FFA500")
                        p = subprocess.run('diskpart /s rollback.txt', shell=True, capture_output=True, timeout=30)
                        if p.returncode == 0:
                            self.log(f"[ROLLBACK] Раздел {drive_letter}: успешно удален", COLOR_GREEN)
                        else:
                            error_output = self.safe_decode(p.stderr)
                            self.log(f"[ROLLBACK] Ошибка при удалении раздела: {error_output}", COLOR_RED)
                            
                            # Проверяем на ошибку службы виртуальных дисков
                            if "служб" in error_output.lower() and "вирт" in error_output.lower():
                                self.log("[ROLLBACK] Попытка перезапуска службы Virtual Disk...", "#FFA500")
                                try:
                                    # Перезапускаем службу и пробуем снова
                                    subprocess.run('sc stop vds', shell=True, capture_output=True, timeout=20)
                                    time.sleep(2)
                                    subprocess.run('sc start vds', shell=True, capture_output=True, timeout=20)
                                    time.sleep(3)
                                    
                                    # Пробуем снова
                                    self.log("[ROLLBACK] Повторная попытка удаления раздела...", "#FFA500")
                                    p2 = subprocess.run('diskpart /s rollback.txt', shell=True, capture_output=True, timeout=30)
                                    if p2.returncode == 0:
                                        self.log(f"[ROLLBACK] Раздел {drive_letter}: успешно удален со второй попытки", COLOR_GREEN)
                                except Exception as e2:
                                    self.log(f"[ROLLBACK] Ошибка при повторной попытке: {e2}", COLOR_RED)
                    except Exception as e:
                        self.log(f"[ROLLBACK] Ошибка при запуске diskpart: {e}", COLOR_RED)
                        
                        # Проверяем, не связана ли ошибка со службой виртуальных дисков
                        error_str = str(e).lower()
                        if "virt" in error_str or "disk" in error_str or "vds" in error_str or "вирт" in error_str or "диск" in error_str:
                            self.log("[ROLLBACK] Обнаружена ошибка службы виртуальных дисков", "#FFA500")
                            try:
                                # Перезапускаем службу
                                subprocess.run('sc stop vds', shell=True, capture_output=True, timeout=20)
                                time.sleep(2)
                                subprocess.run('sc start vds', shell=True, capture_output=True, timeout=20)
                                time.sleep(3)
                                self.log("[ROLLBACK] Служба Virtual Disk перезапущена", "#FFA500")
                            except Exception as e2:
                                self.log(f"[ROLLBACK] Ошибка при перезапуске службы: {e2}", COLOR_RED)
                    
                    # Удаляем временный файл
                    try:
                        os.remove("rollback.txt")
                    except:
                        pass
                        
                # Проверяем наличие других изменений для отката
                current_stage = getattr(self, 'current_stage', '')
                if current_stage in ['dism', 'copy', 'bootloader']:
                    # Если мы уже применили образ, то нужно удалить запись в BCD
                    self.log("[ROLLBACK] Попытка удалить запись в загрузчике...", "#FFA500")
                    try:
                        # Удаляем запись в загрузчике по имени
                        os.system('bcdedit /delete {current} /cleanup')
                        self.log("[ROLLBACK] Запись в загрузчике удалена", COLOR_GREEN)
                    except Exception as e:
                        self.log(f"[ROLLBACK] Ошибка при удалении записи в загрузчике: {e}", COLOR_RED)
            except Exception as e:
                self.log(f"[ROLLBACK] Ошибка при откате изменений: {e}", COLOR_RED)
        
        # Восстанавливаем интерфейс
        self.btn_install.configure(state="normal", text="СБРОС / ОШИБКА", fg_color=COLOR_RED)
        self.disk_btn.configure(state="normal")
        
        # НЕ УДАЛЯЕМ WIM файл - он может быть рабочим и нужен для повторной попытки
        # try: os.remove(self.wim_path)
        # except: pass

    def safe_decode(self, b):
        if not b: return ""
        try: return b.decode('cp866').strip()
        except: return b.decode('utf-8', errors='ignore').strip()

    def download_file_direct(self, url, destination):
        try:
            response = requests.get(url, stream=True, timeout=20)
            total = int(response.headers.get('content-length', 0))
            dl = 0
            start_time = time.time()
            last_update = 0
            
            with open(destination, "wb") as f:
                for chunk in response.iter_content(32768):
                    if self.cancel_requested: return False
                    if chunk: 
                        f.write(chunk); dl += len(chunk)
                        if total: 
                            progress = dl/total
                            self.progress.set(progress)
                            
                            # Обновляем ETA каждые 0.5 секунды
                            current_time = time.time()
                            if current_time - last_update > 0.5:
                                # Рассчитываем ETA
                                elapsed = current_time - start_time
                                if progress > 0:
                                    eta_seconds = elapsed / progress - elapsed
                                    if eta_seconds < 60:
                                        eta_text = f"ETA: {int(eta_seconds)} сек"
                                    elif eta_seconds < 3600:
                                        eta_text = f"ETA: {int(eta_seconds/60)}:{int(eta_seconds%60):02d} мин"
                                    else:
                                        eta_text = f"ETA: {int(eta_seconds/3600)}:{int((eta_seconds%3600)/60):02d} ч"
                                    
                                    # Добавляем скорость скачивания
                                    speed = dl / elapsed / 1024 / 1024  # В МБ/с
                                    self.eta_label.configure(text=f"ETA: {eta_text} ({speed:.1f} МБ/с)")
                                
                                last_update = current_time
                                self.update_idletasks()
            
            # По завершении скачивания
            self.eta_label.configure(text="Загрузка завершена")
            return True
        except Exception as e:
            self.log(f"[ERROR] Ошибка скачивания: {e}", COLOR_RED)
            return False

    def run_diskpart_script(self, source_drive):
        # Проверяем свободное место на диске перед сжатием
        try:
            import shutil
            free_space_gb = shutil.disk_usage(f"{source_drive}:\\").free / (1024**3)
            self.log(f"[INFO] Free space on {source_drive}: {free_space_gb:.2f} GB", "#555")
            if free_space_gb < INSTALL_SIZE_GB:
                self.log(f"[ERROR] Not enough free space! Need {INSTALL_SIZE_GB} GB, have {free_space_gb:.2f} GB", COLOR_RED)
                return None
                
            # Проверяем службу виртуальных дисков
            self.log("[CHECK] Проверка службы виртуальных дисков...", "#555")
            try:
                # Проверяем статус службы Virtual Disk
                p = subprocess.run('sc query vds', shell=True, capture_output=True, timeout=10)
                output = self.safe_decode(p.stdout)
                
                # Перезапускаем службу в любом случае
                self.log("[INFO] Перезапуск службы Virtual Disk...", "#FFA500")
                # Останавливаем службу
                subprocess.run('sc stop vds', shell=True, capture_output=True, timeout=20)
                time.sleep(3)  # Даем больше времени на остановку
                # Запускаем службу
                subprocess.run('sc start vds', shell=True, capture_output=True, timeout=20)
                time.sleep(5)  # Даем больше времени на запуск
                
                # Проверяем снова
                p = subprocess.run('sc query vds', shell=True, capture_output=True, timeout=10)
                output = self.safe_decode(p.stdout)
                if "RUNNING" in output:
                    self.log("[OK] Служба Virtual Disk успешно запущена", COLOR_GREEN)
                else:
                    # Еще одна попытка с использованием net start
                    self.log("[RETRY] Повторная попытка запуска службы...", "#FFA500")
                    subprocess.run('net stop vds', shell=True, capture_output=True, timeout=20)
                    time.sleep(3)
                    subprocess.run('net start vds', shell=True, capture_output=True, timeout=20)
                    time.sleep(5)
                    
                    # Проверяем еще раз
                    p = subprocess.run('sc query vds', shell=True, capture_output=True, timeout=10)
                    output = self.safe_decode(p.stdout)
                    if "RUNNING" in output:
                        self.log("[OK] Служба Virtual Disk успешно запущена со второй попытки", COLOR_GREEN)
                    else:
                        self.log("[WARN] Не удалось запустить службу Virtual Disk", "#FFA500")
            except Exception as e:
                self.log(f"[WARN] Ошибка при проверке службы Virtual Disk: {e}", "#FFA500")
                
            # Даем дополнительное время для стабилизации службы
            time.sleep(3)
        except Exception as e:
            self.log(f"[WARN] Could not check disk space: {e}", COLOR_RED)
        
        # minimum должен быть меньше desired, чтобы избежать ошибки "слишком большая степень сжатия"
        # Используем 80% от desired как minimum
        desired_mb = INSTALL_SIZE_GB * 1024
        minimum_mb = int(desired_mb * 0.8)  # 80% от desired
        
        s = f"select volume {source_drive}\nshrink desired={desired_mb} minimum={minimum_mb}\ncreate partition primary\nformat fs=ntfs quick label=\"PULZE_OS\"\nassign letter=Z\nexit"
        with open("dp.txt", "w") as f: f.write(s)
        try:
            # Добавляем задержку перед запуском diskpart для устранения проблем со службой виртуальных дисков
            time.sleep(1)
            
            # Запускаем diskpart с повышенным таймаутом
            self.log("[DISK] Запуск diskpart...", "#555")
            p = subprocess.Popen('diskpart /s dp.txt', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Читаем вывод с обработкой ошибок
            for line in p.stdout:
                if self.cancel_requested: p.terminate(); return None
                decoded = self.safe_decode(line)
                if decoded: 
                    self.log(f"Diskpart: {decoded}", "#555")
                    # Показываем ошибки красным
                    if "ошибка" in decoded.lower() or "error" in decoded.lower() or "служб" in decoded.lower() and "вирт" in decoded.lower():
                        self.log(f"[ERROR] {decoded}", COLOR_RED)
                        
                        # Если обнаружена ошибка службы виртуальных дисков
                        if "служб" in decoded.lower() and "вирт" in decoded.lower():
                            self.log("[RETRY] Попытка перезапуска службы Virtual Disk...", "#FFA500")
                            try:
                                # Перезапускаем службу
                                subprocess.run('sc stop vds', shell=True, capture_output=True, timeout=20)
                                time.sleep(2)
                                subprocess.run('sc start vds', shell=True, capture_output=True, timeout=20)
                                time.sleep(3)
                                self.log("[INFO] Служба Virtual Disk перезапущена", "#FFA500")
                            except Exception as e:
                                self.log(f"[ERROR] Ошибка при перезапуске службы: {e}", COLOR_RED)
                    self.update_idletasks()
            p.wait()
            
            # Читаем stderr для дополнительной информации об ошибках
            err_data = p.stderr.read()
            if err_data:
                err_decoded = self.safe_decode(err_data)
                if err_decoded:
                    self.log(f"Diskpart STDERR: {err_decoded}", COLOR_RED)
            
            os.remove("dp.txt")
            return "Z:" if p.returncode == 0 else None
        except Exception as e:
            self.log(f"[ERROR] Diskpart exception: {e}", COLOR_RED)
            
            # Проверяем, не связана ли ошибка со службой виртуальных дисков
            error_str = str(e).lower()
            if "virt" in error_str or "disk" in error_str or "vds" in error_str or "вирт" in error_str or "диск" in error_str:
                self.log("[RETRY] Обнаружена ошибка службы виртуальных дисков. Попытка восстановления...", "#FFA500")
                try:
                    # Перезапускаем службу и пытаемся снова
                    subprocess.run('sc stop vds', shell=True, capture_output=True, timeout=20)
                    time.sleep(2)
                    subprocess.run('sc start vds', shell=True, capture_output=True, timeout=20)
                    time.sleep(3)
                    
                    # Пробуем запустить diskpart снова
                    self.log("[RETRY] Повторная попытка запуска diskpart...", "#FFA500")
                    p2 = subprocess.run('diskpart /s dp.txt', shell=True, capture_output=True, timeout=60)
                    
                    if p2.returncode == 0:
                        self.log("[OK] Повторная попытка успешна!", COLOR_GREEN)
                        try: os.remove("dp.txt")
                        except: pass
                        return "Z:"
                    else:
                        self.log(f"[ERROR] Повторная попытка также неудачна: {self.safe_decode(p2.stderr)}", COLOR_RED)
                except Exception as e2:
                    self.log(f"[ERROR] Ошибка при повторной попытке: {e2}", COLOR_RED)
            
            try: os.remove("dp.txt")
            except: pass
            return None

    def get_wim_index(self):
        """Получает первый доступный индекс из WIM файла"""
        try:
            cmd = f'dism /Get-WimInfo /WimFile:"{self.wim_path}"'
            p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = p.communicate(timeout=30)
            info = self.safe_decode(out)
            
            # Проверяем успешность выполнения команды
            if p.returncode != 0:
                self.log(f"[WARN] DISM не смог получить информацию о WIM файле, используем индекс 1", COLOR_RED)
                return 1
                
            # Ищем все индексы
            indexes = re.findall(r'Index\s*:\s*(\d+)', info)
            if indexes:
                index = int(indexes[0])  # Берем первый найденный индекс
                self.log(f"[OK] WIM Index found: {index}", COLOR_GREEN)
                return index
            else:
                # Если индексы не найдены, но команда выполнилась успешно, используем индекс 1
                self.log("[WARN] No index found, using default: 1", "#FFA500")
                return 1
        except Exception as e:
            self.log(f"[WARN] WIM Check Error: {e}, using default index: 1", "#FFA500")
            return 1

    def apply_image(self, drive):
        """
        Применяет WIM-образ к диску
        Возвращает:
        - True в случае успеха
        - False в случае ошибки
        - "cancel" в случае отмены пользователем
        """
        try:
            # Проверяем отмену перед началом
            if self.cancel_requested:
                return "cancel"
                
            # 1. Проверяем существование файла и его размер
            self.log(f"[SEARCH] Проверка наличия WIM файла", "#555")
            if not os.path.exists(self.wim_path):
                self.log(f"[ERROR] WIM файл не найден", COLOR_RED)
                self.log(f"[SEARCH] Searching for WIM in all possible locations...", "#FFA500")
                # Используем функцию поиска
                found_path = self.find_wim_file()
                if found_path and os.path.exists(found_path):
                    wim_size_alt = os.path.getsize(found_path) / (1024**3)
                    self.log(f"[OK] Found valid WIM file ({wim_size_alt:.2f} GB)", COLOR_GREEN)
                    self.wim_path = found_path
                else:
                    self.log(f"[ERROR] WIM файл не найден нигде!", COLOR_RED)
                    return False
            
            wim_size = os.path.getsize(self.wim_path) / (1024**3)  # GB
            wim_size_bytes = os.path.getsize(self.wim_path)
            self.log(f"[INFO] Размер WIM файла: {wim_size:.2f} GB", "#555")
            
            # Проверяем, что файл имеет достаточный размер (минимум 3 ГБ)
            if wim_size < 3.0:
                self.log(f"[ERROR] WIM файл слишком маленький: {wim_size:.2f} GB (требуется > 3.0 GB)", COLOR_RED)
                self.log(f"   Проверьте наличие WIM файла", COLOR_RED)
                return False
            else:
                self.log(f"[OK] WIM файл имеет достаточный размер: {wim_size:.2f} GB", COLOR_GREEN)
            
            # 2. Получаем индекс из WIM
            wim_index = self.get_wim_index()
            
            # 3. Проверяем свободное место на диске
            try:
                free_space = shutil.disk_usage(drive).free / (1024**3)  # GB
                self.log(f"[INFO] Free space on {drive}: {free_space:.2f} GB", "#555")
                if free_space < wim_size * 0.5:  # Нужно минимум 50% от размера WIM
                    self.log(f"[WARN] Low disk space! Need ~{wim_size * 0.5:.2f} GB", COLOR_RED)
            except:
                pass
            
            # 4. Проверяем, что диск существует и доступен
            if not os.path.exists(drive):
                self.log(f"[ERROR] Drive {drive} does not exist!", COLOR_RED)
                return False
            
            # 5. Пробуем DISM БЕЗ /CheckIntegrity (может вызывать проблемы)
            self.log(f"[APPLY] Применение WIM образа (Index {wim_index})...", "#FFA500")
            cmd = f'dism /Apply-Image /ImageFile:"{self.wim_path}" /Index:{wim_index} /ApplyDir:{drive}\\'
            self.log(f"[INFO] Подготовка к распаковке...", "#333")
            
            # Запускаем с кодировкой cp866 для правильного отображения русского
            p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            output_lines = []
            error_lines = []
            
            # Читаем stdout (проценты)
            start_time = time.time()
            last_update = 0
            last_progress = 0
            self.eta_label.configure(text="Подготовка к распаковке...")
            
            while True:
                if self.cancel_requested: 
                    self.log("[CANCEL] Отмена применения образа по запросу пользователя", "#FFA500")
                    p.terminate()
                    return "cancel"
                    
                line = p.stdout.readline()
                if not line and p.poll() is not None: 
                    break
                    
                if line:
                    decoded = self.safe_decode(line)
                    output_lines.append(decoded)
                    
                    # Обрабатываем прогресс
                    if "%" in decoded:
                        # Парсим процент из строки
                        try:
                            percent_str = re.search(r'(\d+\.?\d*)%', decoded)
                            if percent_str:
                                progress = float(percent_str.group(1)) / 100
                                if progress > 0 and abs(progress - last_progress) > 0.01:  # Обновляем если изменилось на 1%
                                    self.progress.set(progress)
                                    last_progress = progress
                                    
                                    # Обновляем ETA каждые 0.5 секунд
                                    current_time = time.time()
                                    if current_time - last_update > 0.5:
                                        # Рассчитываем ETA
                                        elapsed = current_time - start_time
                                        eta_seconds = elapsed / progress - elapsed
                                        
                                        if eta_seconds < 60:
                                            eta_text = f"ETA: {int(eta_seconds)} сек"
                                        elif eta_seconds < 3600:
                                            eta_text = f"ETA: {int(eta_seconds/60)}:{int(eta_seconds%60):02d} мин"
                                        else:
                                            eta_text = f"ETA: {int(eta_seconds/3600)}:{int((eta_seconds%3600)/60):02d} ч"
                                            
                                        self.eta_label.configure(text=f"{eta_text} - Распаковка {int(progress*100)}%")
                                        last_update = current_time
                        except:
                            pass
                            
                        # Показываем только строки с прогрессом
                        self.log(f"[PROGRESS] Распаковка: {decoded.strip()}", "#FFA500")
                        self.update_idletasks()
            
            # Читаем stderr (ошибки)
            err_data = p.stderr.read()
            if err_data:
                err_decoded = self.safe_decode(err_data)
                error_lines = [l for l in err_decoded.split('\n') if l.strip()]
            
            # Ждем завершения
            p.wait()
            
            # Анализ результата
            if p.returncode != 0:
                self.log(f"[ERROR] DISM failed with exit code: {p.returncode}", COLOR_RED)
                
                # Показываем последние строки stdout
                if output_lines:
                    self.log("STDOUT (last 10 lines):", COLOR_RED)
                    for line in output_lines[-10:]:
                        if line.strip():
                            self.log(f"  {line}", COLOR_RED)
                
                # Показываем stderr
                if error_lines:
                    self.log("STDERR:", COLOR_RED)
                    for line in error_lines:
                        if line.strip():
                            self.log(f"  {line}", COLOR_RED)
                
                # Проверяем, не была ли отмена пользователем
                if self.cancel_requested:
                    self.log("[CANCEL] Отмена применения образа после ошибки", "#FFA500")
                    return "cancel"
                
                # Попытка альтернативного метода (без проверки целостности, если еще не пробовали)
                if "/CheckIntegrity" not in cmd:
                    self.log("[RETRY] Trying alternative method...", "#FFA500")
                    # Пробуем еще раз с /Verify (более мягкая проверка)
                    cmd2 = f'dism /Apply-Image /ImageFile:"{self.wim_path}" /Index:{wim_index} /ApplyDir:{drive}\\ /Verify'
                    
                    # Запускаем с возможностью отмены
                    try:
                        p2 = subprocess.Popen(cmd2, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                        # Проверяем отмену во время выполнения
                        while p2.poll() is None:
                            if self.cancel_requested:
                                p2.terminate()
                                self.log("[CANCEL] Отмена альтернативного метода", "#FFA500")
                                return "cancel"
                            time.sleep(0.5)  # Проверяем каждые 0.5 секунды
                        
                        # Получаем результат
                        out, err = p2.communicate()
                        if p2.returncode == 0:
                            self.log("[OK] Alternative method succeeded!", COLOR_GREEN)
                            return True
                        else:
                            self.log(f"[ERROR] Alternative method also failed: {self.safe_decode(err)}", COLOR_RED)
                    except Exception as e:
                        self.log(f"[ERROR] Exception during alternative method: {e}", COLOR_RED)
                
                return False
            else:
                self.progress.set(1.0)  # Устанавливаем прогресс на 100%
                self.eta_label.configure(text="Распаковка завершена")
                self.log("[OK] DISM успешно завершен!", COLOR_GREEN)
                return True
                
        except subprocess.TimeoutExpired:
            self.log("[ERROR] DISM timeout (took too long)", COLOR_RED)
            # Проверяем, не была ли отмена
            if self.cancel_requested:
                return "cancel"
            return False
        except Exception as e:
            self.log(f"[ERROR] EXCEPTION: {e}", COLOR_RED)
            import traceback
            self.log(traceback.format_exc(), COLOR_RED)
            # Проверяем, не была ли отмена
            if self.cancel_requested:
                return "cancel"
            return False

    def setup_boot_safe(self, drive):
        try: 
            self.log("[CONFIG] Конфигурация Bootloader...", "#FFA500")
            
            # Проверяем и перезапускаем службу виртуальных дисков перед настройкой загрузчика
            self.log("[CHECK] Проверка службы виртуальных дисков...", "#555")
            try:
                # Проверяем статус службы Virtual Disk
                p = subprocess.run('sc query vds', shell=True, capture_output=True, timeout=10)
                output = self.safe_decode(p.stdout)
                
                # Перезапускаем службу в любом случае
                self.log("[INFO] Перезапуск службы Virtual Disk...", "#FFA500")
                # Останавливаем службу
                subprocess.run('sc stop vds', shell=True, capture_output=True, timeout=20)
                time.sleep(2)  # Даем время на остановку
                # Запускаем службу
                subprocess.run('sc start vds', shell=True, capture_output=True, timeout=20)
                time.sleep(3)  # Даем время на запуск
                
                # Проверяем снова
                p = subprocess.run('sc query vds', shell=True, capture_output=True, timeout=10)
                output = self.safe_decode(p.stdout)
                if "RUNNING" in output:
                    self.log("[OK] Служба Virtual Disk успешно запущена", COLOR_GREEN)
                else:
                    self.log("[WARN] Служба Virtual Disk не запущена после перезапуска", "#FFA500")
            except Exception as e:
                self.log(f"[WARN] Ошибка при проверке службы Virtual Disk: {e}", "#FFA500")
            
            # Даем дополнительное время для стабилизации службы
            time.sleep(2)
            
            # Пытаемся настроить загрузчик
            success = install_bootloader(drive, "PULZE OS")
            if success: return True
            
            # Если не получилось, пробуем еще раз с дополнительной задержкой
            self.log("[RETRY] Повторная попытка настройки загрузчика...", "#FFA500")
            time.sleep(5)  # Дополнительная задержка
            success = install_bootloader(drive, "PULZE OS")
            return success
        except Exception as e:
            self.log(f"[ERROR] Ошибка при настройке загрузчика: {e}", COLOR_RED)
            return False

    def copy_puls_files(self, target_drive):
        """Copy license key to the target drive"""
        # Создаем папку PULZE на целевом диске
        dest = os.path.join(target_drive, "PULZE")
        try:
            # Обновляем индикатор прогресса
            self.progress.set(0.1)  # Начальный прогресс
            self.eta_label.configure(text="Копирование лицензии...")
            self.update_idletasks()
                
            # Проверяем существование целевого диска
            if not os.path.exists(target_drive):
                self.log(f"[ERROR] Целевой диск не существует: {target_drive}", COLOR_RED)
                return False
                
            # Подсчитываем количество файлов для прогресс-бара
            self.progress.set(0.2)
            self.eta_label.configure(text="Подсчет файлов...")
            self.update_idletasks()
            
            # Функция для подсчета файлов в директории
            def count_files(directory):
                count = 0
                for root, dirs, files in os.walk(directory):
                    count += len(files)
                return count
                
            try:
                # Копируем только ключ лицензии
                self.log(f"[INFO] Подготовка к копированию ключа лицензии", "#555")
            except Exception as e:
                self.log(f"[WARN] Не удалось подсчитать файлы: {e}", "#FFA500")
                total_files = 100  # Примерное количество файлов
            
            # Проверяем доступ на запись в целевой диск
            test_file = os.path.join(target_drive, "test_copy_access.tmp")
            try:
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
                self.log(f"[OK] Диск {target_drive} доступен для записи", "#555")
            except Exception as e:
                self.log(f"[ERROR] Нет доступа на запись в {target_drive}: {e}", COLOR_RED)
                return False
                
            # Удаляем существующую папку, если она есть
            if os.path.exists(dest): 
                self.log(f"[INFO] Удаление существующей папки: {dest}", "#555")
                try:
                    shutil.rmtree(dest)
                except Exception as e:
                    self.log(f"[WARN] Не удалось удалить папку: {e}", "#FFA500")
                    # Пробуем создать новую папку с другим именем
                    dest = os.path.join(target_drive, "PULZE_NEW")
                    self.log(f"[INFO] Используем альтернативную папку: {dest}", "#FFA500")
            
            # Создаем родительскую папку, если нужно
            parent_dir = os.path.dirname(dest)
            if not os.path.exists(parent_dir):
                self.log(f"[INFO] Создание родительской папки: {parent_dir}", "#555")
                os.makedirs(parent_dir, exist_ok=True)
                
            # Копируем файлы с отображением прогресса
            self.log(f"[INFO] Копирование файлов...", "#555")
            
            # Создаем целевую директорию
            if not os.path.exists(dest):
                os.makedirs(dest, exist_ok=True)
                
            # Копируем ключ лицензии
            try:
                # Копируем только ключ лицензии
                # Проверяем разные пути к файлу лицензии
                possible_paths = [
                    os.path.join(self.base_path, "licence.key"),
                    os.path.join(os.path.dirname(self.base_path), "licence.key"),
                    os.path.join(os.getcwd(), "licence.key")
                ]
                
                # Ищем файл лицензии в разных местах
                licence_key_src = None
                for path in possible_paths:
                    if os.path.exists(path):
                        licence_key_src = path
                        self.log(f"[INFO] Найден ключ лицензии: {path}", "#555")
                        break
                        
                licence_key_dst = os.path.join(dest, "licence.key")
                
                if licence_key_src and os.path.exists(licence_key_src):
                    # Создаем директорию, если не существует
                    os.makedirs(os.path.dirname(licence_key_dst), exist_ok=True)
                    
                    # Копируем файл
                    shutil.copy2(licence_key_src, licence_key_dst)
                    
                    # Обновляем прогресс
                    self.progress.set(1.0)  # 100%
                    self.eta_label.configure(text="Копирование завершено")
                    self.update_idletasks()
                    
                    self.log(f"[OK] Ключ лицензии скопирован", COLOR_GREEN)
                    return True
                else:
                    self.log(f"[WARN] Ключ лицензии не найден: {licence_key_src}", "#FFA500")
                    return False
            except Exception as e:
                self.log(f"[ERROR] Ошибка при копировании ключа лицензии: {e}", COLOR_RED)
                return False
        except Exception as e:
            self.log(f"[ERROR] Ошибка при копировании ключа лицензии: {e}", COLOR_RED)
            return False
    
    def check_bitlocker(self, drive_letter):
        try:
            c = wmi.WMI()
            for v in c.Win32_EncryptableVolume(DriveLetter=drive_letter.strip(':')):
                if v.ProtectionStatus == 1: return True
        except: pass
        return False

    def reboot_pc(self): os.system("shutdown /r /t 0")
    
    def center_window(self):
        """Центрирует окно на экране"""
        # Получаем размеры экрана
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Получаем размеры окна
        window_width = 850
        window_height = 600
        
        # Вычисляем координаты для центрирования
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # Устанавливаем позицию окна
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")

# Импортируем модуль с улучшениями
try:
    from installer_enhancements import InstallerEnhancements
    ENHANCEMENTS_AVAILABLE = True
except ImportError:
    ENHANCEMENTS_AVAILABLE = False

if __name__ == "__main__":
    try:
        if is_admin():
            app = PulzeInstaller()
            
            # Применяем улучшения, если они доступны
            if ENHANCEMENTS_AVAILABLE:
                try:
                    enhancements = InstallerEnhancements(app)
                    enhancements.setup()
                    app.enhancements = enhancements
                    print("[INFO] Улучшения инсталлера активированы")
                    
                    # Добавляем информацию о доступных улучшениях
                    app.after(1000, lambda: app.log("[INFO] Активированы улучшения инсталлера:", "#0fffc1"))
                    app.after(1200, lambda: app.log("- Поддержка сворачивания в трей", "#0fffc1"))
                    app.after(1400, lambda: app.log("- Предупреждение при закрытии во время установки", "#0fffc1"))
                    app.after(1600, lambda: app.log("- Проверка системных требований", "#0fffc1"))
                    app.after(1800, lambda: app.log("- Сохранение логов установки", "#0fffc1"))
                    app.after(2000, lambda: app.log("- Возобновление прерванной установки", "#0fffc1"))
                    app.after(2200, lambda: app.log("- Руководство после установки", "#0fffc1"))
                except Exception as e:
                    print(f"[WARN] Не удалось активировать улучшения: {e}")
                    traceback.print_exc()
            
            app.mainloop()
        else:
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    except Exception as e:
        print(f"CRASH: {e}")
        traceback.print_exc()
        input("Press Enter...")
