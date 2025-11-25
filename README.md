# PULZE Components

This folder contains the organized components of the PULZE OS project, separated by functionality.

## Folder Structure

```
PULZE_Components/
├── Common/           # Shared files used by both Installer and Launcher
│   ├── auth_client.py    # KeyAuth authentication client
│   ├── keyauth.py        # KeyAuth API implementation
│   ├── config.py         # Configuration settings
│   └── icon.ico          # Application icon
│
├── Installer/        # PULZE OS Installer components
│   ├── installer.py      # Main installer application
│   ├── installer.spec    # PyInstaller specification file
│   └── boot_manager.py   # Boot configuration manager
│
└── Launcher/         # PULZE OS Launcher components
    ├── launcher.py       # Main launcher application
    ├── launcher.spec     # PyInstaller specification file
    ├── launcher_config.json # Launcher configuration
    └── tweaker.py        # System optimization engine
```

## Component Descriptions

### Installer

The Installer components are responsible for deploying PULZE OS on the user's computer. The main features include:

- GUI interface with CustomTkinter
- KeyAuth authentication
- WIM file download and validation
- Disk partitioning with Diskpart
- Image application with DISM
- Boot configuration with BCD

### Launcher

The Launcher components replace the standard Windows Explorer shell and provide a custom interface for PULZE OS. Key features include:

- Full-screen Tkinter interface with Cyberpunk style
- Game/application launching
- System optimization tweaks
- Global crosshair overlay
- RAM cleaner
- System information display

### Common

The Common folder contains shared components used by both the Installer and Launcher:

- Authentication modules
- Configuration settings
- Visual assets

## Compilation Instructions

### Installer
```bash
cd PULZE_Components/Installer
pyinstaller --noconfirm --onefile --windowed --icon "../Common/icon.ico" --name "Installer" --clean installer.py
```

### Launcher
```bash
cd PULZE_Components/Launcher
pyinstaller --noconfirm --onefile --windowed --icon "../Common/icon.ico" --name "Launcher" --clean launcher.py
```

## Dependencies

- customtkinter
- tkinter
- requests
- wmi
- psutil
- ctypes
- subprocess
- winreg
- hashlib
