
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

def is_writable(path):
    try:
        test_file = os.path.join(path, "temp_write_test")
        with open(test_file, "w") as f: f.write("test")
        os.remove(test_file)
        return True
    except PermissionError:
        return False

def run_as_admin(executable, args=None):
    import ctypes
    if args is None:
        args = []
    params = " ".join([f'"{arg}"' for arg in args])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)

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
        
        # Check permissions
        if not is_writable(app_path):
            QMessageBox.warning(self, "Permissions Required", "The application folder is not writable.\nPlease restart the update; you will be prompted to grant Administrator privileges.")
            # Launch current exe as admin with a flag (not implemented) or just user restarts
            # Better: Launch the UPDATER (this logic) as admin? 
            # Since we are deep in logic, let's just try to elevate the current app to restart?
            # Or assume the user will restart.
            # However, we can try to run the *updater.bat* as admin later.
            # Let's proceed to create the bat file in TEMP (writable) and run IT as admin.
        
        extract_dir = os.path.join(os.path.dirname(zip_path), "extracted_update")
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        os.makedirs(extract_dir)

        # 1. Extract to temp
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        except Exception as e:
            raise Exception(f"Failed to extract zip: {e}")

        # 2. Identify the new content
        # If the zip contains a root folder (e.g. sdm_v26.0.2/), we need to copy contents FROM there.
        # Otherwise copy from extract_dir.
        source_dir = extract_dir
        items = os.listdir(extract_dir)
        if len(items) == 1 and os.path.isdir(os.path.join(extract_dir, items[0])):
            source_dir = os.path.join(extract_dir, items[0])

        # 3. Create Updater Bat
        # We use a batch file to wait for PID termination and then move files.
        # This avoids "File in use" errors.
        
        bat_path = os.path.join(os.path.dirname(zip_path), "updater.bat")
        
        # Escape paths for batch
        # We need to copy FROM source_dir TO app_path
        # And rename current_exe to backup
        
        name_part, ext = os.path.splitext(exe_name)
        base_name = name_part.split('_v')[0]
        backup_name = f"{base_name}_v{VERSION}{ext}"
        
        bat_content = f"""@echo off
title Updating Social Download Manager...
echo Waiting for application to close...
timeout /t 3 /nobreak > NUL

:LOOP
tasklist /FI "PID eq {os.getpid()}" 2>NUL | find /I /N "{os.getpid()}" >NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 1 /nobreak > NUL
    goto LOOP
)

echo Backing up current version...
cd /d "{app_path}"
if exist "{exe_name}" (
    move /y "{exe_name}" "{backup_name}"
)

echo Installing new version...
xcopy /s /e /y "{source_dir}\\*" "{app_path}\\"

echo Restarting...
start "" "{exe_name}"

echo Cleaning up...
rmdir /s /q "{os.path.dirname(zip_path)}"

del "%~f0"
"""
        with open(bat_path, "w") as f:
            f.write(bat_content)

        # 4. Run Bat and Exit
        self.status_label.setText("Restarting to apply update...")
        
        if getattr(sys, 'frozen', False):
            # If app dir is NOT writable, run the BAT as admin
            if not is_writable(app_path):
                run_as_admin(bat_path)
            else:
                subprocess.Popen([bat_path], shell=True)
            
            sys.exit(0)
        else:
             QMessageBox.information(self, "Dev Mode", f"Updater script created at:\n{bat_path}")
             self.accept()
