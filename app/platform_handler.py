"""
Platform-specific handlers for scraping and downloading.
"""
import yt_dlp
from abc import ABC, abstractmethod

def extract_metadata_with_ytdlp(url, max_entries=100):
    """
    Helper to extract metadata using yt-dlp.
    Can handle single URLs or playlists/feeds (up to max_entries).
    """
    if not url or not isinstance(url, str) or not url.strip().startswith(('http', 'ftp')):
        print(f"Invalid URL passed to yt-dlp extractor: {url}")
        return [{'url': url, 'title': 'Invalid URL', 'type': 'video'}]

    YDL_OPTS = {
        'quiet': True,
        'extract_flat': True, # Fast extraction, gets video page URLs
        'force_generic_extractor': False,
        'playlistend': max_entries,
        'ignoreerrors': True, # Skip deleted/private items
        'no_warnings': True,
    }
    
    results = []
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if 'entries' in info:
                # It's a playlist or feed
                for entry in info['entries']:
                    if entry:
                        results.append({
                            'url': entry.get('url') or entry.get('webpage_url'),
                            'title': entry.get('title', 'N/A'),
                            'type': 'video' # yt-dlp primarily handles video, treat as such for now
                        })
            else:
                # Single item
                results.append({
                    'url': info.get('webpage_url', url),
                    'title': info.get('title', 'N/A'),
                    'type': 'video'
                })
    except Exception as e:
        print(f"yt-dlp extraction error for {url}: {e}")
        # Fallback: If yt-dlp fails completely, return the single URL as a basic item
        # This allows the system to at least try downloading the URL itself later
        results.append({'url': url, 'title': 'Unknown (Scrape Failed)', 'type': 'video'})
        
    return results

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
        return extract_metadata_with_ytdlp(url, max_entries=1)

    def get_playlist_metadata(self, url, max_entries=100):
        return extract_metadata_with_ytdlp(url, max_entries=max_entries)

    def download(self, item, progress_callback):
        print(f"Downloading YouTube video: {item['title']}")
        # Placeholder for actual download logic
        progress_callback(50)
        progress_callback(100)
        return True

class TikTokHandler(BaseHandler):
    def can_handle(self, url):
        return 'tiktok.com' in url

    def get_metadata(self, url):
        return extract_metadata_with_ytdlp(url, max_entries=1)

    def get_playlist_metadata(self, url, max_entries=100):
        return extract_metadata_with_ytdlp(url, max_entries=max_entries)

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
        # Revert to simpler behavior, as yt-dlp for Pinterest can be problematic
        # and often fails to find video formats or handle image pins correctly.
        return self.get_metadata(url)

    def download(self, item, progress_callback):
        print(f"Downloading Pinterest pin: {item['title']}")
        progress_callback(100)
        return True

class FacebookHandler(BaseHandler):
    def can_handle(self, url):
        return 'facebook.com' in url or 'fb.watch' in url

    def get_metadata(self, url):
        return extract_metadata_with_ytdlp(url, max_entries=1)
    
    def get_playlist_metadata(self, url, max_entries=100):
        return extract_metadata_with_ytdlp(url, max_entries=max_entries)

    def download(self, item, progress_callback):
        print(f"Downloading Facebook video: {item['title']}")
        progress_callback(100)
        return True

class InstagramHandler(BaseHandler):
    def can_handle(self, url):
        return 'instagram.com' in url

    def get_metadata(self, url):
        return extract_metadata_with_ytdlp(url, max_entries=1)

    def get_playlist_metadata(self, url, max_entries=100):
        return extract_metadata_with_ytdlp(url, max_entries=max_entries)

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
        # Add more test URLs as needed
    ]

    for url in test_urls:
        handler = factory.get_handler(url)
        if handler:
            print(f"Found handler for {url}: {handler.__class__.__name__}")
            metadata = handler.get_playlist_metadata(url, max_entries=5) # Test with small limit
            print(f"  Metadata (first 5): {metadata}")
        else:
            print(f"No handler found for {url}")