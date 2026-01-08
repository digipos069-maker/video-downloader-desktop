
import sys
import os
import urllib.request
import json
import logging

"""
Utility functions for the application.
"""

def check_for_updates():
    """
    Checks GitHub for a new version.
    Returns (True, update_info) if update available, (False, None) otherwise.
    """
    from app.config.version import VERSION, VERSION_URL
    try:
        # Create request with headers to avoid being blocked
        req = urllib.request.Request(
            VERSION_URL, 
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            remote_version = data.get("version")
            
            if remote_version and remote_version != VERSION:
                logging.info(f"Update available: {remote_version} (Current: {VERSION})")
                return True, data
    except Exception as e:
        logging.error(f"Update check failed: {e}")
    
    return False, None

def resource_path(relative_path):
    """ 
    Get absolute path to resource.
    Robustly handles Nuitka OneFile by anchoring to the module location.
    """
    roots = []
    
    # 1. Strategy: Self-Anchoring (Most Reliable for Nuitka OneFile)
    # We are in .../temp_dir/app/helpers.py
    # We want .../temp_dir/
    try:
        app_dir = os.path.dirname(os.path.abspath(__file__)) # .../app
        project_root = os.path.dirname(app_dir)              # .../
        roots.append(project_root)
    except Exception:
        pass

    # 2. Strategy: PyInstaller / Nuitka Standard Temp Dir
    if hasattr(sys, '_MEIPASS'):
        roots.append(sys._MEIPASS)
        
    # 3. Strategy: Executable Directory (Standalone)
    try:
        roots.append(os.path.dirname(os.path.abspath(sys.argv[0])))
    except Exception:
        pass
        
    # 4. Strategy: CWD (Dev)
    roots.append(os.path.abspath("."))

    # --- Path Variants ---
    rel_norm = os.path.normpath(relative_path)
    variants = [rel_norm]
    
    # Variant: Mapped 'app/resources' -> 'assets'
    match_part = os.path.join("app", "resources")
    if match_part in rel_norm:
        variants.append(rel_norm.replace(match_part, "assets"))
            
    # Variant: Filename at root (for styles.qss)
    variants.append(os.path.basename(rel_norm))
    
    # Variant: Subpath in assets (e.g. assets/images/...)
    if "images" in rel_norm:
        sub = rel_norm.split("images")[-1]
        variants.append(os.path.normpath(os.path.join("assets", "images", sub.lstrip(os.sep))))
    elif "icons" in rel_norm:
        sub = rel_norm.split("icons")[-1]
        variants.append(os.path.normpath(os.path.join("assets", "icons", sub.lstrip(os.sep))))

    # --- Search ---
    for root in roots:
        for variant in variants:
            full_path = os.path.join(root, variant)
            if os.path.exists(full_path):
                return full_path

    # Fallback
    return os.path.join(roots[0] if roots else ".", variants[1] if len(variants) > 1 else rel_norm)

def get_app_path():
    """
    Returns the absolute path to the application directory.
    - Frozen (EXE): The directory containing the .exe
    - Source: The project root directory
    """
    if getattr(sys, 'frozen', False):
        # If the application is run as a bundle, the PyInstaller bootloader
        # extends the sys module by a flag frozen=True.
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
        # Go up one level from 'app/helpers.py' to project root
        application_path = os.path.dirname(application_path)
    
    return application_path

def format_bytes(size):
    """Converts bytes to a human-readable format."""
    if size is None:
        return "N/A"
    power = 1024
    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power and n < len(power_labels):
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

def validate_path(path):
    """Checks if a path is valid and writable."""
    # To be implemented
    return True
