
"""
UI tests for the downloader application.
"""
import pytest
from PySide6.QtWidgets import QApplication

# Mark all tests in this module as needing the qt_bot fixture
pytestmark = pytest.mark.qt

def test_app_creation(qt_bot):
    """
    Test that the main window can be created.
    This is a very basic smoke test.
    """
    # Import inside the test to avoid issues with QApplication instance
    from app.ui.downloader_tab import DownloaderTab

    # QApplication is already created by pytest-qt
    
    widget = DownloaderTab()
    qt_bot.addWidget(widget)

    # Check if the window title is set correctly (if it were a main window)
    # For a QWidget, we can check if it's visible
    widget.show()
    assert widget.isVisible()

    # Check for a key widget
    assert widget.url_input is not None
    assert widget.scrap_button is not None
    assert widget.activity_table is not None

