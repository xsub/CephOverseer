import asyncio
import random
from cephoverseer.models.dataclasses import CephCluster, Host, OSD, Pool, ClusterTelemetry

class MockAPIClient:
    """
    Simulates fetching data from Prometheus and Ceph MGR via HTTP.
    Uses asyncio.sleep to mimic network latency.
    """
    def __init__(self):
        # Initial dummy state
        self.cluster = CephCluster(
            name="Production-Cluster",
            prometheus_url="http://prometheus:9090",
            mgr_url="https://ceph-mgr:8443",
            hosts=[
                Host(name="node-01", ip="10.0.0.11", osds=[
                    OSD(id=0, name="osd.0", status="up", in_cluster=True, weight=1.0, utilization_percent=45.2),
                    OSD(id=1, name="osd.1", status="up", in_cluster=True, weight=1.0, utilization_percent=46.1),
                ]),
                Host(name="node-02", ip="10.0.0.12", osds=[
                    OSD(id=2, name="osd.2", status="up", in_cluster=True, weight=1.0, utilization_percent=50.5),
                    OSD(id=3, name="osd.3", status="down", in_cluster=False, weight=0.0, utilization_percent=0.0), # Simulated failure
                ])
            ],
            pools=[
                Pool(id=1, name="rbd", pg_num=128, used_bytes=1024**4), # 1TB
                Pool(id=2, name="cephfs_data", pg_num=64, used_bytes=500*1024**3), # 500GB
            ],
            telemetry=ClusterTelemetry(
                health_status="HEALTH_WARN",
                active_pgs=192
            )
        )

    async def fetch_state(self) -> CephCluster:
        """
        Simulate an API call that returns the updated state of the cluster.
        """
        await asyncio.sleep(0.5)  # Simulate network latency
        
        # Simulate changing metrics (like Prometheus would return)
        self.cluster.telemetry.total_iops = random.randint(1000, 5000)
        self.cluster.telemetry.read_bytes_sec = random.randint(10, 500) * 1024**2 # 10-500 MB/s
        self.cluster.telemetry.write_bytes_sec = random.randint(10, 500) * 1024**2
        
        # Jitter OSD utilization slightly
        for host in self.cluster.hosts:
            host.cpu_usage = random.uniform(10.0, 90.0)
            host.ram_usage = random.uniform(40.0, 80.0)
            for osd in host.osds:
                if osd.status == "up":
                    osd.utilization_percent += random.uniform(-0.1, 0.1)
                    osd.utilization_percent = max(0, min(100, osd.utilization_percent))

        return self.cluster
