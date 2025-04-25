import { useState, useEffect } from "react";

interface SensorData {
  [key: string]: number | string;
}

const sensorLabels = [
  "Voltage",
  "Cond Fan Current",
  "Evap Fan Current",
  "Compressor Current",
  "Total Current",
  "pressure_200",
  "pressure_300",
  "temp1",
  "temp2",
  "temp3",
  "labjack_temp",
  "air_temp",
  "pressure_switch",
];

export default function App() {
  const [sensorData, setSensorData] = useState<SensorData>({});
  const [startTime, setStartTime] = useState<string>("Loading...");
  const [runtime, setRuntime] = useState<string>("00:00:00");

  const fetchData = async () => {
    const response = await fetch("/data");
    const data = await response.json();

    if (startTime === "Loading...") {
      setStartTime(data.start_time);
    }

    setSensorData(data.sensor_data);

    // Calculate runtime
    const runSecs = data.run_time;
    const hours = Math.floor(runSecs / 3600);
    const minutes = Math.floor((runSecs % 3600) / 60);
    const seconds = Math.floor(runSecs % 60);
    setRuntime(
      `${hours.toString().padStart(2, "0")}:${minutes
        .toString()
        .padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`
    );
  };

  const saveAs = async () => {
    let newFilename = prompt("Enter new filename:", "saved_data");
    if (!newFilename) return;
    if (!newFilename.toLowerCase().endsWith(".csv")) {
      newFilename += ".csv";
    }

    const response = await fetch("/prepare_download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ newFilename }),
    });

    const result = await response.json();
    if (response.ok) {
      window.location.href = result.downloadUrl;
    } else {
      alert("Error: " + result.error);
    }
  };

  useEffect(() => {
    fetchData(); // Initial call
    const interval = setInterval(fetchData, 1000); // Fetch every second
    return () => clearInterval(interval); // Cleanup
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-100 to-gray-200 p-8 font-sans">
      <header className="mb-8">
        <h1 className="text-4xl font-extrabold text-gray-800 mb-2">
          LabJack Dashboard
        </h1>
        <div className="flex flex-col md:flex-row md:items-center md:justify-between">
          <div className="text-gray-600 text-lg">
            <span className="font-semibold">Start Time:</span> {startTime}
          </div>
          <div className="text-gray-600 text-lg">
            <span className="font-semibold">Runtime:</span> {runtime}
          </div>
        </div>
      </header>

      <div className="flex justify-end mb-6">
        <button
          onClick={saveAs}
          className="bg-green-500 hover:bg-green-600 transition text-white font-bold py-2 px-6 rounded-lg shadow-md"
        >
          Save Data as CSV
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
        {sensorLabels.map((label) => {
          const id = label.replace(/\s+/g, "_");
          const value = sensorData[id];

          return (
            <div
              key={id}
              className="bg-white p-6 rounded-2xl shadow-lg hover:shadow-xl transition duration-300 transform hover:scale-105"
            >
              <h3 className="text-md font-semibold text-gray-700 mb-2 text-center">
                {label.replace(/_/g, " ")}
              </h3>
              <p className="text-3xl font-bold text-center text-gray-900">
                {typeof value === "number" ? value.toFixed(2) : value ?? "0.00"}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
