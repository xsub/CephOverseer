import asyncio
from typing import List
from PyQt5.QtCore import QObject, pyqtSignal
from api.prometheus_client import PrometheusClient
from api.ceph_mgr_client import CephMgrClient
from api.mock_client import MockAPIClient
from models.dataclasses import CephCluster, Host, OSD, Pool
from models.config import ConfigManager

class PollingWorker(QObject):
    """
    Runs an asyncio loop in the background or integrates with qasync 
    to poll APIs without blocking the PyQt main thread.
    """
    # Signal emitted when new cluster data is fetched
    data_fetched = pyqtSignal(list) # Emits a list of CephClusters
    error_occurred = pyqtSignal(str)
    log_event = pyqtSignal(str) # Emits log messages to the UI

    def __init__(self, config_manager: ConfigManager, interval_seconds: float = 5.0):
        super().__init__()
        self.interval = interval_seconds
        self.config_manager = config_manager
        self._is_running = False
        self.use_mock = self.config_manager.use_simulation
        
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
            self.log_event.emit(f"Initialized API clients for cluster: {cfg.name}")

    async def start_polling(self):
        """
        The main asynchronous loop that fetches data at intervals.
        """
        self._is_running = True
        while self._is_running:
            try:
                if self.use_mock:
                    clusters_state = await self.mock_client.fetch_state()
                    self.log_event.emit("Fetched mock cluster state successfully.")
                else:
                    clusters_state = await self._fetch_real_state()
                
                # Emit signal to the UI thread with the new data
                self.data_fetched.emit(clusters_state)
            except Exception as e:
                self.error_occurred.emit(str(e))
                self.log_event.emit(f"Error fetching state: {e}")
                
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

            try:
                # Concurrently fetch all telemetry metrics from Prometheus
                iops, (read_bw, write_bw), pgs, health = await asyncio.gather(
                    prom_client.get_total_iops(),
                    prom_client.get_bandwidth_bytes_sec(),
                    prom_client.get_active_pgs(),
                    prom_client.get_health_status()
                )

                # Reconstruct the Cluster model
                cluster = CephCluster(
                    name=cfg.name,
                    prometheus_url=cfg.prometheus_url,
                    mgr_url=cfg.mgr_url,
                )
                
                # Apply telemetry
                cluster.telemetry.total_iops = int(iops)
                cluster.telemetry.read_bytes_sec = int(read_bw)
                cluster.telemetry.write_bytes_sec = int(write_bw)
                cluster.telemetry.active_pgs = pgs
                cluster.telemetry.health_status = health

                # Fetch Hosts/OSDs/Pools from MGR API concurrently
                mgr_hosts_task = asyncio.create_task(mgr_client.get_hosts())
                mgr_osds_task = asyncio.create_task(mgr_client.get_osds())
                mgr_pools_task = asyncio.create_task(mgr_client.get_pools())

                mgr_hosts, mgr_osds, mgr_pools = await asyncio.gather(
                    mgr_hosts_task, mgr_osds_task, mgr_pools_task
                )

                # Process Pools
                parsed_pools = []
                for p_dict in mgr_pools:
                    # Depending on MGR version, fields might slightly differ
                    p_id = p_dict.get('pool', p_dict.get('pool_id', 0))
                    p_name = p_dict.get('pool_name', p_dict.get('name', f"pool_{p_id}"))
                    p_pg = p_dict.get('pg_num', 0)
                    p_used = p_dict.get('stats', {}).get('bytes_used', 0)
                    parsed_pools.append(Pool(id=p_id, name=p_name, pg_num=p_pg, used_bytes=p_used))
                cluster.pools = parsed_pools

                # Process Hosts and map OSDs
                parsed_hosts = []
                for h_dict in mgr_hosts:
                    h_name = h_dict.get('hostname', 'unknown')
                    # Find all OSDs that belong to this host
                    # MGR /osd endpoint usually includes the server name or we map it from the CRUSH tree. 
                    # For simplicity, we filter the flat OSD list if 'server' matches
                    host_osds = []
                    for o_dict in mgr_osds:
                        o_server = o_dict.get('server', '')
                        if o_server == h_name:
                            o_id = o_dict.get('osd', 0)
                            o_up = "up" if o_dict.get('up', 0) == 1 else "down"
                            o_in = bool(o_dict.get('in', 0))
                            o_weight = o_dict.get('weight', 0.0)
                            o_util = o_dict.get('stats', {}).get('stat_bytes_used', 0) / max(1, o_dict.get('stats', {}).get('stat_bytes', 1)) * 100
                            host_osds.append(OSD(id=o_id, name=f"osd.{o_id}", status=o_up, in_cluster=o_in, weight=o_weight, utilization_percent=o_util))
                            
                    parsed_hosts.append(Host(name=h_name, ip="", osds=host_osds))
                
                # If the MGR didn't return host mapping correctly, just lump OSDs into a dummy host
                if not parsed_hosts and mgr_osds:
                    dummy_osds = []
                    for o_dict in mgr_osds:
                        o_id = o_dict.get('osd', 0)
                        o_up = "up" if o_dict.get('up', 0) == 1 else "down"
                        o_in = bool(o_dict.get('in', 0))
                        o_util = o_dict.get('stats', {}).get('stat_bytes_used', 0) / max(1, o_dict.get('stats', {}).get('stat_bytes', 1)) * 100
                        dummy_osds.append(OSD(id=o_id, name=f"osd.{o_id}", status=o_up, in_cluster=o_in, weight=0.0, utilization_percent=o_util))
                    parsed_hosts.append(Host(name="all_nodes", ip="", osds=dummy_osds))

                cluster.hosts = parsed_hosts
                
                clusters.append(cluster)
            except Exception as e:
                err_msg = f"Error fetching real state for {cfg.name}: {e}"
                print(err_msg)
                self.log_event.emit(err_msg)

        return clusters

    async def stop(self):
        self._is_running = False
        # Clean up async connections
        if not self.use_mock:
            for prom_client, mgr_client in self.clients.values():
                await prom_client.close()
                await mgr_client.close()
