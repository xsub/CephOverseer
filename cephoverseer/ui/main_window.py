from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QTreeView, QTableView, QLabel
)
from PyQt5.QtCore import Qt
import pyqtgraph as pg

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CephOverseer")
        self.resize(1200, 800)

        # Main central widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Splitter to separate Explorer Tree (Left) from Content (Right)
        self.splitter = QSplitter(Qt.Horizontal)
        self.layout.addWidget(self.splitter)

        # 1. Left Pane: Explorer Tree View
        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(True)
        self.splitter.addWidget(self.tree_view)

        # 2. Right Pane: Split vertically (Top: Graphs, Bottom: Details)
        self.right_pane = QWidget()
        self.right_layout = QVBoxLayout(self.right_pane)
        self.splitter.addWidget(self.right_pane)

        # 2a. Top Right: PyQtGraph
        self.graph_widget = pg.PlotWidget(title="Live Telemetry (IOPS)")
        self.graph_widget.setBackground('w')
        self.graph_widget.showGrid(x=True, y=True)
        self.right_layout.addWidget(self.graph_widget)

        # Set up a plot data line
        self.time_data = []
        self.iops_data = []
        self.data_line = self.graph_widget.plot(
            self.time_data, self.iops_data, pen=pg.mkPen(color=(0, 114, 178), width=2)
        )

        # 2b. Bottom Right: Details/Properties Table
        self.details_table = QTableView()
        self.right_layout.addWidget(self.details_table)

        # Initial splitter sizes (30% left, 70% right)
        self.splitter.setSizes([360, 840])
        
        # Status Bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

    def update_ui_with_data(self, cluster_state):
        """
        Slot called by the background worker when new data arrives.
        """
        # Update Status Bar with Health
        health_color = "green" if cluster_state.telemetry.health_status == "HEALTH_OK" else ("orange" if "WARN" in cluster_state.telemetry.health_status else "red")
        self.status_bar.showMessage(f"Cluster: {cluster_state.name} | Status: {cluster_state.telemetry.health_status}")
        self.status_bar.setStyleSheet(f"color: {health_color}; font-weight: bold;")

        # Update Graph (Simulate a rolling window of 60 data points)
        self.iops_data.append(cluster_state.telemetry.total_iops)
        if len(self.time_data) == 0:
            self.time_data.append(0)
        else:
            self.time_data.append(self.time_data[-1] + 1)
            
        if len(self.iops_data) > 60:
            self.iops_data = self.iops_data[-60:]
            self.time_data = self.time_data[-60:]
            
        self.data_line.setData(self.time_data, self.iops_data)

        # TODO: Update the Tree View and Table View using QAbstractItemModels
