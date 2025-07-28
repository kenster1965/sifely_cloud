import os
import csv
from datetime import datetime, timezone

from .const import CONF_HISTORY_ENTRIES, HISTORY_RECORD_TYPES

HISTORY_FOLDER = "history"


def get_history_path(lock_id: int) -> str:
    """Return full CSV path for the given lock_id inside the component's folder."""
    base_dir = os.path.dirname(__file__)
    history_dir = os.path.join(base_dir, HISTORY_FOLDER)
    os.makedirs(history_dir, exist_ok=True)  # Make sure it exists

    return os.path.join(history_dir, f"history_{lock_id}.csv")

def read_csv(path: str):
    """Read and parse existing CSV history file."""
    seen_ids = set()
    existing_rows = []

    if os.path.isfile(path):
        with open(path, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                seen_ids.add(row["recordId"])
                existing_rows.append(row)

    return seen_ids, existing_rows


def write_csv(path: str, rows: list[dict]):
    """Write lock history entries to CSV."""
    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["recordId", "lockDate", "username", "recordType", "success"])
        writer.writeheader()
        writer.writerows(rows)


async def fetch_and_update_lock_history(coordinator, lock_id: int):
    """Fetch and persist new lock history entries for a given lock."""
    new_entries = await coordinator.async_query_lock_history(lock_id)
    if not new_entries:
        return []

    path = get_history_path(lock_id)
    os.makedirs(HISTORY_FOLDER, exist_ok=True)

    seen_ids, existing_rows = await coordinator.hass.async_add_executor_job(read_csv, path)

    fresh_rows = []
    for row in new_entries:
        record_id = str(row.get("recordId"))
        if record_id in seen_ids:
            continue

        ts = row.get("lockDate")
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).astimezone()
        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")

        record_type_code = row.get("recordType")
        record_type = HISTORY_RECORD_TYPES.get(record_type_code, f"Type {record_type_code}")
        raw_username = row.get("username", "Unknown")
        
        if isinstance(raw_username, str) and "_" in raw_username:
            username = raw_username.split("_")[0] + "_"
        else:
            username = raw_username
            
        success = "Success" if row.get("success", -1) == 1 else "Failed"

        fresh_rows.append({
            "recordId": record_id,
            "lockDate": formatted_time,
            "username": username,
            "recordType": record_type,
            "success": success,
        })

    if fresh_rows:
        existing_rows.extend(fresh_rows)
        existing_rows = sorted(existing_rows, key=lambda r: r["recordId"], reverse=True)

        limit = coordinator.config_entry.options.get(CONF_HISTORY_ENTRIES, 20)
        trimmed = existing_rows[:limit]

        await coordinator.hass.async_add_executor_job(write_csv, path, trimmed)
        return trimmed

    return existing_rows[:coordinator.config_entry.options.get(CONF_HISTORY_ENTRIES, 20)]
