import json
import math
import re
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
HISTORY_DIR = Path("data/history")

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# BASIC HELPERS
# --------------------------------------------------

def celsius_to_fahrenheit(values):
    return values * 9 / 5 + 32


def find_column(df, candidates):
    """
    Find a column using several possible names.

    First tries exact matches.
    Then tries case-insensitive partial matching.
    """

    # Exact match first
    for candidate in candidates:
        if candidate in df.columns:
            return candidate

    # More flexible matching
    normalized_columns = {
        str(column).strip().lower(): column
        for column in df.columns
    }

    for candidate in candidates:
        candidate_lower = candidate.strip().lower()

        for normalized, original in normalized_columns.items():
            if candidate_lower in normalized:
                return original

    return None


def numeric_series_from_candidates(df, candidates):
    column = find_column(df, candidates)

    if column is None:
        return pd.Series(
            index=df.index,
            dtype=float
        )

    return pd.to_numeric(
        df[column],
        errors="coerce"
    )


def safe_stats(series):
    values = series.dropna()

    if values.empty:
        return {
            "min": None,
            "avg": None,
            "max": None
        }

    return {
        "min": round(float(values.min()), 1),
        "avg": round(float(values.mean()), 1),
        "max": round(float(values.max()), 1)
    }


def first_value(series):
    values = series.dropna()

    if values.empty:
        return None

    return round(
        float(values.iloc[0]),
        1
    )


def last_value(series):
    values = series.dropna()

    if values.empty:
        return None

    return round(
        float(values.iloc[-1]),
        1
    )


# --------------------------------------------------
# TIME / DATE
# --------------------------------------------------

def get_elapsed_minutes(df):
    if "time" not in df.columns:
        return pd.Series(
            index=df.index,
            dtype=float
        )

    times = pd.to_timedelta(
        df["time"],
        errors="coerce"
    )

    seconds = times.dt.total_seconds()

    # Handle drives crossing midnight
    backwards = seconds.diff() < -43200
    day_offset = backwards.cumsum() * 86400

    seconds = seconds + day_offset

    valid = seconds.dropna()

    if valid.empty:
        return pd.Series(
            index=df.index,
            dtype=float
        )

    start = valid.iloc[0]

    return (
        seconds - start
    ) / 60


def get_first_csv_time(df):
    """
    Get the first usable clock time from the CSV.

    Returns a Python time object or None.
    """

    if "time" not in df.columns:
        return None

    values = df["time"].dropna()

    for value in values:
        text = str(value).strip()

        formats = [
            "%H:%M:%S.%f",
            "%H:%M:%S",
            "%H:%M",
            "%I:%M:%S %p",
            "%I:%M %p"
        ]

        for fmt in formats:
            try:
                return datetime.strptime(
                    text,
                    fmt
                ).time()

            except ValueError:
                continue

    return None


def get_drive_datetime(path, df=None):
    """
    Determine drive date/time safely.

    Priority:
    1. Full timestamp in filename
    2. Date from filename + first CSV time
    3. Date/hour from filename
    4. File modification time
    """

    stem = path.stem

    # Full Car Scanner filename:
    # 2026-09-04 16-21-34
    full_match = re.search(
        r"(\d{4}-\d{2}-\d{2})[ _](\d{2})-(\d{2})-(\d{2})",
        stem
    )

    if full_match:
        try:
            return datetime.strptime(
                (
                    f"{full_match.group(1)} "
                    f"{full_match.group(2)}:"
                    f"{full_match.group(3)}:"
                    f"{full_match.group(4)}"
                ),
                "%Y-%m-%d %H:%M:%S"
            )

        except ValueError:
            pass


    # At minimum, preserve the DATE from the filename.
    date_match = re.search(
        r"(\d{4}-\d{2}-\d{2})",
        stem
    )

    if date_match:
        try:
            drive_date = datetime.strptime(
                date_match.group(1),
                "%Y-%m-%d"
            ).date()

            # Prefer actual first time inside the CSV
            if df is not None:
                csv_time = get_first_csv_time(df)

                if csv_time is not None:
                    return datetime.combine(
                        drive_date,
                        csv_time
                    )

            # If filename has only an hour,
            # e.g. "2026-09-04 17"
            hour_match = re.search(
                r"\d{4}-\d{2}-\d{2}[ _](\d{1,2})$",
                stem
            )

            if hour_match:
                hour = int(
                    hour_match.group(1)
                )

                return datetime.combine(
                    drive_date,
                    datetime.min.time()
                ).replace(
                    hour=hour
                )

            # Date is still reliable even without time
            return datetime.combine(
                drive_date,
                datetime.min.time()
            )

        except ValueError:
            pass


    # Absolute last fallback
    return datetime.fromtimestamp(
        path.stat().st_mtime
    )


# --------------------------------------------------
# DISTANCE
# --------------------------------------------------

def calculate_distance(
    elapsed_min,
    speed_mph
):
    temp = pd.DataFrame(
        {
            "elapsed_min": elapsed_min,
            "speed_mph": speed_mph
        }
    ).dropna()

    if len(temp) < 2:
        return 0.0

    delta_hours = (
        temp["elapsed_min"]
        .diff()
        .fillna(0)
        / 60
    )

    previous_speed = (
        temp["speed_mph"]
        .shift(1)
    )

    average_speed = (
        temp["speed_mph"]
        + previous_speed
    ) / 2

    distance = (
        average_speed.fillna(0)
        * delta_hours
    ).sum()

    return float(distance)


# --------------------------------------------------
# CHART SAMPLING
# --------------------------------------------------

def sample_chart(
    x,
    y,
    max_points=350
):
    temp = pd.DataFrame(
        {
            "x": x,
            "y": y
        }
    ).dropna()

    if temp.empty:
        return []

    step = max(
        1,
        math.ceil(
            len(temp)
            / max_points
        )
    )

    sampled = temp.iloc[
        ::step
    ].copy()

    if (
        sampled.index[-1]
        != temp.index[-1]
    ):
        sampled = pd.concat(
            [
                sampled,
                temp.iloc[[-1]]
            ]
        )

    return [
        {
            "x": round(
                float(row.x),
                2
            ),

            "y": round(
                float(row.y),
                2
            )
        }

        for row
        in sampled.itertuples()
    ]


# --------------------------------------------------
# VEHICLE IDENTIFICATION
# --------------------------------------------------

def identify_vehicle(df):
    columns_lower = [
        str(column).lower()
        for column in df.columns
    ]

    has_mg1 = any(
        "mg1" in column
        for column in columns_lower
    )

    has_mg2 = any(
        "mg2" in column
        for column in columns_lower
    )

    has_soc = any(
        (
            "state of charge"
            in column
        )
        or (
            "soc"
            in column
        )
        for column in columns_lower
    )

    has_battery_temp = any(
        "batt tb" in column
        or "battery" in column
        for column in columns_lower
    )

    if (
        has_mg1
        and has_mg2
        and has_soc
        and has_battery_temp
    ):
        return (
            "2013 Toyota Camry Hybrid XLE"
        )

    return "Unknown Vehicle"


# --------------------------------------------------
# CLEANUP
# --------------------------------------------------

def cleanup_old_data():
    cutoff = (
        datetime.now()
        - timedelta(days=7)
    )

    for directory in [
        RAW_DIR,
        PROCESSED_DIR,
        HISTORY_DIR
    ]:

        for path in directory.iterdir():

            if not path.is_file():
                continue

            if path.name == ".gitkeep":
                continue

            drive_time = (
                get_drive_datetime(path)
            )

            if drive_time < cutoff:

                print(
                    f"[cleanup] Removing: "
                    f"{path}"
                )

                path.unlink(
                    missing_ok=True
                )


# --------------------------------------------------
# MAIN PROCESSOR
# --------------------------------------------------

def process_file(csv_path):
    csv_path = Path(csv_path)

    print(
        f"[processor] Processing "
        f"{csv_path.name}"
    )

    df = pd.read_csv(
        csv_path
    )

    # Remove accidental spaces from CSV headers
    df.columns = [
        str(column).strip()
        for column in df.columns
    ]


    # -------------------------
    # TIME
    # -------------------------

    elapsed = (
        get_elapsed_minutes(df)
    )

    drive_datetime = (
        get_drive_datetime(
            csv_path,
            df
        )
    )


    # -------------------------
    # VEHICLE
    # -------------------------

    vehicle_name = (
        identify_vehicle(df)
    )


    # -------------------------
    # SPEED
    # -------------------------

    speed = (
        numeric_series_from_candidates(
            df,
            [
                "Speed (GPS) (mph)",
                "GPS Speed",
                "Vehicle Speed",
                "Speed"
            ]
        )
    )


    # -------------------------
    # ENGINE RPM
    # -------------------------

    rpm = (
        numeric_series_from_candidates(
            df,
            [
                "Engine RPM (rpm)",
                "Engine RPM",
                "RPM"
            ]
        )
    )


    # -------------------------
    # INTAKE AIR
    # -------------------------

    intake_air = (
        numeric_series_from_candidates(
            df,
            [
                "Intake Air Temperature_7E0 (℉)",
                "Intake Air Temperature",
                "Intake air temperature",
                "Intake Air Temp",
                "IAT"
            ]
        )
    )


    # -------------------------
    # ENGINE COOLANT
    # -------------------------

    engine = (
        numeric_series_from_candidates(
            df,
            [
                "Engine coolant temperature (℉)",
                "Engine Coolant Temperature",
                "Engine coolant temperature"
            ]
        )
    )


    # -------------------------
    # INVERTER COOLANT
    # -------------------------

    inverter_raw = (
        numeric_series_from_candidates(
            df,
            [
                "Inverter Coolant Temp ()",
                "Inverter Coolant Temp",
                "Inverter coolant temperature"
            ]
        )
    )

    # Existing Car Scanner field is Celsius
    inverter_f = (
        celsius_to_fahrenheit(
            inverter_raw
        )
    )


    # -------------------------
    # MG1 / MG2
    # -------------------------

    mg1 = (
        numeric_series_from_candidates(
            df,
            [
                "MG1 temperature (℉)",
                "MG1 temperature",
                "MG1 Temp"
            ]
        )
    )

    mg2 = (
        numeric_series_from_candidates(
            df,
            [
                "MG2 temperature (℉)",
                "MG2 temperature",
                "MG2 Temp"
            ]
        )
    )


    # -------------------------
    # HYBRID BATTERY SOC
    # -------------------------

    soc = (
        numeric_series_from_candidates(
            df,
            [
                "State of Charge (%)",
                "State of Charge",
                "Battery SOC",
                "SOC"
            ]
        )
    )


    # -------------------------
    # BATTERY TEMPERATURES
    # -------------------------

    tb1 = (
        numeric_series_from_candidates(
            df,
            [
                "Temp of Batt TB1 (℉)",
                "Temp of Batt TB1",
                "Battery TB1"
            ]
        )
    )

    tb2 = (
        numeric_series_from_candidates(
            df,
            [
                "Temp of Batt TB2 (℉)",
                "Temp of Batt TB2",
                "Battery TB2"
            ]
        )
    )

    tb3 = (
        numeric_series_from_candidates(
            df,
            [
                "Temp of Batt TB3 (℉)",
                "Temp of Batt TB3",
                "Battery TB3"
            ]
        )
    )


    battery_average = pd.concat(
        [
            tb1,
            tb2,
            tb3
        ],
        axis=1
    ).mean(
        axis=1,
        skipna=True
    )


    # -------------------------
    # DRIVE DISTANCE / TIME
    # -------------------------

    distance = (
        calculate_distance(
            elapsed,
            speed
        )
    )

    valid_elapsed = (
        elapsed.dropna()
    )

    if valid_elapsed.empty:

        drive_minutes = 0.0

    else:

        drive_minutes = float(
            valid_elapsed.max()
        )


    # -------------------------
    # PROCESSED CSV
    # -------------------------

    processed = pd.DataFrame(
        {
            "elapsed_min":
                elapsed,

            "speed_mph":
                speed,

            "engine_rpm":
                rpm,

            "intake_air_f":
                intake_air,

            "engine_coolant_f":
                engine,

            "inverter_coolant_f":
                inverter_f,

            "mg1_f":
                mg1,

            "mg2_f":
                mg2,

            "battery_soc_pct":
                soc,

            "battery_tb1_f":
                tb1,

            "battery_tb2_f":
                tb2,

            "battery_tb3_f":
                tb3,

            "battery_average_f":
                battery_average
        }
    )


    processed_path = (
        PROCESSED_DIR
        / f"{csv_path.stem}.csv"
    )

    processed.to_csv(
        processed_path,
        index=False
    )


    # -------------------------
    # JSON SUMMARY
    # -------------------------

    summary = {

        "id":
            csv_path.stem,

        "vehicle":
            vehicle_name,

        "date":
            drive_datetime.strftime(
                "%b %d, %Y"
            ),

        "time":
            drive_datetime.strftime(
                "%I:%M %p"
            ),

        "drive_minutes":
            round(
                drive_minutes,
                1
            ),

        "distance_miles":
            round(
                distance,
                2
            ),

        "speed":
            safe_stats(speed),

        "rpm":
            safe_stats(rpm),

        "intake_air":
            safe_stats(
                intake_air
            ),

        "soc": {
            **safe_stats(soc),

            "start":
                first_value(soc),

            "end":
                last_value(soc)
        },

        "temperatures": {

            "engine":
                safe_stats(engine),

            "inverter":
                safe_stats(
                    inverter_f
                ),

            "mg1":
                safe_stats(mg1),

            "mg2":
                safe_stats(mg2),

            "battery":
                safe_stats(
                    battery_average
                ),

            "battery_tb1":
                safe_stats(tb1),

            "battery_tb2":
                safe_stats(tb2),

            "battery_tb3":
                safe_stats(tb3)
        },

        "charts": {

            "speed":
                sample_chart(
                    elapsed,
                    speed
                ),

            "rpm":
                sample_chart(
                    elapsed,
                    rpm
                ),

            "intake_air":
                sample_chart(
                    elapsed,
                    intake_air
                ),

            "engine":
                sample_chart(
                    elapsed,
                    engine
                ),

            "inverter":
                sample_chart(
                    elapsed,
                    inverter_f
                ),

            "mg1":
                sample_chart(
                    elapsed,
                    mg1
                ),

            "mg2":
                sample_chart(
                    elapsed,
                    mg2
                ),

            "battery":
                sample_chart(
                    elapsed,
                    battery_average
                ),

            "soc":
                sample_chart(
                    elapsed,
                    soc
                )
        }
    }


    history_path = (
        HISTORY_DIR
        / f"{csv_path.stem}.json"
    )


    with open(
        history_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            summary,
            f,
            indent=2
        )


    print(
        "[processor] "
        f"Vehicle: {vehicle_name}"
    )

    print(
        "[processor] "
        f"Date: {summary['date']} "
        f"{summary['time']}"
    )

    print(
        "[processor] "
        f"RPM samples: "
        f"{rpm.notna().sum()}"
    )

    print(
        "[processor] "
        f"Intake air samples: "
        f"{intake_air.notna().sum()}"
    )


    cleanup_old_data()


    print(
        f"[processor] Finished: "
        f"{history_path.name}"
    )

    return summary


# --------------------------------------------------
# PROCESS ALL RAW FILES
# --------------------------------------------------

def process_all_raw():
    cleanup_old_data()

    for csv_path in sorted(
        RAW_DIR.glob("*.csv")
    ):

        history_path = (
            HISTORY_DIR
            / f"{csv_path.stem}.json"
        )

        if (
            not history_path.exists()
            or
            history_path.stat().st_mtime
            <
            csv_path.stat().st_mtime
        ):

            process_file(
                csv_path
            )


if __name__ == "__main__":
    process_all_raw()