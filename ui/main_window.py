from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QTreeView, QTableView, QLabel, QHeaderView
)
from PyQt5.QtCore import Qt, QItemSelectionModel
import pyqtgraph as pg
from ui.tree_model import ClusterTreeBuilder
from ui.table_model import DetailsTableBuilder

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CephOverseer")
        self.resize(1200, 800)
        
        # Currently selected entity key
        self.current_selection_key = None
        self.last_clusters_state = []

        # Main central widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Splitter to separate Explorer Tree (Left) from Content (Right)
        self.splitter = QSplitter(Qt.Horizontal)
        self.layout.addWidget(self.splitter)

        # 1. Left Pane: Explorer Tree View
        self.tree_builder = ClusterTreeBuilder()
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.tree_builder.get_model())
        self.tree_view.setHeaderHidden(False)
        # Auto-expand initially
        self._initial_expand_done = False
        self.splitter.addWidget(self.tree_view)

        # 2. Right Pane: Split vertically (Top: Graphs, Bottom: Details)
        self.right_pane = QWidget()
        self.right_layout = QVBoxLayout(self.right_pane)
        self.splitter.addWidget(self.right_pane)

        # 2a. Top Right: PyQtGraph
        self.graph_widget = pg.PlotWidget(title="Live Telemetry (Cluster IOPS)")
        self.graph_widget.setBackground('w')
        self.graph_widget.showGrid(x=True, y=True)
        self.right_layout.addWidget(self.graph_widget)

        # Set up plot data lines for different contexts
        self.time_data = []
        self.graph_data_1 = [] # E.g., Total IOPS or CPU
        self.data_line = self.graph_widget.plot(
            self.time_data, self.graph_data_1, pen=pg.mkPen(color=(0, 114, 178), width=2)
        )

        # 2b. Bottom Right: Details/Properties Table
        self.table_builder = DetailsTableBuilder()
        self.details_table = QTableView()
        self.details_table.setModel(self.table_builder.get_model())
        self.details_table.horizontalHeader().setStretchLastSection(True)
        self.details_table.verticalHeader().setVisible(False)
        self.right_layout.addWidget(self.details_table)

        # Initial splitter sizes (30% left, 70% right)
        self.splitter.setSizes([360, 840])
        
        # Connect Selection Changed Event on the Tree View
        self.tree_view.selectionModel().selectionChanged.connect(self.on_tree_selection_changed)
        
        # Status Bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

    def update_ui_with_data(self, clusters_state):
        """
        Slot called by the background worker when new data arrives.
        """
        self.last_clusters_state = clusters_state

        # Update Status Bar with Health of the first cluster for now (or a combined state)
        if clusters_state:
            cluster = clusters_state[0]
            health_color = "green" if cluster.telemetry.health_status == "HEALTH_OK" else ("orange" if "WARN" in cluster.telemetry.health_status else "red")
            self.status_bar.showMessage(f"Cluster: {cluster.name} | Status: {cluster.telemetry.health_status} (+ {len(clusters_state)-1} more)")
            self.status_bar.setStyleSheet(f"color: {health_color}; font-weight: bold;")

        # Update the Tree View using QStandardItemModel
        self.tree_builder.update_tree(clusters_state)
        
        # Expand tree on first load
        if not self._initial_expand_done:
            self.tree_view.expandAll()
            self._initial_expand_done = True
            
        # Update details table and graph context if something is selected
        self.update_details_table()
        self.update_graph_context()

    def update_graph_context(self):
        """
        Updates the real-time graph depending on what is selected in the tree view.
        """
        if not self.last_clusters_state:
            return

        new_val = 0
        title = "Live Telemetry"

        key = self.current_selection_key
        if not key or key.startswith("cluster_"):
            cluster_name = key.split("cluster_")[1] if key else self.last_clusters_state[0].name
            for cluster in self.last_clusters_state:
                if cluster.name == cluster_name:
                    new_val = cluster.telemetry.total_iops
                    title = f"Live Telemetry ({cluster.name} Total IOPS: {new_val})"
                    break
        elif key.startswith("host_"):
            # Format: host_{cluster_name}_{hostname}
            parts = key.split("_")
            cluster_name = parts[1]
            hostname = "_".join(parts[2:])
            for cluster in self.last_clusters_state:
                if cluster.name == cluster_name:
                    for host in cluster.hosts:
                        if host.name == hostname:
                            new_val = host.cpu_usage
                            title = f"Live Telemetry ({host.name} CPU Usage: {new_val:.1f}%)"
                            break
                    break
        elif key.startswith("osd_"):
            # Format: osd_{cluster_name}_{osd_id}
            parts = key.split("_")
            cluster_name = parts[1]
            osd_id = int(parts[2])
            for cluster in self.last_clusters_state:
                if cluster.name == cluster_name:
                    for host in cluster.hosts:
                        for osd in host.osds:
                            if osd.id == osd_id:
                                new_val = osd.utilization_percent
                                title = f"Live Telemetry ({osd.name} Utilization: {new_val:.1f}%)"
                                break
                    break

        self.graph_widget.setTitle(title)

        # Update Graph Data Arrays (Simulate a rolling window of 60 data points)
        self.graph_data_1.append(new_val)
        if len(self.time_data) == 0:
            self.time_data.append(0)
        else:
            self.time_data.append(self.time_data[-1] + 1)
            
        if len(self.graph_data_1) > 60:
            self.graph_data_1 = self.graph_data_1[-60:]
            self.time_data = self.time_data[-60:]
            
        self.data_line.setData(self.time_data, self.graph_data_1)

    def on_tree_selection_changed(self, selected, deselected):
        indexes = selected.indexes()
        if indexes:
            item_data = indexes[0].data(Qt.UserRole)
            if item_data:
                # If we change selection, clear the graph history to avoid jumping charts
                if self.current_selection_key != item_data:
                    self.time_data.clear()
                    self.graph_data_1.clear()

                self.current_selection_key = item_data
                self.update_details_table()
                self.update_graph_context()

    def update_details_table(self):
        if not self.last_clusters_state or not self.current_selection_key:
            return
            
        data_to_show = {}
        key = self.current_selection_key
        
        # Helper to find cluster by name
        def get_cluster(name):
            for c in self.last_clusters_state:
                if c.name == name:
                    return c
            return None
        
        if key.startswith("cluster_"):
            cluster_name = key.split("cluster_")[1]
            cluster = get_cluster(cluster_name)
            if cluster:
                data_to_show = {
                    "Name": cluster.name,
                    "Prometheus URL": cluster.prometheus_url,
                    "MGR URL": cluster.mgr_url,
                    "Health Status": cluster.telemetry.health_status,
                    "Total IOPS": cluster.telemetry.total_iops,
                    "Read Bytes/sec": f"{cluster.telemetry.read_bytes_sec / 1024**2:.2f} MB/s",
                    "Write Bytes/sec": f"{cluster.telemetry.write_bytes_sec / 1024**2:.2f} MB/s",
                    "Active PGs": cluster.telemetry.active_pgs
                }
        elif key.startswith("host_"):
            parts = key.split("_")
            cluster_name = parts[1]
            hostname = "_".join(parts[2:])
            cluster = get_cluster(cluster_name)
            if cluster:
                for host in cluster.hosts:
                    if host.name == hostname:
                        data_to_show = {
                            "Hostname": host.name,
                            "IP Address": host.ip,
                            "CPU Usage": f"{host.cpu_usage:.1f}%",
                            "RAM Usage": f"{host.ram_usage:.1f}%",
                            "OSDs Count": len(host.osds)
                        }
                        break
        elif key.startswith("osd_"):
            parts = key.split("_")
            cluster_name = parts[1]
            osd_id = int(parts[2])
            cluster = get_cluster(cluster_name)
            if cluster:
                for host in cluster.hosts:
                    for osd in host.osds:
                        if osd.id == osd_id:
                            data_to_show = {
                                "OSD ID": osd.id,
                                "Name": osd.name,
                                "Status": osd.status,
                                "In Cluster": osd.in_cluster,
                                "Weight": osd.weight,
                                "Utilization": f"{osd.utilization_percent:.2f}%",
                                "Host": host.name
                            }
                            break
        elif key.startswith("pool_"):
            parts = key.split("_")
            cluster_name = parts[1]
            pool_id = int(parts[2])
            cluster = get_cluster(cluster_name)
            if cluster:
                for pool in cluster.pools:
                    if pool.id == pool_id:
                        data_to_show = {
                            "Pool ID": pool.id,
                            "Name": pool.name,
                            "PG Num": pool.pg_num,
                            "Used Space": f"{pool.used_bytes / 1024**3:.2f} GB"
                        }
                        break
                    
        self.table_builder.update_with_dict(data_to_show)
