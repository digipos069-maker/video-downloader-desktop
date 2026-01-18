
import os
import sys
import shutil
import subprocess

def run_command(command, description):
    print(f"\n--- {description} ---")
    print(f"Executing: {command}")
    try:
        # split command string into list if it's a string, for subprocess
        # But for Nuitka with many args, keeping it as list in python is better.
        # Here we assume command is passed as list or string.
        if isinstance(command, str):
            subprocess.check_call(command, shell=True)
        else:
            subprocess.check_call(command)
        print(f"--- {description} Completed ---\n")
    except subprocess.CalledProcessError as e:
        print(f"Error during {description}: {e}")
        sys.exit(1)

def main():
    print("Starting Build Process for Social Download Manager...")
    
    project_root = os.getcwd()
    dist_dir = os.path.join(project_root, "build", "SocialDownloadManager.dist")
    
    # 1. Prepare Playwright Browsers
    print("Step 1: Preparing Playwright Browsers...")
    if not os.path.exists("playwright-browsers"):
        print("Browsers not found locally. Running copy_browsers.py...")
        run_command([sys.executable, "copy_browsers.py"], "Copy Browsers")
    
    if not os.path.exists("playwright-browsers"):
        print("Error: 'playwright-browsers' folder is still missing. Build cannot proceed.")
        sys.exit(1)

    # 2. Construct Nuitka Command
    nuitka_cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--enable-plugin=pyside6",
        
        # Configuration for problematic modules (yt_dlp lazy extractors)
        "--user-package-configuration-file=nuitka-config.yaml",
        
        # Include Assets
        # Mapping app/resources to app/resources in the dist folder
        "--include-data-dir=app/resources=app/resources",
        
        # Include Browsers
        "--include-data-dir=playwright-browsers=playwright-browsers",
        
        # Windows Specifics
        "--windows-icon-from-ico=app/resources/images/logo.ico",
        "--windows-company-name=TeleTool",
        "--windows-product-name=Social Download Manager",
        "--windows-file-version=1.0.0.0",
        "--windows-product-version=1.0.0.0",
        "--windows-file-description=Video Downloader Application",
        "--copyright=Copyright 2026",
        
        # Output
        "--output-dir=build",
        "--output-filename=SocialDownloadManager",
        
        # Optimization (Optional, can increase build time)
        # "--lto=no", 
        
        # Hide Console (Enable for production)
        "--windows-console-mode=disable", 
        
        "main.py"
    ]

    # 3. Run Nuitka
    run_command(nuitka_cmd, "Building with Nuitka")

    # 4. Post-Build Copying
    print("Step 4: Post-Build Operations...")
    
    # Check where the dist folder is
    # Nuitka naming convention: {output_filename}.dist
    if not os.path.exists(dist_dir):
        # Fallback check
        possible_dist = os.path.join(project_root, "build", "main.dist")
        if os.path.exists(possible_dist):
             print(f"Renaming {possible_dist} to {dist_dir}")
             os.rename(possible_dist, dist_dir)
    
    if not os.path.exists(dist_dir):
        print(f"Error: Could not find distribution directory at {dist_dir}")
        sys.exit(1)

    # Copy ffmpeg.exe
    ffmpeg_src = "ffmpeg.exe"
    ffmpeg_dst = os.path.join(dist_dir, "ffmpeg.exe")
    if os.path.exists(ffmpeg_src):
        print(f"Copying {ffmpeg_src} to dist folder...")
        shutil.copy2(ffmpeg_src, ffmpeg_dst)
    else:
        print("Warning: ffmpeg.exe not found in root. The app might not download videos correctly without it.")

    # Copy license.dat if it exists
    license_src = "license.dat"
    license_dst = os.path.join(dist_dir, "license.dat")
    if os.path.exists(license_src):
        print(f"Copying {license_src} to dist folder...")
        shutil.copy2(license_src, license_dst)

    print("\n---------------------------------------------------------")
    print("Build Successful!")
    print(f"Executable is located at: {os.path.join(dist_dir, 'SocialDownloadManager.exe')}")
    print("You can zip the 'SocialDownloadManager.dist' folder and distribute it.")
    print("---------------------------------------------------------")

if __name__ == "__main__":
    main()
