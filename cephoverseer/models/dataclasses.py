from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class OSD:
    id: int
    name: str
    status: str  # e.g., "up", "down"
    in_cluster: bool  # "in", "out"
    weight: float
    utilization_percent: float

@dataclass
class Host:
    name: str
    ip: str
    osds: List[OSD] = field(default_factory=list)
    cpu_usage: float = 0.0
    ram_usage: float = 0.0

@dataclass
class Pool:
    id: int
    name: str
    pg_num: int
    used_bytes: int

@dataclass
class ClusterTelemetry:
    total_iops: int = 0
    read_bytes_sec: int = 0
    write_bytes_sec: int = 0
    health_status: str = "HEALTH_UNKNOWN"
    active_pgs: int = 0

@dataclass
class CephCluster:
    name: str
    prometheus_url: str
    mgr_url: str
    hosts: List[Host] = field(default_factory=list)
    pools: List[Pool] = field(default_factory=list)
    telemetry: ClusterTelemetry = field(default_factory=ClusterTelemetry)
