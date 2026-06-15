import asyncio
from PyQt5.QtCore import QObject, pyqtSignal
from cephoverseer.api.mock_client import MockAPIClient
from cephoverseer.models.dataclasses import CephCluster

class PollingWorker(QObject):
    """
    Runs an asyncio loop in the background or integrates with qasync 
    to poll APIs without blocking the PyQt main thread.
    """
    # Signal emitted when new cluster data is fetched
    data_fetched = pyqtSignal(CephCluster)
    error_occurred = pyqtSignal(str)

    def __init__(self, interval_seconds: float = 2.0):
        super().__init__()
        self.interval = interval_seconds
        self.client = MockAPIClient()
        self._is_running = False

    async def start_polling(self):
        """
        The main asynchronous loop that fetches data at intervals.
        """
        self._is_running = True
        while self._is_running:
            try:
                # Fetch new state from APIs
                cluster_state = await self.client.fetch_state()
                
                # Emit signal to the UI thread with the new data
                self.data_fetched.emit(cluster_state)
            except Exception as e:
                self.error_occurred.emit(str(e))
                
            # Wait for next poll interval
            await asyncio.sleep(self.interval)

    def stop(self):
        self._is_running = False
