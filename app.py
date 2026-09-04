import json
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request
)

from processor import (
    process_all_raw,
    cleanup_old_data
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

                drives.append(
                    json.load(f)
                )

        except Exception as error:
            print(
                f"Could not read {path}: "
                f"{error}"
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

    requested = request.args.get("drive")

    selected = None

    if requested:
        for drive in drives:

            if drive["id"] == requested:
                selected = drive
                break

    if selected is None:
        selected = drives[0]

    return render_template(
        "index.html",
        drive=selected,
        drives=drives
    )


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5001,
        debug=False
    )