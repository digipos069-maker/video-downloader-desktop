
"""
Core download orchestrator.
Manages the download queue, concurrency, and communicates with platform handlers.
"""

from PySide6.QtCore import QObject, Signal, QThreadPool, QRunnable, Slot

class DownloadWorker(QRunnable):
    """
    Worker for downloading a single item.
    """
    def __init__(self, item_id, url, handler, settings):
        super().__init__()
        self.item_id = item_id
        self.url = url
        self.handler = handler
        self.settings = settings
        self.signals = WorkerSignals()

    def progress_callback(self, percentage):
        self.signals.progress.emit(self.item_id, percentage)

    @Slot()
    def run(self):
        """
        Runs the download process for a single item.
        """
        self.signals.status.emit(self.item_id, f"Starting download for {self.url}")
        try:
            success = self.handler.download(
                {'url': self.url, 'settings': self.settings},
                self.progress_callback
            )
            self.signals.finished.emit(self.item_id, success)
        except Exception as e:
            self.signals.status.emit(self.item_id, f"Error: {str(e)}")
            self.signals.finished.emit(self.item_id, False)

class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    """
    progress = Signal(str, int)  # item_id, percentage
    status = Signal(str, str)    # item_id, status_message
    finished = Signal(str, bool) # item_id, success

class Downloader(QObject):
    """
    The main downloader class.
    """
    progress = Signal(str, int)
    status = Signal(str, str)
    finished = Signal(str, bool)
    download_started = Signal(str, str) # New signal: item_id, url
    download_removed = Signal(str)      # New signal: item_id

    def __init__(self, platform_handler_factory, max_concurrent_downloads=3):
        super().__init__()
        self.platform_handler_factory = platform_handler_factory
        self.max_concurrent_downloads = max_concurrent_downloads
        self.queue = []
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(self.max_concurrent_downloads)
        print(f"Initialized Downloader with max {self.max_concurrent_downloads} concurrent downloads.")

    def add_to_queue(self, url, handler, settings):
        """Adds a download task to the queue."""
        item_id = self.generate_item_id(url)
        self.queue.append({
            'id': item_id,
            'url': url,
            'handler': handler,
            'settings': settings,
            'status': 'queued'
        })
        self.status.emit(item_id, "Added to queue")
        # Do not automatically process queue here, wait for user action

    def process_queue(self):
        """Processes the download queue."""
        while not self.queue_empty() and self.thread_pool.activeThreadCount() < self.max_concurrent_downloads:
            self.start_next_download()

    def start_next_download(self):
        """Starts the next download from the queue."""
        if self.queue_empty():
            return

        item = self.queue.pop(0)
        item['status'] = 'downloading'
        
        # Emit the signal that a download has started
        self.download_started.emit(item['id'], item['url'])

        worker = DownloadWorker(item['id'], item['url'], item['handler'], item['settings'])
        worker.signals.progress.connect(self.progress)
        worker.signals.status.connect(self.status)
        worker.signals.finished.connect(self._download_finished_callback)

        self.thread_pool.start(worker)
        self.status.emit(item['id'], 'Starting download...')


    @Slot(str, bool)
    def _download_finished_callback(self, item_id, success):
        """Internal callback for when a worker finishes."""
        # Emit the signal that a download has finished and should be removed from the active list
        self.download_removed.emit(item_id)
        
        self.finished.emit(item_id, success)
        self.process_queue() # Try to start another download

    def generate_item_id(self, url):
        """Generates a unique ID for a download item."""
        # A more robust ID generation might be needed for real app
        return str(hash(url))

    def queue_empty(self):
        return len(self.queue) == 0

if __name__ == '__main__':
    # Example usage would need a QApplication
    print("Downloader module - not intended for direct execution.")
