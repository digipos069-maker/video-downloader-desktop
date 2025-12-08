import pytest
from PySide6.QtWidgets import QHeaderView
from app.ui.downloader_tab import DownloaderTab

@pytest.mark.qt
def test_activity_table_resize_mode(qtbot):
    """
    Verify that the activity table columns are set to Interactive (resizable).
    """
    widget = DownloaderTab()
    qtbot.addWidget(widget)
    
    header = widget.activity_table.horizontalHeader()
    
    # Check column 0 is ResizeToContents
    assert header.sectionResizeMode(0) == QHeaderView.ResizeToContents
    
    # Check columns 1-8 are Interactive
    for i in range(1, 9):
        mode = header.sectionResizeMode(i)
        assert mode == QHeaderView.Interactive, f"Column {i} should be Interactive, but is {mode}"
