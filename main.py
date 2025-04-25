from labjack import ljm
from flask import Flask, jsonify, send_from_directory, request, send_file
import time
import threading
import csv
import os 
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.dates as mdates 
from collections import deque

app = Flask(
    __name__,
    static_folder="frontend/dist/assets",
    template_folder="frontend/dist"
)

# Global sensor data dictionary
sensor_data = {
    "voltage": 0.0,
    "Cond Fan Current": 0.0,
    "Evap Fan Current": 0.0,
    "Compressor Current": 0.0,
    "Total Current": 0.0,
    "pressure_200": 0.0,
    "pressure_300": 0.0,
    "temp1": 0.0,
    "temp2": 0.0,
    "temp3": 0.0,
    "labjack_temp": 0.0,
    "air_temp": 0.0,
    "pressure_switch": "Open"  # Default to Open
}

# Global start time for run time tracking
start_time = datetime.now()

# Buffers for storing data
csv_filename = "data_log.csv"
time_buffer = deque(maxlen=86400)  # Limit to 1 day's worth of data
p200_buffer = deque(maxlen=86400)
p300_buffer = deque(maxlen=86400)
time_stamps = deque(maxlen=86400)


def log_to_csv():
    with open(csv_filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp"] + list(sensor_data.keys()) + ["pressure_switch"])
        while True:
            timestamp = datetime.now().isoformat(timespec='seconds')
            row = [timestamp] + list(sensor_data.values() + [sensor_data["pressure_switch"]])
            writer.writerow(row)
            file.flush()
            time.sleep(1)


def read_all_sensors():
    handle = ljm.openS("T7", "ANY", "ANY")

    ljm.eWriteName(handle, "AIN52_RANGE", 10.0)
    ljm.eWriteName(handle, "AIN53_RANGE", 10.0)
    ljm.eWriteName(handle, "AIN54_RANGE", 10.0)
    ljm.eWriteName(handle, "AIN55_RANGE", 10.0)
    ljm.eWriteName(handle, "AIN56_RANGE", 10.0)
    ljm.eWriteName(handle, "AIN57_RANGE", 10.0)
    ljm.eWriteName(handle, "AIN58_RANGE", 10.0)

    for ch in [52, 53, 54, 55, 56, 57, 58]:
        ljm.eWriteName(handle, f"AIN{ch}_NEGATIVE_CH", 199)

    registers = ["AIN0", "AIN1", "AIN2", "AIN3", "TEMPERATURE_DEVICE_K", "TEMPERATURE_AIR_K"]
    R_known = [1012, 1011, 1008]
    R0 = 1000
    alpha = 0.003851

    try:
        while True:
            values = ljm.eReadNames(handle, len(registers), registers)
            V_AIN0, V_AIN1, V_AIN2, V_supply, labjack_temp_K, air_temp_K = values

            def convert(V, Vs, Rk):
                R = Rk * (V / (Vs - V)) if Vs > V else Rk
                temp_C = -(R - R0) / (alpha * R0)
                return (temp_C * 9/5) + 32

            # Update sensor data dictionary
            sensor_data["temp1"] = convert(V_AIN0, V_supply, R_known[0])
            sensor_data["temp2"] = convert(V_AIN1, V_supply, R_known[1])
            sensor_data["temp3"] = convert(V_AIN2, V_supply, R_known[2])
            sensor_data["labjack_temp"] = ((labjack_temp_K - 273.15) * 9/5) + 32
            sensor_data["air_temp"] = ((air_temp_K - 273.15) * 9/5) + 32

            sensor_data["voltage"] = ljm.eReadName(handle, "AIN52") * 10.0
            sensor_data["pressure_200"] = ljm.eReadName(handle, "AIN53") * (200.0 / 10.0)
            sensor_data["pressure_300"] = ljm.eReadName(handle, "AIN54") * (300.0 / 10.0)

            cond_raw = ljm.eReadName(handle, "AIN55")
            evap_raw = ljm.eReadName(handle, "AIN56")
            comp_raw = ljm.eReadName(handle, "AIN57")
            total_raw = ljm.eReadName(handle, "AIN58")
            # Read the pressure switch voltage from AIN51
            pressure_switch_voltage = ljm.eReadName(handle, "AIN51")
            # Set pressure switch state based on voltage threshold (2V)
            sensor_data["pressure_switch"] = "Closed" if pressure_switch_voltage > 2.0 else "Open"

            sensor_data["Cond Fan Current"] = cond_raw * (25.0 / 5.0)
            sensor_data["Evap Fan Current"] = evap_raw * (25.0 / 5.0)
            sensor_data["Compressor Current"] = comp_raw * (100.0 / 5.0)
            sensor_data["Total Current"] = total_raw * (100.0 / 5.0)

            now = datetime.now()
            timestamp = now.timestamp()  # Use Unix timestamp
            time_buffer.append(timestamp)
            time_stamps.append(now.strftime("%H:%M:%S"))
            p200_buffer.append(sensor_data["pressure_200"])
            p300_buffer.append(sensor_data["pressure_300"])

            time.sleep(1)
    except Exception as e:
        print(f"Error reading sensors: {e}")
    finally:
        ljm.close(handle)


def animate(i):
    plt.cla()

    if len(time_buffer) > 1:
        # Convert timestamps to datetime for plotting
        time_values = [datetime.fromtimestamp(ts) for ts in time_buffer]

        # Plot the pressure data with timestamps
        line1, = plt.plot(time_values, p200_buffer, 'r-', label='High Pressure (200psi)')
        line2, = plt.plot(time_values, p300_buffer, 'b-', label='Low Pressure (300psi)')

        # Dynamically set x-axis limits
        if len(time_buffer) > 60:
            # If more than 60 points, show the last 30 minutes
            plt.gca().set_xlim([datetime.fromtimestamp(time_buffer[-1] - 3600), datetime.fromtimestamp(time_buffer[-1])])
        else:
            # Show all data points for the last 60 seconds
            plt.gca().set_xlim([datetime.fromtimestamp(time_buffer[0]), datetime.fromtimestamp(time_buffer[-1])])

        # Set x-axis formatting
        plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())  # Auto adjusts date ticks
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

        plt.gcf().autofmt_xdate()  # Auto-format the x-axis labels

        plt.legend(loc="upper right")
    
    plt.xlabel("Time")
    plt.ylabel("Pressure (psi)")
    plt.title("Pressure Over Time")
    plt.tight_layout()


def start_plotting():
    plt.figure(figsize=(10, 5))
    ani = animation.FuncAnimation(plt.gcf(), animate, interval=1000, cache_frame_data=False)
    plt.show()


@app.route("/")
def index():
    return send_from_directory("frontend/dist", "index.html")

@app.route("/assets/<path:path>")
def serve_assets(path):
    return send_from_directory("frontend/dist/assets", path)


@app.route("/data")
def data():
    current_time = datetime.now()
    run_time = (current_time - start_time).total_seconds()
    return jsonify({
        "sensor_data": sensor_data,
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "run_time_seconds": int(run_time)
    })


@app.route("/prepare_download", methods=["POST"])
def prepare_download():
    # Get the user-entered filename, defaulting to "saved_data.csv" if none is provided
    new_filename = request.json.get("newFilename", "saved_data.csv")
    
    # Ensure the filename ends with ".csv"
    if not new_filename.endswith(".csv"):
        new_filename += ".csv"
    
    new_filepath = os.path.join(os.path.dirname(csv_filename), new_filename)
    
    try:
        import shutil
        shutil.copyfile(csv_filename, new_filepath)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    return jsonify({"message": "CSV saved", "downloadUrl": f"/download_custom/{new_filename}"})


@app.route("/download_custom/<filename>")
def download_custom(filename):
    filepath = os.path.join(os.path.dirname(csv_filename), filename)
    return send_file(filepath, as_attachment=True)


def run_flask():
    app.run(host="0.0.0.0", port=5000)


if __name__ == "__main__":
    # Start threads for sensor data reading, CSV logging, and Flask server
    sensor_thread = threading.Thread(target=read_all_sensors)
    sensor_thread.daemon = True
    sensor_thread.start()

    csv_thread = threading.Thread(target=log_to_csv)
    csv_thread.daemon = True
    csv_thread.start()

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Start the real-time plotting
    start_plotting()
