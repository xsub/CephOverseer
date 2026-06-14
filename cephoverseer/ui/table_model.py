from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt

class DetailsTableBuilder:
    """
    Manages the QStandardItemModel for the bottom-right details table.
    Converts cluster/host/osd/pool objects into key-value property lists.
    """
    def __init__(self):
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Property", "Value"])

    def get_model(self):
        return self.model

    def update_with_dict(self, data: dict):
        """
        Clears the table and populates it with key-value pairs from the dictionary.
        """
        self.model.removeRows(0, self.model.rowCount())
        for key, value in data.items():
            key_item = QStandardItem(str(key))
            key_item.setEditable(False)
            
            val_item = QStandardItem(str(value))
            val_item.setEditable(False)
            
            self.model.appendRow([key_item, val_item])
