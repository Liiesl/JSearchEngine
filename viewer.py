import sys
import os
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTableView, QHeaderView, 
    QLineEdit, QVBoxLayout, QWidget, QLabel, QHBoxLayout
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

# --- CONFIGURATION ---
CSV_FILE = "final_api_data.csv"
WINDOW_TITLE = "JAV Database Viewer (Sorted)"

class OptimizedPandasModel(QAbstractTableModel):
    def __init__(self, dataframe):
        super().__init__()
        self._df = dataframe
        self._headers = list(dataframe.columns)
        
    def rowCount(self, parent=QModelIndex()):
        return self._df.shape[0]

    def columnCount(self, parent=QModelIndex()):
        return self._df.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        if role == Qt.DisplayRole or role == Qt.ToolTipRole:
            return str(self._df.iat[index.row(), index.column()])

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return self._headers[section]
            if orientation == Qt.Vertical:
                return str(section + 1)
        return None

    # --- SORTING IMPLEMENTATION ---
    def sort(self, column, order):
        """
        Sorts the Pandas DataFrame when a header is clicked.
        """
        self.layoutAboutToBeChanged.emit()
        
        col_name = self._headers[column]
        is_ascending = (order == Qt.AscendingOrder)
        
        # Sort the DataFrame natively in Pandas (High Performance)
        # na_position='last' puts empty dates at the bottom usually
        try:
            self._df = self._df.sort_values(
                by=col_name, 
                ascending=is_ascending, 
                kind='quicksort',
                na_position='last'
            )
        except Exception as e:
            print(f"Sort warning: {e}")

        self.layoutChanged.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1400, 900)
        self._original_df = None

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # --- Search Bar ---
        search_layout = QHBoxLayout()
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search... (Press Enter)")
        self.search_bar.returnPressed.connect(self.perform_search)
        
        self.status_label = QLabel("Loading...")
        self.status_label.setStyleSheet("color: gray; padding-left: 10px;")

        search_layout.addWidget(self.search_bar)
        search_layout.addWidget(self.status_label)
        layout.addLayout(search_layout)

        # --- Table View ---
        self.table_view = QTableView()
        layout.addWidget(self.table_view)

        # 1. VISUAL OPTIMIZATIONS
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setShowGrid(False) # Cleaner look
        
        # 2. SELECTION BEHAVIOR (Fixes the "Whole Column Selected" issue)
        # SelectRows: Clicking a cell selects the whole horizontal row
        # SingleSelection: Prevents selecting multiple rows (keeps it fast)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setSelectionMode(QTableView.SingleSelection)

        # 3. HEADER CONFIGURATION
        v_header = self.table_view.verticalHeader()
        v_header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        v_header.setDefaultSectionSize(30)
        
        h_header = self.table_view.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h_header.setStretchLastSection(True)
        # Enable clicking headers to sort
        self.table_view.setSortingEnabled(True)

        self.load_csv_data()

    def load_csv_data(self):
        if not os.path.exists(CSV_FILE):
            self.status_label.setText(f"Error: {CSV_FILE} not found.")
            return

        try:
            self.status_label.setText("Reading CSV...")
            QApplication.processEvents()

            # Load CSV
            self._original_df = pd.read_csv(CSV_FILE, encoding="utf-8-sig", dtype=str).fillna("")
            
            # --- DEFAULT SORT: LATEST DATE FIRST ---
            # We assume 'releaseDate' is one of the columns.
            if 'releaseDate' in self._original_df.columns:
                self.status_label.setText("Sorting by Date...")
                self._original_df = self._original_df.sort_values(
                    by='releaseDate', 
                    ascending=False
                )

            self.set_model_data(self._original_df)

            # --- COLUMN SIZING (Adjust indices based on your CSV) ---
            # 0:dvdId, 1:title, 2:jpTitle, 3:actress, 4:date
            self.table_view.setColumnWidth(0, 110) # ID
            self.table_view.setColumnWidth(1, 400) # Title
            self.table_view.setColumnWidth(2, 200) # JP Title
            self.table_view.setColumnWidth(3, 200) # Actress
            self.table_view.setColumnWidth(4, 100) # Date

        except Exception as e:
            self.status_label.setText(f"Error: {e}")

    def set_model_data(self, df):
        # We temporarily disable sorting while swapping models to prevent glitches
        self.table_view.setSortingEnabled(False)
        
        model = OptimizedPandasModel(df)
        self.table_view.setModel(model)
        self.status_label.setText(f"Records: {len(df):,}")
        
        # Re-enable sorting so user can click headers
        self.table_view.setSortingEnabled(True)

    def perform_search(self):
        query = self.search_bar.text().lower().strip()
        
        if not query:
            self.set_model_data(self._original_df)
            return

        self.status_label.setText("Searching...")
        QApplication.processEvents()

        try:
            mask = (
                self._original_df['title'].str.lower().str.contains(query, regex=False) | 
                self._original_df['actress_names'].str.lower().str.contains(query, regex=False) |
                self._original_df['dvdid'].str.lower().str.contains(query, regex=False)
            )
            filtered_df = self._original_df[mask]
            self.set_model_data(filtered_df)
        except Exception as e:
            self.status_label.setText(f"Search Error: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())