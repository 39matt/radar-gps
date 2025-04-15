from typing import Tuple

import segyio
import numpy as np
import matplotlib.pyplot as plt
from pygnssutils import gnssstreamer
import serial

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
    data = get_data_from_file("data/20190413_233934.SGY")
    show_data(data)
    coords = get_current_location()
    print(f"Coordinates: {coords}")