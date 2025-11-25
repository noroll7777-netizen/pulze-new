import os
import re

def update_imports(file_path, replacements):
    """
    Update import statements in a file based on a list of replacements.
    
    Args:
        file_path (str): Path to the file to update
        replacements (list): List of tuples (pattern, replacement)
    """
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        updated_content = content
        for pattern, replacement in replacements:
            updated_content = re.sub(pattern, replacement, updated_content)
        
        if content != updated_content:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(updated_content)
            print(f"Updated imports in {file_path}")
        else:
            print(f"No changes needed in {file_path}")
    
    except Exception as e:
        print(f"Error updating {file_path}: {e}")

# Define the replacements for each file
replacements = {
    # Installer files
    "Installer/installer.py": [
        (r"from auth_client import KeyAuthAPI", r"import sys\nimport os\n\n# Add Common directory to path\nsys.path.append(os.path.join(os.path.dirname(__file__), '../Common'))\nfrom auth_client import KeyAuthAPI"),
        (r"from boot_manager import install_bootloader", r"from boot_manager import install_bootloader")
    ],
    
    # Launcher files
    "Launcher/launcher.py": [
        (r"from keyauth import KeyAuthAPI", r"import sys\nimport os\n\n# Add Common directory to path\nsys.path.append(os.path.join(os.path.dirname(__file__), '../Common'))\nfrom keyauth import KeyAuthAPI"),
        (r"from tweaker import TweakerEngine", r"from tweaker import TweakerEngine")
    ]
}

# Base directory
base_dir = os.path.dirname(os.path.abspath(__file__))

# Update imports in each file
for rel_path, file_replacements in replacements.items():
    file_path = os.path.join(base_dir, rel_path)
    update_imports(file_path, file_replacements)

print("Import paths updated successfully!")
