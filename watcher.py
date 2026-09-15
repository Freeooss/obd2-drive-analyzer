import shutil
import subprocess
import time
from pathlib import Path


PROJECT_DIR = Path.home() / "Documents" / "obd2-drive-analyzer"
DOWNLOADS_DIR = Path.home() / "Downloads"
RAW_DIR = PROJECT_DIR / "data" / "raw"

PYTHON = PROJECT_DIR / "venv" / "bin" / "python"
PROCESSOR = PROJECT_DIR / "processor.py"

CHECK_INTERVAL = 3
STABLE_WAIT = 2


RAW_DIR.mkdir(parents=True, exist_ok=True)


def log(message):
    print(
        f"[watcher] {message}",
        flush=True
    )


def csv_files(directory):
    return {
        path.name: path
        for path in directory.glob("*.csv")
        if path.is_file()
    }


def file_is_stable(path):
    """
    Make sure the incoming CSV has finished copying
    before we process it.
    """

    try:
        size1 = path.stat().st_size
        time.sleep(STABLE_WAIT)
        size2 = path.stat().st_size

        return size1 == size2 and size2 > 0

    except FileNotFoundError:
        return False


def copy_new_downloads():
    """
    Copy CSV files from Downloads into data/raw.

    Returns True if at least one file was copied
    or updated.
    """

    changed = False

    for source in DOWNLOADS_DIR.glob("*.csv"):

        if not source.is_file():
            continue

        destination = RAW_DIR / source.name

        try:
            source_stat = source.stat()

            needs_copy = (
                not destination.exists()
                or destination.stat().st_size
                != source_stat.st_size
                or destination.stat().st_mtime
                < source_stat.st_mtime
            )

            if not needs_copy:
                continue

            if not file_is_stable(source):
                log(
                    f"Waiting for copy to finish: "
                    f"{source.name}"
                )
                continue

            log(
                f"Importing: {source.name}"
            )

            shutil.copy2(
                source,
                destination
            )

            changed = True

            log(
                f"Imported to data/raw: "
                f"{source.name}"
            )

        except Exception as e:
            log(
                f"Import error for "
                f"{source.name}: {e}"
            )

    return changed


def get_raw_snapshot():

    snapshot = {}

    for path in RAW_DIR.glob("*.csv"):

        try:
            snapshot[path.name] = (
                path.stat().st_size,
                path.stat().st_mtime
            )

        except FileNotFoundError:
            pass

    return snapshot


def run_processor():

    log("Running processor.py")

    try:

        result = subprocess.run(
            [
                str(PYTHON),
                str(PROCESSOR)
            ],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True
        )

        if result.stdout:
            print(
                result.stdout,
                end="",
                flush=True
            )

        if result.stderr:
            print(
                result.stderr,
                end="",
                flush=True
            )

        if result.returncode == 0:

            log(
                "processor.py finished successfully"
            )

        else:

            log(
                f"processor.py failed with "
                f"exit code {result.returncode}"
            )

    except Exception as e:

        log(
            f"Could not run processor.py: {e}"
        )


def main():

    log("OBD-II watcher started")
    log(f"Watching: {DOWNLOADS_DIR}")
    log(f"Raw directory: {RAW_DIR}")

    # Import anything that arrived while the
    # watcher or Mac was offline.
    imported = copy_new_downloads()

    if imported:
        run_processor()

    previous_raw = get_raw_snapshot()

    while True:

        try:

            imported = copy_new_downloads()

            current_raw = get_raw_snapshot()

            if imported:

                run_processor()
                current_raw = get_raw_snapshot()

            elif current_raw != previous_raw:

                log(
                    "CSV change detected directly "
                    "inside data/raw"
                )

                run_processor()
                current_raw = get_raw_snapshot()

            previous_raw = current_raw

            time.sleep(CHECK_INTERVAL)

        except Exception as e:

            log(
                f"Watcher loop error: {e}"
            )

            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()