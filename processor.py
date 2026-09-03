import pandas as pd
from pathlib import Path


RAW_DATA_DIR = Path("data/raw")


def celsius_to_fahrenheit(value):
    return (value * 9 / 5) + 32


def load_latest_drive():
    csv_files = list(RAW_DATA_DIR.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError("No CSV files found in data/raw.")

    latest_file = max(
        csv_files,
        key=lambda file: file.stat().st_mtime
    )

    print(f"Loading: {latest_file.name}")

    df = pd.read_csv(latest_file)

    return df


def analyze_drive(df):
    sensors = {
        "Engine Coolant": {
            "column": "Engine coolant temperature (℉)",
            "convert_from_c": False
        },

        "Inverter Coolant": {
            "column": "Inverter Coolant Temp ()",
            "convert_from_c": True
        },

        "MG1 Temperature": {
            "column": "MG1 temperature (℉)",
            "convert_from_c": False
        },

        "MG2 Temperature": {
            "column": "MG2 temperature (℉)",
            "convert_from_c": False
        },

        "Battery SOC": {
            "column": "State of Charge (%)",
            "convert_from_c": False
        },

        "Battery Temp TB1": {
            "column": "Temp of Batt TB1 (℉)",
            "convert_from_c": False
        },

        "Battery Temp TB2": {
            "column": "Temp of Batt TB2 (℉)",
            "convert_from_c": False
        },

        "Battery Temp TB3": {
            "column": "Temp of Batt TB3 (℉)",
            "convert_from_c": False
        },

        "GPS Speed": {
            "column": "Speed (GPS) (mph)",
            "convert_from_c": False
        }
    }

    print("\n=== TODAY'S DRIVE ===")

    for name, config in sensors.items():

        column = config["column"]

        if column not in df.columns:
            print(f"{name}: column not found")
            continue

        values = pd.to_numeric(
            df[column],
            errors="coerce"
        ).dropna()

        if values.empty:
            print(f"{name}: no valid data")
            continue

        if config["convert_from_c"]:
            values = celsius_to_fahrenheit(values)

        print(f"\n{name}")

        if "SOC" in name:
            unit = "%"

        elif "Speed" in name:
            unit = "mph"

        else:
            unit = "°F"

        print(f"  Minimum: {values.min():.1f} {unit}")
        print(f"  Average: {values.mean():.1f} {unit}")
        print(f"  Maximum: {values.max():.1f} {unit}")


def main():
    df = load_latest_drive()

    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns)}")

    analyze_drive(df)


if __name__ == "__main__":
    main()