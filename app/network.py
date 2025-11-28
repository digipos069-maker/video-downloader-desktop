import psutil
import time
from PySide6.QtCore import QThread, Signal
import platform
import subprocess

class NetworkMonitor(QThread):
    stats_signal = Signal(float, float, float) # download_mbps, upload_mbps, ping_ms

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.last_net_io = psutil.net_io_counters()
        self.last_time = time.time()
        self.cached_ping = 0.0
        self.last_ping_time = 0

    def run(self):
        while self.running:
            current_time = time.time()
            current_net_io = psutil.net_io_counters()

            time_delta = current_time - self.last_time
            if time_delta >= 1.0:
                # Calculate Bytes per second
                bytes_recv = current_net_io.bytes_recv - self.last_net_io.bytes_recv
                bytes_sent = current_net_io.bytes_sent - self.last_net_io.bytes_sent

                # Convert to Mbps (Megabits per second)
                down_mbps = (bytes_recv * 8) / (1024 * 1024) / time_delta
                up_mbps = (bytes_sent * 8) / (1024 * 1024) / time_delta

                # Measure Ping every 15 seconds
                if current_time - self.last_ping_time >= 15.0:
                    self.cached_ping = self.measure_ping()
                    self.last_ping_time = current_time

                self.stats_signal.emit(down_mbps, up_mbps, self.cached_ping)

                self.last_net_io = current_net_io
                self.last_time = current_time
            
            time.sleep(1) # Update stats every second

    def measure_ping(self):
        host = "8.8.8.8"  # Google DNS
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        command = ['ping', param, '1', host]
        
        try:
            # Using subprocess to run ping command
            # We need to parse the output to get the time, or just return -1 if failed
            # For simplicity in this blocking thread (since it sleeps anyway), we can run it.
            # Ideally ping should be non-blocking or quick.
            
            # Startupinfo to hide console window on Windows
            startupinfo = None
            if platform.system().lower() == 'windows':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            output = subprocess.run(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                startupinfo=startupinfo,
                timeout=1.5 # Short timeout
            )
            
            if output.returncode == 0:
                # Parse output for time
                output_str = output.stdout.decode('utf-8')
                # Windows: "time=12ms" or "time<1ms"
                # Linux: "time=12.3 ms"
                if "time=" in output_str:
                    part = output_str.split("time=")[1]
                    ms_part = part.split("ms")[0].strip()
                    return float(ms_part)
                elif "time<" in output_str:
                    return 1.0
            return 0.0
        except Exception:
            return 0.0

    def stop(self):
        self.running = False
        self.wait()