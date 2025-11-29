
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

    def set_max_threads(self, count):
        """Updates the maximum number of concurrent downloads."""
        self.max_concurrent_downloads = count
        self.thread_pool.setMaxThreadCount(count)
        print(f"Updated max concurrent downloads to {count}")

    def add_to_queue(self, url, handler, settings):
        """Adds a download task to the queue."""
        item_id = self.generate_item_id(url)
        self.queue.append({
            'id': item_id,
            'url': url,
            'handler': handler,
            'settings': settings,
            'status': 'held'
        })
        self.status.emit(item_id, "Added to list")
        return item_id
        # Do not automatically process queue here, wait for user action

    def update_queue_settings(self, new_settings):
        """Updates settings for all queued items."""
        for item in self.queue:
            if item['status'] == 'queued':
                item['settings'].update(new_settings)

    def process_queue(self):
        """Processes the download queue."""
        while not self.queue_empty() and self.thread_pool.activeThreadCount() < self.max_concurrent_downloads:
            self.start_next_download()

    @Slot(str, bool)
    def _download_finished_callback(self, item_id, success):
        """Internal callback for when a worker finishes."""
        # Emit the signal that a download has finished and should be removed from the active list
        self.download_removed.emit(item_id)
        
        self.finished.emit(item_id, success)
        
        # Check for shutdown if queue is empty and no active threads
        if self.queue_empty() and self.thread_pool.activeThreadCount() == 0:
            # Check if any of the finished items had shutdown enabled.
            # Since we remove items from queue, we can't check them there.
            # However, the 'settings' are updated before processing.
            # A cleaner way is to check a flag set during 'update_queue_settings' or pass it down.
            # But since we don't persist finished items here easily, we'll rely on the fact that
            # the UI passes 'shutdown' in the settings of items.
            # We can assume if the LAST processed item had shutdown=True, we shut down.
            # Better: The UI should manage the "shutdown after all" state, but user requested logic here.
            # Let's check if we can find the settings for this item_id? No, it's gone from queue.
            pass

        self.process_queue() # Try to start another download

    def check_shutdown(self, settings):
         if settings.get('shutdown', False):
             import os
             import sys
             if sys.platform == 'win32':
                 os.system("shutdown /s /t 60") # Shutdown in 60 seconds
             elif sys.platform == 'linux' or sys.platform == 'darwin':
                 os.system("shutdown -h +1") # Shutdown in 1 minute
             print("Shutdown initiated...")

    def queue_items(self, item_ids):
        """Sets the status of specific items to 'queued'."""
        ids_set = set(item_ids)
        count = 0
        for item in self.queue:
            if item['id'] in ids_set:
                item['status'] = 'queued'
                count += 1
        print(f"Set {count} items to 'queued' status.")

    def queue_all(self):
        """Sets the status of all 'held' items to 'queued'."""
        count = 0
        for item in self.queue:
            if item['status'] == 'held':
                item['status'] = 'queued'
                count += 1
        print(f"Set {count} items to 'queued' status.")

    def start_next_download(self):
        """Starts the next download from the queue."""
        # Find the first item with status 'queued'
        idx_to_pop = -1
        for i, item in enumerate(self.queue):
            if item['status'] == 'queued':
                idx_to_pop = i
                break
        
        if idx_to_pop == -1:
            return # No items ready to download

        item = self.queue.pop(idx_to_pop)
        item['status'] = 'downloading'
        
        # Emit the signal that a download has started
        self.download_started.emit(item['id'], item['url'])

        worker = DownloadWorker(item['id'], item['url'], item['handler'], item['settings'])
        worker.signals.progress.connect(self.progress)
        worker.signals.status.connect(self.status)
        # Pass settings to callback to check for shutdown
        worker.signals.finished.connect(lambda i, s: self._download_finished_callback_with_settings(i, s, item['settings']))

        self.thread_pool.start(worker)
        self.status.emit(item['id'], 'Starting download...')

    @Slot(str, bool)
    def _download_finished_callback_with_settings(self, item_id, success, settings):
        self._download_finished_callback(item_id, success)
        if self.queue_empty() and self.thread_pool.activeThreadCount() == 0:
            self.check_shutdown(settings)

    def generate_item_id(self, url):
        """Generates a unique ID for a download item."""
        import uuid
        return str(uuid.uuid4())

    def queue_empty(self):
        return len(self.queue) == 0

    def promote_to_front(self, item_ids):
        """
        Moves the specified items to the front of the queue.
        """
        # Filter out items that match the IDs and those that don't
        promoted_items = []
        remaining_items = []
        
        # Create a set for O(1) lookup
        ids_to_promote = set(item_ids)
        
        for item in self.queue:
            if item['id'] in ids_to_promote:
                promoted_items.append(item)
            else:
                remaining_items.append(item)
        
        # Reconstruct the queue: promoted items first, then the rest
        self.queue = promoted_items + remaining_items
        print(f"Promoted {len(promoted_items)} items to the front of the queue.")

if __name__ == '__main__':
    # Example usage would need a QApplication
    print("Downloader module - not intended for direct execution.")
