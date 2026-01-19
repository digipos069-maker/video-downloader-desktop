
import os
import sys
import zipfile
import shutil
import subprocess
import urllib.request
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextBrowser, QProgressBar, QMessageBox, QWidget
)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QUrl
from app.config.version import VERSION
from app.helpers import get_app_path, resource_path

class DownloadWorker(QThread):
    progress = Signal(int)
    finished = Signal(str) # Path to downloaded file
    error = Signal(str)

    def __init__(self, url, dest_path):
        super().__init__()
        self.url = url
        self.dest_path = dest_path

    def run(self):
        try:
            def report_hook(block_num, block_size, total_size):
                if total_size > 0:
                    percent = int((block_num * block_size * 100) / total_size)
                    self.progress.emit(percent)
            
            urllib.request.urlretrieve(self.url, self.dest_path, report_hook)
            self.finished.emit(self.dest_path)
        except Exception as e:
            self.error.emit(str(e))

class UpdateDialog(QDialog):
    def __init__(self, update_info, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.new_version = update_info.get("version", "Unknown")
        self.download_url = update_info.get("download_url", "")
        self.release_notes = update_info.get("release_notes", "No release notes available.")
        
        self.setWindowTitle(f"Update Available - v{self.new_version}")
        self.setFixedSize(500, 400)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #18181B;
                color: #F4F4F5;
            }
            QLabel {
                color: #F4F4F5;
            }
            QTextBrowser {
                background-color: #27272A;
                color: #D4D4D8;
                border: 1px solid #3F3F46;
                border-radius: 6px;
                padding: 10px;
                font-family: \"Segoe UI\", sans-serif;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 10pt;
            }
            QProgressBar {
                border: 1px solid #3F3F46;
                border-radius: 6px;
                text-align: center;
                color: white;
                background-color: #27272A;
            }
            QProgressBar::chunk {
                background-color: #10B981;
                border-radius: 5px;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel(f"A new version is available!")
        title_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #10B981;")
        
        ver_label = QLabel(f"v{VERSION}  ➜  v{self.new_version}")
        ver_label.setStyleSheet("font-size: 11pt; color: #A1A1AA;")
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(ver_label)
        layout.addLayout(header_layout)

        # Release Notes
        notes_label = QLabel("What's New:")
        notes_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        layout.addWidget(notes_label)

        self.notes_browser = QTextBrowser()
        
        # Format Release Notes with Icons
        icon_path = resource_path("app/resources/images/icons/checklist.png")
        icon_url = QUrl.fromLocalFile(icon_path).toString()
        
        html_notes = ""
        for line in self.release_notes.split("\n"):
            line = line.strip()
            if not line: continue
            
            # If line starts with - or *, add icon
            if line.startswith("- ") or line.startswith("* "):
                text = line[2:].strip()
                html_notes += f'<div style="margin-bottom: 8px;"><img src="{icon_url}" width="14" height="14"> &nbsp; {text}</div>'
            else:
                html_notes += f'<div style="margin-bottom: 8px;">{line}</div>'
                
        self.notes_browser.setHtml(html_notes)
        layout.addWidget(self.notes_browser)

        # Progress Bar (Hidden initially)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(25)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #A1A1AA; font-size: 9pt;")
        layout.addWidget(self.status_label)

        # Buttons
        btn_layout = QHBoxLayout()
        
        self.skip_btn = QPushButton("Skip This Version")
        self.skip_btn.setCursor(Qt.PointingHandCursor)
        self.skip_btn.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                color: #71717A;
                border: 1px solid #3F3F46;
            }
            QPushButton:hover {
                background-color: #27272A;
                color: #A1A1AA;
            }
            """
        )
        self.skip_btn.clicked.connect(self.reject)

        self.update_btn = QPushButton("Update Now")
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
            QPushButton:pressed {
                background-color: #1D4ED8;
            }
            """
        )
        self.update_btn.clicked.connect(self.start_update)

        btn_layout.addWidget(self.skip_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.update_btn)
        layout.addLayout(btn_layout)

    @Slot()
    def start_update(self):
        if not self.download_url:
            QMessageBox.critical(self, "Error", "Download URL is missing in update info.")
            return

        self.update_btn.setEnabled(False)
        self.update_btn.setText("Please wait, updating...")
        self.skip_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Downloading update...")

        # Temp path for zip
        temp_dir = os.path.join(get_app_path(), "temp_update")
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            
        zip_path = os.path.join(temp_dir, f"update_v{self.new_version}.zip")
        
        self.worker = DownloadWorker(self.download_url, zip_path)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self.on_download_finished)
        self.worker.error.connect(self.on_download_error)
        self.worker.start()

    @Slot(str)
    def on_download_finished(self, zip_path):
        self.status_label.setText("Extracting files...")
        self.progress_bar.setRange(0, 0) # Indeterminate mode for extraction
        
        # Process extraction in a separate logical step (could be thread, but zip extract is fast)
        try:
            self.apply_update(zip_path)
        except Exception as e:
            QMessageBox.critical(self, "Update Failed", f"Failed to apply update:\n{e}")
            self.update_btn.setEnabled(True)
            self.skip_btn.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.status_label.setText("Update failed.")

    @Slot(str)
    def on_download_error(self, error_msg):
        QMessageBox.critical(self, "Download Failed", f"Error downloading update:\n{error_msg}")
        self.update_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Download failed.")

    def apply_update(self, zip_path):
        app_path = get_app_path()
        current_exe = sys.executable
        exe_name = os.path.basename(current_exe)
        
        # 1. Rename current executable to archive version
        # "keep app version exe with app name v{app version}"
        # e.g., SocialDownloadManager_v26.0.0.exe
        
        name_part, ext = os.path.splitext(exe_name)
        # Avoid double versioning if already has version
        base_name = name_part.split('_v')[0]
        
        archive_name = f"{base_name}_v{VERSION}{ext}"
        archive_path = os.path.join(app_path, archive_name)
        
        # If running from source (python.exe), we can't really "update" the exe. 
        # We assume this runs in the frozen environment.
        if getattr(sys, 'frozen', False):
            try:
                # Rename current running exe? Windows allows renaming running executables usually.
                if os.path.exists(archive_path):
                    os.remove(archive_path) # Remove old archive if exists
                
                os.rename(current_exe, archive_path)
                
                # 2. Extract Zip
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(app_path)
                
                # 3. Check if new exe exists
                # The zip should contain the executable with the ORIGINAL name (e.g. SocialDownloadManager.exe)
                # If the zip structure is different, this might fail. We assume flat or root structure.
                
                # Clean up zip
                try:
                    os.remove(zip_path)
                    os.rmdir(os.path.dirname(zip_path))
                except:
                    pass

                # 4. Restart
                self.status_label.setText("Restarting application...")
                QMessageBox.information(self, "Update Complete", "Update installed successfully!\nThe application will now restart.")
                
                # Launch new exe
                # We expect the new file to have the original name 'SocialDownloadManager.exe' (or whatever exe_name was)
                new_exe_path = os.path.join(app_path, exe_name)
                
                if os.path.exists(new_exe_path):
                    subprocess.Popen([new_exe_path])
                    sys.exit(0)
                else:
                    # Fallback: Maybe zip had a folder?
                    # For now, just restore logic? 
                    # If failed, rename back
                    os.rename(archive_path, current_exe)
                    raise Exception("New executable not found after extraction.")

            except Exception as e:
                # Attempt rollback
                if os.path.exists(archive_path) and not os.path.exists(current_exe):
                    os.rename(archive_path, current_exe)
                raise e
        else:
            # Dev mode
            QMessageBox.information(self, "Dev Mode", f"Update downloaded to:\n{zip_path}\n\nCannot auto-update in dev mode.")
            self.accept()
