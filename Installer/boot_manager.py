import sys
import os
import subprocess
import re

def run_cmd(cmd):
    try:
        # Используем shell=True для простых команд, чтобы винда не тупила с путями
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try: 
            return res.stdout.decode('cp866')
        except: 
            return res.stdout.decode('utf-8', errors='ignore')
    except Exception as e:
        return str(e)

def get_bcd_entries():
    """ Получает список всех ID в загрузчике """
    try:
        # Читаем вывод bcdedit
        output = run_cmd("bcdedit /enum all")
        ids = set()
        for line in output.splitlines():
            if "identifier" in line.lower():
                # Вытаскиваем {GUID}
                parts = line.split()
                if len(parts) > 1:
                    ids.add(parts[1].strip())
        return ids
    except:
        return set()

def install_bootloader(target_drive, os_name="PULZE OS"):
    target_drive = target_drive.replace(":", "") # Например "Z"
    
    print(f"--- BOOT MANAGER: {target_drive} -> {os_name} ---")

    # 1. Пути (Sysnative fix)
    if os.path.exists(r"C:\Windows\Sysnative\bcdboot.exe"):
        bcdboot = r"C:\Windows\Sysnative\bcdboot.exe"
        bcdedit = r"C:\Windows\Sysnative\bcdedit.exe"
    else:
        bcdboot = r"C:\Windows\System32\bcdboot.exe"
        bcdedit = r"C:\Windows\System32\bcdedit.exe"

    windows_path = f"{target_drive}:\\Windows"

    # 2. Копирование файлов (BCDBOOT)
    print("1. Copying boot files...")
    # Просто копируем файлы, не заботимся о записи
    run_cmd(f'"{bcdboot}" {windows_path} /d /v')
    
    # 3. Создаем новую запись напрямую
    print("2. Creating new boot entry...")
    # Создаем новую запись с названием PULZE OS
    create_output = run_cmd(f'"{bcdedit}" /create /d "{os_name}" /application osloader')
    print(f"   Output: {create_output.strip()}")
    
    # Ищем ID в ответе
    match = re.search(r'\{[a-fA-F0-9\-]{36}\}', create_output)
    
    if not match:
        # Если не нашли ID, пробуем альтернативный метод
        print("Warning: ID not found. Trying alternative method...")
        
        # Пробуем создать запись с другим подходом
        # Сначала создаем запись без названия
        create_output = run_cmd(f'"{bcdedit}" /create /application osloader')
        match = re.search(r'\{[a-fA-F0-9\-]{36}\}', create_output)
        
        if not match:
            # Если и это не сработало, пробуем найти существующую запись
            print("Warning: Still no ID. Searching for existing entries...")
            entries_output = run_cmd(f'"{bcdedit}" /enum')
            # Ищем любую запись Windows
            match = re.search(r'\{[a-fA-F0-9\-]{36}\}', entries_output)
            
            if not match:
                print("CRITICAL ERROR: Could not find any boot entry.")
                return False
    
    new_id = match.group(0)
    print(f"SUCCESS: Got ID {new_id}")

    # 4. Настройка путей
    print(f"3. Targeting drive {target_drive}...")
    run_cmd(f'"{bcdedit}" /set {new_id} device partition={target_drive}:')
    run_cmd(f'"{bcdedit}" /set {new_id} osdevice partition={target_drive}:')
    
    # Дополнительные настройки для новой записи
    print("   Setting additional parameters...")
    run_cmd(f'"{bcdedit}" /set {new_id} path \\windows\\system32\\winload.exe')
    run_cmd(f'"{bcdedit}" /set {new_id} systemroot \\Windows')
    run_cmd(f'"{bcdedit}" /set {new_id} winpe no')
    # Устанавливаем название еще раз
    run_cmd(f'"{bcdedit}" /set {new_id} description "{os_name}"')

    # 5. Приоритет
    print("4. Setting priority...")
    # Устанавливаем название еще раз для гарантии
    run_cmd(f'"{bcdedit}" /set {new_id} description "{os_name}"')
    # Устанавливаем порядок отображения
    run_cmd(f'"{bcdedit}" /displayorder {new_id} /addfirst')
    # Устанавливаем по умолчанию
    run_cmd(f'"{bcdedit}" /default {new_id}')
    # Устанавливаем таймаут
    run_cmd(f'"{bcdedit}" /timeout 10')
    # Дополнительные настройки
    run_cmd(f'"{bcdedit}" /set {new_id} locale ru-RU')
    
    # Дополнительный метод установки по умолчанию
    # Используем прямой вызов bcdedit с параметрами командной строки
    run_cmd(f'cmd /c "{bcdedit}" /default {new_id}')
    # Еще один способ установки по умолчанию
    run_cmd(f'cmd /c "{bcdedit}" /bootsequence {new_id} /addfirst')
    
    # 6. Проверяем результат
    print("5. Verifying boot entry...")
    verify_output = run_cmd(f'"{bcdedit}" /enum {new_id}')
    if os_name in verify_output:
        print(f"SUCCESS: Boot entry created and configured: {new_id}")
    else:
        print(f"WARNING: Boot entry created but verification failed. ID: {new_id}")
        print("Trying to fix boot entry name...")
        # Пробуем исправить название
        run_cmd(f'"{bcdedit}" /set {new_id} description "{os_name}"')
        # Проверяем еще раз
        verify_output = run_cmd(f'"{bcdedit}" /enum {new_id}')
        if os_name in verify_output:
            print(f"SUCCESS: Fixed boot entry name: {new_id}")
        else:
            print(f"WARNING: Could not fix boot entry name. ID: {new_id}")
    
    # 7. Проверяем, что запись установлена по умолчанию
    print("6. Checking default boot entry...")
    default_output = run_cmd(f'"{bcdedit}" /enum ACTIVE')
    if new_id in default_output and "default" in default_output.lower():
        print(f"SUCCESS: Boot entry set as default: {new_id}")
    else:
        print("WARNING: Boot entry may not be set as default. Trying again...")
        # Пробуем еще раз установить по умолчанию
        run_cmd(f'"{bcdedit}" /default {new_id}')
        print(f"Boot entry should now be set as default: {new_id}")
    
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: boot_manager.py <DriveLetter> [OSName]")
        sys.exit(1)
    install_bootloader(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "PULZE OS")
