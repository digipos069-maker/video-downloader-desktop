
"""
Network-related utilities, such as monitoring internet speed.
"""

from PySide6.QtCore import QThread, Signal
import time
import psutil

class NetworkSpeedMonitor(QThread):
    """
    A thread that monitors and emits network upload and download speeds.
    """
    speed_updated = Signal(float, float)  # download_speed (Mbps), upload_speed (Mbps)

    def __init__(self, interval=2):
        super().__init__()
        self.interval = interval
        self._is_running = True

    def run(self):
        """Monitors network speed at a set interval."""
        last_bytes_sent = psutil.net_io_counters().bytes_sent
        last_bytes_recv = psutil.net_io_counters().bytes_recv
        time.sleep(self.interval)

        while self._is_running:
            current_bytes_sent = psutil.net_io_counters().bytes_sent
            current_bytes_recv = psutil.net_io_counters().bytes_recv

            upload_speed = (current_bytes_sent - last_bytes_sent) / self.interval
            download_speed = (current_bytes_recv - last_bytes_recv) / self.interval

            # Convert to Mbps
            upload_mbps = (upload_speed * 8) / (1024 * 1024)
            download_mbps = (download_speed * 8) / (1024 * 1024)

            self.speed_updated.emit(download_mbps, upload_mbps)

            last_bytes_sent = current_bytes_sent
            last_bytes_recv = current_bytes_recv
            time.sleep(self.interval)

    def stop(self):
        self._is_running = False

if __name__ == '__main__':
    # This is not how it will be used in the app, this is for testing
    import sys
    from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

    app = QApplication(sys.argv)
    window = QWidget()
    layout = QVBoxLayout(window)
    speed_label = QLabel("Loading...")
    layout.addWidget(speed_label)

    def update_speed_label(down, up):
        speed_label.setText(f"Download: {down:.2f} Mbps\nUpload: {up:.2f} Mbps")

    monitor = NetworkSpeedMonitor()
    monitor.speed_updated.connect(update_speed_label)
    monitor.start()

    window.show()
    app.aboutToQuit.connect(monitor.stop)
    sys.exit(app.exec())
