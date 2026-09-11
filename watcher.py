import subprocess
import time
from pathlib import Path


PROJECT_DIR = Path.home() / "Documents" / "obd2-drive-analyzer"
RAW_DIR = PROJECT_DIR / "data" / "raw"

CHECK_INTERVAL = 3


def get_csv_snapshot():
    return {
        path.name: path.stat().st_mtime
        for path in RAW_DIR.glob("*.csv")
    }


def run_processor():
    print("[watcher] Running latest processor.py")

    subprocess.run(
        [
            str(PROJECT_DIR / "venv" / "bin" / "python"),
            str(PROJECT_DIR / "processor.py")
        ],
        cwd=PROJECT_DIR
    )


def main():
    print("[watcher] OBD-II watcher started")

    previous = get_csv_snapshot()

    while True:
        time.sleep(CHECK_INTERVAL)

        current = get_csv_snapshot()

        if current != previous:
            print("[watcher] CSV change detected")

            # Give the incoming file a moment to finish copying
            time.sleep(2)

            run_processor()

            previous = get_csv_snapshot()


if __name__ == "__main__":
    main()