import json
from pathlib import Path

from flask import (
    Flask,
    jsonify,
    render_template,
    request
)

from processor import (
    cleanup_old_data,
    process_all_raw
)


app = Flask(__name__)

HISTORY_DIR = Path("data/history")


def load_history():
    process_all_raw()
    cleanup_old_data()

    drives = []

    for path in HISTORY_DIR.glob("*.json"):

        try:
            with open(
                path,
                "r",
                encoding="utf-8"
            ) as f:

                drive = json.load(f)
                drives.append(drive)

        except Exception as error:
            print(
                f"[app] Could not read "
                f"{path.name}: {error}"
            )

    drives.sort(
        key=lambda drive: drive["id"],
        reverse=True
    )

    return drives


@app.route("/")
def index():
    drives = load_history()

    if not drives:
        return render_template(
            "index.html",
            drive=None,
            drives=[]
        )

    requested_drive = request.args.get(
        "drive"
    )

    selected_drive = None

    if requested_drive:

        for drive in drives:

            if drive["id"] == requested_drive:
                selected_drive = drive
                break

    if selected_drive is None:
        selected_drive = drives[0]

    return render_template(
        "index.html",
        drive=selected_drive,
        drives=drives
    )


@app.route("/api/latest")
def api_latest():
    drives = load_history()

    if not drives:
        return jsonify(
            {
                "id": None
            }
        )

    latest_drive = drives[0]

    return jsonify(
        {
            "id": latest_drive["id"],
            "vehicle": latest_drive.get(
                "vehicle",
                "Unknown Vehicle"
            ),
            "date": latest_drive.get(
                "date"
            ),
            "time": latest_drive.get(
                "time"
            )
        }
    )


@app.route("/api/history")
def api_history():
    drives = load_history()

    history = []

    for drive in drives:

        history.append(
            {
                "id": drive.get("id"),
                "vehicle": drive.get(
                    "vehicle",
                    "Unknown Vehicle"
                ),
                "date": drive.get("date"),
                "time": drive.get("time"),
                "distance_miles": drive.get(
                    "distance_miles"
                ),
                "drive_minutes": drive.get(
                    "drive_minutes"
                )
            }
        )

    return jsonify(history)


if __name__ == "__main__":

    print(
        "[app] Starting OBD-II "
        "Drive Analyzer"
    )

    print(
        "[app] Open:"
        " http://localhost:5001"
    )

    app.run(
        host="127.0.0.1",
        port=5001,
        debug=False
    )