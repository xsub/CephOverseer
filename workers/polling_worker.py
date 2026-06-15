import asyncio
from typing import List
from PyQt5.QtCore import QObject, pyqtSignal
from api.prometheus_client import PrometheusClient
from api.ceph_mgr_client import CephMgrClient
from api.mock_client import MockAPIClient
from models.dataclasses import CephCluster
from models.config import ConfigManager

class PollingWorker(QObject):
    """
    Runs an asyncio loop in the background or integrates with qasync 
    to poll APIs without blocking the PyQt main thread.
    """
    # Signal emitted when new cluster data is fetched
    data_fetched = pyqtSignal(list) # Emits a list of CephClusters
    error_occurred = pyqtSignal(str)

    def __init__(self, config_manager: ConfigManager, interval_seconds: float = 5.0, use_mock: bool = True):
        super().__init__()
        self.interval = interval_seconds
        self.config_manager = config_manager
        self._is_running = False
        self.use_mock = use_mock
        
        # Clients dictionary mapping cluster_name -> (PrometheusClient, CephMgrClient)
        self.clients = {}
        if self.use_mock:
            self.mock_client = MockAPIClient(config_manager=self.config_manager)
        else:
            self._init_real_clients()

    def _init_real_clients(self):
        self.clients.clear()
        for cfg in self.config_manager.clusters:
            prom_client = PrometheusClient(base_url=cfg.prometheus_url)
            mgr_client = CephMgrClient(base_url=cfg.mgr_url, username=cfg.username, password=cfg.password)
            self.clients[cfg.name] = (prom_client, mgr_client)

    async def start_polling(self):
        """
        The main asynchronous loop that fetches data at intervals.
        """
        self._is_running = True
        while self._is_running:
            try:
                if self.use_mock:
                    clusters_state = await self.mock_client.fetch_state()
                else:
                    clusters_state = await self._fetch_real_state()
                
                # Emit signal to the UI thread with the new data
                self.data_fetched.emit(clusters_state)
            except Exception as e:
                self.error_occurred.emit(str(e))
                
            # Wait for next poll interval
            await asyncio.sleep(self.interval)

    async def _fetch_real_state(self) -> List[CephCluster]:
        """
        Polls actual Prometheus and Ceph MGR endpoints.
        """
        # Note: In a production app, we would gather these concurrently using asyncio.gather
        clusters = []
        for cfg in self.config_manager.clusters:
            prom_client, mgr_client = self.clients.get(cfg.name, (None, None))
            if not prom_client or not mgr_client:
                continue

            # Fetch Telemetry from Prometheus
            total_iops = await prom_client.get_total_iops()
            # Fetch other metrics... (implementing these inside prometheus_client)

            # Reconstruct the Cluster model
            cluster = CephCluster(
                name=cfg.name,
                prometheus_url=cfg.prometheus_url,
                mgr_url=cfg.mgr_url,
            )
            cluster.telemetry.total_iops = total_iops
            # Add fetched hosts/osds data here...

            clusters.append(cluster)
        
        return clusters

    async def stop(self):
        self._is_running = False
        # Clean up async connections
        if not self.use_mock:
            for prom_client, mgr_client in self.clients.values():
                await prom_client.close()
                await mgr_client.close()
