import unittest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication, QTableWidget
import sys
from app.ui.downloader_tab import DownloaderTab

class TestUiIssue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.tab = DownloaderTab()
        # Mock dependencies
        self.tab.settings_tab = MagicMock()
        self.tab.downloader = MagicMock()
        self.tab.platform_handler_factory = MagicMock()
        
        # Mock settings to allow multiple videos
        self.settings = {
            'video': {'enabled': True, 'top': False, 'count': 50, 'all': True, 'resolution': '1080p'},
            'photo': {'enabled': True, 'top': False, 'count': 50, 'all': True, 'quality': 'High'}
        }
        self.tab.settings_tab.get_settings.return_value = self.settings

    def test_multiple_items_added_to_ui(self):
        handler = MagicMock()
        # Return 5 video items
        mock_metadata = [
            {'url': f'http://test.com/video{i}.mp4', 'title': f'Video {i}', 'type': 'scraped_link'}
            for i in range(5)
        ]
        handler.get_playlist_metadata.return_value = mock_metadata
        self.tab.platform_handler_factory.get_handler.return_value = handler
        self.tab.downloader.add_to_queue.side_effect = lambda url, h, s: f"id_{url}"

        # Run scraping
        print("\n--- Starting Scraping ---")
        self.tab.process_scraping('http://test.com/playlist')
        print("--- Finished Scraping ---")

        # Check Queue calls
        self.assertEqual(self.tab.downloader.add_to_queue.call_count, 5)
        
        # Check UI Table Count
        row_count = self.tab.activity_table.rowCount()
        print(f"Final UI Row Count: {row_count}")
        self.assertEqual(row_count, 5)

if __name__ == '__main__':
    unittest.main()
