import segyio
import numpy as np
import matplotlib.pyplot as plt
import sys
import serial
import time
import os

from typing import Tuple
from PySide6 import QtWidgets, QtCore, QtGui
from matplotlib.backends.backend_qt5agg  import FigureCanvasQTAgg as FigureCanvas
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
        self._observer.stop()
        self._observer.join()


    def file_created(self, filepath):
        self.new_file_signal.emit(filepath)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, data: np.ndarray):
        super().__init__()

        self.data = data

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)


        self.button = QtWidgets.QPushButton('Plot')
        self.button.clicked.connect(self.plot)

        self.watch_checkbox = QtWidgets.QCheckBox('Watch for new files')
        self.watch_checkbox.stateChanged.connect(self.toggle_watching)



        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        layout.addWidget(self.button)
        layout.addWidget(self.watch_checkbox)

        central_widget = QtWidgets.QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.watcher = None

    def plot(self):
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
        if state == 2:
            self.start_watching()
        else:
            self.stop_watching()

    def start_watching(self):
        folder = os.path.join(os.getcwd(), "data")
        self.watcher = FolderWatcher(folder)
        self.watcher.new_file_signal.connect(get_current_location)
        self.watcher.start()
        print("Started watching folder")

    def stop_watching(self):
        if self.watcher:
            self.watcher.stop()
            print("Stopped watching folder")

def get_data_from_file(file_path: str) -> np.ndarray:
    # Open the file directly with segyio
    with segyio.open(file_path, ignore_geometry=True) as f:
        # Print some info about the file
        print(f"Number of traces: {f.tracecount}")

        # Get the trace data for display
        return np.asarray([f.trace[i] for i in range(0, f.tracecount)])  # Get traces 100-300

def show_data(data: np.ndarray) -> None:
    # Plot the data
    fig, ax = plt.subplots(figsize=(15, 8))
    im = ax.imshow(data.T, aspect='auto', cmap='seismic_r')
    ax.invert_yaxis()  # To have time/depth increasing downward
    ax.set_xlabel("Trace")
    ax.set_ylabel("TWT")
    ax.set_title("Seismic Section")
    plt.colorbar(im, ax=ax, label="Amplitude")

    plt.grid(True, color='grey', linestyle='--', linewidth=0.5)
    plt.tight_layout()
    plt.show()

def show_data_qt(data: np.ndarray) -> None:
    app = QtWidgets.QApplication([])

    widget = MainWindow(data)
    widget.resize(800, 600)
    widget.show()

    sys.exit(app.exec())

def get_current_location() -> Tuple[float, float]:
    try:
        # ovde treba port (USB) na koji je uredjaj povezan i trebalo bi da radi
        ser = serial.Serial('/dev/ttyUSB0', 9600)
        with gnssstreamer.GNSSStreamer(app=None, stream=ser) as streamer:

            data = streamer.read()

            if hasattr(data, 'lat') and hasattr(data, 'lon'):
                return data.lat, data.lon
            else:
                print("No valid GPS data received")
                return 0.0, 0.0
    except Exception as e:
        print(f"Error getting GPS coordinates: {e}")
        return 0.0, 0.0

if __name__ == "__main__":
    sgy_data = get_data_from_file("data/20190413_233934.SGY")
    show_data_qt(sgy_data)