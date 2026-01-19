import os
import sys
import subprocess
import re

VERSION_FILE = os.path.join("app", "config", "version.py")

def get_current_version():
    if not os.path.exists(VERSION_FILE):
        return "Unknown"
    with open(VERSION_FILE, "r") as f:
        content = f.read()
        match = re.search(r'VERSION = "(.+?)"', content)
        if match:
            return match.group(1)
    return "Unknown"

def update_version(new_version):
    with open(VERSION_FILE, "r") as f:
        content = f.read()
    
    new_content = re.sub(r'VERSION = "(.+?)"', f'VERSION = "{new_version}"', content)
    
    with open(VERSION_FILE, "w") as f:
        f.write(new_content)
    print(f"Updated version to {new_version} in {VERSION_FILE}")

def run_build():
    current_ver = get_current_version()
    print(f"Current Version: {current_ver}")
    
    new_ver = input("Enter new version number (leave blank to keep current): ").strip()
    if new_ver:
        update_version(new_ver)
    else:
        new_ver = current_ver

    print(f"\nStarting PyInstaller build for version {new_ver}...")

    # PyInstaller Command
    # python -m PyInstaller --noconfirm --onedir --windowed --add-data "app/resources;app/resources" --add-data "playwright-browsers;playwright-browsers" --add-binary "ffmpeg.exe;." --collect-all playwright --name "sdm" --icon "app/resources/images/logo.ico" main.py
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--add-data", "app/resources;app/resources",
        "--add-data", "playwright-browsers;playwright-browsers",
        "--add-binary", "ffmpeg.exe;.",
        "--collect-all", "playwright",
        "--name", f"sdm_v{new_ver}",
        "--icon", "app/resources/images/logo.ico",
        "main.py"
    ]

    print(f"Executing: {' '.join(cmd)}")
    
    try:
        subprocess.check_call(cmd)
        print("\nBuild Successful!")
        print(f"Executable folder: dist/sdm_v{new_ver}")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed with error code: {e.returncode}")
        sys.exit(1)

if __name__ == "__main__":
    run_build()
