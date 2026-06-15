from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QFormLayout, 
    QLineEdit, QPushButton, QMessageBox, QGroupBox, QWidget, QCheckBox
)
from PyQt5.QtCore import Qt
from models.config import ConfigManager, ClusterConfig

class SettingsDialog(QDialog):
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cluster Connection Settings")
        self.resize(700, 450)
        
        self.config_manager = config_manager
        
        # Keep a local working copy
        self._working_clusters = []
        for c in self.config_manager.clusters:
            self._working_clusters.append(
                ClusterConfig(c.name, c.prometheus_url, c.mgr_url, c.username, c.password)
            )
        self._working_use_sim = self.config_manager.use_simulation

        self.init_ui()
        self.refresh_list()

    def init_ui(self):
        main_layout = QHBoxLayout(self)

        # --- Left Pane: List of Clusters ---
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        
        self.cluster_list = QListWidget()
        self.cluster_list.currentRowChanged.connect(self.on_cluster_selected)
        left_layout.addWidget(self.cluster_list)

        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("➕ Add Cluster")
        self.btn_remove = QPushButton("➖ Remove")
        
        self.btn_add.clicked.connect(self.on_add_cluster)
        self.btn_remove.clicked.connect(self.on_remove_cluster)
        
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_remove)
        left_layout.addLayout(btn_layout)
        
        main_layout.addWidget(left_pane, stretch=1)

        # --- Right Pane: Configuration Form ---
        right_pane = QGroupBox("Cluster Details")
        form_layout = QFormLayout(right_pane)

        self.edit_name = QLineEdit()
        self.edit_prom_url = QLineEdit()
        self.edit_mgr_url = QLineEdit()
        self.edit_user = QLineEdit()
        
        self.edit_pass = QLineEdit()
        self.edit_pass.setEchoMode(QLineEdit.Password)

        # Connect text changes to update the working model immediately
        self.edit_name.textChanged.connect(lambda t: self._update_current_field("name", t))
        self.edit_prom_url.textChanged.connect(lambda t: self._update_current_field("prometheus_url", t))
        self.edit_mgr_url.textChanged.connect(lambda t: self._update_current_field("mgr_url", t))
        self.edit_user.textChanged.connect(lambda t: self._update_current_field("username", t))
        self.edit_pass.textChanged.connect(lambda t: self._update_current_field("password", t))

        form_layout.addRow("Cluster Name:", self.edit_name)
        form_layout.addRow("Prometheus URL:", self.edit_prom_url)
        form_layout.addRow("Ceph MGR URL:", self.edit_mgr_url)
        form_layout.addRow("Username (MGR):", self.edit_user)
        form_layout.addRow("Password (MGR):", self.edit_pass)

        # Bottom Buttons & Sim Toggle
        action_btn_layout = QHBoxLayout()
        
        self.chk_sim = QCheckBox("Run in Simulation Mode (Mock Data)")
        self.chk_sim.setChecked(self._working_use_sim)
        self.chk_sim.stateChanged.connect(lambda state: setattr(self, '_working_use_sim', state == Qt.Checked))
        
        self.btn_save = QPushButton("Save && Apply")
        self.btn_cancel = QPushButton("Cancel")
        
        self.btn_save.clicked.connect(self.on_save)
        self.btn_cancel.clicked.connect(self.reject)
        
        action_btn_layout.addWidget(self.chk_sim)
        action_btn_layout.addStretch()
        action_btn_layout.addWidget(self.btn_cancel)
        action_btn_layout.addWidget(self.btn_save)

        # Combine Right Side
        right_main_layout = QVBoxLayout()
        right_main_layout.addWidget(right_pane)
        right_main_layout.addLayout(action_btn_layout)

        main_layout.addLayout(right_main_layout, stretch=2)

    def refresh_list(self, select_idx=0):
        self.cluster_list.blockSignals(True)
        self.cluster_list.clear()
        for c in self._working_clusters:
            self.cluster_list.addItem(c.name)
        self.cluster_list.blockSignals(False)
        
        if self._working_clusters and 0 <= select_idx < len(self._working_clusters):
            self.cluster_list.setCurrentRow(select_idx)
        else:
            self._clear_form()

    def _clear_form(self):
        self.edit_name.clear()
        self.edit_prom_url.clear()
        self.edit_mgr_url.clear()
        self.edit_user.clear()
        self.edit_pass.clear()

    def on_cluster_selected(self, idx):
        if idx < 0 or idx >= len(self._working_clusters):
            self._clear_form()
            return
            
        c = self._working_clusters[idx]
        self.edit_name.blockSignals(True)
        self.edit_name.setText(c.name)
        self.edit_name.blockSignals(False)
        
        self.edit_prom_url.setText(c.prometheus_url)
        self.edit_mgr_url.setText(c.mgr_url)
        self.edit_user.setText(c.username)
        self.edit_pass.setText(c.password)

    def _update_current_field(self, field, value):
        idx = self.cluster_list.currentRow()
        if 0 <= idx < len(self._working_clusters):
            setattr(self._working_clusters[idx], field, value)
            
            # If name changes, update list visual without losing selection
            if field == "name":
                item = self.cluster_list.item(idx)
                if item:
                    item.setText(value)

    def on_add_cluster(self):
        new_c = ClusterConfig(
            name=f"New-Cluster-{len(self._working_clusters)+1}",
            prometheus_url="http://",
            mgr_url="https://"
        )
        self._working_clusters.append(new_c)
        self.refresh_list(select_idx=len(self._working_clusters)-1)

    def on_remove_cluster(self):
        idx = self.cluster_list.currentRow()
        if 0 <= idx < len(self._working_clusters):
            del self._working_clusters[idx]
            self.refresh_list(select_idx=max(0, idx-1))

    def on_save(self):
        # Validate names are unique and not empty
        names = [c.name for c in self._working_clusters]
        if len(names) != len(set(names)) or any(not n.strip() for n in names):
            QMessageBox.warning(self, "Validation Error", "All clusters must have a unique, non-empty name.")
            return
            
        # Apply working list to actual ConfigManager
        self.config_manager.clusters = self._working_clusters
        self.config_manager.use_simulation = self._working_use_sim
        self.config_manager.save_config()
        self.accept()
