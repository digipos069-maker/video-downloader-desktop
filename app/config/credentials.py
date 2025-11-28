
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
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {}

    def save_credentials(self):
        """Saves credentials to the config file."""
        with open(self.config_path, 'w') as f:
            json.dump(self.credentials, f, indent=4)

    def get_credential(self, platform, key):
        """Gets a specific credential for a platform."""
        return self.credentials.get(platform, {}).get(key)

    def set_credential(self, platform, key, value):
        """Sets a specific credential for a platform."""
        if platform not in self.credentials:
            self.credentials[platform] = {}
        self.credentials[platform][key] = value
        self.save_credentials()

if __name__ == '__main__':
    # Example usage
    manager = CredentialsManager()
    manager.set_credential('youtube', 'api_key', 'your_youtube_api_key')
    print(manager.get_credential('youtube', 'api_key'))
