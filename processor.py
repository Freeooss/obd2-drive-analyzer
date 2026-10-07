
import json
import math
import re
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
HISTORY_DIR = Path("data/history")

for directory in (RAW_DIR, PROCESSED_DIR, HISTORY_DIR):
    directory.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# BASIC HELPERS
# --------------------------------------------------

def celsius_to_fahrenheit(values):
    return values * 9 / 5 + 32


def find_column(df, candidates):
    # Try exact matches first.
    for name in candidates:
        if name in df.columns:
            return name

    normalized = {
        str(col).strip().lower(): col
        for col in df.columns
    }

    # Then try case-insensitive partial matches.
    for name in candidates:
        for key, original in normalized.items():
            if name.strip().lower() in key:
                return original

    return None


def numeric_series_from_candidates(df, candidates):
    name = find_column(df, candidates)

    if name is None:
        return pd.Series(index=df.index, dtype=float)

    return pd.to_numeric(df[name], errors="coerce")


def safe_stats(series):
    valid = series.dropna()

    if valid.empty:
        return {
            "min": None,
            "avg": None,
            "max": None
        }

    return {
        "min": round(float(valid.min()), 1),
        "avg": round(float(valid.mean()), 1),
        "max": round(float(valid.max()), 1)
    }


def first_value(series):
    valid = series.dropna()

    if valid.empty:
        return None

    return round(float(valid.iloc[0]), 1)


def last_value(series):
    valid = series.dropna()

    if valid.empty:
        return None

    return round(float(valid.iloc[-1]), 1)


# --------------------------------------------------
# TIME / DATE
# --------------------------------------------------

def get_elapsed_minutes(df):
    if "time" not in df.columns:
        return pd.Series(index=df.index, dtype=float)

    times = pd.to_timedelta(
        df["time"],
        errors="coerce"
    )

    seconds = times.dt.total_seconds()

    # Handle drives crossing midnight.
    backwards = seconds.diff() < -43200
    seconds = seconds + backwards.cumsum() * 86400

    valid = seconds.dropna()

    if valid.empty:
        return pd.Series(index=df.index, dtype=float)

    return (seconds - valid.iloc[0]) / 60


def get_first_csv_time(df):
    if "time" not in df.columns:
        return None

    for value in df["time"].dropna():
        for fmt in (
            "%H:%M:%S.%f",
            "%H:%M:%S",
            "%H:%M",
            "%I:%M:%S %p",
            "%I:%M %p"
        ):
            try:
                return datetime.strptime(
                    str(value).strip(),
                    fmt
                ).time()

            except ValueError:
                continue

    return None


def get_drive_datetime(path, df=None):
    stem = path.stem

    # Full Car Scanner filename timestamp.
    match = re.search(
        r"(\d{4}-\d{2}-\d{2})[ _](\d{2})-(\d{2})-(\d{2})",
        stem
    )

    if match:
        try:
            return datetime.strptime(
                (
                    f"{match.group(1)} "
                    f"{match.group(2)}:"
                    f"{match.group(3)}:"
                    f"{match.group(4)}"
                ),
                "%Y-%m-%d %H:%M:%S"
            )
        except ValueError:
            pass

    date_match = re.search(
        r"(\d{4}-\d{2}-\d{2})",
        stem
    )

    if date_match:
        try:
            date = datetime.strptime(
                date_match.group(1),
                "%Y-%m-%d"
            ).date()

            first_time = (
                get_first_csv_time(df)
                if df is not None
                else None
            )

            if first_time is not None:
                return datetime.combine(date, first_time)

            hour_match = re.search(
                r"\d{4}-\d{2}-\d{2}[ _](\d{1,2})$",
                stem
            )

            if hour_match:
                return datetime.combine(
                    date,
                    datetime.min.time()
                ).replace(
                    hour=int(hour_match.group(1))
                )

            return datetime.combine(
                date,
                datetime.min.time()
            )

        except ValueError:
            pass

    return datetime.fromtimestamp(path.stat().st_mtime)


# --------------------------------------------------
# CHART SAMPLING
# --------------------------------------------------

def sample_chart(x, y, max_points=350):
    valid = pd.DataFrame({
        "x": x,
        "y": y
    }).dropna()

    if valid.empty:
        return []

    step = max(
        1,
        math.ceil(len(valid) / max_points)
    )

    sampled = valid.iloc[::step].copy()

    if sampled.index[-1] != valid.index[-1]:
        sampled = pd.concat([
            sampled,
            valid.iloc[[-1]]
        ])

    return [
        {
            "x": round(float(row.x), 2),
            "y": round(float(row.y), 2)
        }
        for row in sampled.itertuples()
    ]


# --------------------------------------------------
# VEHICLE IDENTIFICATION
# --------------------------------------------------

def identify_vehicle(df):
    columns = [
        str(c).lower()
        for c in df.columns
    ]

    has_mg1 = any("mg1" in c for c in columns)
    has_mg2 = any("mg2" in c for c in columns)

    has_soc = any(
        "state of charge" in c or "soc" in c
        for c in columns
    )

    has_battery = any(
        "batt tb" in c or "battery" in c
        for c in columns
    )

    if has_mg1 and has_mg2 and has_soc and has_battery:
        return "2013 Toyota Camry Hybrid XLE"

    return "Unknown Vehicle"


# --------------------------------------------------
# CLEANUP
# --------------------------------------------------

def cleanup_old_data():
    cutoff = datetime.now() - timedelta(days=7)

    # Preserve raw CSVs.
    # Remove only old processed data and history.
    for directory in (
        PROCESSED_DIR,
        HISTORY_DIR
    ):
        for path in directory.iterdir():
            if not path.is_file():
                continue

            if path.name == ".gitkeep":
                continue

            if get_drive_datetime(path) < cutoff:
                print(f"[cleanup] Removing: {path}")
                path.unlink(missing_ok=True)


# --------------------------------------------------
# MAIN PROCESSOR
# --------------------------------------------------

def process_file(csv_path):
    csv_path = Path(csv_path)

    print(f"[processor] Processing {csv_path.name}")

    df = pd.read_csv(csv_path)

    df.columns = [
        str(c).strip()
        for c in df.columns
    ]

    elapsed = get_elapsed_minutes(df)
    drive_datetime = get_drive_datetime(csv_path, df)
    vehicle = identify_vehicle(df)

    # -------------------------
    # ENGINE RPM
    # -------------------------

    rpm = numeric_series_from_candidates(
        df,
        [
            "Engine RPM (rpm)",
            "Engine RPM",
            "Engine Speed_7E0 (rpm)"
        ]
    )

    # -------------------------
    # MG1 / MG2 RPM (NEW)
    # -------------------------

    mg1_rpm = numeric_series_from_candidates(
        df,
        [
            "MG1 revolution (rpm)",
            "MG1 Revolution",
            "MG1 RPM"
        ]
    )

    mg2_rpm = numeric_series_from_candidates(
        df,
        [
            "MG2 revolution (rpm)",
            "MG2 Revolution",
            "MG2 RPM"
        ]
    )

    # -------------------------
    # ENGINE LOAD (NEW)
    # -------------------------

    engine_load = numeric_series_from_candidates(
        df,
        [
            "Calculated Load_7E0 (%)",
            "Calculated Load",
            "Engine Load"
        ]
    )

    # -------------------------
    # MASS AIR FLOW (NEW)
    # -------------------------

    maf = numeric_series_from_candidates(
        df,
        [
            "Mass Air Flow (g/sec)",
            "Mass Air Flow",
            "MAF"
        ]
    )

    # -------------------------
    # TEMPERATURES
    # -------------------------

    intake_air = numeric_series_from_candidates(
        df,
        [
            "Intake Air Temperature_7E0 (℉)",
            "Intake Air Temperature",
            "Intake Air Temp",
            "IAT"
        ]
    )

    engine = numeric_series_from_candidates(
        df,
        [
            "Engine coolant temperature (℉)",
            "Engine Coolant Temperature"
        ]
    )

    inverter_raw = numeric_series_from_candidates(
        df,
        [
            "Inverter Coolant Temp ()",
            "Inverter Coolant Temp"
        ]
    )

    inverter_f = celsius_to_fahrenheit(inverter_raw)

    mg1 = numeric_series_from_candidates(
        df,
        [
            "MG1 temperature (℉)",
            "MG1 temperature",
            "MG1 Temp"
        ]
    )

    mg2 = numeric_series_from_candidates(
        df,
        [
            "MG2 temperature (℉)",
            "MG2 temperature",
            "MG2 Temp"
        ]
    )

    # -------------------------
    # HYBRID BATTERY SOC
    # -------------------------

    soc = numeric_series_from_candidates(
        df,
        [
            "State of Charge (%)",
            "State of Charge",
            "Battery SOC",
            "SOC"
        ]
    )

    # -------------------------
    # BATTERY TEMPERATURES
    # -------------------------

    tb1 = numeric_series_from_candidates(
        df,
        [
            "Temp of Batt TB1 (℉)",
            "Temp of Batt TB1",
            "Battery TB1"
        ]
    )

    tb2 = numeric_series_from_candidates(
        df,
        [
            "Temp of Batt TB2 (℉)",
            "Temp of Batt TB2",
            "Battery TB2"
        ]
    )

    tb3 = numeric_series_from_candidates(
        df,
        [
            "Temp of Batt TB3 (℉)",
            "Temp of Batt TB3",
            "Battery TB3"
        ]
    )

    battery_average = pd.concat(
        [tb1, tb2, tb3],
        axis=1
    ).mean(
        axis=1,
        skipna=True
    )

    # -------------------------
    # DRIVE TIME
    # -------------------------

    valid_elapsed = elapsed.dropna()

    drive_minutes = (
        float(valid_elapsed.max())
        if not valid_elapsed.empty
        else 0.0
    )

    # -------------------------
    # PROCESSED CSV
    # -------------------------

    processed = pd.DataFrame({
        "elapsed_min": elapsed,
        "engine_rpm": rpm,
        "mg1_rpm": mg1_rpm,
        "mg2_rpm": mg2_rpm,
        "engine_load_pct": engine_load,
        "mass_air_flow_gps": maf,
        "intake_air_f": intake_air,
        "engine_coolant_f": engine,
        "inverter_coolant_f": inverter_f,
        "mg1_f": mg1,
        "mg2_f": mg2,
        "battery_soc_pct": soc,
        "battery_tb1_f": tb1,
        "battery_tb2_f": tb2,
        "battery_tb3_f": tb3,
        "battery_average_f": battery_average
    })

    processed_path = (
        PROCESSED_DIR / f"{csv_path.stem}.csv"
    )

    processed.to_csv(
        processed_path,
        index=False
    )

    # -------------------------
    # JSON SUMMARY
    # -------------------------

    summary = {
        "id": csv_path.stem,
        "vehicle": vehicle,
        "date": drive_datetime.strftime("%b %d, %Y"),
        "time": drive_datetime.strftime("%I:%M %p"),
        "drive_minutes": round(drive_minutes, 1),

        "rpm": safe_stats(rpm),
        "mg1_rpm": safe_stats(mg1_rpm),
        "mg2_rpm": safe_stats(mg2_rpm),
        "engine_load": safe_stats(engine_load),
        "maf": safe_stats(maf),
        "intake_air": safe_stats(intake_air),

        "soc": {
            **safe_stats(soc),
            "start": first_value(soc),
            "end": last_value(soc)
        },

        "temperatures": {
            "engine": safe_stats(engine),
            "inverter": safe_stats(inverter_f),
            "mg1": safe_stats(mg1),
            "mg2": safe_stats(mg2),
            "battery": safe_stats(battery_average),
            "battery_tb1": safe_stats(tb1),
            "battery_tb2": safe_stats(tb2),
            "battery_tb3": safe_stats(tb3)
        },

        "charts": {
            "rpm": sample_chart(elapsed, rpm),
            "mg1_rpm": sample_chart(elapsed, mg1_rpm),
            "mg2_rpm": sample_chart(elapsed, mg2_rpm),
            "engine_load": sample_chart(elapsed, engine_load),
            "maf": sample_chart(elapsed, maf),
            "intake_air": sample_chart(elapsed, intake_air),
            "engine": sample_chart(elapsed, engine),
            "inverter": sample_chart(elapsed, inverter_f),
            "mg1": sample_chart(elapsed, mg1),
            "mg2": sample_chart(elapsed, mg2),
            "battery": sample_chart(elapsed, battery_average),
            "soc": sample_chart(elapsed, soc)
        }
    }

    history_path = (
        HISTORY_DIR / f"{csv_path.stem}.json"
    )

    with history_path.open(
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(summary, f, indent=2)

    cleanup_old_data()

    print(f"[processor] Finished: {history_path.name}")

    return summary


# --------------------------------------------------
# PROCESS ALL RAW FILES
# --------------------------------------------------

def process_all_raw():
    cleanup_old_data()

    for csv_path in sorted(RAW_DIR.glob("*.csv")):
        history_path = (
            HISTORY_DIR / f"{csv_path.stem}.json"
        )

        if (
            not history_path.exists()
            or history_path.stat().st_mtime
            < csv_path.stat().st_mtime
        ):
            process_file(csv_path)


if __name__ == "__main__":
    process_all_raw()
