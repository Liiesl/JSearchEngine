import sys
import os
import winreg
import ctypes
import json
import datetime
from pathlib import Path
from collections import Counter

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QListWidget, QPushButton, QLabel, 
                               QMessageBox, QTabWidget, QInputDialog, QFileDialog,
                               QListWidgetItem, QStyledItemDelegate, QStyle)
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QIcon, QAction, QColor, QPainter, QBrush, QPen

# Windows Constants for Broadcasting changes
HWND_BROADCAST = 0xFFFF
WM_SETTINGCHANGE = 0x001A
SMTO_ABORTIFHUNG = 0x0002

# Custom Roles for the Delegate
ROLE_MISSING = Qt.UserRole + 1
ROLE_DUPLICATE = Qt.UserRole + 2

class PathRegistryManager:
    """Handles low-level registry operations safely."""
    
    def __init__(self):
        self.user_key_path = r"Environment"
        self.system_key_path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"

    def get_path(self, scope="user"):
        """Reads the PATH variable from registry."""
        hkey = winreg.HKEY_CURRENT_USER if scope == "user" else winreg.HKEY_LOCAL_MACHINE
        sub_key = self.user_key_path if scope == "user" else self.system_key_path
        
        try:
            with winreg.OpenKey(hkey, sub_key, 0, winreg.KEY_READ) as key:
                try:
                    value, reg_type = winreg.QueryValueEx(key, "Path")
                    # Handle empty path
                    if not value:
                        return [], reg_type
                    # Split by semicolon, remove empty strings
                    paths = [p for p in value.split(';') if p]
                    return paths, reg_type
                except FileNotFoundError:
                    return [], winreg.REG_EXPAND_SZ
        except PermissionError:
            return None, None # Signal that we don't have access

    def set_path(self, scope, path_list, reg_type):
        """Writes the PATH variable to registry."""
        hkey = winreg.HKEY_CURRENT_USER if scope == "user" else winreg.HKEY_LOCAL_MACHINE
        sub_key = self.user_key_path if scope == "user" else self.system_key_path
        
        # Join with semicolons
        path_str = ";".join(path_list)
        
        try:
            # We need KEY_SET_VALUE access
            with winreg.OpenKey(hkey, sub_key, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "Path", 0, reg_type, path_str)
            return True
        except PermissionError:
            return False
        except Exception as e:
            print(f"Error writing registry: {e}")
            return False

    def broadcast_changes(self):
        """Notifies the OS that environment variables have changed."""
        result = ctypes.c_long()
        send_message = ctypes.windll.user32.SendMessageTimeoutW
        # Notify top-level windows
        send_message(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", 
                     SMTO_ABORTIFHUNG, 5000, ctypes.byref(result))

class StatusDelegate(QStyledItemDelegate):
    """Custom delegate to draw M (Missing) and D (Duplicate) badges."""
    def paint(self, painter, option, index):
        painter.save()
        
        # Draw standard background (selection highlight, etc.)
        self.parent().style().drawControl(QStyle.CE_ItemViewItem, option, painter, self.parent())
        
        # Retrieve data
        is_missing = index.data(ROLE_MISSING)
        is_duplicate = index.data(ROLE_DUPLICATE)
        text = index.data(Qt.DisplayRole)
        
        rect = option.rect
        # Badge configuration
        badge_size = 20
        badge_margin = 4
        
        # Calculate badges to draw
        badges = []
        if is_duplicate:
            badges.append(("D", QColor("#FF8C00"))) # Dark Orange
        if is_missing:
            badges.append(("M", QColor("#D32F2F"))) # Red
            
        # Draw badges from Right to Left
        current_right = rect.right() - badge_margin
        
        for letter, color in badges:
            badge_rect = QRect(current_right - badge_size, rect.top() + (rect.height() - badge_size)//2, 
                               badge_size, badge_size)
            
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(badge_rect, 4, 4)
            
            painter.setPen(Qt.white)
            painter.drawText(badge_rect, Qt.AlignCenter, letter)
            
            current_right -= (badge_size + badge_margin)

        # Draw Text
        # Ensure text doesn't overlap badges
        text_rect = QRect(rect.left() + 5, rect.top(), 
                          current_right - rect.left() - 10, rect.height())
        
        # Set text color based on selection state
        if option.state & QStyle.State_Selected:
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(option.palette.text().color())
            
        # Draw text elided if it's too long
        elided_text = painter.fontMetrics().elidedText(text, Qt.ElideMiddle, text_rect.width())
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, elided_text)
        
        painter.restore()

class PathTab(QWidget):
    """A tab for editing a specific path list (User or System)."""
    
    def __init__(self, scope, manager, parent=None):
        super().__init__(parent)
        self.scope = scope
        self.manager = manager
        self.current_reg_type = winreg.REG_EXPAND_SZ # Default
        self.original_paths = []
        
        self.layout = QVBoxLayout(self)
        
        # List Widget
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        # Apply custom delegate
        self.delegate = StatusDelegate(self.list_widget)
        self.list_widget.setItemDelegate(self.delegate)
        
        self.layout.addWidget(self.list_widget)
        
        # Buttons Layout
        btn_layout = QHBoxLayout()
        
        self.btn_add = QPushButton("Add Folder...")
        self.btn_edit = QPushButton("Edit Text")
        self.btn_remove = QPushButton("Remove")
        self.btn_up = QPushButton("Move Up")
        self.btn_down = QPushButton("Move Down")
        
        for btn in [self.btn_add, self.btn_edit, self.btn_remove, self.btn_up, self.btn_down]:
            btn_layout.addWidget(btn)
            
        self.layout.addLayout(btn_layout)
        
        # Connect signals
        self.btn_add.clicked.connect(self.add_item)
        self.btn_edit.clicked.connect(self.edit_item)
        self.btn_remove.clicked.connect(self.remove_item)
        self.btn_up.clicked.connect(self.move_up)
        self.btn_down.clicked.connect(self.move_down)
        
        self.load_data()

    def load_data(self):
        paths, reg_type = self.manager.get_path(self.scope)
        
        if paths is None:
            # Handle permission error (likely System path without Admin)
            self.list_widget.setEnabled(False)
            self.btn_add.setEnabled(False)
            lbl = QLabel(f"Admin rights required to edit {self.scope.title()} Path.")
            lbl.setStyleSheet("color: red; font-weight: bold;")
            self.layout.insertWidget(0, lbl)
            return

        self.current_reg_type = reg_type
        self.original_paths = paths.copy()
        
        self.list_widget.clear()
        for p in paths:
            self.list_widget.addItem(QListWidgetItem(p))
            
        self.analyze_items()

    def analyze_items(self):
        """Analyzes items: checks existence and marks duplicates only on subsequent entries."""
        count = self.list_widget.count()
        if count == 0:
            return

        # Set to track unique paths found so far (top to bottom)
        seen_paths = set()

        for i in range(count):
            item = self.list_widget.item(i)
            text = item.text()
            # Normalize: lowercase and strip trailing slashes for comparison
            clean_text = text.lower().rstrip(os.sep)
            
            # Check Missing
            expanded_path = os.path.expandvars(text)
            is_missing = not os.path.exists(expanded_path) and "%" not in text
            
            # Check Duplicate
            # If we have seen this path before, it is a duplicate (the lower one)
            if clean_text in seen_paths:
                is_duplicate = True
            else:
                is_duplicate = False
                seen_paths.add(clean_text)
            
            # Set Data for Delegate
            item.setData(ROLE_MISSING, is_missing)
            item.setData(ROLE_DUPLICATE, is_duplicate)
            
            # Set Tooltip
            warnings = []
            if is_missing: warnings.append("Path does not exist")
            if is_duplicate: warnings.append("Duplicate entry (remove this one)")
            
            if warnings:
                item.setToolTip("Warning: " + ", ".join(warnings))
            else:
                item.setToolTip(expanded_path)

        # Force redraw
        self.list_widget.viewport().update()

    def add_item(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            # Convert to Windows style slashes
            folder = str(Path(folder))
            self.list_widget.addItem(QListWidgetItem(folder))
            self.analyze_items()

    def edit_item(self):
        row = self.list_widget.currentRow()
        if row < 0: return
        
        item = self.list_widget.item(row)
        text, ok = QInputDialog.getText(self, "Edit Path", "Path:", text=item.text())
        if ok and text:
            item.setText(text)
            self.analyze_items()

    def remove_item(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.list_widget.takeItem(row)
            self.analyze_items()

    def move_up(self):
        row = self.list_widget.currentRow()
        if row > 0:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row - 1, item)
            self.list_widget.setCurrentRow(row - 1)
            # Re-analyze because position determines "Original" vs "Duplicate" status
            self.analyze_items()

    def move_down(self):
        row = self.list_widget.currentRow()
        if row < self.list_widget.count() - 1 and row >= 0:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row + 1, item)
            self.list_widget.setCurrentRow(row + 1)
            # Re-analyze because position determines "Original" vs "Duplicate" status
            self.analyze_items()

    def get_current_list(self):
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Safe Windows Path Editor (PySide6)")
        self.resize(750, 600)
        
        self.manager = PathRegistryManager()
        self.is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        
        # Main Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Admin Status
        if not self.is_admin:
            lbl = QLabel("Running as Standard User. System PATH is read-only. Restart as Admin to edit System PATH.")
            lbl.setStyleSheet("background-color: #fff3cd; padding: 5px; border: 1px solid #ffeeba;")
            main_layout.addWidget(lbl)
        
        # Legend
        legend_layout = QHBoxLayout()
        legend_layout.addStretch()
        
        def create_badge(text, color):
            l = QLabel(text)
            l.setStyleSheet(f"background-color: {color}; color: white; padding: 2px 6px; border-radius: 4px; font-weight: bold;")
            return l
            
        legend_layout.addWidget(QLabel("Legend: "))
        legend_layout.addWidget(create_badge("M", "#D32F2F"))
        legend_layout.addWidget(QLabel("= Missing"))
        legend_layout.addWidget(create_badge("D", "#FF8C00"))
        legend_layout.addWidget(QLabel("= Duplicate"))
        main_layout.addLayout(legend_layout)

        # Tabs
        self.tabs = QTabWidget()
        self.user_tab = PathTab("user", self.manager)
        self.system_tab = PathTab("system", self.manager)
        
        self.tabs.addTab(self.user_tab, "User Path (HKCU)")
        self.tabs.addTab(self.system_tab, "System Path (HKLM)")
        
        main_layout.addWidget(self.tabs)
        
        # Action Buttons
        action_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save Changes")
        self.btn_save.setFixedHeight(40)
        self.btn_save.setStyleSheet("font-weight: bold;")
        self.btn_save.clicked.connect(self.save_changes)
        
        self.btn_reload = QPushButton("Reload Registry")
        self.btn_reload.clicked.connect(self.reload_data)
        
        action_layout.addStretch()
        action_layout.addWidget(self.btn_reload)
        action_layout.addWidget(self.btn_save)
        
        main_layout.addLayout(action_layout)

    def reload_data(self):
        self.user_tab.load_data()
        self.system_tab.load_data()
        QMessageBox.information(self, "Reloaded", "Data reloaded from registry (unsaved changes lost).")

    def create_backup(self, user_paths, system_paths):
        """Creates a JSON backup file."""
        backup_data = {
            "timestamp": str(datetime.datetime.now()),
            "user_path": user_paths,
            "system_path": system_paths
        }
        
        filename = f"path_backup_{int(datetime.datetime.now().timestamp())}.json"
        try:
            with open(filename, 'w') as f:
                json.dump(backup_data, f, indent=4)
            return filename
        except Exception as e:
            QMessageBox.critical(self, "Backup Failed", f"Could not create backup: {e}")
            return None

    def save_changes(self):
        # 1. Get current data from UI
        new_user_paths = self.user_tab.get_current_list()
        new_sys_paths = self.system_tab.get_current_list()
        
        # 2. Safety Backup
        backup_file = self.create_backup(self.user_tab.original_paths, self.system_tab.original_paths)
        if not backup_file:
            return # Stop if backup failed
            
        confirm = QMessageBox.question(
            self, "Confirm Save",
            f"Backup created: {backup_file}\n\nAre you sure you want to write these changes to the Windows Registry?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if confirm == QMessageBox.No:
            return

        # 3. Write User Path
        success_user = self.manager.set_path("user", new_user_paths, self.user_tab.current_reg_type)
        
        # 4. Write System Path (Only if Admin and changed)
        success_sys = True
        if self.is_admin:
            success_sys = self.manager.set_path("system", new_sys_paths, self.system_tab.current_reg_type)
            
        if success_user and success_sys:
            # 5. Broadcast
            self.manager.broadcast_changes()
            QMessageBox.information(self, "Success", "Paths saved and broadcast to OS successfully.")
            # Reload originals so we don't backup the new state as 'original' next time
            self.user_tab.original_paths = new_user_paths
            self.system_tab.original_paths = new_sys_paths
        else:
            QMessageBox.critical(self, "Error", "Failed to write to registry. Ensure you have permissions.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Modern styling fix
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())