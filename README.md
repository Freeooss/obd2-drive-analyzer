# OBD-II Drive Analyzer

A Python-based vehicle telemetry analysis and dashboard project that processes OBD-II driving data recorded with Car Scanner and a Bluetooth OBD-II adapter.

The project converts raw vehicle sensor data into an interactive local dashboard for reviewing drive summaries, hybrid-system temperatures, battery state of charge, engine RPM, speed, and other vehicle metrics.

## Overview

Vehicle data is recorded using:

- Veepeak Bluetooth OBD-II adapter
- Car Scanner mobile app
- Toyota hybrid vehicle telemetry

The recorded CSV file is transferred to a Mac mini. Once the file appears in the monitored folder, the analyzer can automatically process the data and update the local dashboard.

Raw vehicle data is kept private and is excluded from the GitHub repository.

## Features

- Processes Car Scanner CSV telemetry using Python and Pandas
- Automatically detects newly imported Car Scanner CSV files
- Calculates drive time and estimated distance from GPS speed data
- Displays minimum, maximum, and average sensor values
- Converts selected temperature data from Celsius to Fahrenheit
- Stores short-term drive history
- Automatically removes drive data older than 3 days
- Displays interactive time-series charts
- Automatically detects new drive records while viewing the latest dashboard
- Runs locally through a Flask web application

## Vehicle Data

The current version analyzes:

- Engine coolant temperature
- Inverter coolant temperature
- MG1 temperature
- MG2 temperature
- Hybrid battery state of charge
- Hybrid battery temperature
- Engine RPM
- Intake air temperature
- GPS vehicle speed
- Estimated trip distance
- Drive duration

## Dashboard

The dashboard provides a quick summary of each drive, including:

- Distance
- Drive time
- Average speed
- Maximum speed
- Average RPM
- Maximum RPM
- Intake air temperature
- Hybrid battery SOC
- Engine and hybrid-system temperatures

Time-series charts are available for:

- Hybrid battery SOC
- Engine RPM
- Vehicle speed
- Engine coolant temperature
- Inverter coolant temperature
- MG1 temperature
- MG2 temperature
- Hybrid battery temperature
- Intake air temperature

Previous drives can also be selected from the Drive History section.

## Data Pipeline

```text
Vehicle ECU
    ↓
Veepeak OBD-II Adapter
    ↓ Bluetooth
Car Scanner
    ↓
CSV Export
    ↓
Mac mini
    ↓
File Watcher
    ↓
Raw CSV Validation
    ↓
Pandas Processing
    ↓
Processed Data + Drive Summary
    ↓
Flask Dashboard
```

## Project Structure

```text
obd2-drive-analyzer/
│
├── app.py
├── processor.py
├── watcher.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── history/
│
├── templates/
│   └── index.html
│
├── static/
│   └── style.css
│
└── logs/
```

## Technologies

- Python
- Pandas
- Flask
- Chart.js
- Watchdog
- HTML
- CSS
- Git / GitHub

## How It Works

### 1. Record vehicle data

Car Scanner records selected OBD-II and hybrid-system sensors during a drive.

### 2. Export the drive

The drive is exported from Car Scanner as a CSV file.

### 3. Transfer the CSV

The CSV can be transferred to the Mac mini.

The current workflow supports transferring the file from a phone and placing it in the monitored Downloads folder.

### 4. Detect the file

`watcher.py` monitors the folder for newly created CSV files.

Before importing a file, it checks for expected Car Scanner columns so unrelated CSV files are ignored.

### 5. Process the data

`processor.py`:

- Reads the raw CSV
- Converts sensor values to numeric data
- Normalizes selected temperature units
- Calculates summary statistics
- Estimates distance from GPS speed and elapsed time
- Creates processed drive data
- Generates a JSON drive summary

### 6. Display the dashboard

`app.py` runs a Flask web server that displays the latest drive and recent drive history.

The dashboard is available locally at:

```text
http://localhost:5001
```

## Installation

Clone the repository:

```bash
git clone https://github.com/Freeooss/obd2-drive-analyzer.git
cd obd2-drive-analyzer
```

Create a Python virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run the Analyzer

Process available raw CSV files:

```bash
python processor.py
```

Start the dashboard:

```bash
python app.py
```

Then open:

```text
http://localhost:5001
```

To monitor for newly transferred CSV files:

```bash
python watcher.py
```

## Automatic Startup on macOS

The project can be configured with macOS `launchd` so that the Flask dashboard and file watcher start automatically after login.

This allows the analyzer to run without manually opening a terminal each time the Mac starts.

## Data Retention

The analyzer keeps only recent drive data.

Files older than 7 days are automatically removed from:

```text
data/raw/
data/processed/
data/history/
```

This keeps local storage usage small while preserving recent drive history.

## Privacy

Real vehicle telemetry is not included in this repository.

The `.gitignore` excludes:

- Raw CSV files
- Processed drive data
- Drive history
- Runtime logs
- Python virtual environments

Some Car Scanner exports may contain sensitive information such as:

- GPS coordinates
- Driving history
- Vehicle-specific information

For this reason, raw data should remain local.

## Current Limitations

- CSV export from Car Scanner still requires a user action.
- File transfer to the Mac may require accepting the transfer.
- Vehicle identification currently uses available sensor characteristics rather than guaranteed vehicle metadata.
- Fuel economy calculation is not yet included because the available fuel-rate data is not consistent enough for a reliable trip MPG calculation.
- Distance is estimated using GPS speed and time rather than a dedicated trip-distance PID.

## Future Improvements

Possible future improvements include:

- More reliable automatic vehicle identification
- Fuel economy and energy-use analysis
- Additional hybrid battery metrics
- Trip comparison tools
- Longer-term summarized history
- Automatic report generation
- Improved file-transfer automation
- Additional vehicle profiles

## Purpose

This project was created as a hands-on data science and automotive technology project to explore how real-world vehicle telemetry can be collected, processed, analyzed, automated, and visualized using Python.