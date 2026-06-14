from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt
from cephoverseer.models.dataclasses import CephCluster

class ClusterTreeBuilder:
    """
    Helper class to manage and update a QStandardItemModel representing
    the Ceph cluster hierarchy, updating items in place to avoid UI jumping.
    """
    def __init__(self):
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Explorer"])
        self._root_item = None
        self._hosts_item = None
        self._pools_item = None
        
        # Cache of items to update them in place by ID/Name
        self._items_cache = {}

    def get_model(self):
        return self.model

    def _get_or_create_item(self, parent_item: QStandardItem, key: str, text: str) -> QStandardItem:
        if key in self._items_cache:
            item = self._items_cache[key]
            if item.text() != text:
                item.setText(text)
            return item
        
        item = QStandardItem(text)
        item.setEditable(False)
        
        # Store user data (the key) to identify what is selected later
        item.setData(key, Qt.UserRole)
        
        parent_item.appendRow(item)
        self._items_cache[key] = item
        return item

    def update_tree(self, cluster: CephCluster):
        # 1. Root Cluster Node
        root_key = f"cluster_{cluster.name}"
        if not self._root_item:
            self._root_item = QStandardItem(f"📂 {cluster.name}")
            self._root_item.setEditable(False)
            self._root_item.setData(root_key, Qt.UserRole)
            self.model.appendRow(self._root_item)
            self._items_cache[root_key] = self._root_item
        else:
            self._root_item.setText(f"📂 {cluster.name}")

        # 2. Hosts Category
        hosts_cat_key = f"{root_key}_hosts_cat"
        self._hosts_item = self._get_or_create_item(self._root_item, hosts_cat_key, "🖥️ Hosts")
        
        for host in cluster.hosts:
            host_key = f"host_{host.name}"
            host_text = f"🖥️ {host.name}"
            host_item = self._get_or_create_item(self._hosts_item, host_key, host_text)
            
            for osd in host.osds:
                osd_key = f"osd_{osd.id}"
                status_icon = "🟢" if osd.status == "up" else "🔴"
                osd_text = f"💿 {osd.name} {status_icon} ({osd.utilization_percent:.1f}%)"
                self._get_or_create_item(host_item, osd_key, osd_text)

        # 3. Pools Category
        pools_cat_key = f"{root_key}_pools_cat"
        self._pools_item = self._get_or_create_item(self._root_item, pools_cat_key, "🏊 Pools")
        
        for pool in cluster.pools:
            pool_key = f"pool_{pool.id}"
            pool_text = f"🌊 {pool.name} ({pool.pg_num} PGs)"
            self._get_or_create_item(self._pools_item, pool_key, pool_text)
