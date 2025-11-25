import winreg
import subprocess
import os
import math
import sys
import ctypes
try:
    import psutil
except ImportError:
    psutil = None # <--- ДОБАВЛЕНО

# Определение путей
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class TweakerEngine:
    def __init__(self, log_queue=None):
        self.log_queue = log_queue

    def log(self, msg):
        print(f"[TWEAKER] {msg}")
        if self.log_queue:
            self.log_queue.put(("LOG", msg))

    def run_all_tweaks(self):
        try:
            self.log("=== STARTING OPTIMIZATION ENGINE ===")
            
            self.optimize_ram()
            self.optimize_network()
            self.optimize_gpu_priority()
            self.optimize_input_lag()
            
            self.disable_services()
            self.disable_devices()
            
            self.apply_bcd_tweaks()
            self.apply_custom_power_plan()
            self.import_nvidia_profile()
            self.disable_lock_screen()
            
            # НОВАЯ ФУНКЦИЯ
            self.optimize_pagefile()
            
            self.log("=== OPTIMIZATION COMPLETE ===")
            
            if self.log_queue:
                self.log_queue.put(("DONE_TWEAK", ""))
                
        except Exception as e:
            err_msg = f"Tweaker Error: {str(e)}"
            print(err_msg)
            if self.log_queue:
                self.log_queue.put(("ERR", err_msg))

    # --- ИНСТРУМЕНТЫ ---
    def _reg_write(self, root, path, name, value, reg_type):
        try:
            key = winreg.CreateKey(root, path)
            winreg.SetValueEx(key, name, 0, reg_type, value)
            winreg.CloseKey(key)
        except: pass

    # --- МОДУЛИ ---
    def optimize_pagefile(self):
        self.log("[SYS] Configuring Pagefile (Swap)...")
        try:
            # 1. Отключаем автоматическое управление
            cmd_disable_auto = "wmic computersystem where name='%computername%' set AutomaticManagedPagefile=False"
            subprocess.run(cmd_disable_auto, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 2. Ищем лучший диск (Больше всего места)
            if not psutil:
                 self.log("[SYS] Psutil missing, skipping pagefile check.")
                 return

            best_drive = None
            max_free = 0
            
            for part in psutil.disk_partitions():
                if 'fixed' in part.opts or 'rw' in part.opts:
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                        free_gb = usage.free / (1024**3)
                        # Ищем диск, где больше 20 ГБ свободно
                        if free_gb > 20 and free_gb > max_free:
                            max_free = free_gb
                            best_drive = part.device.replace("\\", "") # C:
                    except: pass

            if best_drive:
                self.log(f"[SYS] Setting 16GB Pagefile on {best_drive}...")
                # Удаляем старые файлы подкачки
                subprocess.run("wmic pagefileset delete", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Создаем новый 16GB (16384 MB) - 24GB
                cmd_set = f"wmic pagefileset create name='{best_drive}\\pagefile.sys'"
                subprocess.run(cmd_set, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                cmd_size = f"wmic pagefileset where name='{best_drive}\\pagefile.sys' set InitialSize=16384,MaximumSize=24576"
                subprocess.run(cmd_size, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                self.log("[SYS] Not enough space for optimal Pagefile.")

        except Exception as e:
            self.log(f"[SYS] Pagefile Error: {e}")

    def optimize_ram(self):
        self.log("[MEM] Analyzing Memory...")
        try:
            ram_b = subprocess.check_output("wmic computersystem get totalphysicalmemory", shell=True).decode().split('\n')[1].strip()
            ram_gb = math.ceil(int(ram_b) / (1024**3))
            self.log(f"[MEM] Detected: {ram_gb} GB")

            val = 380000 
            if ram_gb <= 4: val = 4194304
            elif ram_gb <= 8: val = 8388608
            elif ram_gb <= 16: val = 16777216
            elif ram_gb > 16: val = 33554432

            self._reg_write(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control", "SvcHostSplitThresholdInKB", val, winreg.REG_DWORD)
            self.log(f"[MEM] Optimized Svchost for {ram_gb}GB")
        except: self.log("[MEM] Detection failed")

    def optimize_network(self):
        self.log("[NET] Optimizing TCP/IP...")
        path = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
                for i in range(100):
                    try:
                        guid = winreg.EnumKey(key, i)
                        p = f"{path}\\{guid}"
                        self._reg_write(winreg.HKEY_LOCAL_MACHINE, p, "TcpAckFrequency", 1, winreg.REG_DWORD)
                        self._reg_write(winreg.HKEY_LOCAL_MACHINE, p, "TCPNoDelay", 1, winreg.REG_DWORD)
                    except: break
        except: pass
        self._reg_write(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile", "NetworkThrottlingIndex", 0xFFFFFFFF, winreg.REG_DWORD)

    def optimize_gpu_priority(self):
        self.log("[GPU] Boosting Rust Priority...")
        self._reg_write(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\RustClient.exe\PerfOptions", "CpuPriorityClass", 3, winreg.REG_DWORD)
        self._reg_write(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", 2, winreg.REG_DWORD)

    def optimize_input_lag(self):
        self.log("[INP] Fixing Mouse & Keyboard...")
        self._reg_write(winreg.HKEY_CURRENT_USER, r"Control Panel\Mouse", "MouseSpeed", "0", winreg.REG_SZ)
        self._reg_write(winreg.HKEY_CURRENT_USER, r"Control Panel\Accessibility\Keyboard Response", "Flags", "0", winreg.REG_SZ)

    def disable_services(self):
        self.log("[SVC] Stopping Bloatware Services...")
        services = ["Spooler", "Fax", "WbioSrvc", "DiagTrack", "SysMain", "MapsBroker", "PcaSvc", "XblAuthManager", "XblGameSave"]
        for s in services:
            subprocess.run(f"sc config {s} start= disabled", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(f"sc stop {s}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def disable_devices(self):
        self.log("[DEV] Disabling HPET...")
        cmd = "Get-PnpDevice -FriendlyName 'High precision event timer' -ErrorAction SilentlyContinue | Disable-PnpDevice -Confirm:$false"
        subprocess.run(["powershell", "-Command", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def apply_bcd_tweaks(self):
        self.log("[SYS] BCD Tweaks...")
        cmds = ["bcdedit /deletevalue useplatformclock", "bcdedit /set disabledynamictick yes", "bcdedit /set useplatformtick yes"]
        for cmd in cmds: subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def apply_custom_power_plan(self):
        self.log("[PWR] Configuring Power Plan...")
        plan1 = os.path.join(BASE_DIR, "PULZE OPT V1.0 IDLE ON.pow")
        plan2 = os.path.join(BASE_DIR, "PULZE ULTIMATE.pow")
        
        guid1 = "11111111-1111-1111-1111-111111111111"
        guid2 = "22222222-2222-2222-2222-222222222222"

        def try_import(path, guid, name):
            if os.path.exists(path):
                self.log(f"[PWR] Importing {name}...")
                subprocess.run(f'powercfg -import "{path}" {guid}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(f'powercfg -setactive {guid}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.log(f"[PWR] Active: {name}")
                return True
            return False

        if not try_import(plan1, guid1, "PULZE OPT V1.0"):
            if not try_import(plan2, guid2, "PULZE ULTIMATE"):
                self.log("[PWR] Custom plans missing. High Performance set.")
                subprocess.run("powercfg -setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def import_nvidia_profile(self):
        insp = os.path.join(BASE_DIR, r"Tools\nvidiaProfileInspector.exe")
        prof = os.path.join(BASE_DIR, r"Tools\RustProfile.nip")
        if os.path.exists(insp) and os.path.exists(prof):
            self.log("[GPU] Importing Nvidia Profile...")
            subprocess.run([insp, prof, "-silent"])
        else:
            self.log("[GPU] Profile tools not found.")

    def disable_lock_screen(self):
        self.log("[SYS] Killing Lock Screen...")
        self._reg_write(winreg.HKEY_CURRENT_USER, r"Software\Policies\Microsoft\Windows\Personalization", "NoLockScreen", 1, winreg.REG_DWORD)

if __name__ == "__main__":
    print("Standalone Mode")
    def is_admin():
        try: return ctypes.windll.shell32.IsUserAnAdmin()
        except: return False

    if is_admin():
        e = TweakerEngine()
        e.run_all_tweaks()
        input("Done...")
    else:
        print("Run as Admin!")