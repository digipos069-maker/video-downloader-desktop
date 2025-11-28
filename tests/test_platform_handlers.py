
"""
Tests for the platform handlers.
"""
import pytest
from app.platform_handler import PlatformHandlerFactory

def test_handler_factory():
    """
    Tests that the factory returns the correct handler for each URL.
    """
    factory = PlatformHandlerFactory()
    
    # Test cases: (URL, expected_handler_name)
    test_cases = [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "YouTubeHandler"),
        ("https://youtu.be/dQw4w9WgXcQ", "YouTubeHandler"),
        ("https://www.tiktok.com/@user/video/12345", "TikTokHandler"),
        ("https://www.pinterest.com/pin/12345/", "PinterestHandler"),
        ("https://www.facebook.com/user/videos/12345/", "FacebookHandler"),
        ("https://fb.watch/a1b2c3d4e5/", "FacebookHandler"),
        ("https://www.instagram.com/p/Cabcdefghij/", "InstagramHandler"),
    ]

    for url, expected_handler in test_cases:
        handler = factory.get_handler(url)
        assert handler is not None, f"No handler found for {url}"
        assert handler.__class__.__name__ == expected_handler, \
            f"Incorrect handler for {url}. Got {handler.__class__.__name__}, expected {expected_handler}"

def test_no_handler():
    """
    Tests that the factory returns None for unsupported URLs.
    """
    factory = PlatformHandlerFactory()
    unsupported_url = "https://www.google.com"
    handler = factory.get_handler(unsupported_url)
    assert handler is None

def test_handler_metadata_stub():
    """
    Tests the stubbed get_metadata method for a handler.
    This will need to be updated when real implementation is added.
    """
    factory = PlatformHandlerFactory()
    handler = factory.get_handler("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    metadata = handler.get_metadata("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert isinstance(metadata, list)
    assert len(metadata) > 0
    assert 'url' in metadata[0]
    assert 'title' in metadata[0]

