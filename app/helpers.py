
"""
Utility functions for the application.
"""

def format_bytes(size):
    """Converts bytes to a human-readable format."""
    if size is None:
        return "N/A"
    power = 1024
    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power and n < len(power_labels):
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

def validate_path(path):
    """Checks if a path is valid and writable."""
    # To be implemented
    return True
