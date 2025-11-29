
import unittest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QTableWidget
import sys

# Mocking the app structure since we can't load full UI in headless easily without QApp
# We will test the logic of process_scraping by isolating it or replicating it in test

from app.ui.downloader_tab import DownloaderTab

class TestProcessScraping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.tab = DownloaderTab()
        self.tab.settings_tab = MagicMock()
        self.tab.downloader = MagicMock()
        self.tab.platform_handler_factory = MagicMock()
        
        # Mock settings
        self.settings = {
            'video': {'enabled': True, 'top': False, 'count': 5, 'all': False, 'resolution': '1080p'},
            'photo': {'enabled': True, 'top': False, 'count': 5, 'all': False, 'quality': 'High'}
        }
        self.tab.settings_tab.get_settings.return_value = self.settings

    def test_pinterest_resolution_setting(self):
        # Setup handler mock
        handler = MagicMock()
        # Simulate a pinterest link returned by metadata
        handler.get_playlist_metadata.return_value = [
            {'url': 'https://pinterest.com/pin/12345', 'title': 'Test Pin', 'type': 'scraped_link'}
        ]
        self.tab.platform_handler_factory.get_handler.return_value = handler

        # Run process_scraping
        self.tab.process_scraping('https://pinterest.com/board/123')

        # Verify downloader.add_to_queue was called
        self.tab.downloader.add_to_queue.assert_called()
        
        # Inspect arguments
        args, _ = self.tab.downloader.add_to_queue.call_args
        url, h, settings = args
        
        print(f"URL: {url}")
        print(f"Captured Settings: {settings}")
        
        # Check if resolution is present
        # Current expectation: It is MISSING because detection fails for Pinterest
        if 'resolution' in settings:
            print("Resolution found in settings.")
        else:
            print("FAIL: Resolution NOT found in settings for Pinterest link.")

if __name__ == '__main__':
    unittest.main()
