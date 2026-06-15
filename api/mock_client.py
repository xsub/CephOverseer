import asyncio
import random
from typing import List
from models.dataclasses import CephCluster, Host, OSD, Pool, ClusterTelemetry
from models.config import ConfigManager

class MockAPIClient:
    """
    Simulates fetching data from Prometheus and Ceph MGR via HTTP.
    Uses asyncio.sleep to mimic network latency.
    """
    def __init__(self, config_manager: ConfigManager = None):
        self.config_manager = config_manager or ConfigManager()
        self.clusters = []
        self._initialize_from_config()

    def _initialize_from_config(self):
        """
        Dynamically generate mock data based on the clusters defined in the user's config file.
        """
        self.clusters = []
        for cfg in self.config_manager.clusters:
            # Generate a mock cluster profile based on the loaded configuration
            cluster = CephCluster(
                name=cfg.name,
                prometheus_url=cfg.prometheus_url,
                mgr_url=cfg.mgr_url,
                hosts=[
                    Host(name="node-01", ip="10.0.0.11", osds=[
                        OSD(id=0, name="osd.0", status="up", in_cluster=True, weight=1.0, utilization_percent=random.uniform(20,60)),
                        OSD(id=1, name="osd.1", status="up", in_cluster=True, weight=1.0, utilization_percent=random.uniform(20,60)),
                    ]),
                    Host(name="node-02", ip="10.0.0.12", osds=[
                        OSD(id=2, name="osd.2", status="up", in_cluster=True, weight=1.0, utilization_percent=random.uniform(20,60)),
                    ])
                ],
                pools=[
                    Pool(id=1, name="rbd", pg_num=128, used_bytes=random.randint(100, 500) * 1024**3),
                ],
                telemetry=ClusterTelemetry(
                    health_status="HEALTH_OK" if random.random() > 0.1 else "HEALTH_WARN",
                    active_pgs=128
                )
            )
            self.clusters.append(cluster)

        # Fallback if config is empty
        if not self.clusters:
            self.clusters = [
                CephCluster(name="Empty-Config", prometheus_url="", mgr_url="")
            ]

    async def fetch_state(self) -> List[CephCluster]:
        """
        Simulate an API call that returns the updated state of ALL configured clusters.
        """
        await asyncio.sleep(0.5)  # Simulate network latency
        
        # Simulate changing metrics for all clusters
        for cluster in self.clusters:
            # Staging has lower IOPS than Production
            base_iops = 1000 if "Production" in cluster.name else 100
            
            cluster.telemetry.total_iops = random.randint(base_iops, base_iops * 5)
            cluster.telemetry.read_bytes_sec = random.randint(10, 500) * 1024**2 
            cluster.telemetry.write_bytes_sec = random.randint(10, 500) * 1024**2
            
            # Jitter OSD utilization slightly
            for host in cluster.hosts:
                host.cpu_usage = random.uniform(10.0, 90.0)
                host.ram_usage = random.uniform(40.0, 80.0)
                for osd in host.osds:
                    if osd.status == "up":
                        osd.utilization_percent += random.uniform(-0.1, 0.1)
                        osd.utilization_percent = max(0, min(100, osd.utilization_percent))

        return self.clusters
