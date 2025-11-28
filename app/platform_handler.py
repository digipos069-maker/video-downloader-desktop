
"""
Platform-specific handlers for scraping and downloading.
"""
import yt_dlp
from abc import ABC, abstractmethod

class BaseHandler(ABC):
    """
    Abstract base class for platform handlers.
    """
    @abstractmethod
    def can_handle(self, url):
        """Checks if the handler can process the given URL."""
        pass

    @abstractmethod
    def get_metadata(self, url):
        """
        Scrapes metadata from a single URL.
        Should return a list containing one item dictionary.
        """
        pass

    @abstractmethod
    def get_playlist_metadata(self, url, max_entries=100):
        """
        Scrapes metadata from a playlist URL.
        Should return a list of item dictionaries.
        """
        pass

    @abstractmethod
    def download(self, item, progress_callback):
        """
        Downloads a single item (video or photo).
        `item` is a dictionary from the metadata scrape.
        `progress_callback` is a function to report progress.
        """
        pass

class YouTubeHandler(BaseHandler):
    def can_handle(self, url):
        return 'youtube.com' in url or 'youtu.be' in url

    def get_metadata(self, url):
        YDL_OPTS = {'quiet': True, 'extract_flat': True, 'force_generic_extractor': False}
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            return [{'url': info.get('webpage_url', url), 'title': info.get('title', 'N/A'), 'type': 'video'}]

    def get_playlist_metadata(self, url, max_entries=100):
        YDL_OPTS = {
            'quiet': True,
            'extract_flat': True,
            'force_generic_extractor': False,
            'playlistend': max_entries,
        }
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            playlist_dict = ydl.extract_info(url, download=False)
            
            if 'entries' in playlist_dict:
                return [
                    {'url': entry.get('url'), 'title': entry.get('title', 'N/A'), 'type': 'video'}
                    for entry in playlist_dict['entries'] if entry
                ]
            else:
                # Not a playlist, return single video metadata
                return [
                    {'url': playlist_dict.get('webpage_url', url), 'title': playlist_dict.get('title', 'N/A'), 'type': 'video'}
                ]


    def download(self, item, progress_callback):
        print(f"Downloading YouTube video: {item['title']}")
        # Here you would use yt-dlp to download
        progress_callback(50)
        progress_callback(100)
        return True

class TikTokHandler(BaseHandler):
    def can_handle(self, url):
        return 'tiktok.com' in url

    def get_metadata(self, url):
        print(f"Getting metadata for TikTok URL: {url}")
        return [{'url': url, 'title': 'Sample TikTok Video', 'type': 'video'}]

    def get_playlist_metadata(self, url, max_entries=100):
        return self.get_metadata(url)

    def download(self, item, progress_callback):
        print(f"Downloading TikTok video: {item['title']}")
        progress_callback(100)
        return True


class PinterestHandler(BaseHandler):
    def can_handle(self, url):
        return 'pinterest.com' in url

    def get_metadata(self, url):
        print(f"Getting metadata for Pinterest URL: {url}")
        return [{'url': url, 'title': 'Sample Pinterest Pin', 'type': 'photo'}]

    def get_playlist_metadata(self, url, max_entries=100):
        return self.get_metadata(url)

    def download(self, item, progress_callback):
        print(f"Downloading Pinterest pin: {item['title']}")
        progress_callback(100)
        return True

class FacebookHandler(BaseHandler):
    def can_handle(self, url):
        return 'facebook.com' in url or 'fb.watch' in url

    def get_metadata(self, url):
        print(f"Getting metadata for Facebook URL: {url}")
        return [{'url': url, 'title': 'Sample Facebook Video', 'type': 'video'}]
    
    def get_playlist_metadata(self, url, max_entries=100):
        return self.get_metadata(url)

    def download(self, item, progress_callback):
        print(f"Downloading Facebook video: {item['title']}")
        progress_callback(100)
        return True

class InstagramHandler(BaseHandler):
    def can_handle(self, url):
        return 'instagram.com' in url

    def get_metadata(self, url):
        print(f"Getting metadata for Instagram URL: {url}")
        return [{'url': url, 'title': 'Sample Instagram Post', 'type': 'photo'}]

    def get_playlist_metadata(self, url, max_entries=100):
        return self.get_metadata(url)

    def download(self, item, progress_callback):
        print(f"Downloading Instagram post: {item['title']}")
        progress_callback(100)
        return True


class PlatformHandlerFactory:
    def __init__(self):
        self.handlers = [
            YouTubeHandler(),
            TikTokHandler(),
            PinterestHandler(),
            FacebookHandler(),
            InstagramHandler(),
        ]

    def get_handler(self, url):
        for handler in self.handlers:
            if handler.can_handle(url):
                return handler
        return None

if __name__ == '__main__':
    factory = PlatformHandlerFactory()
    test_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.tiktok.com/@user/video/12345",
        "https://www.pinterest.com/pin/12345/",
        "https://www.facebook.com/user/videos/12345/",
        "https://www.instagram.com/p/Cabcdefghij/",
        "https://www.google.com"
    ]

    for url in test_urls:
        handler = factory.get_handler(url)
        if handler:
            print(f"Found handler for {url}: {handler.__class__.__name__}")
            metadata = handler.get_metadata(url)
            print(f"  Metadata: {metadata}")
        else:
            print(f"No handler found for {url}")
