import json
import os
from app.helpers import get_app_path

SETTINGS_FILE = os.path.join(get_app_path(), "settings.json")

DEFAULT_SETTINGS = {
    'video': {
        'enabled': False,
        'top': False,
        'count': 5,
        'all': False,
        'resolution': "Best Available"
    },
    'photo': {
        'enabled': False,
        'top': False,
        'count': 5,
        'all': False,
        'quality': "Best Available"
    },
    'download': {
        'extension': "Best",
        'naming': "Original Name",
        'subtitles': False,
        'video_path': "",
        'photo_path': ""
    },
    'system': {
        'threads': 4,
        'shutdown': False
    }
}

def load_settings():
    """Loads settings from the JSON file, falling back to defaults."""
    if not os.path.exists(SETTINGS_FILE):
        return DEFAULT_SETTINGS.copy()
    
    try:
        with open(SETTINGS_FILE, 'r') as f:
            loaded_settings = json.load(f)
            # Merge with defaults to ensure all keys exist
            settings = DEFAULT_SETTINGS.copy()
            # Deep merge for nested dictionaries
            for section, content in loaded_settings.items():
                if section in settings and isinstance(content, dict):
                    settings[section].update(content)
                else:
                    settings[section] = content
            return settings
    except (json.JSONDecodeError, IOError):
        return DEFAULT_SETTINGS.copy()

def save_settings(new_settings):
    """Saves the settings dictionary to the JSON file, merging with existing ones."""
    try:
        # Load current state to preserve other sections
        current_settings = load_settings()
        
        # Update with new settings
        for key, value in new_settings.items():
            current_settings[key] = value
            
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(current_settings, f, indent=4)
        return True
    except IOError:
        return False
