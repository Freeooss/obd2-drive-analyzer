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


def celsius_to_fahrenheit(values):
    return values * 9 / 5 + 32


def numeric_series(df, column):
    if column not in df.columns:
        return pd.Series(index=df.index, dtype=float)

    return pd.to_numeric(
        df[column],
        errors="coerce"
    )


def get_elapsed_minutes(df):
    if "time" not in df.columns:
        return pd.Series(index=df.index, dtype=float)

    times = pd.to_timedelta(
        df["time"],
        errors="coerce"
    )

    seconds = times.dt.total_seconds()

    # Handle a drive that crosses midnight
    backwards = seconds.diff() < -43200
    day_offset = backwards.cumsum() * 86400

    seconds = seconds + day_offset

    valid = seconds.dropna()

    if valid.empty:
        return pd.Series(index=df.index, dtype=float)

    start = valid.iloc[0]

    return (seconds - start) / 60


def calculate_distance(elapsed_min, speed_mph):
    temp = pd.DataFrame({
        "elapsed_min": elapsed_min,
        "speed_mph": speed_mph
    }).dropna()

    if len(temp) < 2:
        return 0.0

    delta_hours = (
        temp["elapsed_min"]
        .diff()
        .fillna(0)
        / 60
    )

    # Trapezoidal approximation
    previous_speed = temp["speed_mph"].shift(1)
    average_speed = (
        temp["speed_mph"] + previous_speed
    ) / 2

    distance = (
        average_speed.fillna(0)
        * delta_hours
    ).sum()

    return float(distance)


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

    return round(float(values.iloc[0]), 1)


def last_value(series):
    values = series.dropna()

    if values.empty:
        return None

    return round(float(values.iloc[-1]), 1)


def sample_chart(x, y, max_points=350):
    temp = pd.DataFrame({
        "x": x,
        "y": y
    }).dropna()

    if temp.empty:
        return []

    step = max(
        1,
        math.ceil(len(temp) / max_points)
    )

    sampled = temp.iloc[::step].copy()

    # Always include the final point
    if sampled.index[-1] != temp.index[-1]:
        sampled = pd.concat(
            [sampled, temp.iloc[[-1]]]
        )

    return [
        {
            "x": round(float(row.x), 2),
            "y": round(float(row.y), 2)
        }
        for row in sampled.itertuples()
    ]


def get_drive_datetime(path):
    match = re.match(
        r"(\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2})",
        path.stem
    )

    if match:
        try:
            return datetime.strptime(
                match.group(1),
                "%Y-%m-%d %H-%M-%S"
            )
        except ValueError:
            pass

    return datetime.fromtimestamp(
        path.stat().st_mtime
    )


def cleanup_old_data():
    cutoff = datetime.now() - timedelta(days=3)

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

            drive_time = get_drive_datetime(path)

            if drive_time < cutoff:
                print(
                    f"[cleanup] Removing: {path}"
                )

                path.unlink(missing_ok=True)


def process_file(csv_path):
    csv_path = Path(csv_path)

    print(f"[processor] Processing {csv_path.name}")

    df = pd.read_csv(csv_path)

    elapsed = get_elapsed_minutes(df)

    engine = numeric_series(
        df,
        "Engine coolant temperature (℉)"
    )

    inverter_c = numeric_series(
        df,
        "Inverter Coolant Temp ()"
    )

    inverter_f = celsius_to_fahrenheit(
        inverter_c
    )

    mg1 = numeric_series(
        df,
        "MG1 temperature (℉)"
    )

    mg2 = numeric_series(
        df,
        "MG2 temperature (℉)"
    )

    soc = numeric_series(
        df,
        "State of Charge (%)"
    )

    tb1 = numeric_series(
        df,
        "Temp of Batt TB1 (℉)"
    )

    tb2 = numeric_series(
        df,
        "Temp of Batt TB2 (℉)"
    )

    tb3 = numeric_series(
        df,
        "Temp of Batt TB3 (℉)"
    )

    battery_average = pd.concat(
        [tb1, tb2, tb3],
        axis=1
    ).mean(axis=1)

    speed = numeric_series(
        df,
        "Speed (GPS) (mph)"
    )

    distance = calculate_distance(
        elapsed,
        speed
    )

    valid_elapsed = elapsed.dropna()

    drive_minutes = (
        float(valid_elapsed.max())
        if not valid_elapsed.empty
        else 0
    )

    drive_datetime = get_drive_datetime(
        csv_path
    )

    processed = pd.DataFrame({
        "elapsed_min": elapsed,
        "speed_mph": speed,
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
        PROCESSED_DIR
        / f"{csv_path.stem}.csv"
    )

    processed.to_csv(
        processed_path,
        index=False
    )

    summary = {
        "id": csv_path.stem,

        "date": drive_datetime.strftime(
            "%b %d, %Y"
        ),

        "time": drive_datetime.strftime(
            "%I:%M %p"
        ),

        "drive_minutes": round(
            drive_minutes,
            1
        ),

        "distance_miles": round(
            distance,
            2
        ),

        "speed": safe_stats(speed),

        "soc": {
            **safe_stats(soc),
            "start": first_value(soc),
            "end": last_value(soc)
        },

        "temperatures": {
            "engine": safe_stats(engine),
            "inverter": safe_stats(
                inverter_f
            ),
            "mg1": safe_stats(mg1),
            "mg2": safe_stats(mg2),
            "battery": safe_stats(
                battery_average
            ),
            "battery_tb1": safe_stats(tb1),
            "battery_tb2": safe_stats(tb2),
            "battery_tb3": safe_stats(tb3)
        },

        "charts": {
            "engine": sample_chart(
                elapsed,
                engine
            ),

            "inverter": sample_chart(
                elapsed,
                inverter_f
            ),

            "mg1": sample_chart(
                elapsed,
                mg1
            ),

            "mg2": sample_chart(
                elapsed,
                mg2
            ),

            "battery": sample_chart(
                elapsed,
                battery_average
            ),

            "soc": sample_chart(
                elapsed,
                soc
            ),

            "speed": sample_chart(
                elapsed,
                speed
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

    cleanup_old_data()

    print(
        f"[processor] Finished: "
        f"{history_path.name}"
    )

    return summary


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
            or history_path.stat().st_mtime
            < csv_path.stat().st_mtime
        ):
            process_file(csv_path)


if __name__ == "__main__":
    process_all_raw()