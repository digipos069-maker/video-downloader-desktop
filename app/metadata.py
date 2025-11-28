
"""
Handles reading and writing metadata for downloaded files.
"""

import json
import os

def save_metadata(video_info, filepath):
    """
    Saves the video metadata to a JSON file next to the video.
    """
    metadata_path = os.path.splitext(filepath)[0] + '.json'
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(video_info, f, ensure_ascii=False, indent=4)
    print(f"Metadata saved to {metadata_path}")

def load_metadata(filepath):
    """
    Loads video metadata from a JSON file.
    """
    metadata_path = os.path.splitext(filepath)[0] + '.json'
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None
