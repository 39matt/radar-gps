import segyio
import numpy as np
import matplotlib.pyplot as plt
import sys
import serial
import time
import os

from typing import Tuple
from PySide6 import QtWidgets, QtCore
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pygnssutils import gnssstreamer


class SGYStartHandler(FileSystemEventHandler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def on_created(self, event):
        if event.src_path.endswith(".sgy"):
            print(f"New SGY file detected: {event.src_path}")
            self.callback(event.src_path)


class FolderWatcher(QtCore.QThread):
    new_file_signal = QtCore.Signal(str)

    def __init__(self, folder):
        super().__init__()
        self.folder = folder
        self._observer = None

    def run(self):
        handler = SGYStartHandler(self.file_created)
        self._observer = Observer()
        self._observer.schedule(handler, self.folder, recursive=False)
        self._observer.start()
        print(f"FolderWatcher running on: {self.folder}")
        try:
            while self._observer.is_alive():
                time.sleep(0.5)
        finally:
            self._observer.stop()
            self._observer.join()

    def stop(self):
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join()

    def file_created(self, filepath):
        self.new_file_signal.emit(filepath)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.data = None
        self.watch_folder = os.path.join(os.getcwd(), "data")

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)

        self.file_layout = QtWidgets.QHBoxLayout()
        self.file_label = QtWidgets.QLabel("SEG-Y File:")
        self.file_path = QtWidgets.QLineEdit()
        self.file_path.setReadOnly(True)
        self.browse_button = QtWidgets.QPushButton("Browse...")
        self.browse_button.clicked.connect(self.browse_segy_file)

        self.file_layout.addWidget(self.file_label)
        self.file_layout.addWidget(self.file_path)
        self.file_layout.addWidget(self.browse_button)

        self.button = QtWidgets.QPushButton('Plot')
        self.button.clicked.connect(self.plot)

        self.folder_layout = QtWidgets.QHBoxLayout()
        self.folder_label = QtWidgets.QLabel("Watch Folder:")
        self.folder_path = QtWidgets.QLineEdit(self.watch_folder)
        self.folder_path.setReadOnly(True)
        self.folder_browse_button = QtWidgets.QPushButton("Select Folder...")
        self.folder_browse_button.clicked.connect(self.browse_watch_folder)

        self.folder_layout.addWidget(self.folder_label)
        self.folder_layout.addWidget(self.folder_path)
        self.folder_layout.addWidget(self.folder_browse_button)

        self.watch_checkbox = QtWidgets.QCheckBox('Watch for new files')
        self.watch_checkbox.stateChanged.connect(self.toggle_watching)
        self.folder_layout.addWidget(self.watch_checkbox)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(self.file_layout)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        layout.addWidget(self.button)

        plot_group = QtWidgets.QGroupBox("Watch Folder")
        plot_group.setLayout(self.folder_layout)
        layout.addWidget(plot_group)

        central_widget = QtWidgets.QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.watcher = None

    def plot(self):
        if self.data is None:
            QtWidgets.QMessageBox.warning(self, "No Data", "Please load a SEG-Y file first.")
            return

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        im = ax.imshow(self.data.T, aspect='auto', cmap='seismic_r')
        ax.invert_yaxis()
        ax.set_xlabel("Trace")
        ax.set_ylabel("TWT")
        ax.set_title("Seismic Section")
        ax.grid(True, color='grey', linestyle='--', linewidth=0.5)
        self.figure.colorbar(im, ax=ax, label="Amplitude")
        self.figure.tight_layout()
        self.canvas.draw()

    def toggle_watching(self, state):
        if state == 2:  # Checked
            self.start_watching()
            self.folder_path.setEnabled(False)
            self.folder_browse_button.setEnabled(False)
            self.folder_label.setEnabled(False)
        else:
            self.stop_watching()
            self.folder_path.setEnabled(True)
            self.folder_browse_button.setEnabled(True)
            self.folder_label.setEnabled(True)

    def start_watching(self):
        if not os.path.exists(self.watch_folder):
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid Folder",
                f"The selected folder does not exist: {self.watch_folder}"
            )
            self.watch_checkbox.setChecked(False)
            return

        self.watcher = FolderWatcher(self.watch_folder)
        self.watcher.new_file_signal.connect(self.process_new_file)
        self.watcher.start()
        print(f"Started watching folder: {self.watch_folder}")

    def stop_watching(self):
        if self.watcher:
            self.watcher.stop()
            print("Stopped watching folder")

    def browse_segy_file(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select SEG-Y File", self.watch_folder, "SEG-Y Files (*.sgy *.segy *.SGY);;All Files (*)"
        )
        if file_path:
            self.file_path.setText(file_path)
            self.load_segy_file(file_path)

    def browse_watch_folder(self):
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Folder to Watch", self.watch_folder
        )
        if folder_path:
            self.watch_folder = folder_path
            self.folder_path.setText(folder_path)

            if self.watch_checkbox.isChecked():
                self.stop_watching()
                self.start_watching()

    def load_segy_file(self, file_path):
        try:
            self.data = get_data_from_file(file_path)
            self.statusBar().showMessage(f"Loaded: {file_path}", 3000)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error Loading File",
                f"Failed to load SEG-Y file: {str(e)}"
            )
            self.data = None

    def process_new_file(self, file_path):
        self.file_path.setText(file_path)
        self.load_segy_file(file_path)
        self.plot()

        lat, lon = get_current_location()
        if lat != 0.0 and lon != 0.0:
            self.statusBar().showMessage(f"File: {os.path.basename(file_path)} | Location: {lat:.6f}, {lon:.6f}", 5000)


def get_data_from_file(file_path: str) -> np.ndarray:
    with segyio.open(file_path, ignore_geometry=True) as f:
        print(f"Number of traces: {f.tracecount}")

        return np.asarray([f.trace[i] for i in range(0, f.tracecount)])


def show_data(data: np.ndarray) -> None:
    fig, ax = plt.subplots(figsize=(15, 8))
    im = ax.imshow(data.T, aspect='auto', cmap='seismic_r')
    ax.invert_yaxis()
    ax.set_xlabel("Distance (m)")
    ax.set_ylabel("Depth (m)")
    ax.set_title("Seismic Section")
    plt.colorbar(im, ax=ax, label="Amplitude")

    plt.grid(True, color='grey', linestyle='--', linewidth=0.5)
    plt.tight_layout()
    plt.show()


def get_current_location() -> Tuple[float, float]:
    try:
        ser = serial.Serial('/dev/pts/4', 9600)
        with gnssstreamer.GNSSStreamer(app=None, stream=ser) as streamer:
            data = streamer.get_coordinates()
            print(data)

            if hasattr(data, 'lat') and hasattr(data, 'lon'):
                return data.lat, data.lon
            else:
                print("No valid GPS data received")
                return 0.0, 0.0
    except Exception as e:
        print(f"Error getting GPS coordinates: {e}")
        return 0.0, 0.0


if __name__ == "__main__":
    app = QtWidgets.QApplication([])

    widget = MainWindow()
    widget.resize(800, 600)
    widget.show()

    sys.exit(app.exec())