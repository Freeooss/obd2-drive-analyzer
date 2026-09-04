import shutil
import time
from pathlib import Path

import pandas as pd

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from processor import (
    process_file,
    cleanup_old_data
)


DOWNLOADS = Path.home() / "Downloads"
RAW_DIR = Path("data/raw")


def looks_like_car_scanner_csv(path):
    try:
        columns = pd.read_csv(
            path,
            nrows=1
        ).columns

        required = {
            "time",
            "Speed (GPS) (mph)",
            "State of Charge (%)"
        }

        return required.issubset(
            set(columns)
        )

    except Exception:
        return False


def wait_until_finished(path):
    previous_size = -1

    for _ in range(20):

        if not path.exists():
            return False

        current_size = path.stat().st_size

        if (
            current_size > 0
            and current_size == previous_size
        ):
            return True

        previous_size = current_size

        time.sleep(1)

    return False


def import_file(path):
    path = Path(path)

    if path.suffix.lower() != ".csv":
        return

    print(
        f"[watcher] CSV detected: {path.name}"
    )

    if not wait_until_finished(path):
        return

    if not looks_like_car_scanner_csv(path):
        print(
            "[watcher] Not a Car Scanner CSV."
        )
        return

    destination = RAW_DIR / path.name

    if destination.exists():
        print(
            "[watcher] File already imported."
        )
        return

    shutil.copy2(
        path,
        destination
    )

    print(
        f"[watcher] Imported: "
        f"{destination}"
    )

    process_file(destination)

    cleanup_old_data()


class DownloadHandler(
    FileSystemEventHandler
):

    def on_created(self, event):

        if not event.is_directory:
            import_file(
                event.src_path
            )

    def on_moved(self, event):

        if not event.is_directory:
            import_file(
                event.dest_path
            )


def scan_existing_files():

    for path in DOWNLOADS.glob("*.csv"):
        import_file(path)


if __name__ == "__main__":

    print(
        f"[watcher] Watching "
        f"{DOWNLOADS}"
    )

    cleanup_old_data()

    scan_existing_files()

    observer = Observer()

    observer.schedule(
        DownloadHandler(),
        str(DOWNLOADS),
        recursive=False
    )

    observer.start()

    try:
        while True:
            time.sleep(60)
            cleanup_old_data()

    except KeyboardInterrupt:
        observer.stop()

    observer.join()