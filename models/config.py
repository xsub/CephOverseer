import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List

@dataclass
class ClusterConfig:
    name: str
    prometheus_url: str
    mgr_url: str
    username: str = ""
    password: str = ""

class ConfigManager:
    """
    Manages loading and saving Ceph cluster connection configurations.
    Stores config in the user's home directory.
    """
    def __init__(self, config_file: str = "config.json"):
        # Setup config directory (e.g., ~/.cephoverseer)
        self.config_dir = Path.home() / ".cephoverseer"
        self.config_file = self.config_dir / config_file
        self.clusters: List[ClusterConfig] = []
        self.load_config()

    def load_config(self):
        """Loads configuration from disk, creates default if missing."""
        if not self.config_file.exists():
            self._create_default_config()
            
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
                self.clusters = [ClusterConfig(**c) for c in data.get("clusters", [])]
        except Exception as e:
            print(f"Failed to load config: {e}. Using defaults.")
            self.clusters = []

    def _create_default_config(self):
        """Creates a dummy configuration file for first-time users."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        default_clusters = [
            ClusterConfig(
                name="Local-Test-Cluster", 
                prometheus_url="http://localhost:9090", 
                mgr_url="https://localhost:8443"
            )
        ]
        
        with open(self.config_file, 'w') as f:
            json.dump({"clusters": [asdict(c) for c in default_clusters]}, f, indent=4)

    def save_config(self):
        """Saves current cluster list to disk."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump({"clusters": [asdict(c) for c in self.clusters]}, f, indent=4)

    def add_cluster(self, cluster: ClusterConfig):
        self.clusters.append(cluster)
        self.save_config()

    def remove_cluster(self, name: str):
        self.clusters = [c for c in self.clusters if c.name != name]
        self.save_config()
