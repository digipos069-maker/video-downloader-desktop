"""
Manages platform credentials (API keys, cookies, login info).
"""

import json
import os

class CredentialsManager:
    def __init__(self, config_path='app/config/credentials.json'):
        self.config_path = config_path
        self.credentials = self.load_credentials()

    def load_credentials(self):
        """Loads credentials from the config file."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def save_credentials(self):
        """Saves credentials to the config file."""
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.credentials, f, indent=4)

    def get_credential(self, platform, key=None):
        """Gets a specific credential for a platform, or all if key is None."""
        platform_data = self.credentials.get(platform, {})
        if key is None:
            return platform_data
        return platform_data.get(key)

    def set_credential(self, platform, key, value=None):
        """
        Sets a specific credential for a platform.
        If 'key' is a dictionary and 'value' is None, updates the platform with that dictionary.
        """
        if platform not in self.credentials:
            self.credentials[platform] = {}
            
        if isinstance(key, dict) and value is None:
            self.credentials[platform].update(key)
        else:
            self.credentials[platform][key] = value
            
        self.save_credentials()

if __name__ == '__main__':
    # Example usage
    manager = CredentialsManager()
    manager.set_credential('youtube', 'api_key', 'your_youtube_api_key')
    print(manager.get_credential('youtube', 'api_key'))