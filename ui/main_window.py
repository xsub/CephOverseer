from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QTreeView, QTableView, QLabel, QHeaderView, QAction, QMenuBar, QDialog, QTextEdit, QDockWidget, QMenu, QMessageBox, QSystemTrayIcon, QInputDialog
)
from PyQt5.QtCore import Qt, QItemSelectionModel, pyqtSignal
import pyqtgraph as pg
from ui.tree_model import ClusterTreeBuilder
from ui.table_model import DetailsTableBuilder
from ui.settings_dialog import SettingsDialog
from models.config import ConfigManager

class MainWindow(QMainWindow):
    # Signal to tell main.py that settings changed and worker needs a restart
    settings_changed = pyqtSignal()
    # Signal for administrative actions
    osd_action_requested = pyqtSignal(str, int, str)
    pool_action_requested = pyqtSignal(str, str, str, int)

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.setWindowTitle("CephOverseer")
        self.resize(1200, 800)
        self.config_manager = config_manager
        
        # Currently selected entity key
        self.current_selection_key = None
        self.last_clusters_state = []

        self._init_menu()

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
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.on_tree_context_menu)
        # Auto-expand initially
        self._initial_expand_done = False
        self.splitter.addWidget(self.tree_view)

        # 2. Right Pane: Split vertically (Top: Graphs, Bottom: Details)
        self.right_pane = QWidget()
        self.right_layout = QVBoxLayout(self.right_pane)
        self.splitter.addWidget(self.right_pane)

        # Desktop Notifications
        self.cluster_health_states = {}
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(self.style().SP_ComputerIcon))
        self.tray_icon.show()

        # 2a. Top Right: PyQtGraph GraphicsLayoutWidget for Multiple Charts
        self.graph_layout = pg.GraphicsLayoutWidget()
        self.graph_layout.setBackground('w')
        self.right_layout.addWidget(self.graph_layout)

        self.plot_iops = self.graph_layout.addPlot(title="Total IOPS")
        self.plot_iops.showGrid(x=True, y=True)
        self.graph_layout.nextRow()
        self.plot_bw = self.graph_layout.addPlot(title="Bandwidth (MB/s)")
        self.plot_bw.showGrid(x=True, y=True)
        self.plot_bw.addLegend()

        # Set up plot data lines
        self.time_data = []
        self.iops_data = []
        self.read_bw_data = []
        self.write_bw_data = []
        
        self.line_iops = self.plot_iops.plot(pen=pg.mkPen(color=(0, 114, 178), width=2))
        self.line_read_bw = self.plot_bw.plot(pen=pg.mkPen(color=(0, 158, 115), width=2), name="Read")
        self.line_write_bw = self.plot_bw.plot(pen=pg.mkPen(color=(213, 94, 0), width=2), name="Write")

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

        # 3. Bottom Pane: Logging Console (DockWidget)
        self.log_dock = QDockWidget("Events Console", self)
        self.log_dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_dock.setWidget(self.log_console)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        
        # Status Bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

    def _init_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        
        settings_action = QAction("Settings...", self)
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def open_settings(self):
        dialog = SettingsDialog(self.config_manager, self)
        if dialog.exec_() == QDialog.Accepted:
            # Settings were saved, we should tell the worker to restart
            self.settings_changed.emit()

    def log_event(self, message: str):
        """
        Appends a message to the logging console with a timestamp.
        """
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_console.append(f"[{timestamp}] {message}")

    def update_ui_with_data(self, clusters_state):
        """
        Slot called by the background worker when new data arrives.
        """
        self.last_clusters_state = clusters_state

        # Desktop Notifications for Health State
        for cluster in clusters_state:
            old_status = self.cluster_health_states.get(cluster.name, "HEALTH_OK")
            new_status = cluster.telemetry.health_status
            if old_status != new_status and new_status in ["HEALTH_WARN", "HEALTH_ERR"]:
                self.tray_icon.showMessage(
                    "CephOverseer Alert", 
                    f"Cluster '{cluster.name}' transitioned to {new_status}", 
                    QSystemTrayIcon.Warning, 5000
                )
            self.cluster_health_states[cluster.name] = new_status

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

        iops_val = 0
        read_bw_val = 0
        write_bw_val = 0
        title_iops = "Total IOPS"
        title_bw = "Bandwidth (MB/s)"

        key = self.current_selection_key
        
        # Cross-Cluster Federation View (Root selected or nothing)
        if not key:
            iops_val = sum(c.telemetry.total_iops for c in self.last_clusters_state)
            read_bw_val = sum(c.telemetry.read_bytes_sec for c in self.last_clusters_state) / 1024**2
            write_bw_val = sum(c.telemetry.write_bytes_sec for c in self.last_clusters_state) / 1024**2
            title_iops = f"Federated IOPS: {iops_val}"
            title_bw = f"Federated Bandwidth: R={read_bw_val:.1f} W={write_bw_val:.1f} MB/s"
            
        elif key.startswith("cluster_"):
            cluster_name = key.split("cluster_")[1]
            for cluster in self.last_clusters_state:
                if cluster.name == cluster_name:
                    iops_val = cluster.telemetry.total_iops
                    read_bw_val = cluster.telemetry.read_bytes_sec / 1024**2
                    write_bw_val = cluster.telemetry.write_bytes_sec / 1024**2
                    title_iops = f"{cluster.name} IOPS: {iops_val}"
                    title_bw = f"{cluster.name} Bandwidth: R={read_bw_val:.1f} W={write_bw_val:.1f} MB/s"
                    break
        elif key.startswith("host_"):
            parts = key.split("_")
            cluster_name = parts[1]
            hostname = "_".join(parts[2:])
            for cluster in self.last_clusters_state:
                if cluster.name == cluster_name:
                    for host in cluster.hosts:
                        if host.name == hostname:
                            iops_val = host.cpu_usage
                            read_bw_val = host.ram_usage
                            title_iops = f"{host.name} CPU Usage: {iops_val:.1f}%"
                            title_bw = f"{host.name} RAM Usage: {read_bw_val:.1f}%"
                            break
                    break
        elif key.startswith("osd_"):
            parts = key.split("_")
            cluster_name = parts[1]
            osd_id = int(parts[2])
            for cluster in self.last_clusters_state:
                if cluster.name == cluster_name:
                    for host in cluster.hosts:
                        for osd in host.osds:
                            if osd.id == osd_id:
                                iops_val = osd.utilization_percent
                                title_iops = f"{osd.name} Utilization: {iops_val:.1f}%"
                                title_bw = f"{osd.name} Weight: {osd.weight}"
                                read_bw_val = osd.weight
                                break
                    break
        elif key.startswith("pool_"):
            parts = key.split("_")
            cluster_name = parts[1]
            pool_id = int(parts[2])
            for cluster in self.last_clusters_state:
                if cluster.name == cluster_name:
                    for pool in cluster.pools:
                        if pool.id == pool_id:
                            iops_val = pool.used_bytes / 1024**3
                            read_bw_val = pool.pg_num
                            title_iops = f"{pool.name} Used Space: {iops_val:.1f} GB"
                            title_bw = f"{pool.name} PGs: {read_bw_val}"
                            break
                    break

        self.plot_iops.setTitle(title_iops)
        self.plot_bw.setTitle(title_bw)

        # Update Arrays
        if len(self.time_data) == 0:
            self.time_data.append(0)
        else:
            self.time_data.append(self.time_data[-1] + 1)
            
        self.iops_data.append(iops_val)
        self.read_bw_data.append(read_bw_val)
        self.write_bw_data.append(write_bw_val)
            
        if len(self.time_data) > 60:
            self.time_data = self.time_data[-60:]
            self.iops_data = self.iops_data[-60:]
            self.read_bw_data = self.read_bw_data[-60:]
            self.write_bw_data = self.write_bw_data[-60:]
            
        self.line_iops.setData(self.time_data, self.iops_data)
        self.line_read_bw.setData(self.time_data, self.read_bw_data)
        self.line_write_bw.setData(self.time_data, self.write_bw_data)

    def on_tree_context_menu(self, position):
        indexes = self.tree_view.selectedIndexes()
        if not indexes:
            return
            
        index = indexes[0]
        item_data = index.data(Qt.UserRole)
        
        if not item_data:
            return
            
        menu = QMenu()
        
        if item_data.startswith("osd_"):
            parts = item_data.split("_")
            cluster_name = parts[1]
            osd_id = int(parts[2])
            
            mark_out_action = menu.addAction(f"Mark OSD.{osd_id} OUT")
            mark_in_action = menu.addAction(f"Mark OSD.{osd_id} IN")
            menu.addSeparator()
            mark_down_action = menu.addAction(f"Mark OSD.{osd_id} DOWN")

            action = menu.exec_(self.tree_view.viewport().mapToGlobal(position))
            
            if action:
                cmd = ""
                if action == mark_out_action: cmd = "out"
                elif action == mark_in_action: cmd = "in"
                elif action == mark_down_action: cmd = "down"
                
                if cmd:
                    self.trigger_osd_action(cluster_name, osd_id, cmd)
                    
        elif item_data.startswith("pool_"):
            parts = item_data.split("_")
            cluster_name = parts[1]
            pool_id = int(parts[2])
            
            # Find pool name
            pool_name = ""
            for c in self.last_clusters_state:
                if c.name == cluster_name:
                    for p in c.pools:
                        if p.id == pool_id:
                            pool_name = p.name
                            break
                    break
            
            if not pool_name:
                return
                
            set_pg_action = menu.addAction(f"Set PG Num for '{pool_name}'...")
            action = menu.exec_(self.tree_view.viewport().mapToGlobal(position))
            
            if action == set_pg_action:
                new_pg, ok = QInputDialog.getInt(self, "Set PG Num", f"New PG count for {pool_name}:", 128, 1, 32768, 1)
                if ok:
                    self.log_event(f"Action requested: Set pool '{pool_name}' pg_num to {new_pg}...")
                    self.pool_action_requested.emit(cluster_name, pool_name, "pg_num", new_pg)

    def trigger_osd_action(self, cluster_name: str, osd_id: int, action: str):
        reply = QMessageBox.question(
            self, 'Confirm Action',
            f"Are you sure you want to mark osd.{osd_id} '{action}' in cluster '{cluster_name}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.log_event(f"Action requested: Mark osd.{osd_id} '{action}' via MGR API...")
            # Ideally this triggers the worker to do an async call. 
            # We emit a signal that the main loop can catch and route to the specific MGR Client.
            self.osd_action_requested.emit(cluster_name, osd_id, action)

    def on_tree_selection_changed(self, selected, deselected):
        indexes = selected.indexes()
        if indexes:
            item_data = indexes[0].data(Qt.UserRole)
            if item_data:
                # If we change selection, clear the graph history to avoid jumping charts
                if self.current_selection_key != item_data:
                    self.time_data.clear()
                    self.iops_data.clear()
                    self.read_bw_data.clear()
                    self.write_bw_data.clear()

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
