
import pytest
from app.platform_handler import is_valid_media_link

@pytest.mark.parametrize("href, domain, expected", [
    # Media Files
    ("http://example.com/image.jpg", "example.com", True),
    ("http://example.com/video.mp4", "example.com", True),
    ("http://example.com/doc.pdf", "example.com", False),
    
    # YouTube
    ("https://www.youtube.com/watch?v=123", "youtube.com", True),
    ("https://www.youtube.com/shorts/abc", "youtube.com", True),
    ("https://www.youtube.com/about", "youtube.com", False),
    ("https://youtu.be/123", "youtu.be", True),

    # TikTok
    ("https://www.tiktok.com/@user/video/123", "tiktok.com", True),
    ("https://www.tiktok.com/@user", "tiktok.com", False),

    # Pinterest
    ("https://www.pinterest.com/pin/123/", "pinterest.com", True),
    ("https://www.pinterest.com/search", "pinterest.com", False),
    
    # Instagram
    ("https://www.instagram.com/p/123/", "instagram.com", True),
    ("https://www.instagram.com/reel/123/", "instagram.com", True),
    ("https://www.instagram.com/user/", "instagram.com", False),

    # Facebook
    ("https://www.facebook.com/watch/?v=123", "facebook.com", True),
    ("https://www.facebook.com/user/videos/123/", "facebook.com", True),
    ("https://www.facebook.com/groups/feed", "facebook.com", False),

    # Generic Site (Non-matching content)
    ("https://other.com/page", "other.com", False),
])
def test_is_valid_media_link(href, domain, expected):
    assert is_valid_media_link(href, domain) == expected
